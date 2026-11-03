"""Finalize only the separate vNext package. Never write to product or original dataset."""
from pathlib import Path
import json,hashlib,subprocess,sys,zipfile,re,importlib.metadata
ROOT=Path(__file__).resolve().parents[1]
def write(p,v):
    f=ROOT/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(b):return hashlib.sha256(b).hexdigest()
old=ROOT/'validation';historical=ROOT/'baseline_reference/v1_validation'
assert old.resolve().is_relative_to(ROOT.resolve()) and historical.resolve().is_relative_to(ROOT.resolve())
if old.is_dir() and not historical.exists():old.rename(historical)
write('docs/관측값_스키마.md','''# Reviewed 관측 스키마

실행 모델에는 질문·시나리오만 전달하고 정답/fixture state를 관측값으로 복사하지 않는다. 아래 회귀 테스트는 합성이며 제품 결과로 제출할 수 없다.

공통 JSONL: id, run_id, run_status, attempt, observed_at, checkout, commit, dirty_diff_sha256, model_config, response_text. 완료 상태는 completed, 실패는 product_failure/provider_error/metadata_verifying/evaluator_error/not_executed를 구분한다. product_failure는 failure_capture가 실제 product_failure_observation 캡처에 결합되어야 하며 문자열 상태만으로 제품 오류를 확정하지 않는다.

캡처 참조는 {path, sha256}. path는 --artifacts 아래 상대 경로이며 oracle/fixtures/baseline_reference/reports를 증거로 허용하지 않는다. 실제 캡처 JSON은 {case_id,run_id,origin,captured_at,payload}이며 해당 실행/문항과 해시가 일치해야 한다. 화면 캡처 이미지 자체는 별도 파일로 연결해 보존한다. 이 스키마는 collector 출력 계약이지 자동 실행기 구현이 아니다.

QT: label은 규칙 검사 입력, predicted_query_type과 classification_scope(component_function/actual_api_route)는 분류 지표 입력이다. 실제 관측 없이 gold label을 복사하지 않는다.

CQ: clarification_required, executed, query_resolved, semantic_review. 사람 의미 검토에는 actor_type=human, reviewer, approved_at, response_sha256, human_reviewed=true, reason, target_correct, conditions_preserved가 필요하다.

DA: sources, rows, table_rows. sources={org_id,table_id,item_id,classifications,frequency}; rows={period,value,unit}. 실제 UI 표가 없으면 table_rows를 원자료로 채우지 않는다.

D: calculation_input_series, display_only_series, calculation_sources, rows, observed_source_rows(alias→period:value). 정의만 된 미사용 계열을 계산 필수 입력으로 강제하지 않는다. 실제 입력 수치도 fixture와 대조한다. 조회된 전체 sources는 진단용이며 calculation_sources와 구분한다.

E/F: snapshots.initial_query(origin=initial_query_snapshot,sequence=1), snapshots.fixture_ready(origin=fixture_ready_snapshot,sequence>1). 각각 payload.state가 필요하다. checkpoints=[{step,state,capture}], 캡처 origin=ui_checkpoint, 최상위 step와 payload.state가 관측 step/state와 같아야 한다. 초기 복원 정답은 실제 최초 조회 상태로 해석한다. 고정 fixture 준비 상태를 제품의 초기 스냅샷에 주입하지 않는다.

E28/E39/F27: rendered_points=[{step,alias,period,color,visible,marker_size_px,position_matches,within_plot,occluded,capture}]. capture origin=rendered_point_observation, payload는 capture를 뺀 실제 측정 행과 일치해야 한다. size=0, 위치 불일치, 가림은 실패다.

F downloads=[{ordinal,step,format,path,sha256,actual_revision,screen_revision,capture_id,independent_artifact_review}]. 실제 파일과 동시점 화면을 보존한다. 검토에는 artifact_sha256/reference_state_sha256/actor_type/method/matches가 필요하다. PNG/PDF는 actor_type=human, approval=APPROVED, reviewer, approved_at 필수. AI는 승인자가 아니다. SVG는 method=svg_attribute_and_render_review 및 해당 문항 component_results를 모두 bool로 기록한다. CSV/XLSX는 decoded_numeric_compare의 실제 파일 수치 대조 결과를 기록한다. initial_query_snapshot을 참조하는 다운로드의 reference hash는 실제 초기 상태를 해석한 후 계산한다.

RAGAS: response_capture(origin=product_response,payload.response_text), assertion_count, response_kind, evidence_contexts=[{capture,selector,text}]. context origin은 retrieval_trace/official_api_response/executed_calculation_evidence/official_metadata_snapshot만 허용한다. selector는 /payload/에서 실제 메타데이터·값을 선택하며 question/query/summary/explanation/gold는 금지한다. text는 선택한 원문 또는 ensure_ascii=False,sort_keys=True JSON과 정확히 같아야 한다. 예시는 audit/validation/synthetic_regression에 평가기 테스트 전용으로만 있다.

실행별 models/버전/프롬프트/데이터 모드/최초 및 재시도/선택 기준/비용·시간을 manifest로 보존한다. 원 결과를 덮어쓰지 않는다. 계약 사람 승인과 PNG/PDF 승인은 서로 별개다.
''')
write('docs/RAGAS_통계도메인_판정기준.md','# Reviewed RAGAS 판정 기준\n\n최신 적용 기준·우선 사례·원 점수·미실행 사유는 ../RAGAS_AUDIT.md와 ../03_평가지표.md를 따른다. 실제 response/context는 관측값_스키마.md에 따라 같은 run/case/hash로 결합한다. 원 v1 규칙은 baseline_reference/source_hashes.json이 가리키는 원본에서 확인할 수 있다. 질문·gold·생성 설명을 사실 context로 넣지 않는다.\n')
for filename in ['oracle/authoring_manifest.json']:
    p=ROOT/filename;v=json.loads(p.read_text(encoding='utf-8-sig'));v={'original_authoring_manifest':v,'reviewed_contract_version':'2.0.0-reviewed-vNext','human_review':'REVIEW_REQUIRED','semantic_changes':['E40','F34'],'question_changes':0,'numeric_changes':0};write(filename,v) if 'original_authoring_manifest' not in json.loads(p.read_text(encoding='utf-8-sig')) else None
template=json.loads((ROOT/'results/run_manifest.template.json').read_text(encoding='utf-8-sig'))
template.update({'contract_version':'2.0.0-reviewed-vNext','actual_observations_available':False,'original_judge_scores_preserved':True,'new_judge_executed':False,'initial_snapshot_policy':'actual initial query and fixture-ready separately; never inject initial state','original_oracle_approval':None,'changed_contract_approval':None,'artifact_human_approval':None})
write('results/run_manifest.template.json',template)
subprocess.run([sys.executable,'-B',str(ROOT/'scripts/render_reviewed.py')],check=True)
subprocess.run([sys.executable,'-B',str(ROOT/'scripts/validate_reviewed.py')],check=True)
validation=json.loads((ROOT/'audit/validation/reviewed_validation.json').read_text(encoding='utf-8'))
files=[]
for p in sorted(ROOT.rglob('*')):
    if not p.is_file() or '__pycache__' in p.parts or 'matplotlib_cache' in p.parts or p.name in {'manifest.json','package_integrity.json'}:continue
    assert p.suffix.lower()!='.env' and not p.name.startswith('.env')
    if p.suffix.lower() in {'.md','.json','.jsonl','.txt','.csv'}:
        txt=p.read_text(encoding='utf-8-sig')
        assert not re.search(r'\bsk-[A-Za-z0-9_-]{24,}',txt),'Possible secret; inspect without printing value'
    files.append(p)
versions={}
for name in ['pydantic','pandas','numpy','matplotlib','plotly']:
    try:versions[name]=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:versions[name]=None
manifest={'name':'StatBridge EvalSet Reviewed vNext','version':'2.0.0-reviewed-vNext','date':'2026-10-29','cases':120,'groups':{g:20 for g in ['QT','CQ','DA','D','E','F']},'questions_changed':0,'numeric_gold_changed':0,'semantic_contract_changes':['E40','F34'],'dataset_validation':{'scope':'offline contracts and evaluator regression','checks':validation['checks'],'passed':validation['passed'],'failed':validation['failed']},'source_product_text_files_read':1292,'original_package_files_preserved':58,'local_component_defect_families':2,'local_component_related_case_ids':['E26','E28','E39','F27','F34'],'reported_product_candidate_cases':14,'confirmed_judge_error_cases':0,'human_visual_artifacts_pending':18,'human_review':'REVIEW_REQUIRED','product_evaluation_executed':False,'local_pure_component_probe_executed':True,'offline_D_engine_executed':True,'ui_e2e_executed':False,'ragas_judge_executed':False,'original_raw_run_artifacts_available':False,'historical_only':['baseline_reference/v1_validation','baseline_reference/manifest.original.json'],'dependencies':versions,'files_sha256':{p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in files},'manifest_self_hash_excluded':True,'synthetic_evaluator_test_artifacts_not_product_results':'audit/validation/synthetic_regression'}
write('manifest.json',manifest)
archive=ROOT.parent/(ROOT.name+'.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for p in files+[ROOT/'manifest.json']:z.write(p,ROOT.name+'/'+p.relative_to(ROOT).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for rel,h in manifest['files_sha256'].items():assert sha(z.read(ROOT.name+'/'+rel))==h
write('audit/validation/package_integrity.json',{'archive':archive.name,'archive_sha256':sha(archive.read_bytes()),'archive_bytes':archive.stat().st_size,'zip_integrity':'pass','all_manifest_entries_verified':len(files),'note':'This external receipt is intentionally not inside the ZIP or manifest; avoids self-referential archive hash.'})
print(json.dumps({'archive':str(archive),'files':len(files)+1,'archive_bytes':archive.stat().st_size,'validation':manifest['dataset_validation']},ensure_ascii=False))
