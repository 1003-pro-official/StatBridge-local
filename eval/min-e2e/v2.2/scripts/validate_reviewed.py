"""Offline contract and evaluator regression checks, never product E2E scores."""
from pathlib import Path
from copy import deepcopy
from decimal import Decimal
from collections import Counter
import json,hashlib,sys,os,ast
ROOT=Path(__file__).resolve().parents[1]
PRODUCT=ROOT.parent/'StatBridge'/'StatBridge-local1'
os.environ['PYTHONDONTWRITEBYTECODE']='1';os.environ['LANGFUSE_TRACING_ENABLED']='false';os.environ['STATBRIDGE_DATA_DIR']=str(PRODUCT/'data/processed')
sys.path[:0]=[str(PRODUCT/'src/agent'),str(PRODUCT/'src/backend')]
from score_reviewed import score
from reviewed_evidence import sha,canonical,contract_sha,capture,lookup
from export_reviewed_ragas import export
from validate_dataset import numeric_reference
from classification_metrics import calculate
from legacy_score_core import source_key,compare_rows
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
cases=[json.loads(l) for l in (ROOT/'oracle/cases.jsonl').read_text(encoding='utf-8').splitlines()]
old=[json.loads(l) for l in (ROOT/'baseline_reference/cases.original.jsonl').read_text(encoding='utf-8').splitlines()]
by={c['id']:c for c in cases};oldby={c['id']:c for c in old};checks=[]
def check(n,ok,detail=None):
    checks.append({'check':n,'status':'pass' if ok else 'fail','detail':detail})
    if not ok:print('FAIL',n,detail)
check('120 unique and 6x20',len(cases)==len(by)==120 and Counter(c['group'] for c in cases)=={g:20 for g in ['QT','CQ','DA','D','E','F']})
questions=[json.loads(l) for l in (ROOT/'runner/questions.jsonl').read_text(encoding='utf-8').splitlines()]
check('runner contains input only',questions==[{'id':c['id'],'query':c['query']} for c in cases])
check('semantic changes exactly E40 F34',read('audit/changes/semantic_changes.json')==['E40','F34'])
check('failure status alone is not product evidence',score(by['D25'],{'run_status':'product_failure'},ROOT)['status']=='REVIEW_REQUIRED')
metadata=read('audit/evidence/approved_metadata.json');tables={r['TBL_ID'] for r in metadata['tables']}
for c in cases:
    cid=c['id'];o=oldby[cid];e=c['expected']
    check(cid+' original question unchanged',c['query']==o['query'])
    check(cid+' observed type not fabricated',c['predicted_query_type'] is None)
    check(cid+' review pending not auto approved',c['approval']['status']=='REVIEW_REQUIRED')
    check(cid+' metadata indicator families exist',all(s['table_id'] in tables for s in c['expected_indicator_ids']))
    check(cid+' provenance and operation contract',bool(c['evidence_links']) and bool(c['requested_operations']))
    check(cid+' RAGAS missing observation not executed',score(c,None)['status']=='NOT_EXECUTED' and export(c,{'run_status':'not_executed'},ROOT)[1]=='NOT_EXECUTED')
    if c['group']=='D':
        check(cid+' numeric and units unchanged',e['expected']==o['expected']['expected'] and e['unit']==o['expected']['unit'])
        check(cid+' original plan already correct',e['plan']==o['expected']['plan'])
        check(cid+' calc roles agree plan',set(c['calculation_input_series'])=={s['alias'] for s in e['plan']['sources']})
    if c['group']=='DA':
        d=read(e['snapshot_file']);s=e['sources'][0]
        check(cid+' official snapshot identity periods finite units',d['status']=='fetched' and Counter(r['period'] for r in d['rows'])==Counter(e['periods']) and all(source_key(r)==source_key(s) and Decimal(r['value']).is_finite() and r['unit'] for r in d['rows']))
        check(cid+' official response hash',d['response_sha256']==sha(canonical(d['response']).encode()))
        if e.get('equivalence_snapshot_file'):check(cid+' GDP equivalent snapshot',compare_rows(read(e['equivalence_snapshot_file'])['rows'],d['rows']))
    if c['group'] in ['E','F']:
        check(cid+' distinct initial and ready snapshots',e['snapshot_contract']['never_inject_initial_snapshot'] and e['snapshot_contract']['source_capture_must_be_same_run'])
        check(cid+' no captured snapshot cannot score pass',score(c,{'run_status':'completed','run_id':'synthetic-test-only'},ROOT)['status']=='REVIEW_REQUIRED')
        if cid in ['E40','F34']:check(cid+' restore is actual initial snapshot',e['checkpoints'][-1]['expected_state_ref']=='initial_query_snapshot' and 'expected_state' not in e['checkpoints'][-1])
        if cid in ['E26','E39','F34']:check(cid+' table graph independent',e['table_graph_independence']['table_series']==['a','b'])
        if cid in ['E28','E39','F27']:check(cid+' points must visibly render',all(r['marker_size_gt']==0 and r['visible'] and r['position_matches'] and not r['occluded'] for r in e['visible_point_requirements']))
        if cid in ['F26','F27','F37']:check(cid+' SVG outside-range styles retained','base_line_color' in e['svg_components_required'] and 'period_and_coordinates' in e['svg_components_required'])
from expression_tree_schema import ExpressionPlan
from expression_tree_validator import validate_plan
from dynamic_expression_executor import DynamicExpressionExecutor,Series
from derived_catalog_tools import DerivedCatalogTools
from statbridge_mcp.metadata_store import MetadataStore
catalog=DerivedCatalogTools(MetadataStore());fixture=read('fixtures/v2_source_contract.json')['fixture']
for c in cases:
    if c['group']!='D':continue
    ref=numeric_reference(c,fixture);e=c['expected'];plan=ExpressionPlan.model_validate(e['plan'])
    check(c['id']+' independent Decimal formulas',all(abs(ref[r['period']]-Decimal(r['value']))<=Decimal('0.000001') for r in e['expected']))
    bounds=validate_plan(plan,catalog)
    sources={a:Series(dict(zip(fixture['months'],map(float,fixture[a]))),'연리%','M',[a]) for a in c['calculation_input_series']}
    actual=DynamicExpressionExecutor().execute(plan,sources)['rows']
    check(c['id']+' actual local engine only required sources',len(actual)==len(ref) and all(r['PRD_DE'] in ref and r['UNIT_NM']==e['unit'] and abs(Decimal(str(r['DT']))-ref[r['PRD_DE']])<=Decimal('0.000001') for r in actual) and bounds==e['history'])
# Evidence-bounded synthetic regression: these captures are evaluator tests, never actual UI runs.
testroot=ROOT/'audit/validation/synthetic_regression';testroot.mkdir(parents=True,exist_ok=True)
def save(name,cid,origin,payload,**extra):
    doc={'case_id':cid,'run_id':'SYNTHETIC_EVALUATOR_TEST','origin':origin,'captured_at':'2026-10-29','payload':payload,**extra}
    data=json.dumps(doc,ensure_ascii=False).encode();p=testroot/name;p.write_bytes(data)
    return {'path':name,'sha256':sha(data)}
cid='DA21-19';c=by[cid]
response='2008 SNA 기준 자금순환표 잔액입니다.'
rr=save('response.json',cid,'product_response',{'response_text':response})
er=save('metadata.json',cid,'official_metadata_snapshot',{'metadata':{'path':'한국은행 > 자금순환표 > 2008 SNA 기준'},'query':c['query'],'explanation':response})
p={'id':cid,'run_id':'SYNTHETIC_EVALUATOR_TEST','run_status':'completed','response_text':response,'response_capture':rr,'assertion_count':1,'evidence_contexts':[{'capture':er,'selector':'/payload/metadata','text':canonical({'path':'한국은행 > 자금순환표 > 2008 SNA 기준'})}]}
rec,err=export(c,p,testroot);check('RAGAS exports genuine same-run captured metadata',rec is not None and err is None and not rec['ragas_judge_executed'])
for name,change in [('wrong run',lambda q:q.update(run_id='WRONG')),('wrong case',lambda q:q.update(id='DA21-20')),('hash mutation',lambda q:q['evidence_contexts'][0]['capture'].update(sha256='0'*64)),('query context leakage',lambda q:q['evidence_contexts'][0].update(selector='/payload/query',text=c['query'])),('generated explanation leakage',lambda q:q['evidence_contexts'][0].update(selector='/payload/explanation',text=response)),('no context',lambda q:q.update(evidence_contexts=[]))]:
    bad=deepcopy(p);change(bad)
    if name=='wrong case':record,error=export(by['DA21-20'],bad,testroot)
    else:record,error=export(c,bad,testroot)
    check('RAGAS rejects '+name,record is None and bool(error))
bad=deepcopy(p);bad['run_status']='provider_error';check('provider failure is NA not zero',export(c,bad,testroot)==(None,'PROVIDER_FAILURE'))
bad=deepcopy(p);bad['response_kind']='clarification';check('unexpected clarification not scored faithful',export(c,bad,testroot)==(None,'UNEXPECTED_CLARIFICATION_REVIEW'))
def observation(cid):
    c=by[cid];ready=read('fixtures/baseline.json');initial=deepcopy(ready);initial['title']='ACTUAL INITIAL QUERY — synthetic evaluator test'
    initial['series']['a']['color']='#112233'
    snaps={'initial_query':save(cid+'_initial.json',cid,'initial_query_snapshot',{'state':initial},sequence=1),'fixture_ready':save(cid+'_ready.json',cid,'fixture_ready_snapshot',{'state':ready},sequence=2)}
    cps=[]
    for cp in c['expected']['checkpoints']:
        state=deepcopy(initial if cp.get('expected_state_ref') else cp['expected_state'])
        row={'step':cp['step'],'state':state,'capture':save(cid+'_step'+str(cp['step'])+'.json',cid,'ui_checkpoint',{'state':state},step=cp['step'])}
        if cp.get('clarification'):row.update(clarification_slots=cp['clarification']['slots'],revision_unchanged=True)
        cps.append(row)
    return {'id':cid,'run_id':'SYNTHETIC_EVALUATOR_TEST','run_status':'completed','snapshots':snaps,'checkpoints':cps},initial
for cid in ['E40','F34']:
    obs,initial=observation(cid);result=score(by[cid],obs,testroot)
    check(cid+' actual initial restoration accepted by edit rules',result.get('checks',{}).get('edit_contract') is True,result)
    check(cid+' no final PASS without approvals',result['status']!='PASS')
    bad=deepcopy(obs);cp=bad['checkpoints'][-1];cp['state']['title']='WRONG FIXTURE TITLE';cp['capture']=save(cid+'_badrestore.json',cid,'ui_checkpoint',{'state':cp['state']},step=cp['step'])
    check(cid+' wrong initial restoration fails',score(by[cid],bad,testroot)['status']=='FAIL')
obs,_=observation('E28')
points=[]
for i,r in enumerate(by['E28']['expected']['visible_point_requirements']):
    row={'step':r['step'],'alias':r['alias'],'period':r['period'],'color':r['color'],'visible':True,'marker_size_px':0,'position_matches':True,'within_plot':True,'occluded':False}
    row['capture']=save('point'+str(i)+'.json','E28','rendered_point_observation',deepcopy(row));points.append(row)
obs['rendered_points']=points;check('stored color with marker size zero fails',score(by['E28'],obs,testroot)['status']=='FAIL')
for i,r in enumerate(points):
    r['marker_size_px']=8;r['capture']=save('point_visible'+str(i)+'.json','E28','rendered_point_observation',{k:v for k,v in r.items() if k!='capture'})
check('visible marker satisfies rendered point rule',all(v is True for k,v in score(by['E28'],obs,testroot)['checks'].items() if k.startswith('visible_point_')))
obs,_=observation('F26');downloads=[]
for w in by['F26']['expected']['downloads']:
    path=testroot/('test_f26.'+w['format']);path.write_bytes(b'SYNTHETIC EVALUATOR TEST FILE, NOT PRODUCT OUTPUT')
    ah=sha(path.read_bytes());components={k:True for k in by['F26']['expected']['svg_components_required']};components['base_line_color']=False
    review={'artifact_sha256':ah,'reference_state_sha256':sha(canonical(w['expected_state']).encode()),'actor_type':'independent_parser' if w['format']=='svg' else 'AI','method':'svg_attribute_and_render_review','matches':False if w['format']=='svg' else True,'component_results':components,'approval':'APPROVED','reviewer':'synthetic-test','approved_at':'2026-10-29'}
    downloads.append({'path':path.name,'sha256':ah,'step':w['step'],'ordinal':w['ordinal'],'format':w['format'],'actual_revision':1,'screen_revision':1,'capture_id':'synthetic-test','independent_artifact_review':review})
obs['downloads']=downloads;result=score(by['F26'],obs,testroot)
check('SVG mismatch remains fail with PNG AI review pending',result['status']=='FAIL' and result['checks']['screen_file_consistency'] is False)
check('AI cannot grant PNG human approval',any(v is None for k,v in result['checks'].items() if k.endswith('human_visual_approval')))
qt=[{'id':c['id'],'classification_scope':'component_function','predicted_query_type':c['expected_query_type']} for c in cases if c['group']=='QT']
api=[{**r,'classification_scope':'actual_api_route','predicted_query_type':None if r['id']=='QT21-11' else r['predicted_query_type']} for r in qt]
m=calculate(cases,qt+api,'actual_api_route');check('classification scopes and coverage separate',calculate(cases,qt+api,'component_function')['observed']==20 and m['observed']==19 and m['unobserved']==['QT21-11'] and m['coverage']==0.95)
for cid in ['D25','D27','D38']:check(cid+' unused B not required',by[cid]['calculation_input_series']==['a'] and by[cid]['unused_defined_series']==['b'])
for cid in ['D25','D27','D38']:
    c=by[cid];e=c['expected'];p={'id':cid,'run_id':'SYNTHETIC_EVALUATOR_TEST','run_status':'completed','calculation_input_series':['a'],'display_only_series':[],'calculation_sources':[{'org_id':'301',**s} for s in e['plan']['sources']],'rows':[{'period':r['period'],'value':r['value'],'unit':e['unit']} for r in e['expected']],'observed_source_rows':{'a':dict(zip(fixture['months'],fixture['a']))}}
    check(cid+' A-only synthetic observation satisfies computation rules',score(c,p,testroot)['rule_status']=='pass')
    bad=deepcopy(p);bad['observed_source_rows']['a'][fixture['months'][0]]='999999'
    check(cid+' wrong raw input rejected despite correct output',score(c,bad,testroot)['status']=='FAIL')
v4=PRODUCT/'eval/table-discovery/v4.1';public={n:[json.loads(l) for l in (v4/n).read_text(encoding='utf-8-sig').splitlines()] for n in ['dev.jsonl','test.jsonl','cases_labeled.jsonl']}
check('v4.1 is separate public discovery benchmark 50+70=120',len(public['dev.jsonl'])==50 and len(public['test.jsonl'])==70 and len(public['cases_labeled.jsonl'])==120 and json.loads((v4/'MANIFEST.json').read_text(encoding='utf-8-sig'))['scope']=='table_discovery')
for p in (ROOT/'scripts').glob('*.py'):
    try:ast.parse(p.read_text(encoding='utf-8-sig'));ok=True
    except SyntaxError:ok=False
    check('script syntax '+p.name,ok)
orig=read('baseline_reference/source_hashes.json');originalroot=Path(orig['root'])
check('all 58 original package files unchanged',len(orig['files'])==58 and all(sha((originalroot/p).read_bytes())==h for p,h in orig['files'].items()))
idx=read('audit/evidence/full_source_read_index.json')
check('all 1292 read product files unchanged',idx['files']==1292 and all(sha((PRODUCT/e['path']).read_bytes())==e['sha256'] for e in idx['inventory']))
for n in ['01_질의전용_120문항.md','02_질의와_정답_120문항.md','04_정답_사람검토_120문항.md']:
    text=(ROOT/n).read_text(encoding='utf-8');check(n+' includes every case',all(c['id'] in text for c in cases))
review=read('human_review/artifact_checklist.json');check('18 visual artifacts, 14 in pending 10 cases',len(review)==18 and sum(r['reported_case_status']=='human_pending' for r in review)==14 and len({r['id'] for r in review if r['reported_case_status']=='human_pending'})==10 and all(r['approval']=='REVIEW_REQUIRED' for r in review))
check('all 22 reported NA slots preserved without invented IDs',len(read('audit/ragas_applicability.json')['records'])==22)
check('new RAGAS score absent',read('audit/ragas_regrade.json')['new_score'] is None)
try:lookup({},None);null_selector_rejected=False
except ValueError:null_selector_rejected=True
check('null evidence selector rejected safely',null_selector_rejected)
result={'scope':'offline contracts, independent Decimal formulas, actual local pure engine, evaluator synthetic regression; not live API/UI/model/RAGAS performance','checks':len(checks),'passed':sum(r['status']=='pass' for r in checks),'failed':sum(r['status']=='fail' for r in checks),'product_api_executed':False,'ui_e2e_executed':False,'ragas_judge_executed':False,'human_review_completed':False,'results':checks}
(ROOT/'audit/validation/reviewed_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
report='# vNext 검증 결과\n\n실행일: 2026-10-29. '+str(result['checks'])+'개 검사 중 '+str(result['passed'])+'개 통과, '+str(result['failed'])+'개 실패.\n\n질의 120개·수치/단위·계산 의존성·공식 스냅샷·현재 카탈로그·D20 독립 Decimal 및 실제 로컬 엔진·초기 상태 복원·점 비가시성·SVG 실패 우선·AI 승인 차단·context 출처·NA·원본 보존을 검증했다. 실제 검사별 결과는 audit/validation/reviewed_validation.json에 있다. 합성 캡처는 평가기 회귀 테스트이며 제품 E2E 관측이 아니다.\n\n로컬 제품 컴포넌트 별도 probe는 표/그래프 독립성과 색상만 지정한 점 비가시성 두 원인을 재현했다. 합성 SVG에서는 보고서의 기본색 변형을 재현하지 못했다. 전체 소스 읽기 대상 1,292개와 원본 패키지 58개 해시를 재검사했다.\n\n미실행: 로그인·자연어 모델·실 API·브라우저 E2E·원 실제 파일40개 재검증·RAGAS Judge 재채점·사람 승인. 따라서 제품 성공률·새 Faithfulness 점수는 제시하지 않는다. 기존 v1의 617/617은 역사적 검증 수치이며 본 검사 수치와 합산하지 않는다.\n'
(ROOT/'VALIDATION_REPORT.md').write_text(report,encoding='utf-8');(ROOT/'05_평가셋_검증결과.md').write_text(report,encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='results'},ensure_ascii=False))
raise SystemExit(1 if result['failed'] else 0)
