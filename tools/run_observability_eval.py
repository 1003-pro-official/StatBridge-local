"""Isolated HTTP integration for real tracing, account checks and immutable fixture data."""
from pathlib import Path
import os,sys,json,runpy,argparse
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',default='.venv/cache/langfuse-20261020/http-eval');args=parser.parse_args()
    out=(ROOT/args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    os.environ['STATBRIDGE_TABLE_PREVIEW_DIR']=str(out/'isolated-app')
    state=runpy.run_path(str(ROOT/'tools/serve_table_edit_preview.py'))
    api,client=state['api'],state['client']
    graph=client.get('/api/account/graphs').json()['items'][0]['id']
    before=client.get('/api/workspace/'+graph).json();revision=before['outputSpec'].get('editVersion',0);checks=[]
    def check(name,condition):
        checks.append({'name':name,'status':'PASS' if condition else 'FAIL'})
        if not condition:raise AssertionError(name)
    response=client.post('/api/output/edit',json={'edit_session_id':graph,'revision':revision,'instruction':'','commands':[{'kind':'STYLE_EDIT','operation':'set_title','value':'Observed fixture edit'}]})
    check('edit_success',response.status_code==200)
    current=response.json();run=current['observability'][-1];trace_id=run['traceId']
    check('real_steps_and_duration',run['durationMs']>0 and {'request.edit','edit.validate_apply','edit.apply','output.build','chart.render','table.build'}<={s['name'] for s in run['steps']})
    check('no_extra_model_calls',run['modelCalls']==0)
    raw=lambda value:[(s['id'],s['unit'],s['points']) for s in value['chart']]
    check('immutable_observations',raw(current)==raw(before))
    failed=client.post('/api/output/edit',json={'edit_session_id':graph,'revision':current['outputSpec']['editVersion'],'instruction':'','document':{'version':'invalid-secret-cannot-leak'}})
    check('validation_error_response',failed.status_code==422)
    error_trace=failed.json()['observability'][-1]
    check('error_time_and_code',error_trace['status']=='failed' and error_trace['durationMs']>0 and any(s.get('error',{}).get('code')=='validation_failed' for s in error_trace['steps']))
    check('no_raw_error_or_input', 'invalid-secret-cannot-leak' not in json.dumps(error_trace))
    restored=client.get('/api/workspace/'+graph).json()
    check('failed_edit_keeps_original',restored['outputSpec']['editVersion']==current['outputSpec']['editVersion'] and raw(restored)==raw(current))
    file=client.post('/api/table/export',json={'edit_session_id':graph,'revision':current['outputSpec']['editVersion'],'format':'xlsx'})
    check('export_bytes_preserved',file.status_code==200 and file.content.startswith(b'PK'))
    export_trace=client.get('/api/observability/'+file.headers['x-statbridge-trace-id']).json()
    check('export_is_observed',any(s['name']=='export.table' for s in export_trace['steps']))
    check('owner_can_read_trace',client.get('/api/observability/'+trace_id).status_code==200)
    from fastapi.testclient import TestClient
    other=TestClient(api.app)
    created=other.post('/api/auth/signup',json={'username':'trace_other_user','name':'Trace test','email':'trace@example.test','password':'test-trace-1234'})
    if created.status_code not in (200,409):raise AssertionError('temporary signup failed')
    other.post('/api/auth/login',json={'username':'trace_other_user','password':'test-trace-1234'}).raise_for_status()
    check('other_account_blocked',other.get('/api/observability/'+trace_id).status_code==404)
    anonymous=TestClient(api.app)
    check('anonymous_blocked',anonymous.get('/api/observability/'+trace_id).status_code==401)
    report={'passed':len(checks),'failed':0,'skipped':0,'model_calls':0,'data_source':'frozen attachment observations; not live KOSIS','checks':checks,'sample':{'success':run,'failure':error_trace,'export':export_trace}}
    (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:report[key] for key in ['passed','failed','skipped','model_calls','data_source']}))
    return 0

if __name__=='__main__':raise SystemExit(main())
