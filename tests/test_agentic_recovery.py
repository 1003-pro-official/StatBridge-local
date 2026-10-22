import base64
import copy
import io
import json
import pytest
from PIL import Image
from pydantic import ValidationError
from chart_reference import ChartReference
from openai_chart_client import OpenAIChartClient, OpenAIEditModel
from recovery import recovery_question
from authenticated_client import TestClient
import bridge_api as api
from test_chart_edit_period_and_box import fixture_session
from chart_edit_agent import ChartEditAgent


def reference():
    buf=io.BytesIO();Image.new('RGB',(20,20),'white').save(buf,format='PNG')
    return {'name':'reference.png','mime':'image/png','data_url':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()}


class Response:
    ok=True
    status_code=200
    def __init__(self,text):self.text=text
    def json(self):return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':self.text}]}]}


class Transport:
    def __init__(self):self.calls=[]
    def post(self,url,**kw):
        self.calls.append((url,kw))
        return Response(json.dumps({'commands':[{'operation':'set_title','value':'참고 형식 제목'}],
          'coverage':[{'source_id':'instruction','text':'참고 형식으로','status':'covered','command_indices':[0]}]}))


def test_json_mode_explicitly_requests_json_in_input_message():
    class JsonTransport(Transport):
        def post(self, url, **kwargs):
            body = kwargs['json']
            assert body['text']['format']['type'] == 'json_object'
            text = body['input'][0]['content'][0]['text']
            assert 'json' in text.lower()
            assert text.endswith('{"instruction":"범례를 위로 옮겨 주세요"}')
            return Response('{"commands":[]}')
    client = OpenAIChartClient(api_key='synthetic-key', session=JsonTransport())
    text, _ = client.request('JSON commands로 반환', '{"instruction":"범례를 위로 옮겨 주세요"}', json_mode=True)
    assert json.loads(text) == {'commands': []}


def test_responses_image_is_multimodal_and_current_values_are_preserved():
    transport=Transport();client=OpenAIChartClient(api_key='synthetic-key',session=transport)
    _,session=fixture_session();before=copy.deepcopy(session['result'])
    model=OpenAIEditModel(client)
    # Review/coverage contracts are covered by the existing edit agent suite;
    # isolate multimodal transport and actual graph application here.
    model.review=None
    output=ChartEditAgent(model,api.agent.output_agent).edit(session['result'],session['output'],'참고 형식으로',{'reference_files':[reference()]})
    body=transport.calls[0][1]['json']
    assert body['model']==client.settings.main_model and body['store'] is False
    assert body['input'][0]['content'][1]['type']=='input_image'
    assert 'base64' not in body['input'][0]['content'][0]['text']
    assert output['chartState']['title']=='참고 형식 제목'
    assert session['result']==before
    assert output['table']['rows']==session['output']['table']['rows']


def test_missing_key_and_provider_failure_do_not_leak_credentials():
    with pytest.raises(ValueError,match='OPENAI_API_KEY'):OpenAIChartClient(api_key='').chat_main('system','request')
    class Failure(Transport):
        def post(self,*args,**kwargs):
            response=Response('private provider details');response.ok=False;response.status_code=429;return response
    with pytest.raises(ValueError,match='429') as error:OpenAIChartClient(api_key='synthetic-key',session=Failure()).chat_main('s','u')
    assert 'synthetic-key' not in str(error.value) and 'private provider' not in str(error.value)


def test_forged_image_and_nested_reference_are_rejected():
    bad={**reference(),'data_url':'data:image/png;base64,'+base64.b64encode(b'<script>bad</script>').decode()}
    with pytest.raises(ValidationError):ChartReference.model_validate(bad)
    from output_schema import VisualEditContext
    with pytest.raises(ValidationError):VisualEditContext.model_validate({'reference_files':[bad]})
    assert recovery_question('기간을 선택해 주세요')['choices'][0]['id']=='period'


def test_failure_asks_question_and_retry_keeps_graph(monkeypatch):
    _,session=fixture_session();monkeypatch.setitem(api.EDIT_SESSIONS,'recovery-fixture',session)
    before=copy.deepcopy(session)
    class Fail:
        def edit(self,*args,**kwargs):raise ValueError('어떤 제목으로 변경할까요?')
    monkeypatch.setattr(api,'edit_agent',Fail())
    client=TestClient(api.app)
    response=client.post('/api/output/edit',json={'edit_session_id':'recovery-fixture','instruction':'알아서 해줘'})
    assert response.status_code==422
    assert response.json()['recovery']['question']=='어떤 제목으로 변경할까요?'
    assert session==before
    updated=client.post('/api/output/edit',json={'edit_session_id':'recovery-fixture','instruction':'','commands':[{'operation':'set_title','kind':'STYLE_EDIT','value':'명확한 제목'}]})
    assert updated.status_code==200 and session['output']['chartState']['title']=='명확한 제목'
    assert session['result']==before['result']


def test_no_match_preserves_requested_period_and_confirmed_state(monkeypatch):
    monkeypatch.setattr(api.agent,'run',lambda **kwargs:{'status':'no_match'})
    client=TestClient(api.app)
    state={'confirmed':{'region':'전국'}}
    response=client.post('/api/query',json={'query':'없는 지표 2020년부터 2025년까지','state':state})
    assert response.status_code==200
    data=response.json()
    assert data['status']=='no_match' and data['state']==state
    assert data['requiresQueryRefinement'] is True
    assert '지표' in data['refinementQuestion']
    assert data['chart']==[]
    assert data['period']=={'start':'2020-01-01','end':'2025-12-31'}
    assert any(x['id']=='table' for x in data['recovery']['choices'])


def test_reference_upload_cannot_access_other_account_graph(monkeypatch):
    _,session=fixture_session();monkeypatch.setitem(api.EDIT_SESSIONS,'private-reference',session)
    owner=TestClient(api.app)
    from fastapi.testclient import TestClient as RawClient
    stranger=RawClient(api.app)
    assert stranger.post('/api/auth/login',json={'username':'test2','password':'1234'}).status_code==200
    response=stranger.post('/api/output/edit',json={'edit_session_id':'private-reference','instruction':'참고 형식으로','reference_files':[reference()]})
    assert response.status_code==404
