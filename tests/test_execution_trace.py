from types import SimpleNamespace
import copy
from execution_trace import initial_traces,edit_trace

def test_initial_runs_use_actual_paths_and_separate_output_invocation():
    one={'orchestration':{'engine':'langgraph','stage':'awaiting_output_selection','path':['resolve_request','execute_statistics','await_output_selection']}}
    two={'orchestration':{'engine':'langgraph','stage':'awaiting_output_selection','path':['resolve_request','execute_statistics','await_output_selection']}}
    rendered={'orchestration':{**one['orchestration'],'stage':'output_ready','path':[*one['orchestration']['path'],'prepare_output']}}
    runs=initial_traces([one,two],rendered,one)
    assert [r['kind'] for r in runs]==['query','query','output']
    assert runs[-1]['path']==['prepare_output']
    assert initial_traces([{'api_key':'private'}],{}, {})==[]

def test_direct_edit_and_langgraph_edit_are_distinct():
    payload=SimpleNamespace(action='edit',undo_property=None,document=None,restore_initial=False)
    out={'editVersion':2,'editChanges':['제목 변경'],'editAgent':{'path':['interpret_edit','render_output']}}
    assert edit_trace(payload,out)['engine']=='direct'
    run=edit_trace(payload,out,used_edit_graph=True)
    assert run['engine']=='langgraph' and run['path']==['interpret_edit','render_output'] and run['revision']==2

def test_actual_api_edits_accumulate_runs_and_failed_edits_do_not_commit(monkeypatch):
    import bridge_api as api
    from authenticated_client import TestClient
    from test_chart_edit_period_and_box import fixture_session
    _,session=fixture_session();monkeypatch.setitem(api.EDIT_SESSIONS,'evidence-fixture',session)
    client=TestClient(api.app)
    change=client.post('/api/output/edit',json={'edit_session_id':'evidence-fixture','commands':[{'operation':'set_title','kind':'STYLE_EDIT','value':'실행 근거 검증'}]})
    assert change.status_code==200
    first=change.json()['executionRuns'];assert len(first)==1 and first[0]['engine']=='direct'
    before=copy.deepcopy(session)
    failed=client.post('/api/output/edit',json={'edit_session_id':'evidence-fixture','commands':[{'operation':'set_line_width','kind':'STYLE_EDIT','value':99}]})
    assert failed.status_code==422 and session==before
    undo=client.post('/api/output/edit',json={'edit_session_id':'evidence-fixture','action':'undo'})
    assert undo.status_code==200
    runs=undo.json()['executionRuns'];assert len(runs)==2 and 'undo' in runs[-1]['path']
    reopened=client.get('/api/workspace/evidence-fixture');assert reopened.status_code==200 and reopened.json()['executionRuns']==runs
