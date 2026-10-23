"""Offline scoring only; never imports the app or calls a model."""
import sys, json, hashlib, html
from pathlib import Path
from decimal import Decimal, InvalidOperation
from collections import Counter

import argparse
parser = argparse.ArgumentParser(description='Offline scoring with the original v3 rubric.')
parser.add_argument('--run-dir', type=Path, help='Completed fresh run; omit to rescore saved archive observations.')
parser.add_argument('--output', type=Path, required=True, help='New output directory; refuses overwrite.')
args = parser.parse_args()
ARCHIVE = Path(__file__).resolve().parents[1]
ROOT = ARCHIVE.parent
RUN = args.run_dir.resolve() if args.run_dir else None
SOURCE = RUN/'output' if RUN else ARCHIVE/'execution'
QUESTION_PATH = RUN/'input/questions.jsonl' if RUN else ARCHIVE/'questions.jsonl'
OUT = args.output.resolve()
OUT.mkdir(parents=True, exist_ok=False)
def network_denied(event,args):
    if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('scorer network disabled')
sys.addaudithook(network_denied)
assert json.loads((SOURCE/'completion.json').read_text())['completed']
def lines(path):return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
observed=lines(SOURCE/'observations.jsonl')
assert len(observed)==20 and len({r['id'] for r in observed})==20
input_rows=lines(QUESTION_PATH)
# Gold is opened here only, after all observations exist and the model worker ended.
gold_path=ARCHIVE/'answer_key.jsonl'
gold=lines(gold_path)
assert [(r['id'],r['query']) for r in gold]==[(r['id'],r['query']) for r in input_rows]
calls=lines(SOURCE/'http.jsonl')
preflight=json.loads((SOURCE/'preflight.json').read_text())
completion=json.loads((SOURCE/'completion.json').read_text())
assert completion['gold_access_attempts_after_selftest']==0
assert hashlib.sha256(QUESTION_PATH.read_bytes()).hexdigest()==preflight['questions_sha256']
freq=lambda x:{'A':'Y','H':'S'}.get(x,x)
results=[]
for g,o in zip(gold,observed):
    assert g['id']==o['id']
    r=o.get('result') or {};execution=r.get('execution') or {};rows=execution.get('rows') or []
    e=g['expected'];p=e['params'];plans=r.get('api_plans') or ([r['api_plan']] if r.get('api_plan') else [])
    cc=[c for c in calls if c['case_id']==g['id']]
    data=[c for c in cc if c['kind']=='kosis_data']
    exact_plan=len(plans)==1
    plan=plans[0] if exact_plan else {}
    checks={}
    checks['API 호출']=bool(data and execution.get('status')=='success' and any(s.get('source')=='kosis_api' for s in execution.get('sources',[])))
    checks['기관·표']=bool(exact_plan and plan.get('org_id')==p['orgId'] and plan.get('table_id')==p['tblId'] and all(x.get('TBL_ID')==p['tblId'] and str(x.get('ORG_ID'))==p['orgId'] for x in rows))
    checks['항목']=bool(exact_plan and plan.get('item_id')==p['itmId'] and all(x.get('ITM_ID')==p['itmId'] for x in rows))
    classes={k:v for k,v in p.items() if k.startswith('objL')}
    checks['분류']=bool(exact_plan and plan.get('classifications')==classes and all({f'objL{i}':x[f'C{i}'] for i in range(1,9) if x.get(f'C{i}')}==classes for x in rows))
    wanted={x['period']:x for x in e['points']}
    checks['주기·기간']=bool(exact_plan and freq(plan.get('frequency'))==freq(p['prdSe']) and plan.get('start_period')==p['startPrdDe'] and plan.get('end_period')==p['endPrdDe'] and len(rows)==len(wanted) and {x.get('PRD_DE') for x in rows}==set(wanted) and all(freq(x.get('PRD_SE'))==freq(p['prdSe']) for x in rows))
    checks['단위']=bool(rows and all(x.get('UNIT_NM')==e['points'][0]['unit'] for x in rows))
    differences=[]
    for period,w in wanted.items():
        found=[x for x in rows if x.get('PRD_DE')==period]
        try:match=len(found)==1 and Decimal(str(found[0]['DT']))==Decimal(w['value'])
        except (InvalidOperation,KeyError,TypeError):match=False
        if not match:differences.append({'period':period,'expected':w['value'],'observed':[x.get('DT') for x in found]})
    checks['수치']=not differences
    failed=[k for k,v in checks.items() if not v]
    results.append({'id':g['id'],'query':g['query'],'result':'통과' if not failed else '미통과','checks':checks,'failed_checks':failed,'runtime_status':r.get('status'),'execution_status':execution.get('status'),'runtime_error':execution.get('error') or o.get('error_type'),'clarification_question':r.get('question'),'expected_table':p['tblId'],'observed_plans':plans,'expected_periods':list(wanted),'observed_periods':sorted({str(x.get('PRD_DE')) for x in rows}),'numeric_differences':differences,'model_http_calls':len([c for c in cc if c['kind']=='model']),'kosis_http_calls':len(data)})
passed=sum(r['result']=='통과' for r in results)
summary={'total':20,'passed':passed,'failed':20-passed,'score_percent':passed*5,'axis_passed':{k:sum(r['checks'][k] for r in results) for k in results[0]['checks']},'models':dict(Counter(('NCP embedding v2' if 'embedding' in c['path'] else c.get('body',{}).get('model') or c['path'].rstrip('/').split('/')[-1]) for c in calls if c['kind']=='model' and isinstance(c.get('body'),dict))),'actual_http_counts':completion['http_calls'],'gold_isolation':{'preflight_passed':3,'gold_access_attempts_after_selftest':0,'scorer_network_disabled':True},'scope':'Actual StatBridge Agent/MCP/live KOSIS execution, no browser or authenticated HTTP route test. One independent query per case; no answer-informed clarification, no rerun. Deterministic resolver shortcuts are included; some questions may make zero model calls.','reference':'User-reviewed gold with v3 query prefix change fixed snapshot (347 ZIP + 2 live downloads); live revisions remain strict mismatches in this run.','gold_sha256':hashlib.sha256(gold_path.read_bytes()).hexdigest(),'observations_sha256':hashlib.sha256((SOURCE/'observations.jsonl').read_bytes()).hexdigest(),'questions_sha256':hashlib.sha256(QUESTION_PATH.read_bytes()).hexdigest()}
(OUT/'scores.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in results),encoding='utf-8',newline='\n')
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
esc=lambda x:html.escape(str(x))
body='<h1>データ'.replace('データ','데이터')+' 정확도 v3 평가 결과</h1><p><b>통과 '+str(passed)+'/20 · 미통과 '+str(20-passed)+'/20 · '+str(passed*5)+'점</b></p>'
body+='<p>7개 항목 모두 통과해야 최종 통과. 실시간 API 결과를 사전 고정 정답으로 채점했다. 정답으로 실행을 보완하거나 재실행하지 않았다.</p><p>입력·파일 목록·읽기 차단 사전 검사 3개 통과. 모델 실행 종료 후 별도 네트워크 차단 채점 프로세스에서 정답을 읽었다.</p>'
body+='<table><tr><th>문항</th><th>판정</th><th>미통과 항목</th><th>모델 호출</th></tr>'+''.join('<tr><td>'+esc(r['id'])+'</td><td>'+r['result']+'</td><td>'+esc(', '.join(r['failed_checks']))+'</td><td>'+str(r['model_http_calls'])+'</td></tr>' for r in results)+'</table>'
for r in results:body+='<section><h2>'+r['id']+' · '+r['result']+'</h2><p>'+esc(r['query'])+'</p><pre>'+esc(json.dumps({k:v for k,v in r.items() if k not in ('query','observed_plans')},ensure_ascii=False,indent=2))+'</pre><details><summary>관측된 계획</summary><pre>'+esc(json.dumps(r['observed_plans'],ensure_ascii=False,indent=2))+'</pre></details></section>'
(OUT/'report.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>데이터 정확도 평가 결과</title><style>body{max-width:1100px;margin:40px auto;font:16px/1.7 sans-serif;padding:0 16px}td,th{border:1px solid #ccc;padding:8px}table{border-collapse:collapse}section{border-top:2px solid #ccc;margin-top:24px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>'+body+'</html>',encoding='utf-8',newline='\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
