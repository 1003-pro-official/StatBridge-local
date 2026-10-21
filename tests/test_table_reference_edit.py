"""Offline reference-edit contracts; never reported as live GPT evidence."""
import copy,base64,io
from types import SimpleNamespace
import pytest
from table_reference_edit import edit_table_reference
from test_chart_edit_period_and_box import fixture_session

class Model:
    supports_images=True
    model_name='offline-reference-test'
    def __init__(self,proposal):self.proposal=proposal;self.calls=[]
    def interpret(self,system,context):
        self.calls.append((system,context))
        return self.proposal(context) if callable(self.proposal) else self.proposal


def run(proposal):
    agent,session=fixture_session();model=Model(proposal)
    before=copy.deepcopy(session['result'])
    output=edit_table_reference(SimpleNamespace(model=model,output_agent=agent),session['result'],session['output'],'첨부 표처럼 서식을 바꿔줘',{'reference_files':[{'name':'table.png','mime':'image/png','data_url':'data:image/png;base64,reference-fixture'}]},[])
    assert session['result']==before
    return output,model


def test_table_reference_uses_one_model_call_and_preserves_observations():
    output,model=run({'commands':[{'operation':'set_table','params':{'patch':{'template':'BOK-T02','decimals':3}}}]})
    assert len(model.calls)==1 and model.calls[0][1]['visual']['reference_files']
    assert output['tableDocument']['options']['template']=='BOK-T02'
    assert output['tableDocument']['sections'][0]['rows'][0][1:]==[float(10+i) for i in range(8)]
    assert output['editAgent']['interpretation']=='table_reference'


def test_reference_cell_text_can_only_target_editable_labels():
    def proposal(context):
        key=next(c['key'] for s in context['tableTargets'] for r in s['rows'] for c in r['cells'] if c['editable'])
        return {'commands':[{'operation':'set_table','params':{'patch':{'layout':{'cell_text':{key:'수정한 표 머리글'}}}}}]}
    output,_=run(proposal)
    assert any(c['text']=='수정한 표 머리글' for s in output['tableDocument']['layoutSections'] for r in s['sheetRows'] for c in r['cells'])


@pytest.mark.parametrize('proposal',[
 {'commands':[{'operation':'set_title','value':'graph change'}]},
 {'commands':[{'operation':'set_transform','value':'log'}]},
 {'commands':[{'operation':'set_table','params':{'patch':{'labels':['fake']}}}]},
 {'commands':[{'operation':'set_table','params':{'patch':{'recent_periods':1}}}]},
 {'commands':[{'operation':'set_table','params':{'patch':{'layout':{'cell_text':{'missing':'123'}}}}}]},
 {'commands':[{'operation':'set_table','params':{'patch':{'layout':{'code':'execute()'}}}}]},
 {'commands':[],'clarification':'어떤 머리글을 바꿀까요?'},
])
def test_non_table_data_or_invalid_reference_commands_stop(proposal):
    with pytest.raises(ValueError):run(proposal)


def test_numeric_cell_override_from_reference_is_rejected():
    def proposal(context):
        key=next(c['key'] for s in context['tableTargets'] for r in s['rows'] for c in r['cells'] if not c['editable'])
        return {'commands':[{'operation':'set_table','params':{'patch':{'layout':{'cell_text':{key:'99999'}}}}}]}
    with pytest.raises(ValueError,match='관측 수치'):run(proposal)


def test_table_reference_http_route_and_failure_preserve_history(monkeypatch,tmp_path):
    import account_auth as auth,bridge_api as api
    from test_account_auth import login,fixture_graph
    from PIL import Image
    store=auth.AccountStore(tmp_path/'accounts.sqlite3');monkeypatch.setattr(auth,'STORE',store)
    client,user=login('test1');session=fixture_graph(monkeypatch,store,user,'table-reference')
    model=Model({'commands':[{'operation':'set_table','params':{'patch':{'template':'BOK-T06'}}}]});monkeypatch.setattr(api.edit_agent,'model',model)
    stream=io.BytesIO();Image.new('RGB',(20,20),'white').save(stream,format='PNG')
    body={'edit_session_id':'table-reference','edit_target':'table','revision':0,'instruction':'첨부 표처럼 바꿔줘','reference_files':[{'name':'table.png','mime':'image/png','data_url':'data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode()}]}
    before=copy.deepcopy(session['result']);r=client.post('/api/output/edit',json=body);assert r.status_code==200,r.text
    revision=r.json()['outputSpec']['editVersion'];assert r.json()['outputSpec']['tableDocument']['options']['template']=='BOK-T06'
    model.proposal={'commands':[{'operation':'hide_series','value':'계열0'}]}
    r=client.post('/api/output/edit',json={**body,'revision':revision});assert r.status_code==422
    assert session['output']['editVersion']==revision and session['result']==before
    undo=client.post('/api/output/edit',json={'edit_session_id':'table-reference','revision':revision,'action':'undo'});assert undo.status_code==200
