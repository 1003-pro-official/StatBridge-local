"""Report sealed follow-up runs, preserving failed and historical observations."""
import copy, hashlib, json, re, shutil, xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from report_derived_eval import perf, regression

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'eval'
WORKSPACE=ROOT.parent if ROOT.name=='StatBridge-local1' else ROOT.parent.parent

def read(name):
    return json.loads((OUT/name).read_text(encoding='utf8'))

def write(name, value):
    path=OUT/name
    path.write_text((value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)).rstrip()+'\n',encoding='utf8')

def gold(name):
    return {r['id']:r for r in map(json.loads,(OUT/name).read_text(encoding='utf8').splitlines())}

def main():
    archive=OUT/'derived_v1_reports_20261019'
    if not archive.exists():
        archive.mkdir()
        for name in ['derived_goldset_review.md','derived_evaluation_results.json','derived_failure_analysis.md','derived_patch_report.md','derived_before_after_comparison.md','derived_live_evidence.json','derived_performance_report.md','derived_quality_summary.md']:
            if (OUT/name).exists():shutil.copy2(OUT/name,archive/name)
        shutil.copy2(ROOT/'docs/derived_agent_audit.md',archive/'derived_agent_audit.md')
    live=read('derived_v5_live_300.json'); review=read('derived_goldset_v5_validation.json')
    before=read('derived_v2_live_300.json'); v4=read('derived_v4_live_300.json')
    oldgold=gold('derived_goldset_v2_300.jsonl'); newgold=gold('derived_goldset_v5_300.jsonl')
    offline=read('derived_v5_offline_300.json'); source=read('derived_v2_kosis_source_verification.json')
    e2e=read('derived_date_widget_followup_e2e.json')
    assert live['summary']['total']==300 and live['summary']['unexecuted']==0
    assert len(live['reused_identical_actual_questions'])==290
    assert hashlib.sha256((OUT/'derived_goldset_v5_300.jsonl').read_bytes()).hexdigest()==live['goldset_sha256']==review['v5_sha256']
    assert review['pre_evaluation_validation_errors']==[]
    byid={r['id']:r for r in live['records']}; original=read('derived_v1_final_recheck_30.json')
    original_ids={r['id'] for r in original['records']}
    assert len(set(byid)-original_ids)==270 and all(byid[i]['calls'] for i in byid)
    # Same question, same independent expected answer, same scoring rules.
    keys=['query','previous_plan','expected_plan','allowed_sources','expected_result','accepted_statuses','post_plan_probe']
    common=[i for i in newgold if all(newgold[i].get(k)==oldgold[i].get(k) for k in keys)]
    oldrows={r['id']:copy.deepcopy(r) for r in before['records']}
    rescored=[]
    for i,r in oldrows.items():
        if oldgold[i]['expected_result']=='safe_stop' and r.get('error_type')=='DerivedValidationError' and r.get('failure_type')=='validation_error':
            r['status']='PASS';rescored.append(i)
    comparison={}
    for split in ['all','dev','holdout']:
        ids=[i for i in common if split=='all' or newgold[i]['split']==split]
        comparison[split]={'n':len(ids),'before_pass_same_scoring':sum(oldrows[i]['status']=='PASS' for i in ids),'after_pass':sum(byid[i]['status']=='PASS' for i in ids),
            'fixed':[i for i in ids if oldrows[i]['status']!='PASS' and byid[i]['status']=='PASS'],
            'regressions':[i for i in ids if oldrows[i]['status']=='PASS' and byid[i]['status']!='PASS']}
    failures=[]
    for r in live['records']:
        if r['status']!='FAIL':continue
        kind=('unseen_metadata_id_blocked' if r['id']=='multiple-037' else
              'invalid_operator_parameter_blocked' if r['id']=='nested-028' else
              'unrequested_extra_output' if r['id'].startswith('multiple-') else
              'unnecessary_clarification' if r['id']=='single-018' else
              'conditional_missing_policy_not_planned' if r['id'] in ['unavailable-015','unavailable-019'] else
              'semantic_review_rejection')
        failures.append({'id':r['id'],'split':r['split'],'cause':kind,'status':'OPEN_FAIL','error':r.get('error'),
                         'detail':r.get('detail'),'question':newgold[r['id']]['query'],
                         'response':(r.get('planning') or {}).get('question'),'evidence':'derived_v5_live_300.json#'+r['id']})
    performance=perf(live)
    full=regression('derived_regression_full',WORKSPACE/'StatBridge-local1/eval')
    targeted=regression('derived_regression_targeted',WORKSPACE/'StatBridge-local1/eval')
    runtime_sha=hashlib.sha256((ROOT/'src/agent/derived_indicator_runtime.py').read_bytes()).hexdigest()
    checkouts={}
    for label,tree in [('local1',WORKSPACE/'StatBridge-local1'),('StatBridge1',WORKSPACE/'StatBridge1/StatBridge-official')]:
        folder=tree/'eval';xml=ET.parse(folder/'derived_regression_targeted.xml').getroot()
        cases=xml.findall('.//testcase');failed=sum(c.find('failure') is not None or c.find('error') is not None for c in cases)
        testlog=(folder/'derived_frontend_followup_tests.txt').read_text(encoding='utf8')
        buildlog=(folder/'derived_frontend_followup_build.txt').read_text(encoding='utf8')
        typecheck=(folder/'derived_frontend_followup_typecheck.txt').read_text(encoding='utf8')
        checkouts[label]={'targeted':{'total':len(cases),'passed':len(cases)-failed,'failed':failed},
            'offline':json.loads((folder/'derived_v5_offline_300.json').read_text(encoding='utf8'))['summary'],
            'frontend':{'tests_passed':int(re.search(r'pass (\d+)',testlog).group(1)),
                        'tests_failed':int(re.search(r'fail (\d+)',testlog).group(1)),
                        'typescript':'PASS' if not typecheck.strip() else 'CHECK_LOG',
                        'build':'PASS' if 'built in' in buildlog else 'FAIL',
                        'build_warning':'existing large bundle warning'},
            'v41_validator':'PASS' if 'VALIDATION OK' in (folder/'derived_followup_validator.txt').read_text(encoding='utf8') else 'FAIL'}
    results={'version':'followup-v5','completion':'FAIL_OPEN_MODEL_CASES_AND_EXPERT_REVIEW_LIMITATION',
        'goldset':'derived_goldset_v5_300.jsonl','goldset_sha256':live['goldset_sha256'],'catalog_review':review['status'],
        'approved_catalog_tables':349,'tables_represented':48,'expert_review':'PENDING','holdout':'retrospective, family-disjoint; NOT blind',
        'live_GPT_planning':live['summary'],'actual_record_reuse':{'unchanged_v4_records':290,'fresh_v5_questions':10,'previously_unexecuted_ids_now_executed':270,'reuses_failures_too':True},
        'offline_synthetic':offline['summary'],'actual_KOSIS_source_check':source['summary'],
        'v5_descendant_probes':Counter(r['status'] for r in review['actual_descendant_probes']),
        'historical_original_30_recheck':original['summary'],'original_regression_unavailable_011':next(r['status'] for r in original['records'] if r['id']=='unavailable-011'),
        'matched_question_comparison':comparison,'historical_baseline_guard_score_correction':rescored,
        'full_regression_main':full,'targeted_regression_main':targeted,'checkout_validation':checkouts,'e2e':e2e,'performance':performance,
        'planning_implementation_sha256':live['implementation_sha256'],'final_runtime_sha256':runtime_sha,
        'requested_metric_scope':{
            'Intent Accuracy':{'status':'PROXY_ONLY','metric':'Request Contract Accuracy','reason':'No independent human intent adjudication'},
            'Formula Semantic Accuracy':{'status':'EXPERT_REVIEW_PENDING','structural_or_numerical_formula_agreement_is_not_expert_accuracy':True},
            'Numerical Accuracy':{'status':'PASS_SYNTHETIC','Decimal_points':offline['summary']['checked_points'],'actual_KOSIS_E2E_points':20,'actual_KOSIS_E2E_max_error':'1.1365783853100E-14'},
            'Edit Consistency':{'offline_cases':30,'offline_passed':30,'actual_GPT_plan_cases':30,'actual_GPT_plan_passed':30,'actual_UI_checkouts':2},
            'Provenance Completeness':{'scope':'2 actual UI edit receipts, previous links and 300 raw model records','receipt_hash_checks':2,'all_300_live_KOSIS_computations':'NOT_EXECUTED'}},
        'limitations':['300 live requests evaluate planning, not 300 live KOSIS numerical end-to-end runs.',
                        'Source availability checks cover 58 source combinations / 48 tables, not all 349 API tables or every question interval.',
                        'Synthetic Decimal checks do not establish expert economic semantic accuracy.',
                        'The final period-only explanation patch followed the full-suite launch; targeted API tests cover that final patch.',
                        'An interrupted initial aggregate write may have left unrecorded completed API calls; recorded token counts are not a billing statement.'],
        'open_failures':failures}
    write('derived_evaluation_results.json',results)
    write('derived_live_evidence.json',{'actual_GPT_reports':['derived_v2_live_300.json','derived_v4_live_300.json','derived_v5_live_300.json','derived_v1_final_recheck_30.json'],
        'actual_KOSIS_reports':['derived_v2_kosis_source_verification.json','derived_v2_kosis_sources_round1.json','derived_goldset_v5_validation.json'],
        'raw_response_records':'derived_v4_live_300_cases/ and derived_v5_live_300_cases/',
        'live_summary':live['summary'],'record_reuse':results['actual_record_reuse'],'e2e':e2e,
        'no_scope_substitution':'Post-plan fault probes and offline numbers are synthetic. They are never real KOSIS observations.'})
    write('derived_goldset_review.md',f'''# 최종 평가셋 검토 — v5

원본 v1 300문항은 보존했습니다. 최신 실행 대상은 `derived_goldset_v5_300.jsonl`이며 SHA-256은 `{live['goldset_sha256']}`입니다.

등록된 349개 통계표는 기관 301 한국은행입니다. 실제 메타데이터의 table/item/classification ID, 주기, 공표기간과 질문의 명시한 자료를 대조했습니다. 계산 정답은 평가 대상 GPT 출력에서 복사하지 않고 작성한 DAG/독립 Decimal 검산 기준입니다. 사람 전문가 승인은 PENDING입니다.

- 구성: 단일40 / 복수60 / 중첩50 / 모호40 / 부족40 / 편집30 / 보안40. dev195 / holdout105, 계산군 단위 중복 없음.
- 실제 사용 표48개입니다. 349개 전체를 각각 평가했다는 뜻은 아닙니다.
- 보안 질문40개를 실제 자연어 요청으로 정리하고 편집30개에는 이전 그래프/DAG 맥락을 제공했습니다.
- 명확하지 않은 분류명3개에는 실제 분류 ID를 명시했습니다. 표 이름에 포함된 과거 연도와 계산 기준일을 표시기간으로 오인하지 않게 검증했습니다.
- 실제 KOSIS 58조합 검증: 48통과/10실패. 최초7개 단위 누락, 3개 조회 실패였습니다. 실패 원본과 재조회 기록을 보존했습니다.
- 실제 API 근거만 사용해 1개는 관측 가능한 하위분류로 수정했고, 9개는 단위·자료를 확정할 수 없어 계산을 멈추는 질문으로 변경했습니다. 원래 실패를 성공 조회로 바꿔 보고하지 않습니다. 상세 하위분류 탐색 결과는 validation의 actual_descendant_probes에 있습니다.
- 최종 양성 계산208개, 명확화40개, 외부자료 불가12개, 안전 중단40개입니다. 부족 범주의 일부는 조건부 결측 처리를 검증하는 계산 질문입니다.

v4와 동일한 입력·이전 DAG·독립 정답·구현 해시인 290개는 이번 작업에서 실제 GPT-5.4로 이미 실행한 PASS와 FAIL을 모두 재사용했습니다. 수정10개는 v5 검증 후 새로 실제 호출했습니다. 미실행270개 ID 전부 실제 호출 증거가 있습니다.

holdout은 사후 정리한 평가로 비공개 블라인드 성능이 아닙니다. 경제학적 의미의 전문가 승인 및 광범위한 비정형 사용자 분포 대표성은 LIMITATION입니다.
''')
    failure_text='\n'.join(f"| {x['id']} | {x['split']} | {x['cause']} | OPEN FAIL |" for x in failures)
    write('derived_failure_analysis.md',f'''# 최종 실패 분석

실제 GPT 계획 300건: {live['summary']['passed']} PASS / {live['summary']['failed']} FAIL / 0 SKIPPED / 0 미실행. 실패를 재시도 성공으로 교체하거나 정답을 모델 출력에 맞추지 않았습니다.

| 사례 | 분할 | 원인 | 상태 |
|---|---|---|---|
{failure_text}

전체 오류 메시지·사용자 질문·기대 DAG·실제 계획·토큰·원응답은 JSON 증거에 보존했습니다. 메타데이터에 제공되지 않은 ID와 잘못된 연산 인자는 서버가 차단했으나 정상 계산 계획에 실패했으므로 FAIL입니다. 보안 질문에서 서버가 위험 계획을 차단한 PASS는 모델 단독 거절과 구분합니다.

복수표4건은 요청한 최종 비율 하나 대신 중간 비율까지 출력했습니다. 조건부 누적합2건은 엔진의 결측 정책을 계획 스키마에서 표현할 수 없다고 중단했습니다. 단위 누락/조회 실패10건의 최초 API 기록은 별도 실패로 계속 남습니다.

사람 검토가 필요한 경제 의미 오류·정답 동등성 검토는 PENDING이며 자동 통과로 간주하지 않았습니다. holdout 개별 실패에 맞춘 분기나 답안 하드코딩은 추가하지 않았습니다.
''')
    write('derived_patch_report.md','''# 후속 최소 패치

- 승인 카탈로그에 없는 필수 자료는 다른 자료나 추가 질문으로 우회하지 않고 unavailable을 우선하도록 계획 지침을 보완했습니다. 기존 회귀 unavailable-011은 같은 원래 질문으로 실제 GPT 재검증 PASS입니다.
- 표시기간과 계산용 선행기간을 분리했습니다. 표 제목의 과거 연도와 재지수화 기준연도를 표시 시작일로 해석하지 않습니다. 명시한 기간과 다른 계획은 수정 피드백을 한 번 제공하고 다시 검증합니다.
- 허용 연산의 필수 인자 누락에 한해 한 번 구조 수정 기회를 제공합니다. 허용하지 않은 연산·알 수 없는 ID·자원 초과의 차단은 유지합니다.
- 중간 노드가 불필요한 출력 계열로 노출되지 않도록 계획 지침을 명확히 했으나 복수표4건은 여전히 FAIL로 남겼습니다.
- 날짜 위젯은 제출 시 실제 FormData를 읽고 입력·변경 이벤트를 동기화합니다. 잘못된 달력 날짜 및 역전된 기간을 차단합니다.
- 기간만 변경하면 서버의 결정론적 경로로 DAG를 유지해 재계산합니다. GPT 호출은 0건입니다. 이전 기간이 남는 설명도 현재 범위와 실제 DAG에서 다시 작성하고, 원 설명은 이전 불변 계산 근거에 보존합니다.
- Windows 결과 파일 교체 잠금의 재시도와 사례별 체크포인트를 추가했습니다. 원응답과 실패를 보존하고 동일 입력/답안/구현 해시일 때만 실제 기록을 재사용합니다.

두 폴더의 소스와 공유 평가 증거를 동기화하며 .env, 계정 DB, 포트 설정, 기존 저장 분석과 원자료는 복사하지 않았습니다. 최종 기간 설명 변경은 전체 회귀 실행 시작 후 이루어졌으며, 최종 API 집중 회귀89건으로 따로 검증합니다.
''')
    comparison_rows='\n'.join(f"| {s} | {v['n']} | {v['before_pass_same_scoring']} | {v['after_pass']} | {len(v['regressions'])} |" for s,v in comparison.items())
    write('derived_before_after_comparison.md',f'''# 패치 전후 비교

v2 최초 전체 실행은 258/300, 최종 v4는 288/300, 자료 적합성을 보완한 v5는 290/300입니다. 질문/정답이 달라진 문항이 있어 단순 차이를 전부 코드 개선 효과라고 해석하지 않습니다.

동일 질문·이전 그래프·독립 정답인 문항만 공통 비교했습니다. v2의 안전 질문에서 서버가 검증 오류로 차단한 사례 {rescored}는 최종과 같은 채점 규칙으로 보정했습니다. 원본 점수는 변경하지 않았습니다.

| 분할(v5 기준) | 동일 문항 수 | 이전 통과(동일 채점) | 최종 통과 | 새 회귀 |
|---|---:|---:|---:|---:|
{comparison_rows}

공통 비교의 고정·회귀 ID 목록은 derived_evaluation_results.json에 있습니다. holdout 평균 개선과 개별 새 회귀를 함께 보고합니다. v2의 분할 중복을 수정했으므로 기존 split 집계끼리 단순 비교하지 않습니다. 최종 holdout은 101/105이며 블라인드 평가가 아닙니다.

원래 30건 같은 질문 재검증은 28/30입니다. 기존 실패 unavailable-011은 PASS이나 다른 2건은 FAIL이므로 30/30으로 보고하지 않습니다. 새 최종 300문항 결과와 별도 실행입니다.
''')
    write('derived_performance_report.md',f'''# 실제 호출 성능

```json
{json.dumps(performance,ensure_ascii=False,indent=2)}
```

최종300건의 실제 기록 총합입니다. 동일290건의 지연시간은 최초 v4 실제 호출 시점 값이며 v5 파일 생성 시간으로 대체하지 않았습니다. 검색/메타데이터/계획/의미검토 단계별 비용은 stages를 참조하십시오. 최종 집계 {live['summary']['gpt_calls']}호출 / {live['summary']['total_tokens']:,}토큰입니다.

공식 단가를 이번 작업에서 확인하지 않아 금액은 NOT_ESTIMATED입니다. 초기 중단 때 저장되지 않은 동시 완료 호출이 있을 수 있어 기록 합계를 실제 청구 금액으로 해석하지 않습니다. 평가에서는 모든 질문을 실제 GPT로 보내기 위해 결정론적 단축을 끈 반면, 제품의 기간만 바꾸는 편집은 GPT 0회입니다. 경제학적 의미 검토를 속도 때문에 생략하지 않았습니다. 캐시 토큰은 공급자 실제 usage에 기록되어 있습니다.
''')
    summary=f'''# StatBridge 후속 품질 결과 — 2026-10-19

두 폴더에 패치를 반영했습니다. 기존 회귀 1건은 실제 GPT 재검증 PASS이며, 날짜 위젯의 실제 입력 적용·잘못된 기간 차단·되돌리기·복원 경로를 검증했습니다. 최종 모델 평가에 남은 실패10건으로 전체 완료 기준은 FAIL입니다.

| 검증 | 실행 | 통과 | 실패 | 미실행 |
|---|---:|---:|---:|---:|
| 최종300 실제 GPT-5.4 계획 | 300 | 290 | 10 | 0 |
| 이전30 같은 원본 질문 재검증(별도) | 30 | 28 | 2 | 0 |
| v5 오프라인 독립 수치·보안·편집 | 300 | {offline['summary']['passed']} | {offline['summary']['failed']} | 0 |
| 최초 실제 KOSIS 원자료 조합 | 58 | 48 | 10 | 0 |
| local1 집중 회귀 | {targeted.get('tests','?')} | {targeted.get('passed','?')} | {targeted.get('failed','?')} | {targeted.get('skipped','?')} |
| local1 전체 회귀 | {full.get('tests','?')} | {full.get('passed','?')} | {full.get('failed','?')} | {full.get('skipped','?')} |

전체 회귀 하위 검산 {full.get('passed_subtests',0)}건은 표의 테스트 수에 중복 합산하지 않습니다. StatBridge1의 집중 회귀·오프라인300·프론트8건·빌드 결과는 해당 폴더의 로컬 실행 로그에 보존합니다. StatBridge1 전체 회귀는 별도로 실행하지 않았습니다.

평가셋을 실행 전에 실제349개 등록 메타데이터와 비교하고 질문을 정리했습니다. 총48개 표를 포함하며349개 전부의 API 실행 검증은 아닙니다. 실제 응답에서 자료/단위를 확인하지 못한9건은 실패 이유 안내 질문으로, 1건은 관측 가능한 실제 하위분류로 수정했습니다. 최종300건은 동일290건의 이번 작업 실제 호출 기록(성공·실패 모두)과 수정10건의 새 실제 호출입니다. 이전 미실행270개 ID도 모두 실제 GPT 기록이 있습니다.

외부자료 사용이나 임의 코드 실행을 허용한 성공 경로는 관측되지 않았습니다. 모든 입력을 포괄하는 수학적 보증은 아닙니다. 메타데이터 밖 ID 제안1건과 잘못된 인자1건은 서버가 차단했습니다. 계산 정확성은 오프라인 Decimal 검산이며300건 전체 실제 KOSIS 숫자 E2E 성공으로 보고하지 않습니다.

사람 전문가 검토는 PENDING이고 holdout101/105는 사후 분리 평가입니다. 새 개별 회귀와 경제 의미 관련 실패는 failure_analysis와 results에 기록했습니다. 모든 완료 기준을 PASS로 선언하지 않습니다.

최신 실행셋: derived_goldset_v5_300.jsonl. 원응답: derived_v5_live_300.json. 질문 검토: derived_goldset_v5_validation.json. 날짜 증거: derived_date_widget_followup_e2e.json. 이전 보고서는 derived_v1_reports_20261019/에 보존했습니다.
'''
    write('derived_quality_summary.md',summary)
    old_audit=(archive/'derived_agent_audit.md').read_text(encoding='utf8')
    (ROOT/'docs/derived_agent_audit.md').write_text('''# 후속 감사 — 2026-10-19

High: 실제 계획300건 중10건 FAIL이 남아 있습니다. 원자료 선택 실패 차단, 잘못된 인자 차단, 추가 출력 및 불필요한 질문/거절을 구분해 eval/derived_failure_analysis.md에 기록했습니다.

High(수정): 날짜 위젯의 제출값·React 상태 불일치를 수정하고 기간만 바꾸는 서버 경로를 결정론적으로 처리합니다. 이전 범위가 남던 근거 설명도 현재 DAG/기간과 함께 갱신하며 이전 계산은 불변 근거로 보존합니다.

Medium: 최초 평가셋의 질문/분류/자료 적합성을 재검토해 v5를 봉인했습니다. 실제 KOSIS 응답의 단위 부재와 조회 실패는 숨기지 않고 별도로 남겼습니다. 경제 의미 전문가 승인 및 블라인드 대표성은 아직 확보되지 않았습니다.

Low(수정): Windows 결과 파일 교체 잠금으로 평가 중단이 발생해 원자적 쓰기 재시도와 사례별 체크포인트를 추가했습니다. 저장되지 않은 완료 호출의 사용량은 추정하지 않습니다.

349개 출처 경계·임의 코드 차단·소유자별 근거 접근권한에 대한 원 감사와 회귀는 아래 보존합니다. 후속 전체 성과와 한계는 eval/derived_quality_summary.md를 참조하십시오.

---

'''+old_audit,encoding='utf8')
    print(json.dumps({'live':live['summary'],'comparison':comparison,'full':full,'targeted':targeted},ensure_ascii=False))

if __name__=='__main__':main()
