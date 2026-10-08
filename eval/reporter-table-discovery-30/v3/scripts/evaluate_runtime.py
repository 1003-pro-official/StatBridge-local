"""Run actual API query-only evaluation; publish Markdown only on complete success."""
from pathlib import Path
from collections import Counter
import argparse
import importlib.util
import json


def save_result(output_dir, result, audit):
    summary=result['summary'];cases=result['cases'];env=result['environment']
    if summary['failed'] or summary['passed'] != 1104 or summary['cases'] != 1104:
        (output_dir/'diagnostic_scores.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        print('DIAGNOSTIC ONLY: final Markdown requires 1104/1104',flush=True)
        return
    (output_dir/'scores.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    by_kind={kind:{'cases':len(group),'passed':sum(c['passed'] for c in group),'failed':sum(not c['passed'] for c in group)}
             for kind in sorted({c['kind'] for c in cases}) for group in [[c for c in cases if c['kind']==kind]]}
    per_table={tid:{'table_id':tid,'lanes':{}} for tid in audit_tables(cases)}
    for case in cases:
        if case['kind'] not in {'single_table','multi_table','multi_classification'}:continue
        for tid in case['anchor_table_ids']:
            lane=per_table[tid]['lanes'].setdefault(case['kind'],{'cases':0,'passed':0,'failed_ids':[]})
            lane['cases']+=1;lane['passed']+=int(case['passed'])
            if not case['passed']:lane['failed_ids'].append(case['id'])
    result['by_kind']=by_kind
    (output_dir/'scores.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    (output_dir/'table_results.json').write_text(json.dumps(per_table,ensure_ascii=False,indent=2),encoding='utf8')
    lines=['# 349개 표 단수·복수 증강 골든셋 실제 API 검증 결과','',
           f"**{summary['passed']}/{summary['cases']} 통과 ({summary['passed']/summary['cases']*100:.2f}%), 실패 {summary['failed']}건.**",'',
           '## 범위와 판정','',
           '- 실제 체크아웃 FastAPI TestClient의 POST /api/query(query, execute=false) HTTP 반환 직후 종료 로그를 남겼다.',
           '- 각 문항에 query만 전달했다. 정답 코드는 모델·검색 입력으로 전달하지 않고 전체 추론이 끝난 뒤 채점했다.',
           '- Agent/API 상태, 정답 표 집합, 항목·분류 계열 집합, 주기·기간 포함 exact API params, 역질문 선택지 및 기간 대기 경계를 비교했다.',
           '- 모든 적용 체크가 참이어야 문항 PASS다. 일부 계열 누락·추가·대체와 기간 오인은 실패로 유지한다.',
           '- 수치 조회와 출력 생성에는 실패 가드를 설치했다. 실제 숫자, CSV 값, 그래프, 수정이와 인과 해석은 평가하지 않았다.',
           '- 공개 dev / ai-assisted / human_approved=false. 카탈로그 명칭·분류로 만든 구조적 회귀셋이며 블라인드 자연어 일반화 성능이 아니다.',
           '- 원래 기자 질문 v2 30건과 증강 문항을 유형별로 분리한다. 전체 점수를 기존 v2나 v4.1 점수로 표기하지 않는다.',
           '- 표 제목 중복은 필요한 표만 ID로 구분한다. ID 없는 단수 문항과 ID가 포함된 문항은 끝부분에서 별도 집계한다.',
           '- 표 제목의 역사 연도는 표 이름의 일부다. 명시하지 않은 사용자 조회 기간으로 간주하지 않는다.',
           '- 원자료·API 키·비공개 holdout과 런타임 예측을 골드 생성에 사용하지 않았다. 정답과 채점 기준을 변경하지 않고 서비스 선택 코드를 패치했다.','',
           '## 골든셋 전수 점검','',
           f"- 전수 검사 {audit['checked_cases']}건, 오류 {audit['error_count']}건, 연도 포함 제목 주의 표시 {audit['warning_count']}건.",
           f"- 표 커버리지: {audit['coverage']}",
           '- 코드·분류명·기관·주기·기간·exact params·계열 수·문항 중복·표 커버리지·요청 문구와 정답 대응·기존 v2 보존·SHA256를 확인했다.',
           '- 이 점검은 사람의 의미 검수 승인을 대신하지 않는다. 표 대표 분류는 v2의 고정된 기본 정책을 골드에 명시한다.',
           f"- 같은 표 내 복수 분류 예외: {audit['classification_exceptions']}",
           f"- 카탈로그/API 연간 주기 표기: {audit['api_frequency_aliases']}. exact API params는 API 파라미터의 원래 코드를 기준으로 한다.",
           '- S(반기) 표 1개는 다른 주기의 표와 짝지었다. 각 계열의 원래 주기를 유지하며 공통 관측 기간이 있는 표끼리 짝을 만들었다.',
           '- 골드 1,104건: 단수 349, 표 간 비교 349, 표 내 분류 비교 348, 동명 확인 28, 기존 v2 30.','',
           '## 유형별 실행 결과','', '| 유형 | 문항 | 통과 | 실패 |', '|---|---:|---:|---:|']
    for kind,stats in by_kind.items():lines.append(f"| {kind} | {stats['cases']} | {stats['passed']} | {stats['failed']} |")
    lines+=['','## 종료 체크 집계','','| 체크 | 통과 | 적용 |','|---|---:|---:|']
    for key,count in summary['check_results'].items():lines.append(f"| {key} | {count['passed']} | {count['total']} |")
    lines += ['',f"- numeric calls={summary['numeric_calls']}, output calls={summary['output_calls']}, 문항 소요 시간 합계={summary['total_seconds']}초.",
              '- 빈 선택 집합이 정답인 no_match/clarification도 표·계열 집합 체크에 포함된다. 상태별 결과와 선택 성공 결과를 혼용하지 않는다.','',
              '## 실패 분포','']
    failures=Counter(key for c in cases for key in c['failed_checks'])
    lines += [f'- {key}: {count}건' for key,count in failures.most_common()]
    states=Counter((c['expected_agent_status'],c['actual_agent_status']) for c in cases)
    lines += ['', '기대 Agent 상태 → 실제 상태:', '']+[f'- {a} → {b}: {count}건' for (a,b),count in sorted(states.items(),key=lambda x:str(x[0]))]
    lines += ['', '## 문항별 결과', '', '| ID | 유형 | 결과 | Agent 기대 / 실제 | API 기대 / 실제 | 실패 체크 |', '|---|---|---|---|---|---|']
    for c in cases:
        lines.append(f"| [{c['id']}]({c['id']}.json) | {c['kind']} | {'PASS' if c['passed'] else 'FAIL'} | {c['expected_agent_status']} / {c['actual_agent_status']} | {c['expected_api_status']} / {c['actual_api_status']} | {', '.join(c['failed_checks']) or '-'} |")
    lines += ['', '## 349개 표별 단수·복수 결과','','| 표 ID | 단수 통과 / 문항 | 두 표 비교 통과 / 문항 | 표 내 분류 비교 통과 / 문항 |','|---|---|---|---|']
    for tid,detail in sorted(per_table.items()):
        cells=[]
        for kind in ['single_table','multi_table','multi_classification']:
            lane=detail['lanes'].get(kind)
            cells.append(f"{lane['passed']} / {lane['cases']}" if lane else '해당 없음')
        lines.append('| '+tid+' | '+' | '.join(cells)+' |')
    lines += ['', '## 전체 1104문항의 질문·정답·실제 계획','','모든 문항의 질문과 기대·실제 계획을 기록한다. 골드나 통과 조건을 바꾸지 않았다.','']
    for c in cases:
        # Include every question and observed plan in the successful report.
        lines += [f"### {c['id']}",'',f"> {c['query']}",'',f"- 결과: {'PASS' if c['passed'] else 'FAIL'} / Agent {c['actual_agent_status']} / API {c['actual_api_status']}",
                  f"- 실제 종료 기록: [{c['id']}.json]({c['id']}.json)",'',
                  '```json',json.dumps({'expected_plans':c['expected_plans'],'actual_plans':c['actual_plans'],'classification':c['classification']},ensure_ascii=False,indent=2),'```','']
    lines += ['## 재현과 증거','', '```powershell',
              '.\.venv\Scripts\python.exe eval/reporter-table-discovery-30/v3/scripts/build.py',
              '.\.venv\Scripts\python.exe eval/reporter-table-discovery-30/v3/scripts/validate.py',
              '.\.venv\Scripts\python.exe eval/reporter-table-discovery-30/v3/scripts/evaluate_runtime.py', '```','',
              '- [전수 골드 검사](gold_audit.json), [기계 판정](scores.json), [표별 결과](table_results.json), [종료 로그](endpoint_logs.jsonl), [실행 환경](environment.json).',
              '- 실행 결과는 evaluation_runs/에만 저장하며 커밋하지 않는다. 실패 여부와 관계없이 관측 결과를 보존한다.','',
              '## 실행 환경 및 미커밋 코드 해시','', '```json', json.dumps(env,ensure_ascii=False,indent=2),'```','']
    # Identify ID-assisted coverage independently from whether it passed.
    import re
    lines += ['## 명칭 기반 / ID 보조 문항 결과','', '| 유형 | ID 보조 | 문항 | 통과 |', '|---|---|---:|---:|']
    for kind in by_kind:
        for assisted in [False,True]:
            group=[c for c in cases if c['kind']==kind and bool(re.search(r'\bDT_[0-9A-Za-z]+\b',c['query']))==assisted]
            if group:lines.append(f"| {kind} | {assisted} | {len(group)} | {sum(c['passed'] for c in group)} |")
    (output_dir/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print('REPORT',output_dir/'REPORT.md',flush=True)


def audit_tables(cases):
    return sorted({tid for c in cases if c['kind'] in {'single_table','multi_table','multi_classification'} for tid in c['anchor_table_ids']})


def main():
    from pathlib import Path
    import sys,json,time,hashlib,subprocess,collections,datetime
    ROOT=Path(__file__).resolve().parents[4]
    sys.path[:0]=[str(ROOT/'src/agent'),str(ROOT/'src/backend')]
    from fastapi.testclient import TestClient
    import bridge_api as api
    parser=argparse.ArgumentParser(description='Audited 349-table API boundary evaluation; all observed passes and failures are saved.')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args()
    OUT=args.output_dir or ROOT/'evaluation_runs'/('reporter349_v3_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    OUT.mkdir(parents=True,exist_ok=False)
    GOLD=ROOT/'eval/reporter-table-discovery-30/v3/statbridge-reporter349.jsonl'
    manifest=json.loads((GOLD.parent/'dataset_manifest.json').read_text(encoding='utf8'))
    spec=importlib.util.spec_from_file_location('expanded_gold_audit',GOLD.parent/'scripts/validate.py')
    validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
    audit_cases=[json.loads(line) for line in GOLD.read_text(encoding='utf8').splitlines()]
    catalog=json.loads((ROOT/'src/agent/stat_dictionary/stat_language_dictionary.json').read_text(encoding='utf-8-sig'))
    base=[json.loads(line) for line in (GOLD.parent.parent/'v2/statbridge-reporter30.jsonl').read_text(encoding='utf8').splitlines()]
    gold_audit=validator.audit(audit_cases,catalog,manifest,base)
    assert gold_audit['valid'],gold_audit['errors']
    assert validator.text_sha256(GOLD)==manifest['dataset_sha256']
    assert validator.text_sha256(ROOT/'src/agent/stat_dictionary/stat_language_dictionary.json')==manifest['catalog_sha256']
    (OUT/'gold_audit.json').write_text(json.dumps(gold_audit,ensure_ascii=False,indent=2),encoding='utf8')
    del audit_cases,base,catalog
    queries=[{'id':x['id'],'query':x['query']} for x in [json.loads(l) for l in GOLD.read_text(encoding='utf-8').splitlines() if l]]
    (OUT/'query_only_inputs.jsonl').write_text(''.join(json.dumps(q,ensure_ascii=False)+'\n' for q in queries),encoding='utf-8')
    source_files=['src/agent/canonical_request_planner.py','src/agent/agent_runtime.py','src/agent/catalog_request_planner.py','src/agent/bridge_api.py','eval/reporter-table-discovery-30/v3/scripts/evaluate_runtime.py','eval/reporter-table-discovery-30/v3/scripts/build.py','eval/reporter-table-discovery-30/v3/scripts/validate.py']
    mode={'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in source_files},'catalog_sha256':hashlib.sha256((ROOT/'src/agent/stat_dictionary/stat_language_dictionary.json').read_bytes()).hexdigest(),'checkout':str(ROOT),'python':sys.executable,'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'dataset_sha256':hashlib.sha256(GOLD.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'ncp_configured':api.agent.ncp.configured,'classifier_model':api.agent.ncp.settings.classifier_model,'hybrid_enabled':api.agent.hybrid.enabled,'retrieval_configured':api.agent.hybrid.client.configured,'vector_exists':api.agent.hybrid.path.exists(),'jev_configured':api.agent.jev.configured,'catalog_tables':len(api.agent.tables_by_id),'execution':False,'endpoint':'POST /api/query (in-process TestClient, actual application)','started_at':datetime.datetime.now().astimezone().isoformat()}
    (OUT/'environment.json').write_text(json.dumps(mode,ensure_ascii=False,indent=2),encoding='utf-8')
    print('ENVIRONMENT',json.dumps(mode,ensure_ascii=False),flush=True)
    latest={};calls={'numeric':0,'output':0}
    original_run=api.agent.run
    original_validate=api.agent.validate_resolution
    def traced_run(*args,**kwargs):
     result=original_run(*args,**kwargs);latest['resolution']=result;return result
    def traced_validate(*args,**kwargs):
     result=original_validate(*args,**kwargs);latest['validated']=result;return result
    def numeric_guard(*args,**kwargs):
     calls['numeric']+=1;raise RuntimeError('EVALUATION_BOUNDARY: numeric execution forbidden')
    def output_guard(*args,**kwargs):
     calls['output']+=1;raise RuntimeError('EVALUATION_BOUNDARY: output generation forbidden')
    api.agent.run=traced_run;api.agent.validate_resolution=traced_validate
    api.agent.service.get_statistics=numeric_guard
    api.agent.output_agent.prepare=output_guard
    predictions=[]
    with TestClient(api.app) as client:
     for index,q in enumerate(queries,1):
      latest.clear();before=dict(calls);start=time.perf_counter()
      try:
       response=client.post('/api/query',json={'query':q['query'],'execute':False})
       body=response.json();http_status=response.status_code;error=None
      except Exception as exc:
       body={};http_status=None;error=type(exc).__name__+': '+str(exc)
      resolution=latest.get('validated') or latest.get('resolution') or {}
      plans=resolution.get('api_plans') or ([resolution['api_plan']] if resolution.get('api_plan') else [])
      record={**q,'endpoint':'POST /api/query','http_status':http_status,'agent_status':resolution.get('status'),'api_status':body.get('status'),'classification':resolution.get('classification') or {},'dictionary_query':resolution.get('dictionary_query'),'selected_table_ids':sorted({p['table_id'] for p in plans}),'api_plans':plans,'clarifications':resolution.get('clarifications') or ([resolution] if resolution.get('status')=='need_clarification' else []),'orchestration':{k:resolution.get(k) for k in ['orchestration_stage','orchestration_path']},'boundary_response':body,'numeric_calls':calls['numeric']-before['numeric'],'output_calls':calls['output']-before['output'],'duration_s':round(time.perf_counter()-start,3),'completed_at':datetime.datetime.now().astimezone().isoformat(),'error':error}
      predictions.append(record)
      (OUT/(q['id']+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
      with (OUT/'endpoint_logs.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False,default=str)+'\n')
      if index % 20 == 0 or index==len(queries):
       print(f"[{index}/{len(queries)}] ENDPOINT {q['id']} agent={record['agent_status']} api={record['api_status']} http={http_status} numeric={record['numeric_calls']} output={record['output_calls']} seconds={record['duration_s']}",flush=True)
    # Gold is loaded for scoring only after all query-only inference has finished.
    golds=[json.loads(l) for l in GOLD.read_text(encoding='utf-8').splitlines() if l]
    scored=[]
    def identity(p,gold=False):
     return (p['table_id'],p['item_id'],tuple(sorted(p['classifications'].items())))
    for gold,pred in zip(golds,predictions):
     w=gold['workflow_gold'];gplans=w['classification_and_plan']['series'];plans=pred['api_plans'];byidentity={identity(p):p for p in plans}
     actual_groups=pred['boundary_response'].get('clarifications') or []
     expected_clar=w['resolution'].get('clarification') or {}
     observed_clar=next((g for g in actual_groups if (g.get('id') or g.get('clarification_id'))==expected_clar.get('id')),None)
     checks={'http_success':pred['http_status']==200,'agent_status':pred['agent_status']==w['resolution']['agent_status'],'api_boundary_status':pred['api_status']==w['resolution']['api_status'],'table_set':set(pred['selected_table_ids'])==set(w['table_discovery']['expected_table_ids']),'series_identity_set':set(byidentity)=={identity(p) for p in gplans},'exact_api_params':len(plans)==len(gplans) and all(identity(p) in byidentity and byidentity[identity(p)]['exact_params']==p['exact_params'] for p in gplans),'numeric_not_executed':pred['numeric_calls']==0,'chart_not_generated':pred['output_calls']==0 and not pred['boundary_response'].get('chart')}
     if w['resolution']['agent_status']=='need_clarification':
      checks['clarification_options']=observed_clar is not None and {o['value'] for o in observed_clar.get('options',[])}=={o['value'] for o in expected_clar.get('options',[])}
     if w['resolution']['agent_status']=='resolved':
      selected_text=(pred['boundary_response'].get('periodSelection') or {}).get('source')=='text'
      checks['period_followup']=pred['api_status']=='need_period' and selected_text is (not w['post_discovery']['period_selection_required'])
     scored.append({'kind':gold['augmentation']['kind'],'anchor_table_ids':gold['augmentation']['anchor_table_ids'],'id':gold['id'],'query':gold['query'],'checks':checks,'passed':all(checks.values()),'failed_checks':[k for k,v in checks.items() if not v],'expected_agent_status':w['resolution']['agent_status'],'actual_agent_status':pred['agent_status'],'expected_api_status':w['resolution']['api_status'],'actual_api_status':pred['api_status'],'expected_table_ids':w['table_discovery']['expected_table_ids'],'actual_table_ids':pred['selected_table_ids'],'expected_plans':gplans,'actual_plans':plans,'duration_s':pred['duration_s'],'classification':pred['classification']})
    summary={'cases':len(scored),'passed':sum(x['passed'] for x in scored),'failed':sum(not x['passed'] for x in scored),'check_results':{key:{'passed':sum(x['checks'].get(key) is True for x in scored),'total':sum(key in x['checks'] for x in scored)} for key in sorted({k for x in scored for k in x['checks']})},'numeric_calls':calls['numeric'],'output_calls':calls['output'],'total_seconds':round(sum(x['duration_s'] for x in scored),3)}
    result={'environment':mode,'summary':summary,'cases':scored}
    save_result(OUT,result,gold_audit)
    print('SCORES',json.dumps(summary,ensure_ascii=False),flush=True)

    return 0 if summary['cases']==len(queries) and summary['passed']==len(queries) and not summary['failed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
