"""Run actual API query-only evaluation; publish Markdown only on complete success."""
from pathlib import Path
from collections import Counter
import argparse
import importlib.util
import json


def save_result(output_dir,result,audit):
    summary=result['summary'];cases=result['cases']
    name='scores.json' if summary['passed']==36 and summary['cases']==36 and not summary['failed'] else 'diagnostic_scores.json'
    (output_dir/name).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    if name!='scores.json':
        print('DIAGNOSTIC ONLY: final report requires 36/36',flush=True);return
    lines=['# 네 표 요청 증강셋 최종 검증','', '**36/36 통과 (100%)**','',
      '## 질문 설계와 직접 검수','',
      '- v3 원본 1104문항은 변경하지 않았다. 별도 조합 12개 × 표현 3개 = 36문항, 서로 다른 표 48개를 다룬다.',
      '- 문장형, 번호 목록형, 표 ID를 제목 앞에 둔 역순 목록형이다. 모든 문항은 서로 다른 네 표의 대표 분류를 한 계열씩 요청한다.',
      '- 36개 질문 원문을 직접 읽고 제목 전체·동명 표 ID·네 표/네 계열·기간 미지정·주기 보존을 대조했다. 정본 메타데이터 전수 검사 오류 0건.',
      '- 제목이 같은 표도 ID로 명확하게 구분한다. 월/분기/연간이 섞인 요청은 각 표의 원래 주기를 유지하며 독립적으로 조회한다.',
      '- 공개 dev / ai-assisted / human_approved=false. 카탈로그 기반 구조 회귀 검증이며 자유 자연어 일반화 성능 또는 사람의 승인으로 표시하지 않는다.','',
      '## 패치 내용','',
      '- 표 ID가 제목 앞/뒤에 있어도 해당 표에만 연결하고 다음 표 ID를 현재 표의 조건으로 오인하지 않도록 수정했다.',
      '- 정확한 표 ID와 전체 제목이 명시된 요청은 따옴표나 괄호가 없는 제목도 정본 참조로 해석한다.',
      '- 제목과 ID가 어긋나거나 알 수 없는 ID이면 임의의 표를 선택하지 않는다.',
      '- 별도 증강 생성기·전수 검증기·API 종료 로그·정확한 채점·36/36 성공 시에만 저장하는 보고서 경로를 추가했다.',
      '- 골드와 통과 기준은 고정한 상태에서 런타임을 패치했다. API에는 질문만 전달하고 전체 추론 종료 후 채점한다.','',
      '## 검증 범위와 결과','',
      '- 실제 FastAPI TestClient POST /api/query(query, execute=false)의 HTTP 반환 직후 종료 로그를 저장한다.',
      '- HTTP/Agent/API 상태, 정확한 네 표/네 계열 및 API가 반환한 네 표 목록, 항목·분류·기관·주기·기간·exact params, 기간 입력 대기 경계를 모두 확인한다.',
      '- 수치 조회와 출력 생성에는 실행 금지 가드를 설치했다. 숫자·CSV·그래프·수정이 편집은 검증 범위가 아니다.',
      f"- 수치 호출 {summary['numeric_calls']}건, 출력 호출 {summary['output_calls']}건, 문항 시간 합계 {summary['total_seconds']}초.",'',
      '## 전체 질문과 결과','']
    for c in cases:
        lines += [f"### {c['id']}",'',f"> {c['query']}",'',
          f"- 결과: PASS / Agent {c['actual_agent_status']} / API {c['actual_api_status']}",
          f"- 정답 표: {', '.join(c['expected_table_ids'])}",
          f"- 종료 로그: [{c['id']}.json]({c['id']}.json)",'',
          '```json',json.dumps({'checks':c['checks'],'expected_plans':c['expected_plans'],'actual_plans':c['actual_plans']},ensure_ascii=False,indent=2),'```','']
    lines += ['## 실행 환경','', '```json',json.dumps(result['environment'],ensure_ascii=False,indent=2),'```','',
      '재현: .venv/Scripts/python.exe eval/reporter-table-discovery-30/v3-four-tables/scripts/evaluate_runtime.py',
      '증거: scores.json / endpoint_logs.jsonl / gold_audit.json / environment.json. 실패 실행은 진단 JSON만 보존한다.','']
    (output_dir/'REPORT.md').write_text('\n'.join(lines),encoding='utf8')
    print('REPORT',output_dir/'REPORT.md',flush=True)


def audit_tables(cases):
    return sorted({tid for c in cases if c['kind'] in {'four_tables'} for tid in c['anchor_table_ids']})


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
    OUT=args.output_dir or ROOT/'evaluation_runs'/('reporter_four_tables_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    OUT.mkdir(parents=True,exist_ok=False)
    GOLD=ROOT/'eval/reporter-table-discovery-30/v3-four-tables/questions.jsonl'
    manifest=json.loads((GOLD.parent/'manifest.json').read_text(encoding='utf8'))
    spec=importlib.util.spec_from_file_location('expanded_gold_audit',GOLD.parent/'scripts/validate.py')
    validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
    audit_cases=[json.loads(line) for line in GOLD.read_text(encoding='utf8').splitlines()]
    catalog=json.loads((ROOT/'src/agent/stat_dictionary/stat_language_dictionary.json').read_text(encoding='utf-8-sig'))
    gold_audit=validator.audit(audit_cases,catalog,manifest)
    assert gold_audit['valid'],gold_audit['errors']
    assert validator.text_sha256(GOLD)==manifest['dataset_sha256']
    assert validator.text_sha256(ROOT/'src/agent/stat_dictionary/stat_language_dictionary.json')==manifest['catalog_sha256']
    (OUT/'gold_audit.json').write_text(json.dumps(gold_audit,ensure_ascii=False,indent=2),encoding='utf8')
    del audit_cases,catalog
    queries=[{'id':x['id'],'query':x['query']} for x in [json.loads(l) for l in GOLD.read_text(encoding='utf-8').splitlines() if l]]
    (OUT/'query_only_inputs.jsonl').write_text(''.join(json.dumps(q,ensure_ascii=False)+'\n' for q in queries),encoding='utf-8')
    source_files=['src/agent/canonical_request_planner.py','src/agent/agent_runtime.py','src/agent/catalog_request_planner.py','src/agent/bridge_api.py','eval/reporter-table-discovery-30/v3-four-tables/scripts/evaluate_runtime.py','eval/reporter-table-discovery-30/v3-four-tables/scripts/build.py','eval/reporter-table-discovery-30/v3-four-tables/scripts/validate.py']
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
     returned=pred['boundary_response'].get('tables') or []
     checks['api_returned_four_tables']=len(returned)==4 and {t.get('tableId') for t in returned}==set(w['table_discovery']['expected_table_ids'])
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
