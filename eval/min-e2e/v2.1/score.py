"""ai-assisted separate scorer. Reads frozen predictions and public development gold."""
import json,re,hashlib,collections
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def load(p):return json.loads(p.read_text(encoding='utf8'))
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
use_final=(HERE/'final-prediction-freeze.json').exists()
pred=HERE/('final-predictions' if use_final else 'predictions')
freeze=load(HERE/('final-prediction-freeze.json' if use_final else 'prediction-freeze.json'))
assert len(freeze['files'])==60
for name,sha in freeze['files'].items():assert hashlib.sha256((pred/name).read_bytes()).hexdigest()==sha
cases=[json.loads(s) for s in (ROOT/'eval/min-e2e/v2.1/cases.jsonl').read_text(encoding='utf8').splitlines()]
manual=load(HERE/'clarification-review.json') if (HERE/'clarification-review.json').exists() else {}
def unit(x):
 x=str(x).replace('＝','=').replace(' ','')
 m=re.fullmatch(r'\((.+)\)\^1',x)
 return m[1] if m else x
def freq(x):return 'Y' if x=='A' else x
def grade_data(c,d):
 r=d.get('response',{});result=d.get('resolved_result',{})
 if r.get('availability',{}).get('status')=='verifying':return '보류',['KOSIS 메타데이터 확인 대기'],{}
 if not result:return '미통과',[r.get('clarification',{}).get('question') or r.get('summary') or d.get('error_type') or '조회 결과 없음'],{}
 a=c['expected']['answer'];table=re.search(r'\((DT_\w+)\)',a)[1];item=re.search(r'항목 (\d+)',a)[1]
 classes=dict(re.findall(r'(objL\d+)=[^;]+?\(([0-9][A-Za-z0-9_.*]+)\)(?=;)',a))
 frequency=re.search(r'주기 ([A-Z])',a)[1]
 values={p:float(v) for p,v in re.findall(r'(\d{4}(?:\d{2})?): (-?[0-9.]+)',a)}
 expected_unit=re.search(r'단위 (.+?)\. 지정한',a)[1]
 plans=result.get('api_plans') or [result.get('api_plan',{})]
 rows=result.get('execution',{}).get('rows',[])
 errors=[]
 if len(plans)!=1:errors.append(f'요청 계열 1개 대신 {len(plans)}개 선택')
 for p in plans:
  if (p.get('org_id'),p.get('table_id'),p.get('item_id'),p.get('classifications'),freq(p.get('frequency'))) != ('301',table,item,classes,freq(frequency)):
   errors.append('기관·표·항목·분류·주기 중 불일치')
 actual_periods=[str(x.get('PRD_DE')) for x in rows]
 if len(rows)!=len(values) or set(actual_periods)!=set(values):errors.append('요청 기간·행 수 불일치')
 differences=[]
 for row in rows:
  if row.get('TBL_ID') and (row.get('TBL_ID')!=table or row.get('ITM_ID')!=item or any(row.get('C'+k[4:])!=v for k,v in classes.items())):continue
  period=str(row.get('PRD_DE'))
  if unit(row.get('UNIT_NM'))!=unit(expected_unit):errors.append('단위 불일치')
  if period in values:
   try:delta=abs(float(row['DT'])-values[period])
   except (TypeError,ValueError,KeyError):delta=float('inf')
   if delta>1e-6:differences.append({'period':period,'actual':row.get('DT'),'snapshot':values[period]})
 if differences:errors.append('공개 정답 스냅샷과 수치 차이')
 detail={'actual_plans':plans,'actual_rows':rows,'numeric_differences':differences,'unit_normalization':'A/Y annual equivalent; full-width =; (unit)^1 same dimension'}
 if differences and errors==['공개 정답 스냅샷과 수치 차이']:return '보류',['공식 개정 여부 확인 필요'],detail
 return ('미통과' if errors else '통과'),list(dict.fromkeys(errors)) or ['계열·기간·단위·수치 일치'],detail
results=[]
for c in cases:
 d=load(pred/(c['id']+'.json'));group=c['id'][:2];detail={}
 if group=='QT':
  expected=c['expected']['label'];actual=d.get('label');status='통과' if actual==expected else '미통과'
  reasons=[f'기대 {expected} / 관측 {actual}'];detail={'expected':expected,'actual':actual,'mode':'local_branch'}
 elif group=='DA':status,reasons,detail=grade_data(c,d)
 else:
  if d.get('response',{}).get('availability',{}).get('status')=='verifying':status,reasons='보류',['메타데이터 확인 대기 — 사용자 의도 모호성과 구분']
  elif c['id'] not in manual:status,reasons='검토대기',['의미 채점 대기']
  else:status=manual[c['id']]['status'];reasons=manual[c['id']]['reasons']
  detail={'clarification_required':c['expected']['clarification_required'],'response_status':d.get('response',{}).get('status'),'review':'ai-assisted; human review pending'}
 results.append({'id':c['id'],'group':group,'query':c['query'],'status':status,'reasons':reasons,'details':detail})
summary={g:dict(collections.Counter(r['status'] for r in results if r['group']==g)) for g in ['DA','CQ','QT']}
write(HERE/'scores.json',{'prediction_directory':pred.name,'summary':summary,'results':results})
print(json.dumps(summary,ensure_ascii=False))
