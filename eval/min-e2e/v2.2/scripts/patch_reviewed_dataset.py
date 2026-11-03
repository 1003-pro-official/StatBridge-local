"""vNext audit patch; no product writes, no product output used as gold."""
from pathlib import Path
from copy import deepcopy
import json,sys,os,hashlib,csv,subprocess
ROOT=Path(__file__).resolve().parents[1]
PRODUCT=ROOT.parent/'StatBridge'/'StatBridge-local1'
os.environ['PYTHONDONTWRITEBYTECODE']='1';os.environ['LANGFUSE_TRACING_ENABLED']='false'
os.environ['STATBRIDGE_DATA_DIR']=str(PRODUCT/'data/processed')
sys.path[:0]=[str(PRODUCT/'src/agent'),str(PRODUCT/'src/backend')]
from expression_tree_schema import ExpressionPlan
from expression_tree_validator import validate_plan
from derived_catalog_tools import DerivedCatalogTools
from statbridge_mcp.metadata_store import MetadataStore
catalog=DerivedCatalogTools(MetadataStore())
original=[json.loads(l) for l in (ROOT/'baseline_reference/cases.original.jsonl').read_text(encoding='utf-8').splitlines()]
by={c['id']:c for c in original}
master=list(csv.DictReader((PRODUCT/'data/processed/bok_table_master.csv').open(encoding='utf-8-sig')))
items=list(csv.DictReader((PRODUCT/'data/processed/bok_items.csv').open(encoding='utf-8-sig')))
classes=list(csv.DictReader((PRODUCT/'data/processed/bok_classifications.csv').open(encoding='utf-8-sig')))

def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def write(name,data):
    p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data if isinstance(data,str) else json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def leaves(plan):
    nodes={n['id']:n for n in plan['nodes']};sources={s['alias'] for s in plan['sources']};used=set()
    def visit(ref):
        if ref in sources:used.add(ref)
        else:
            for r in nodes[ref]['inputs']:visit(r)
    for output in plan['outputs']:visit(output['node'])
    return used
QT_TABLES={1:['DT_404Y014'],2:['DT_404Y014'],3:['DT_402Y014'],4:['DT_402Y014'],5:['DT_121Y006'],6:['DT_121Y006'],7:['DT_151Y001'],8:['DT_151Y001'],9:['DT_151Y003'],10:['DT_151Y003'],11:['DT_513Y001'],12:['DT_513Y001'],13:['DT_161Y006'],14:['DT_161Y006'],15:['DT_200Y104','DT_200Y108'],16:['DT_200Y104','DT_200Y108'],17:['DT_301Y013'],18:['DT_301Y013'],19:['DT_511Y002'],20:['DT_511Y002']}
CQ_TABLES={1:['DT_121Y006','DT_121Y015'],2:['DT_101Y003','DT_161Y007'],3:['DT_161Y006','DT_101Y003'],4:['DT_200Y107','DT_200Y108'],5:['DT_200Y110','DT_200Y108'],6:['DT_401Y015'],7:['DT_513Y001'],8:['DT_121Y006'],9:['DT_401Y015'],10:['DT_121Y006'],11:['DT_121Y006'],12:['DT_161Y006'],13:['DT_401Y015'],14:['DT_200Y108'],15:['DT_513Y001'],16:['DT_513Y001'],17:['DT_401Y015'],18:['DT_161Y007'],19:['DT_401Y015'],20:['DT_121Y006']}
qtops={2:['arithmetic_mean'],3:['relative_change_from_base'],6:['difference'],7:['divide'],10:['sum_across_regions'],12:['maximum_minus_minimum'],13:['rebase_100'],16:['relative_change_from_base'],17:['sum_across_months'],19:['median']}
point_cases={'E28':[(2,'a','202506','#E53935'),(4,'a','202506','#E53935'),(4,'b','202506','#16A34A')],
 'E39':[(i,'a','202504','#E53935') for i in range(2,6)],
 'F27':[(i,'b','202506','#E53935') for i in range(2,6)]}
hide_cases={'E26','E39','F34'}
human_cases={'F21','F22','F23','F25','F28','F29','F33','F35','F36','F38'}
reported_defects={'QT21-08','QT21-10','CQ21-15','D25','D27','D38','E26','E28','E33','E39','F26','F27','F34','F37'}
priority_judge={'QT21-08','QT21-10','CQ21-15','DA21-19','DA21-20'}
changes=[];cases=[];semantic_changes=[]
for baseline in original:
    c=deepcopy(baseline);cid=c['id'];g=c['group'];e=c['expected'];n=int(cid.split('-')[-1]) if '-' in cid else int(cid[1:]);reasons=[]
    c['schema_version']='2.0.0-reviewed-vNext';c['predicted_query_type']=None
    c['approval']={'status':'REVIEW_REQUIRED','reviewer':None,'approved_contract_sha256':None,'note':'2026-10-29 report states original human oracle approval; original approval manifest unavailable locally. Changed contracts require separate approval. This is separate from PNG/PDF human review.'}
    c['evidence_links']=[{'path':'baseline_reference/cases.original.jsonl','case_id':cid,'kind':'original_contract','sha256':digest(baseline)}]
    c['requested_operations']=[];c['calculation_input_series']=[];c['display_only_series']=[];c['unused_defined_series']=[]
    c['clarification_required']=e.get('clarification_required',False);c['clarification_reason']=e.get('question_target') if g=='CQ' else '질의가 명시한 조건을 유지한다. 정의만 된 계열을 계산 입력으로 강제하지 않는다.'
    if g=='QT':
        c['expected_query_type']=e['label'];c['requested_operations']=qtops.get(n,['fetch_published_values'])
        c['expected_indicator_ids']=[{'table_id':tid,'item_ids':[r['ITM_ID'] for r in items if r['TBL_ID']==tid],'binding':'candidate_family_not_all_required'} for tid in QT_TABLES[n]]
        c['evaluation_scope']='query_type_classification';c['capability_review']='Not all arithmetic requests are guaranteed executable by expression schema; QT grades classification only.'
    elif g=='CQ':
        c['expected_query_type']='undetermined' if n==10 else ('derived' if n in [9,17,20] else 'general')
        c['requested_operations']=['comparison_basis_requires_clarification'] if n==9 else (['aggregation_requires_clarification'] if n==10 else ['yoy_pct'] if n==17 else ['arithmetic_mean'] if n==20 else ['fetch_published_values'])
        c['expected_indicator_ids']=[{'table_id':tid,'binding':'candidate_family_pending_slot' if n<=10 else 'selected_family'} for tid in CQ_TABLES[n]]
        c['evaluation_scope']='clarification_and_condition_preservation'
    elif g=='DA':
        c['expected_query_type']='general';c['requested_operations']=['fetch_published_values'];c['expected_indicator_ids']=deepcopy(e['sources']);c['display_only_series']=['requested_published_series']
        c['evaluation_scope']='data_selection_and_raw_observations'
        c['evidence_links'].append({'path':e['snapshot_file'],'kind':'official_source_snapshot','sha256':hashlib.sha256((ROOT/e['snapshot_file']).read_bytes()).hexdigest()})
    elif g=='D':
        used=leaves(e['plan']);original_plan_sources={s['alias'] for s in e['plan']['sources']}
        defined_sources=json.loads((ROOT/'fixtures/api_fixture.json').read_text(encoding='utf-8'))['sources']
        defined={s['alias'] for s in defined_sources}
        c['expected_query_type']='derived';c['calculation_input_series']=sorted(used);c['unused_defined_series']=sorted(defined-used)
        c['defined_indicator_ids']=deepcopy(defined_sources);c['requested_operations']=[{'operator':node['operator'],'inputs':node['inputs'],'lag':node.get('lag'),'window':node.get('window'),'base_period':node.get('base_period')} for node in e['plan']['nodes']]
        e['plan']['sources']=[s for s in e['plan']['sources'] if s['alias'] in used]
        c['expected_indicator_ids']=deepcopy(e['plan']['sources']);c['evaluation_scope']='derived_computation'
        if original_plan_sources-used:
            e['history']=validate_plan(ExpressionPlan.model_validate(e['plan']),catalog)
            e['retrieval_policy']='May retrieve unused defined series, but it must not become a calculation dependency or force clarification. Compare computation sources, not all fetched sources.'
            reasons.append('DATASET_ERROR: source_exact_match wrongly required unused defined sources as calculation inputs; prune oracle plan to dependency leaves without changing query, arithmetic, output numbers or unit.')
            semantic_changes.append(cid)
        c['clarification_required']=False;c['clarification_reason']='필요한 연산·기간·시차가 질의에 명시됨. 사용하지 않는 A/B 정의는 추가 질문의 사유가 아님.'
        c['evidence_links'].append({'path':'fixtures/api_fixture.json','kind':'fixed_raw_fixture','sha256':hashlib.sha256((ROOT/'fixtures/api_fixture.json').read_bytes()).hexdigest()})
    else:
        c['expected_query_type']='not_applicable';c['workflow_intent']='edit' if g=='E' else 'export';c['requested_operations']=[o['op'] for step in c['reference_operations'] for o in step]
        c['expected_indicator_ids']=deepcopy(json.loads((ROOT/'fixtures/api_fixture.json').read_text(encoding='utf-8'))['sources']);c['display_only_series']=['a','b'];c['evaluation_scope']='stateful_UI_and_actual_artifacts'
        e['snapshot_contract']={'initial_query_snapshot':'capture actual response before any fixture preparation edit','fixture_ready_state':'fixtures/baseline.json after actual UI preparation','history_start':'fixture-ready checkpoint; product initial snapshot remains initial query snapshot','restore_target':'initial_query_snapshot','never_inject_initial_snapshot':True,'source_capture_must_be_same_run':True}
        if cid in ['E40','F34']:
            last=e['checkpoints'][-1];last.pop('expected_state');last['expected_state_ref']='initial_query_snapshot'
            e.pop('final_state');e['final_state_ref']='initial_query_snapshot'
            for download in e['downloads']:
                download.pop('expected_state');download['expected_state_ref']='initial_query_snapshot'
            oldtext=c['reference_text']
            if cid=='E40':c['reference_text']='③ 저장 직전의 fixture-ready 편집 상태를 같은 계정에서 재개한다. ④ 실제 최초 조회 직후 캡처한 초기 스냅샷으로 복원한다. fixture 준비 후 제목·색상과 초기 조회 스냅샷을 혼동하지 않는다. 초기 스냅샷 미수집 시 REVIEW_REQUIRED. 원자료 불변 조건은 유지한다.'
            else:c['reference_text']='숨김·제목 편집 후 실제 최초 조회 직후 캡처한 초기 스냅샷으로 복원하고, PNG·CSV를 해당 시점 화면·원자료와 비교한다. fixture-ready 제목·색상을 최초 스냅샷으로 강제하지 않는다. 그래프 B 숨김이 표의 선택 계열까지 바꾸는지는 별도 독립 검사한다.'
            reasons.append('DATASET_ERROR: fixture-ready title/color was assumed to be the product initial snapshot; replace nonexistent initial-state premise with a same-run observed initial snapshot, not product behavior relaxation.')
            semantic_changes.append(cid)
        if cid in hide_cases:
            e['table_graph_independence']={'required':True,'table_series':['a','b'],'check_every_step':True,'not_waived_by_reset_target_change':True}
            reasons.append('HARNESS_ERROR prevention: graph visibility and table selection are separate; preserve independently at every step.')
        if cid in point_cases:
            e['visible_point_requirements']=[{'step':step,'alias':alias,'period':period,'color':color,'visible':True,'marker_size_gt':0,'within_plot':True,'position_matches':True,'occluded':False} for step,alias,period,color in point_cases[cid]]
            reasons.append('HARNESS_ERROR: stored point color alone cannot demonstrate visible point emphasis; require rendered size, color, position and visibility.')
        if cid in ['F26','F27','F37']:
            e['svg_components_required']=['base_line_color','segment_color','point_emphasis' if cid=='F27' else 'segment_scope','line_width','line_dash','legend','period_and_coordinates']
            reasons.append('HARNESS_ERROR prevention: independently verify SVG base styles outside selected range; never waive transformed colors because highlighted segment matches.')
        if g=='F':
            e['human_visual_review_required']=any(d['format'] in ['png','pdf'] for d in e['downloads'])
            e['human_review_gate']='PNG/PDF: actor_type=human + explicit approval + actual file hash; AI review cannot set human approval. Any confirmed mismatch remains fail even if another file awaits review.'
    # Evidence map for all 120. Textual query is a constraint, not factual RAGAS evidence.
    c['evidence_links'].append({'path':'runner/questions.jsonl','case_id':cid,'kind':'explicit_user_requirements_not_factual_context'})
    c['ragas_contract']={'required_origin':'same_run_captured_metadata_raw_data_and_actual_computation','question_is_not_factual_evidence':True,'generated_explanation_is_not_evidence':True,'missing_metadata_action':'EVIDENCE_GAP','no_claims_action':'NOT_APPLICABLE','judge_or_runtime_error_action':'NOT_EXECUTED','preserve_original_score':True,'rejudge_id_required':True}
    if cid in ['DA21-19','DA21-20']:c['ragas_contract']['metadata_claims_to_check']=['2008 SNA 기준','상세자금순환표(2018~)',c['expected']['sources'][0]['table_id'],'합계','현금 발행 및 예수금 합계']
    c['audit']={'status':'REVIEW_REQUIRED','local_machine_contract_check':'to_be_validated','source_original_sha256':digest(baseline),'reported_product_issue':cid in reported_defects,'reported_judge_priority':cid in priority_judge,'raw_execution_evidence_available':False,'human_approval_validated':False,'primary_category':'DATASET_ERROR' if cid in semantic_changes else 'HARNESS_ERROR' if cid in point_cases else 'REVIEW_REQUIRED','changes':reasons or ['Schema/evidence provenance strengthening only; original question and expected arithmetic preserved.']}
    changes.append({'id':cid,'query_changed':c['query']!=baseline['query'],'semantic_contract_changed':cid in semantic_changes,'before_sha256':digest(baseline),'after_sha256':digest(c),'reasons':c['audit']['changes'],'before':baseline,'after':c})
    cases.append(c)
write('oracle/cases.jsonl',''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in cases))
write('audit/changes/case_diff.json',changes)
write('audit/changes/semantic_changes.json',semantic_changes)
relevant={i['table_id'] for c in cases for i in c.get('expected_indicator_ids',[]) if i.get('table_id')}
evidence={'origin':'local_approved_catalog_static_snapshot_not_foreign_run','captured_at':'2026-10-29','not_retroactive_ragas_context':True,'tables':[r for r in master if r['TBL_ID'] in relevant],'items':[r for r in items if r['TBL_ID'] in relevant],'file_sha256':{n:hashlib.sha256((PRODUCT/'data/processed'/n).read_bytes()).hexdigest() for n in ['bok_table_master.csv','bok_items.csv','bok_classifications.csv']}}
write('audit/evidence/approved_metadata.json',evidence)
readpaths=['src/agent/bridge_api.py','src/agent/output_agent.py','src/agent/expression_tree_schema.py','src/agent/expression_tree_validator.py','src/agent/frontend/src/ChartSketchEditor.tsx','src/agent/frontend/src/workspaceDownload.ts']
write('audit/evidence/product_readonly_refs.json',{'root':str(PRODUCT),'sha256':{name:hashlib.sha256((PRODUCT/name).read_bytes()).hexdigest() for name in readpaths},'claim':'Local code reference only; not a reproduction of PC-1 commit a8eb830... failures.'})
write('audit/evidence/source_availability.json',{'checked_local_root':str(ROOT.parent/'StatBridge_전용_정량평가_규칙검증_RAGAS_120_20261028'),'files':len(json.loads((ROOT/'baseline_reference/source_hashes.json').read_text(encoding='utf-8'))['files']),'available':['dataset contracts','fixed fixtures','DA snapshots','two downloaded narrative reports'],'missing':['2026-10-29 run_manifest.json','2026-10-29 actual observations','58 scored+22 applicability JSON','Judge claim decomposition and verdict JSON','Playwright checkpoints and selected manifest','actual 40 downloads and screenshots','original human approval overlay'],'report_execution_host':r'C:\Users\<user>\Desktop\hcx_test\StatBridge-local','direct_regrade_possible':False})
print(json.dumps({'cases':len(cases),'questions_changed':0,'semantic_contract_changes':semantic_changes,'raw_runs':'not available'},ensure_ascii=False))
