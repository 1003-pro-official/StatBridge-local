import copy
from authenticated_client import TestClient
import bridge_api as api
from test_chart_edit_period_and_box import fixture_session


def test_conflict_refresh_then_retry_keeps_observations(monkeypatch):
 _,session=fixture_session();before=copy.deepcopy(session['result'])
 monkeypatch.setitem(api.EDIT_SESSIONS,'workflow-conflict',session)
 with TestClient(api.app) as client:
  payload={'edit_session_id':'workflow-conflict','instruction':'','revision':session['output'].get('editVersion',0),'commands':[{'operation':'set_title','kind':'STYLE_EDIT','value':'첫 수정'}]}
  assert client.post('/api/output/edit',json=payload).status_code==200
  payload['commands'][0]['value']='두 번째 수정'
  assert client.post('/api/output/edit',json=payload).status_code==409
  latest=client.get('/api/workspace/workflow-conflict').json()
  payload['revision']=latest['outputSpec']['editVersion']
  assert client.post('/api/output/edit',json=payload).status_code==200
  assert session['output']['chartState']['title']=='두 번째 수정'
  assert session['result']==before
