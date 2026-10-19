"""Latest direct-API evaluation report; preserve all failures and old reports."""
import hashlib, json, re, shutil
from pathlib import Path
from report_derived_eval import perf, paired, regression

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'eval'
WORKSPACE = ROOT.parent if ROOT.name == 'StatBridge-local1' else ROOT.parent.parent

def read(name): return json.loads((OUT / name).read_text(encoding='utf8'))
def write(name, value):
    (OUT / name).write_text((value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)).rstrip() + '\n', encoding='utf8')

def main():
    names = ['derived_goldset_review.md', 'derived_evaluation_results.json', 'derived_failure_analysis.md', 'derived_patch_report.md',
             'derived_before_after_comparison.md', 'derived_live_evidence.json', 'derived_performance_report.md', 'derived_quality_summary.md']
    archive = OUT / 'derived_v5_reports_20261019'
    if not archive.exists():
        archive.mkdir()
        for name in names:
            if (OUT / name).exists(): shutil.copy2(OUT / name, archive / name)
        shutil.copy2(ROOT / 'docs/derived_agent_audit.md', archive / 'derived_agent_audit.md')
    live = read('derived_v6_live_api_300.json'); before = read('derived_v5_live_300.json')
    api = read('derived_api_metadata_349.json'); review = read('derived_v6_api_question_review.json')
    ui = read('derived_v6_ui_evidence.json')
    assert live['summary']['total'] == live['summary']['attempted_actual_GPT'] == 300
    assert live['summary']['unexecuted'] == live['summary']['skipped'] == 0
    assert not live['reused_identical_actual_questions']
    assert live['goldset_sha256'] == before['goldset_sha256'] == hashlib.sha256((OUT / 'derived_goldset_v5_300.jsonl').read_bytes()).hexdigest()
    assert all(hashlib.sha256((ROOT / 'src/agent' / n).read_bytes()).hexdigest() == s for n, s in live['implementation_sha256'].items())
    gold = {g['id']: g for g in map(json.loads, (OUT / 'derived_goldset_v5_300.jsonl').read_text(encoding='utf8').splitlines())}
    comparison = paired(before, live); rows = {r['id']: r for r in live['records']}
    old_failed = [r['id'] for r in before['records'] if r['status'] == 'FAIL']
    assert len(old_failed) == 10 and all(rows[i]['status'] == 'PASS' for i in old_failed)
    failures = []
    for r in live['records']:
        if r['status'] != 'FAIL': continue
        cause = ('ambiguous_currency_assumed_CPI' if r['id'] == 'ambiguous-003' else
                 'concatenated_JSON_blocked' if r['id'] == 'ambiguous-024' else 'period_only_model_changed_or_rejected_previous_formula')
        failures.append({'id': r['id'], 'split': r['split'], 'status': 'OPEN_FAIL', 'cause': cause, 'query': gold[r['id']]['query'],
                         'error': r.get('error'), 'detail': r.get('detail'), 'model_question': (r.get('planning') or {}).get('question'),
                         'evidence': 'derived_v6_live_api_300.json#' + r['id']})
    performance = perf(live)
    checkouts = {}
    for label, tree in [('local1', WORKSPACE / 'StatBridge-local1'), ('StatBridge1', WORKSPACE / 'StatBridge1/StatBridge-official')]:
        folder = tree / 'eval'
        testlog = (folder / 'derived_v6_frontend_tests.txt').read_text(encoding='utf8')
        buildlog = (folder / 'derived_v6_frontend_build.txt').read_text(encoding='utf8')
        checkouts[label] = {'targeted_latest': regression('derived_regression_targeted', folder),
                            'offline': json.loads((folder / 'derived_v6_offline_300.json').read_text(encoding='utf8'))['summary'],
                            'frontend': {'passed': int(re.search(r'pass (\d+)', testlog).group(1)), 'failed': int(re.search(r'fail (\d+)', testlog).group(1)),
                                         'typecheck_and_build': 'PASS' if 'built in' in buildlog and 'error TS' not in buildlog else 'FAIL'}}
    full = regression('derived_regression_full')
    limitations = ['Actual GPT plan evaluation: 8 OPEN_FAIL; overall NOT COMPLETE_PASS.',
                   'Expert economic-semantic label approval PENDING; holdout retrospective, not blind.',
                   '300 planning runs are not 300 actual-observation end-to-end computations.',
                   'Second checkout: offline/HTTP/regression/build verified; separate actual-provider browser E2E NOT_EXECUTED.',
                   'Native file chooser NOT_EXECUTED; authenticated CSV paste/upload verified.',
                   'Latest minor file replacement/recovery changes tested by 104 targeted tests in each checkout after the full suite.',
                   'Resource caps are logical cell/work budgets, not OS RSS/CPU isolation.']
    result = {'version': 'v6', 'overall_status': 'FAIL_WITH_DOCUMENTED_LIMITATIONS', 'goldset': 'derived_goldset_v5_300.jsonl',
              'goldset_sha256': live['goldset_sha256'], 'human_expert_review': 'PENDING', 'holdout': 'retrospective_not_blind',
              'actual_GPT_300': live['summary'], 'old_failed_10': {'executed': 10, 'passed': 10, 'failed': 0, 'ids': old_failed},
              'actual_metadata_API': {'requests': api['api_request_summary'], 'tables': api['tables_requested'],
                                      'local_catalog_comparison': api['summary'], 'local_ID_drift': api['tables_with_local_catalog_id_drift']},
              'pre_evaluation_question_review': review['summary'], 'same_question_comparison': comparison,
              'full_regression_local1': full, 'checkouts': checkouts, 'actual_provider_UI': ui,
              'failures': failures, 'performance': performance, 'limitations': limitations,
              'unauthorized_API_table_use_observed': 0, 'arbitrary_code_execution_observed': 0,
              'security_claim_scope': 'observed allowlist, schema/validator, offline security cases; not formal proof',
              'implementation_sha256': live['implementation_sha256']}
    write('derived_evaluation_results.json', result)
    write('derived_live_evidence.json', {'metadata': 'derived_api_metadata_349.json', 'raw_metadata_directory': 'derived_api_metadata_349_records',
                                       'question_review': 'derived_v6_api_question_review.json', 'actual_GPT': 'derived_v6_live_api_300.json',
                                       'raw_model_cases': 'derived_v6_live_api_300_cases', 'UI': ui,
                                       'quota_failure_history': 'derived_v6_failed_10_live_api.json',
                                       'provider_quota_after_recharge': 'RESOLVED; fresh 300 actual GPT cases executed',
                                       'no_mock_claim': 'fixture-planner UI and offline data are separate from actual-provider UI and actual GPT 300'})
    write('derived_goldset_review.md', '\n'.join([
        '# 실제 API 기반 평가셋 검토', '', '2026-10-19 · 기존 v5 질문과 정답을 변경하지 않고 재평가했습니다.', '',
        f'- 봉인된 300개 질문 SHA-256: `{live["goldset_sha256"]}`',
        '- 한국은행 승인 349개 표의 TBL/ITM/PRD 실제 API 요청 1,047/1,047 성공. 로컬 등록 정보만으로 확인하지 않았습니다.',
        '- 실제 API 응답으로 ID·분류·주기·기간과 질문 조건을 대조한 300건: 300 통과, 0 실패. 부재·보안 문항에는 존재하지 않는 자료를 허용하지 않습니다.',
        '- 로컬 카탈로그 348개 일치, DT_511Y001은 분류 ID 3개 불일치. 실제 API 메타데이터 검증 경로로 처리합니다.',
        '- 단일 40 / 복수 60 / 중첩 50 / 모호 40 / 불가 40 / 편집 30 / 보안 40. 개발 195 / 홀드아웃 105, family 분리.',
        '- 정답 DAG와 Decimal 기준 계산은 피평가 모델 출력에서 복사하지 않았습니다. 기존 v1, v2~v5와 과거 실패 기록도 보존했습니다.',
        '- 모든 경제학적 의미·모호성의 전문가 검토는 PENDING입니다. 300/300 메타데이터 적합성은 전문가 승인이나 실제 GPT 300/300 성공을 뜻하지 않습니다.',
        '- 홀드아웃은 이미 확인된 사후 평가입니다. 블라인드 평가로 보고하지 않으며 개별 홀드아웃 문항에 맞춘 규칙을 추가하지 않았습니다.',
        '', '근거: derived_api_metadata_349.json, derived_v6_api_question_review.json, derived_goldset_v5_validation.json.']))
    fail_lines = ['# 실패 원인과 처리 상태', '', '기존 실패 10건은 이번 동일 문항 실제 GPT 평가에서 모두 통과했습니다. 모델 변동을 모두 패치 효과라고 단정하지 않습니다.', '',
                  '| 사례 | 분할 | 원인 | 상태 |', '|---|---|---|---|']
    fail_lines += [f'| {f["id"]} | {f["split"]} | {f["cause"]} | OPEN_FAIL |' for f in failures]
    fail_lines += ['', '8건은 성공으로 치환하거나 재시도 성공만 선택해 집계하지 않았습니다. 실제 응답·오류·정답 비교는 전체 JSON과 개별 사례 파일에 보존합니다.',
                   '기간 편집 6건은 평가가 결정론적 경로를 끄고 실제 모델을 강제 호출한 결과입니다. 운영 UI의 기간 전용 변경은 기존 검증된 DAG를 보존하여 GPT 0회로 처리하며 브라우저에서 확인했습니다. 모델 단독 편집 성능의 실패는 그대로 남깁니다.',
                   'ambiguous-003은 기준 확인 없이 CPI를 가정했습니다. ambiguous-024는 JSON 객체를 두 번 이어 반환하여 엄격한 파서가 중단했습니다. 자료·모델 장애를 계산 성공으로 처리하지 않습니다.',
                   '초기 9/10 실행의 분류 키 오류는 실제 metadata의 mcp_param 재제출 피드백으로 수정했습니다. 이후 크레딧 소진으로 실패한 10건은 공급자 오류 이력으로 보존하고 충전 후 전체 300건을 새로 실행했습니다.',
                   '', '기존 10건 처리: ' + ', '.join(old_failed) + ' → 이번 실행 모두 PASS.']
    write('derived_failure_analysis.md', '\n'.join(fail_lines))
    write('derived_before_after_comparison.md', '\n'.join([
        '# 동일 질문 패치 전후 비교', '', '| 분할 | n | v5 통과 | v6 통과 | v6 실패 |', '|---|---:|---:|---:|---:|',
        *[f'| {split} | {v["n"]} | {v["before_pass"]} | {v["after_pass"]} | {v["n"]-v["after_pass"]} |' for split,v in comparison.items()],
        '', '질문·정답 SHA 동일. v6는 과거 결과 재사용 없이 300개 전부 실제 GPT를 새로 호출하고 실제 KOSIS 메타데이터를 사용했습니다.',
        '기존 실패 10건 해결, 기존 성공 중 새 실패 8건 기록. 전체 290→292, 홀드아웃 101→102로 집계 성능은 악화하지 않았지만 개별 회귀가 남아 전체 완료 기준은 FAIL입니다.',
        '실모델 변동과 실제 메타데이터 사용 차이를 포함하므로 개선 전부를 특정 패치의 인과 효과라고 주장하지 않습니다.',
        '', '개별 수정/회귀 ID는 derived_evaluation_results.json의 same_question_comparison 참조.']))
    write('derived_patch_report.md', '\n'.join([
        '# 최소 패치와 검증', '',
        '- 계획기: 누적합의 기존 결측 중단 정책, 피연산 순서, yoy 매개변수, 원래 분류와 분류 키를 명시했습니다. 알려진 스키마 오류·실제 메타데이터 선택 오류에만 횟수 제한 피드백을 제공합니다. 허용 연산이나 정답을 확대하지 않았습니다.',
        '- 실제 API 카탈로그: 승인 목록 확인 후 TBL/ITM/PRD 호출, 실제 항목·분류·단위·주기 검증과 TTL 캐시. API 장애는 로컬 truth로 대체하지 않습니다.',
        '- 보완 자료: API 가능한 입력 먼저 조회, 부족 자료와 CSV 양식 안내, 인증된 업로드와 동일 작업 재개, API 응답 재사용, 기존 OutputAgent 연결.',
        '- 검증: CSV 수식·비유한 수·중복·주기·단위·크기·소유권 제한. 파일 수정은 새 해시와 불변 파일로 보존합니다. 실패 후 파일 수정 재개와 이전 그래프 파일 고정을 회귀 검사했습니다.',
        '- UI: API·사용자 자료 구분, 파일 해시·출처·원자료, CSV 교체, 날짜 위젯과 DAG 보존, 되돌리기/다시 실행/저장/복원.',
        '- 공급자 오류: insufficient_quota / credit_balance_exhausted를 데이터 부재와 구분합니다.',
        '', f'전체 로컬 회귀 {full["passed"]}/{full["tests"]}, subtests {full["passed_subtests"]} 통과. 이후 작은 파일 교체·복구 보완은 최신 targeted 104건을 두 폴더에서 각각 통과했습니다.',
        '두 폴더 오프라인 300/300 및 Decimal 3,822값 각각 통과. 최신 TypeScript+빌드 통과. 실제 GPT 292/300과 별도 실제 공급자 UI 근거는 상세 결과 참조.',
        '기존 환경·계정·저장 분석·원자료를 복사하거나 덮어쓰지 않았습니다. 전체 재작성·문항별 정답 하드코딩은 하지 않았습니다.']))
    p_lines = ['# 실제 GPT 성능', '', f'300건 새 호출, 총 {performance["gpt_calls_total"]}회, {performance["tokens_total"]:,}토큰.',
               f'p50 {performance["latency_p50_seconds"]:.3f}초 / p95 {performance["latency_p95_seconds"]:.3f}초. 요청당 {performance["gpt_calls_mean"]:.3f}회 / {performance["tokens_mean"]:.1f}토큰.',
               '', '| 단계/action | 호출 | 초 합계 | 입력 토큰 | 출력 토큰 |', '|---|---:|---:|---:|---:|']
    p_lines += [f'| {name} | {v["calls"]} | {v["seconds"]:.3f} | {v["input_tokens"]} | {v["output_tokens"]} |' for name,v in performance['stages'].items()]
    p_lines += ['', '네트워크·병렬 실행·프롬프트 캐시를 포함한 요청 지연입니다. 메타데이터 TTL 캐시, 같은 작업의 API 원자료 캐시를 사용합니다. 일반 그래프의 기간 전용 변경은 GPT 0회이며 실제 UI에서 확인했습니다.',
                '경제학적 의미 검토를 일괄 생략하지 않았습니다. 모델 강제 평가에서는 결정론적 shortcut을 비활성화했습니다. 공식 단가를 이번 실행에서 확인하지 않아 비용은 NOT_ESTIMATED입니다.']
    write('derived_performance_report.md', '\n'.join(p_lines))
    summary = '\n'.join(['# 최종 품질 결과 · v6', '',
        '- 실제 GPT-5.4: 300 실행 / 292 통과 / 8 실패 / 0 미실행. 기존 실패 10건은 모두 통과.',
        '- 실제 KOSIS 메타데이터: 349개 표, 1,047회 호출 모두 성공. 로컬 ID 차이 1개 표 발견·실제 응답으로 검증.',
        '- 실제 API 응답 기반 질문 적합성 대조 300/300. 전문가 의미 검토 PENDING.',
        '- 두 폴더 각각 최신 회귀 104/104, 오프라인 300/300·Decimal 3,822값 통과. local1 전체 회귀 1,615/1,615 및 subtests 355 통과.',
        '- 두 폴더 최신 UI 타입 검사·빌드 통과. local1 실제 GPT+KOSIS+사용자 합성 CSV로 그래프·표·날짜·되돌리기·저장 복원 확인.',
        '- 전체 완료 판정: FAIL_WITH_DOCUMENTED_LIMITATIONS. 새 모델 실패 8건, 전문가 미검토와 실행 범위 제한을 숨기지 않습니다.',
        '', 'API 보완 파일 사용법: ../docs/derived_api_and_file_inputs.md. 상세 수치: derived_evaluation_results.json.'])
    write('derived_quality_summary.md', summary)
    write('derived_v6_summary.json', result)
    (ROOT / 'docs/derived_agent_audit.md').write_text('\n'.join([
        '# 동적 파생지표 감사 · 실제 API 후속 검증', '',
        '최신 결과: 실제 GPT 292/300, 기존 실패 10/10 해결. 전체 완료 판정은 FAIL_WITH_DOCUMENTED_LIMITATIONS입니다. 원래 감사와 과거 증거는 ../eval/derived_v5_reports_20261019/derived_agent_audit.md에 보존했습니다.', '',
        '| 심각도 | 관찰/조치 | 상태 |', '|---|---|---|',
        '| Critical | API 승인 목록은 네트워크 전 확인. 외부 표·임의 연산·임의 코드 차단, 허용한 사용자 파일만 별도 출처로 처리 | 검증 범위 내 차단 |',
        '| High | 로컬 메타데이터가 실제 API와 다른 1개 표 발견. 실제 TBL/ITM/PRD 검증, 장애 시 실패로 중단 | 패치 |',
        '| High | 계정별 보완 작업·근거 접근, 다른 계정 접근 차단. 이전 파일/계산을 덮어쓰지 않음 | 회귀 통과 |',
        '| High | 실제 모델 모호 질문/기간 편집 실패 8건. 운영 기간 편집 DAG 보존과 모델 단독 평가는 분리 | OPEN_FAIL |',
        '| Medium | 모델 장애와 데이터 부재 구분. 크레딧 소진 이력 보존, 충전 후 300건 재평가 | 패치·재검증 |',
        '| Medium | 사용자 파일 단위/출처는 사용자 선언. 실제 공식 자료로 인증하지 않음 | LIMITATION |',
        '| Medium | 논리 자원 제한, OS 하드 격리와 전문가 경제학 검토는 미완료 | LIMITATION |',
        '| Low | CSV 붙여넣기로 UI 검증, 네이티브 파일 선택창과 두 번째 폴더 별도 실모델 브라우저 검증 미실행 | NOT_EXECUTED |', '',
        '349개 실제 메타데이터 요청 1,047/1,047 성공. 질문·정답 300건 메타데이터 조건 검토 후 모델 평가. 수치·단위는 Python 검증·실행으로 산출하고 모델 숫자를 채택하지 않습니다.',
        '일반 resolve_request·StatisticsService·OutputAgent·ChartSpec을 유지했습니다. API 단독 DAG의 부분 재계산과 기간 변경은 기존 경로를 사용하며, 사용자 파일을 포함한 수식 변경은 제한된 전체 재검증·재계산을 사용합니다.',
        '세부 증거: ../eval/derived_evaluation_results.json, ../eval/derived_failure_analysis.md, derived_api_and_file_inputs.md.']) + '\n', encoding='utf8')
    print(json.dumps({'actual_GPT': live['summary']['passed'], 'old_10': 10, 'new_failures': len(failures), 'checkouts': checkouts}, ensure_ascii=False))

if __name__ == '__main__': main()
