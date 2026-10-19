"""Regression for actual duplicated final_answer messages, not guessed repairs."""
import json
from types import SimpleNamespace
import pytest
from openai_chart_client import OpenAIChartClient,OpenAIResponseFormatError,response_text

def message(text,phase='final_answer'):
    return {'type':'message','phase':phase,'content':[{'type':'output_text','text':text}]}

def payload(*messages):return {'status':'completed','output':list(messages)}

@pytest.mark.parametrize('phase',['final_answer',None])
def test_identical_final_documents_execute_once(phase):
    text='{"action":"search","query":"환율"}'
    assert json.loads(response_text(payload(message(text,phase),message(text,phase)),json_mode=True))=={'action':'search','query':'환율'}

def test_identical_objects_with_different_key_order_are_one_document():
    assert json.loads(response_text(payload(message('{"a":1,"b":2}'),message('{"b":2,"a":1}')),json_mode=True))=={'a':1,'b':2}

@pytest.mark.parametrize('texts', [('{"action":"search","query":"환율"}','{"action":"clarify","question":"계산?"}'),('{"value":true}','{"value":1}'),('{}','{}{}')])
def test_conflicting_or_invalid_documents_fail_closed(texts):
    with pytest.raises(OpenAIResponseFormatError):response_text(payload(*(message(t) for t in texts)),json_mode=True)

def test_commentary_is_not_executed_as_final_json():
    assert response_text(payload(message('진행 중','commentary'),message('{"action":"clarify"}')),json_mode=True)=='{"action":"clarify"}'
    with pytest.raises(OpenAIResponseFormatError):response_text(payload(message('{"action":"search"}','commentary')),json_mode=True)

def test_unknown_and_unphased_message_cannot_compete_with_final():
    with pytest.raises(OpenAIResponseFormatError):response_text(payload(message('{}'),message('{"action":"search"}',None)),json_mode=True)

def test_legacy_single_message_and_text_mode_are_unchanged():
    assert response_text(payload(message('{}',None)),json_mode=True)=='{}'
    assert response_text(payload(message('앞'),message('뒤')))=='앞뒤'
    assert response_text(payload(message('{}{}')),json_mode=True)=='{}{}' # strict planner still rejects this

class Transport:
    def __init__(self,replies):self.replies=iter(replies);self.calls=[]
    def post(self,*args,**kwargs):
        self.calls.append(kwargs['json']);body=next(self.replies)
        return SimpleNamespace(ok=True,status_code=200,json=lambda:body)

def test_actual_adapter_passes_one_document_and_strict_schema():
    transport=Transport([payload(message('{"action":"clarify"}'),message('{"action":"clarify"}'))])
    schema={'type':'object','properties':{'action':{'type':'string'}},'required':['action'],'additionalProperties':False}
    text,_=OpenAIChartClient(api_key='synthetic',session=transport).request('JSON','query',json_mode=True,response_schema=schema)
    assert json.loads(text)=={'action':'clarify'}
    assert transport.calls[0]['text']['format']=={'type':'json_schema','name':'statbridge_response','strict':True,'schema':schema}

def test_duplicate_api_action_does_not_spend_json_repair_or_repeat_search():
    from derived_indicator_planner import DerivedIndicatorPlanner
    from derived_catalog_tools import DerivedCatalogTools
    from statbridge_mcp.metadata_store import MetadataStore
    search='{"action":"search","query":"환율"}'
    transport=Transport([payload(message(search),message(search)),payload(message('{"action":"clarify","question":"기간을 확인해 주세요"}'))])
    client=OpenAIChartClient(api_key='synthetic',session=transport)
    result=DerivedIndicatorPlanner(client,DerivedCatalogTools(MetadataStore())).plan('생산자물가 변화율')
    assert result['status']=='need_details' and len(result['usage'])==2 and len(result['searches'])==2
    assert len(transport.calls)==2

def test_model_failure_response_preserves_work_and_offers_retry():
    import bridge_api as api
    response=api._derived_query_response(SimpleNamespace(query='내 질문',period_start=None,period_end=None),
        {'status':'data_unavailable','failure_kind':'model_response_error','failure_stage':'plan_derived_indicator','question':'GPT JSON 오류','state':{'keep':'original'}})
    assert response['status']=='request_failed' and response['failure_kind']=='model_response_error'
    assert response['state']=={'keep':'original'}
    assert response['recovery']['choices'][0]['id']=='retry' and response['recovery']['preserveState']
    assert 'requirements' not in response['recovery']

def test_availability_last_call_uses_terminal_schema():
    from derived_indicator_planner import DerivedIndicatorPlanner
    from derived_catalog_tools import DerivedCatalogTools
    from statbridge_mcp.metadata_store import MetadataStore
    search=payload(message('{"action":"search","query":"환율"}'))
    transport=Transport([search,search,search,payload(message('{"action":"clarify","question":"1기 기준과 평균 대상을 알려주세요","missing":[]}'))])
    result=DerivedIndicatorPlanner(OpenAIChartClient(api_key='synthetic',session=transport),DerivedCatalogTools(MetadataStore())).plan('먼저 확인하고 아직 계산하지 마')
    assert result['status']=='need_details' and len(transport.calls)==4
    assert 'response_schema' not in transport.calls[0]
    assert transport.calls[-1]['text']['format']['schema']['properties']['action']['enum']==['unavailable','clarify']
