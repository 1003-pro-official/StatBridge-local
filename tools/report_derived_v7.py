"""Report an explicitly selected post-patch rerun without fabricating 300/300."""
import hashlib, json, shutil, xml.etree.ElementTree as ET
from pathlib import Path
from report_derived_eval import perf, regression

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'eval'
WORKSPACE = ROOT.parent if ROOT.name == 'StatBridge-local1' else ROOT.parent.parent

def read(n): return json.loads((OUT/n).read_text(encoding='utf8'))
def write(n, v):
    (OUT/n).write_text((v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,indent=2)).rstrip()+'\n',encoding='utf8')

def scoped(summary, selected):
    result=dict(summary)
    result['unexecuted_of_300']=result.pop('unexecuted')
    result.update(selected_cases=selected,unexecuted_selected=selected-summary['total'],not_selected_of_300=300-selected)
    return result

def main():
    archive = OUT/'derived_v6_reports_20261019'
    names = ['derived_goldset_review.md','derived_evaluation_results.json','derived_failure_analysis.md','derived_patch_report.md',
             'derived_before_after_comparison.md','derived_live_evidence.json','derived_performance_report.md','derived_quality_summary.md']
    if not archive.exists():
        archive.mkdir()
        for n in names: shutil.copy2(OUT/n,archive/n)
        shutil.copy2(ROOT/'docs/derived_agent_audit.md',archive/'derived_agent_audit.md')
    before = read('derived_v6_live_api_300.json')
    eight = read('derived_v7_failed_8_verified_live.json')
    related = read('derived_v7_related_holdout_150_live.json')
    selection = read('derived_v7_selection.json')
    baseline = read('derived_v6_summary.json')
    assert eight['summary']['total'] == eight['summary']['passed'] == 8
    assert related['summary']['total'] == 150 and related['summary']['skipped'] == 0
    assert set(selection['ids']) == {r['id'] for r in related['records']}
    old_failed = {r['id'] for r in before['records'] if r['status']=='FAIL'}
    assert old_failed == {r['id'] for r in eight['records']}
    assert eight['implementation_sha256'] == related['implementation_sha256']
    assert all(hashlib.sha256((ROOT/'src/agent'/n).read_bytes()).hexdigest() == s for n,s in related['implementation_sha256'].items())
    old = {r['id']:r for r in before['records']}
    comparison = {}
    for split in ['all','dev','holdout']:
        selected = [r for r in related['records'] if split=='all' or r['split']==split]
        comparison[split] = {'n':len(selected),'before_pass':sum(old[r['id']]['status']=='PASS' for r in selected),
            'after_pass':sum(r['status']=='PASS' for r in selected),
            'regressions':[r['id'] for r in selected if old[r['id']]['status']=='PASS' and r['status']!='PASS'],
            'fixed':[r['id'] for r in selected if old[r['id']]['status']!='PASS' and r['status']=='PASS']}
    failures = [{'id':r['id'],'split':r['split'],'status':'OPEN_FAIL','detail':r.get('detail'),'error':r.get('error'),
                 'question':(r.get('planning') or {}).get('question')} for r in related['records'] if r['status']=='FAIL']
    checkouts = baseline['checkouts']
    for label,tree in [('local1',WORKSPACE/'StatBridge-local1'),('StatBridge1',WORKSPACE/'StatBridge1/StatBridge-official')]:
        checkouts[label]['targeted_latest'] = regression('derived_regression_targeted',tree/'eval')
    full = regression('derived_regression_full')
    assert full['status']=='PASS' and all(v['targeted_latest']['status']=='PASS' for v in checkouts.values())
    assert any(c.get('name') == 'test_concatenated_json_is_not_executed_and_requires_fresh_single_object'
               for c in ET.parse(OUT/'derived_regression_full.xml').getroot().findall('.//testcase')), 'Full suite must include the new patch regressions'
    result = {'version':'v7','overall_status':'PATCH_PASS_WITH_LIMITATIONS' if not failures else 'PATCH_PASS_WITH_OTHER_OPEN_FAILURES',
              'requested_8':scoped(eight['summary'],8),'related_and_holdout_150':scoped(related['summary'],150),
              'newly_selected_cases_not_executed':150,'same_questions_comparison':comparison,
              'previous_full_300':before['summary'],'previous_full_300_is_historical':True,
              'no_merged_300_score':True,'goldset_sha256':related['goldset_sha256'],
              'actual_metadata_API':baseline['actual_metadata_API'],'pre_evaluation_question_review':baseline['pre_evaluation_question_review'],
              'checkouts':checkouts,'full_regression_local1':full,'actual_provider_UI':baseline['actual_provider_UI'],
              'actual_provider_UI_scope':'v6 browser evidence; v7 planner has fresh actual GPT tests and regressions, no new browser run',
              'performance':perf(related),'failures':failures,'implementation_sha256':related['implementation_sha256'],
              'human_expert_review':'PENDING','holdout':'retrospective and inspected; user explicitly requested fixes for these failures; NOT blind',
              'limits':['The remaining 150 cases were not re-executed with the v7 implementation; do not claim 300/300.',
                        'Economic-semantic expert approval pending.', 'Native CSV file chooser not browser-tested; CSV paste and authenticated upload tested.',
                        'Separate real-provider UI E2E on second checkout not executed.', 'Logical work/cell budgets are not OS hard isolation.']}
    write('derived_evaluation_results.json',result);write('derived_v7_summary.json',result)
    resolved = '\n'.join(f'| {i} | FAIL | PASS |' for i in sorted(old_failed))
    failure_text = '\n'.join(['# 새 실패 8건 패치 결과','','동일 질문과 정답을 유지한 새 실제 GPT-5.4 실행에서 8/8 통과했습니다. 초기 패치 중간 실행의 6/8, 5/8 결과도 삭제하지 않았습니다.',
        '', '| 사례 | v6 | v7 확인 실행 |','|---|---|---|',resolved,'',
        '원인: 통화가치의 의미 가정, 이어 붙인 JSON, 기간 변경 중 수식 변조, 의미 검토에서 실제 선택과 설명 필드의 혼동.',
        '수정: 의미 미확정 질문을 clarify로 안내, Extra data JSON 오류에 한 번만 재제출 요청, 기간 전용 edit 계약으로 원자료·노드·출력 불변 검증, 의미 검토의 source_descriptions 필드 분리.',
        '모델 제안을 서버가 정답으로 바꾸지 않습니다. 변경된 수식을 거부하고 모델이 다시 제출해야 하며, 별도 의미 검토도 계속 실행합니다.',
        '',f'추가 실제 평가 150건: {related["summary"]["passed"]} 통과 / {related["summary"]["failed"]} 실패. 기존 전체 300건 결과와 혼합해 300/300으로 보고하지 않습니다.'])
    if failures:
        failure_text += '\n\n추가 평가 미해결: ' + ', '.join(f['id'] for f in failures) + '. 상세 오류는 derived_v7_related_holdout_150_live.json 참조.'
    else: failure_text += '\n\n추가 평가 150건에서도 미해결 실패 0건입니다.'
    write('derived_failure_analysis.md',failure_text)
    patch = '\n'.join(['# 새 실패 8건 공통 패치','','- 모호한 통화가치에서 CPI를 임의로 가정하지 않는 의미 확인 지침.',
        '- JSON 객체 뒤 Extra data: 도구를 실행하지 않고 한 번만 올바른 객체 재요청. 두 번째 오류는 중단.',
        '- 이전 그래프 문맥과 새 날짜를 구별하는 기간 전용 인식. 계산식·자료·스타일·코드 변경이 섞이면 기간 고정 경로로 숨기지 않음.',
        '- 기간 전용 source/node/output 계약을 독립 검사. 최대 두 번 피드백 후에도 수식이 바뀌면 원본 보존·중단.',
        '- 의미 검토의 실제 plan.sources와 설명용 source_descriptions를 구별하고 previous_plan.nodes를 직접 비교. 검토 생략 없음.',
        '',f'요청한 8건 실제 GPT 8/8, 추가 실제 평가 {related["summary"]["passed"]}/150. 전체 회귀 {full["passed"]}/{full["tests"]}, subtests {full["passed_subtests"]}.',
        '두 폴더의 최신 targeted 결과는 결과 JSON 참조. UI 변경은 없으며 v6 파일 업로드·날짜·저장 복원 브라우저 증거를 보존했습니다.',
        '질문별 ID나 수식 정답을 제품 코드에 하드코딩하지 않았습니다. 실제 API 349개 범위와 ID/분류/단위 검증을 유지합니다.'])
    write('derived_patch_report.md',patch)
    compare = ['# v6 → v7 동일 문항 비교','','| 범위 | n | v6 통과 | v7 통과 |','|---|---:|---:|---:|']
    compare += [f'| {k} | {v["n"]} | {v["before_pass"]} | {v["after_pass"]} |' for k,v in comparison.items()]
    compare += ['','150건은 전체 홀드아웃 105건 + 모호/편집 전체 70건의 합집합으로 실행 전에 선정했습니다. 이전 실행을 선택 재사용하지 않았습니다.',
                '8건 별도 확인과 150건은 서로 다른 실행이므로 합산 분모로 중복 집계하지 않습니다. 이전 전체 300건은 292/300이며 v7 미선정 150건은 미실행입니다.',
                '질문·정답 SHA 동일. 사용자 요청에 따라 실패를 보며 패치한 사후 평가이며, 블라인드 또는 미노출 홀드아웃 검증이라고 주장하지 않습니다.']
    write('derived_before_after_comparison.md','\n'.join(compare))
    p=perf(related)
    write('derived_performance_report.md','\n'.join(['# v7 실제 GPT 성능','',
        f'150건: {p["gpt_calls_total"]}회 호출, {p["tokens_total"]:,}토큰, p50 {p["latency_p50_seconds"]:.3f}초, p95 {p["latency_p95_seconds"]:.3f}초.',
        f'요청당 {p["gpt_calls_mean"]:.3f}회 / {p["tokens_mean"]:.1f}토큰. 단계별 호출·시간·입출력 토큰은 derived_evaluation_results.json의 performance.stages 참조.',
        '의미 검토는 유지했습니다. 별도 8건 확인은 14회/39,944토큰이며 150건 수치와 합산하지 않습니다. 공식 단가 미확인으로 비용 NOT_ESTIMATED.']))
    write('derived_live_evidence.json',{'v6_full_300':'derived_v6_live_api_300.json','v7_requested_8':'derived_v7_failed_8_verified_live.json',
         'intermediate_failed_runs':['derived_v7_failed_8_live.json','derived_v7_failed_8_final_live.json'],
         'v7_related_150':'derived_v7_related_holdout_150_live.json','selection':'derived_v7_selection.json',
         'metadata':'derived_api_metadata_349.json','questions':'derived_v6_api_question_review.json','UI':'derived_v6_ui_evidence.json',
         'scope':'all GPT observations actual, API metadata actual; offline/synthetic file values clearly separated'})
    previous_review=(archive/'derived_goldset_review.md').read_text(encoding='utf8')
    write('derived_goldset_review.md',previous_review+'\n\n## v7 후속 실행\n\n질문·정답 변경 없음. 실패 8건 및 사전 선정한 관련/홀드아웃 150건을 새 코드로 실제 호출했습니다. 사후 검증이며 전문가 승인 PENDING입니다.')
    summary='\n'.join(['# v7 최종 패치 결과','',
        f'새 실패 8건 실제 GPT-5.4 재평가: 8 통과 / 0 실패 / 0 미실행. 관련/홀드아웃 150건: {related["summary"]["passed"]} 통과 / {related["summary"]["failed"]} 실패 / 0 미실행.',
        f'전체 회귀 {full["passed"]}/{full["tests"]}, subtests {full["passed_subtests"]} 통과. 두 폴더 동일 코드 반영, 최신 targeted 회귀 통과.',
        '이전 전체 300건은 292/300이며 v7은 150건을 재평가했습니다. 300/300으로 보고하지 않습니다. 전문가 의미 검토·추가 UI 범위 제한은 남습니다.',
        '상세 결과: derived_evaluation_results.json. 실패/중간 이력: derived_failure_analysis.md.'])
    write('derived_quality_summary.md',summary)
    (ROOT/'docs/derived_agent_audit.md').write_text('\n'.join(['# 동적 파생지표 v7 후속 감사','',
        '이전 Critical/High/Medium/Low 감사와 실제 API 349개 검증은 ../eval/derived_v6_reports_20261019/derived_agent_audit.md에 보존했습니다.',
        '', '| 심각도 | 문제 | 조치·상태 |','|---|---|---|',
        '| High | 기간만 변경할 때 원래 계산식 변조 | 불변 edit 계약·재제출 검증, 실제 8건 확인 PASS |',
        '| High | 의미 검토에서 원자료 선택과 설명을 혼동 | source_descriptions 분리·이전 DAG 직접 비교, 별도 검토 유지 |',
        '| Medium | 의미 미확정 통화가치를 CPI로 추정 | 먼저 의미 확인 지침, 실제 확인 PASS |',
        '| Medium | 이어 붙인 JSON 객체 | 도구 실행 전 한 번만 재제출, 반복 오류 중단·회귀 PASS |',
        '| Medium | 전문가 미승인/사후 홀드아웃 | LIMITATION, 블라인드로 보고하지 않음 |',
        '| Low | v7 미선정 150개 실제 모델 미실행 | 이전 전체 결과 보존, 300/300 주장 금지 |','',summary])+'\n',encoding='utf8')
    print(json.dumps({'requested_8':eight['summary']['passed'],'related_150':related['summary']['passed'],'full_regression':full['passed'],'failures':len(failures)}))

if __name__=='__main__': main()
