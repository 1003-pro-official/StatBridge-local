"""Reference-file -> production HTTP edit -> renderer diagnostic (not a visual gold score)."""
import argparse,base64,copy,hashlib,json,os,sys,time,mimetypes
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()
def observations(result):return sorted([{'label':s['label'],'unit':s['unit'],'frequency':s['frequency'],'points':s['points']} for s in result['chart']],key=lambda s:(s['label'],s['unit'],s['frequency']))

def plot_regions(figure):
    layout=figure.get('layout') or {};regions=set()
    for trace in figure.get('data') or []:
        x=str(trace.get('xaxis','x'));y=str(trace.get('yaxis','y'))
        regions.add((tuple((layout.get('xaxis'+x[1:]) or {}).get('domain',[0,1])),tuple((layout.get('yaxis'+y[1:]) or {}).get('domain',[0,1]))))
    return len(regions)
def main():
    p=argparse.ArgumentParser();p.add_argument('--samples',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--live',action='store_true');p.add_argument('--exports',action='store_true');p.add_argument('--case');args=p.parse_args()
    out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True);os.environ['STATBRIDGE_AUTH_DB']=str(out/'accounts.sqlite3')
    sys.path[:0]=[str(ROOT/'src/agent'),str(ROOT/'src/backend')]
    import bridge_api as api
    from fastapi.testclient import TestClient
    api.account_auth.STORE=api.account_auth.AccountStore(out/'accounts.sqlite3')
    source_files=[str(p.relative_to(ROOT)) for area in ['src/agent','src/backend'] for p in (ROOT/area).rglob('*.py')]
    source_files+=['src/agent/stat_dictionary/stat_language_dictionary.json','eval/chart-reference/v1/cases.json']
    hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in source_files}
    provider=[];structured_responses=[];client=getattr(api.edit_agent.model,'client',None)
    if args.live and (not getattr(client,'configured',False) or not api.edit_agent.model.supports_images):p.error('실제 이미지 입력 모델/API 키가 설정되어 있지 않습니다. 성공 점수를 만들지 않습니다.')
    if client:
        original_request=client.request
        def observed_request(*a,**kw):
            started=time.monotonic()
            try:
                text,meta=original_request(*a,**kw);provider.append({'seconds':round(time.monotonic()-started,3),'model':meta.get('model'),'usage':meta.get('usage'),'status':'ok','reference_count':len(kw.get('references',[]))})
                try:
                    response=json.loads(text);structured_responses.append({k:response[k] for k in ('commands','coverage','clarification','reference_style') if k in response});(out/'structured-responses.json').write_text(json.dumps(structured_responses,ensure_ascii=False,indent=2),encoding='utf-8')
                except (ValueError,TypeError):pass
                return text,meta
            except Exception:
                provider.append({'seconds':round(time.monotonic()-started,3),'status':'error'});raise
        client.request=observed_request
    proposals=[]
    original_interpret=api.edit_agent.model.interpret
    def observed_interpret(system,context):
        proposal=original_interpret(system,context)
        proposals.append({'commands':proposal.get('commands'),'clarification':proposal.get('clarification'),'reference_style':proposal.get('reference_style')})
        (out/'proposals.json').write_text(json.dumps(proposals,ensure_ascii=False,indent=2),encoding='utf-8')
        return proposal
    api.edit_agent.model.interpret=observed_interpret
    cases=json.loads(args.samples.read_text(encoding='utf-8-sig'))['cases'];records=[]
    with TestClient(api.app) as http:
        login=http.post('/api/auth/login',json={'username':'test1','password':'1234'});login.raise_for_status()
        for case in cases:
            if args.case and case['id']!=args.case:continue
            record={'id':case['id'],'source_url':case['source_url'],'figure':case['figure'],'pdf_page':case.get('pdf_page'),'pdf_sha256':case.get('pdf_sha256'),'mode':'live' if args.live else 'prepare_only','visual_review':'pending','calls_before':len(provider)}
            try:
                def query(text,dimensions=None):
                    payload={'query':text,'execute':True,'period_start':'2024-01-01','period_end':'2025-12-31'}
                    if dimensions is not None:payload['dimension_values']=dimensions
                    r=http.post('/api/query',json=payload);r.raise_for_status();result=r.json()
                    if not result.get('outputSessionId'):raise ValueError('조회 조건 미확정: '+result.get('summary',''))
                    return result['outputSessionId']
                if case.get('series_tables'):
                    sessions=[]
                    for selected in case['series_tables']:
                        table=api.agent.tables_by_id[selected['table_id']];dimensions={}
                        for dimension in table['dimensions']:
                            matches=[v for v in dimension['values'] if v['value_name']==selected['value_name']]
                            if len(matches)==1:dimensions[dimension['api_param']]=matches[0]['value_id']
                        if not dimensions:raise ValueError('카탈로그에서 정확한 분류를 확인하지 못했습니다.')
                        sessions.append(query(table['table_id']+' '+table['table_name'],dimensions))
                elif case.get('expand_country'):
                    table=api.agent.tables_by_id['DT_303Y005'];dims=table['dimensions'];country=next(d for d in dims if any(case['expand_country'] in str(v.get('value_name') or '') for v in d['values']));measure=next(d for d in dims if d is not country)
                    share=next(v for v in measure['values'] if '비중' in str(v.get('value_name') or ''))
                    values=[v for v in country['values'] if case['expand_country'] in str(v.get('value_name') or '')][:case.get('max_series',5)]
                    sessions=[query('DT_303Y005 국가별 결제통화(수입)',{country['api_param']:v['value_id'],measure['api_param']:share['value_id']}) for v in values]
                else:sessions=[query(case['query'])]
                r=http.post('/api/output',json={'session_ids':sessions,'chart_type':'line','chart_mode':'combined','quick_output':True});r.raise_for_status();before=r.json()
                if len(before['chart'])!=case['expected']['series_count']:raise ValueError('검증 데이터의 계열 수가 기대 조건과 다릅니다.')
                (out/(case['id']+'-before.json')).write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding='utf-8')
                def verify_exports(body,phase):
                    files=[]
                    for format in ('png','svg','pdf'):
                        if format not in body['outputSpec'].get('exportFormats',[]):continue
                        response=http.post('/api/report/export',json={'edit_session_id':body['editSessionId'],'revision':body['outputSpec'].get('editVersion',0),'format':format})
                        response.raise_for_status();filename=case['id']+'-'+phase+'.'+format;(out/filename).write_bytes(response.content)
                        files.append({'format':format,'file':filename,'bytes':len(response.content),'sha256':hashlib.sha256(response.content).hexdigest()})
                    return files
                if args.exports:record['before_exports']=verify_exports(before,'before')
                reference=(args.samples.parent/case['reference_file']).resolve();data=reference.read_bytes();mime=mimetypes.guess_type(reference.name)[0] or 'application/octet-stream';reference_payload={'name':reference.name,'mime':mime,'data_url':'data:'+mime+';base64,'+base64.b64encode(data).decode()}
                record.update(reference_sha256=hashlib.sha256(data).hexdigest(),observations=len([p for s in before['chart'] for p in s['points']]),series=len(before['chart']))
                if not args.live:record['status']='prepared'
                else:
                    identifier=before['editSessionId'];session=api.EDIT_SESSIONS[identifier];raw_hash=digest(session['result']['execution']['rows']);initial=copy.deepcopy(session['output']);started=time.monotonic()
                    edited=http.post('/api/output/edit',json={'edit_session_id':identifier,'instruction':case['instruction'],'revision':0,'reference_files':[reference_payload]});record.update(seconds=round(time.monotonic()-started,3),http_status=edited.status_code)
                    if edited.status_code!=200:
                        detail=edited.json().get('detail')
                        if isinstance(detail,list):detail=[{k:v for k,v in item.items() if k in {'type','loc','msg'}} for item in detail]
                        record.update(status='clarification_or_error',detail=detail,unchanged_on_failure=initial==session['output'],raw_observations_unchanged=raw_hash==digest(session['result']['execution']['rows']))
                    else:
                        after=edited.json();(out/(case['id']+'-after.json')).write_text(json.dumps(after,ensure_ascii=False,indent=2),encoding='utf-8');state=after['outputSpec']['chartState']
                        preserved=digest(observations(before))==digest(observations(after));raw_preserved=raw_hash==digest(session['result']['execution']['rows']);expected=case['expected'];kind=state.get('report',{}).get('kind') if state.get('report') else state['chart_type'];layout=state.get('report',{}).get('kind') if state.get('report') else state['layout']
                        figure=after['outputSpec'].get('plotlyFigure') or {}
                        traces=figure.get('data') or []
                        line_family=all(t.get('type')=='scatter' and 'lines' in t.get('mode','') for t in traces)
                        style=(line_family and layout!='panels' and state.get('layout')=='combined' if expected.get('chart_type')=='line' else kind==expected['chart_type'] if 'chart_type' in expected else plot_regions(figure)==expected['series_count'])
                        if expected.get('trace_types'):
                            style=sorted(t.get('type') for t in traces)==sorted(expected['trace_types'])
                        if expected.get('secondary_axis'):
                            style=style and any(t.get('yaxis')=='y2' for t in traces)
                        record.update(actual_panels=plot_regions(figure),axis_pairs=len({(t.get('xaxis','x'),t.get('yaxis','y')) for t in traces}),status='rendered',observations_unchanged=preserved,raw_observations_unchanged=raw_preserved,chart_type=kind,layout=layout,style_checks_passed=style,changes=after['outputSpec'].get('editChanges'),commands=after['outputSpec'].get('editHistory',[])[-1:])
                        record['contract_passed']=preserved and raw_preserved and bool(after['outputSpec'].get('plotlyFigure',{}).get('data'))
                        if args.exports:record['after_exports']=verify_exports(after,'after')
                record['calls']=len(provider)-record['calls_before']
            except Exception as error:record.update(status='failed',error=str(error))
            records.append(record);(out/'results.json').write_text(json.dumps({'cases':records,'provider':provider,'source_hashes':hashes,'source_unchanged':all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value for name,value in hashes.items()),'visual_review_required':True},ensure_ascii=False,indent=2),encoding='utf-8')
            print(case['id'],record['status'],record.get('seconds'),record.get('style_checks_passed'),flush=True)
    bad=any(r['status']!='rendered' or not r.get('contract_passed') or not r.get('style_checks_passed') for r in records) if args.live else any(r['status']!='prepared' for r in records)
    print('AUTOMATED_CONTRACT',sum(r.get('contract_passed',False) and r.get('style_checks_passed',False) for r in records),'/',len(records),'VISUAL_REVIEW_REQUIRED',flush=True)
    if bad:raise SystemExit(2)
if __name__=='__main__':main()
