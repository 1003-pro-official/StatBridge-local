"""Build Korean reports after execution and scoring; no model or network calls."""
import json,pathlib,shutil,hashlib,collections
A=pathlib.Path(__file__).resolve().parents[1];ROOT=A.parent
RUN=ROOT/'.local-tmp/data-accuracy-raw-rerun-20261023'
def lines(p):return [json.loads(s) for s in p.read_text(encoding='utf8').splitlines()]
def put(p,s):p.write_bytes(s.encode('utf8'))
assert json.loads((RUN/'output/completion.json').read_text())['completed']
if not (A/'execution').exists():
 (A/'execution').mkdir()
 for name in ['http.jsonl','observations.jsonl','preflight.json','completion.json','configuration.json']:
  shutil.copyfile(RUN/'output'/name,A/'execution'/name)
 shutil.copytree(RUN/'output/raw_responses',A/'execution/raw_responses')
s=json.loads((A/'scoring/summary.json').read_text(encoding='utf8'));scores=lines(A/'scoring/scores.jsonl')
gold={r['id']:r for r in lines(A/'answer_key.jsonl')};obs={r['id']:r for r in lines(A/'execution/observations.jsonl')};calls=lines(A/'execution/http.jsonl')
cell=lambda x:str(x).replace('|','\\|').replace('\n','<br>')
L=['# 데이터조회 정확도 재평가 결과','','ai-assisted · 실행 당시 공식 응답 본문 보존 · 2026-10-23','',f"**통과 {s['passed']}/20 · 미통과 {s['failed']}/20 · {s['score_percent']}점**",'','## 평가 범위와 조건','','349개 승인 표를 후보로 사용하는 데이터조회 20문항이다. 서로 다른 표 20개, 월간 12·분기 3·연간 5문항이며 정답 관측값은 58개다. 질문 앞의 한국은행 자료로는 없다. 기존 사용자 검토 정답을 유지하고 제품 코드는 e45ed41 기준으로 실행했다. 이 점수는 규칙·모델·Agent·MCP·실시간 KOSIS 조회를 포함한다. 실제 브라우저 로그인·UI 편집·다운로드 평가는 수행하지 않았다.','', '첨부한 60문항 예시는 문항별 조건·결과·근거, 실패 유형, 재현 방법, 검증 한계를 명시하는 보고서 구성에 반영했다. 그 평가의 고정 응답 재생이나 60/60 점수를 이 평가에 합치지 않는다.','', '메타데이터 전수 확인 캐시는 빈 전용 폴더에서 시작했다. 문항마다 독립 요청 1회이며 후속 답변·재시도에 정답을 사용하지 않았다. 모델·검색 호출 간격은 최소 15초다. 일부 요청은 규칙 경로만 사용한다.','', '## 정답 분리와 채점','','입력 스키마(id/query만), 질문 파일만 있는 입력 폴더, 정답 경로 읽기 차단 시험의 3개 검사를 모델 실행 전에 통과했다. 실행 후 정답 접근 시도는 0회다. 실행 프로세스 종료를 확인한 뒤 별도 네트워크 차단 채점기로 정답을 읽었다. 이 격리는 Python 감사 훅 방식이며 OS 보안 격리는 아니다.','', 'API 호출·기관/표·항목·분류·주기/기간·단위·수치 7개 모두 통과해야 최종 통과다. 누락·확인 대기·조회 오류도 미통과다. API 호출은 실제 요청과 최종 조회 성공을 함께 요구한다. 단일 계열 정답에 불필요한 계열을 더하면 미통과다. 수치는 Decimal로 비교하며 A/Y 연간 별칭은 인정한다. 확인 증거가 없어서 미통과한 항목을 서로 독립된 일곱 원인으로 해석하지 않는다.','', '## 실행 증거','','execution/raw_responses에는 이번 실행 당시 받은 KOSIS·모델·검색 응답 본문이 있다. 실행 중 저장한 요청 ID·문항 ID·인자·시각·HTTP 상태·본문 해시를 execution/http.jsonl에 연결했다. API 키와 인증 헤더는 포함하지 않았다. 본문은 HTTP 압축 해제 후 requests.Response.content 바이트이며 TLS 패킷은 아니다.','',f"실제 요청 집계: {s['actual_http_counts']}. HTTP 상태: {dict(collections.Counter((c['kind'],str(c.get('http_status',c.get('error_type')))) for c in calls))}",'', '## 문항별 요약','','| 문항 | 결과 | 미통과 항목 |','|---|---|---|']
for r in scores:L.append(f"| {r['id']} | {r['result']} | {', '.join(r['failed_checks']) or '없음'} |")
L+=['','## 문항별 결과와 채점 근거','']
for r in scores:
 e=gold[r['id']]['expected'];p=e['params'];rows=((obs[r['id']].get('result') or {}).get('execution') or {}).get('rows') or []
 L += [f"### {r['id']} · {r['result']}",'',r['query'],'','**정답 조건**','',f"- 한국은행(301) / {e['table_name']} (`{p['tblId']}`)",f"- 항목: {e['item_name']} (`{p['itmId']}`)",'- 분류: '+cell(e['classifications']),f"- 주기 {p['prdSe']}, 기간 {p['startPrdDe']}~{p['endPrdDe']}, 단위 {e['points'][0]['unit']}",'','| 채점 항목 | 판정 |','|---|---|']
 for k,v in r['checks'].items():L.append(f"| {k} | {'통과' if v else '미통과'} |")
 L+=['','**실제 결과**','',f"상태: {r['runtime_status']} / 조회: {r['execution_status']}",'- 요청하지 않은 반환 기간: '+str(sorted(set(r['observed_periods'])-set(r['expected_periods']))),'- 요청했지만 반환되지 않은 기간: '+str(sorted(set(r['expected_periods'])-set(r['observed_periods'])))]
 for p2 in r['observed_plans']:L.append('- 실제 계획: '+cell({k:p2.get(k) for k in ['table_id','table_name','item_id','classifications','frequency','start_period','end_period']}))
 if r['runtime_error']:L+=['','오류: '+r['runtime_error']]
 if r['clarification_question']:L+=['','추가 안내: '+r['clarification_question']]
 L+=['','| 정답 기간 | 정답 수치 | 최종 반환 수치 |','|---|---:|---|']
 for pt in e['points']:L.append(f"| {pt['period']} | {pt['value']} | {cell([x.get('DT') for x in rows if x.get('PRD_DE')==pt['period']])} |")
 L+=['','| 실행 요청 | HTTP | 응답 요약 | 이번 실행 원문 |','|---|---|---|---|']
 for c in [c for c in calls if c['case_id']==r['id']]:
  link='[본문](execution/'+c['response_file']+')' if c.get('response_file') else '응답 미수신'
  L.append(f"| {c['request_id']} / {cell(c['params'].get('tblId',c['path']))} | {c.get('http_status',c.get('error_type'))} | {cell(c.get('provider_result','모델·검색 응답'))} | {link} |")
 L+=['','위 계획과 최종 반환값, 해당 문항의 실제 응답 본문이 판정 근거다. 원문에 중간 조회 성공값이 있어도 최종 실행이 오류로 끝나 행을 반환하지 않았다면 최종 성공으로 인정하지 않는다.','']
put(A/'문항별 결과 및 채점 근거.md','\n'.join(L))
P=[r for r in scores if r['failed_checks']==['주기·기간']];E=[r for r in scores if r['execution_status']=='error'];W=[r for r in scores if r['runtime_status']=='need_details']
D=['# 재평가 결과 상세 설명','',f"이번 결과는 {s['passed']}/20 통과, {s['failed']}/20 미통과다. 이전 실행의 25점과 이번 결과는 별도 실행 기록이다.",'','## 기간 오류','','기간만 미통과한 문항: '+', '.join(r['id'] for r in P)+'.','질문 자체의 기간이 원자료에 없는 문제가 아니다. 요청한 2024년 1~3월 대신 1~12월을 반환하면 요청한 세 달이 맞아도 나머지 아홉 달 때문에 미통과다. 아래 값은 이번 실행 기록이다.','']
for r in P:D.append(f"- {r['id']}: 추가 {sorted(set(r['observed_periods'])-set(r['expected_periods']))}, 누락 {sorted(set(r['expected_periods'])-set(r['observed_periods']))}")
D+=['','## 표 선택과 조회 실패','','선택 오류와 API 조회 실패는 동시에 발생할 수 있다. HTTP 200이어도 KOSIS 본문 오류 30은 해당 조건의 데이터 부재다. 표 전체가 없거나 통신 장애라는 뜻은 아니다.']
for r in E:D+=['',f"### {r['id']}",r['query'],str(r['runtime_error']),f"정답 표 {r['expected_table']}; 선택 표 {[p['table_id'] for p in r['observed_plans']]}"]
D+=['','03·04번에서 수신금리를 추가했다면 요청 범위 오류다. 추가한 분류 조합이 오류 30을 받았다면 실제 조회도 실패한 것이다. 이번 문항별 원문 표에서 성공한 가계대출 응답과 실패한 다른 계열을 함께 확인할 수 있다. 배치의 한 요청이 실패하면 최종 관측 행을 반환하지 않는 코드 경로가 있어 중간 성공과 최종 성공을 구분한다.','', '## 확인 질문과 메타데이터 대기','','추가 안내 문항: '+', '.join(r['id'] for r in W)+'.']
for r in W:D+=['',r['id']+': '+str(r['clarification_question'])]
D+=['','공식 분류명의 합계가 파생계산 판별에 걸리면 전체 메타데이터 확인을 요구하는 경로로 들어갈 수 있다. 빈 확인 캐시에서 대기를 반환한 경우 원자료 부재나 HCX-003의 오답으로 단정하지 않는다. 문항별 모델 호출 기록을 확인해야 한다. 60문항 예시의 E12·E13은 조건이 부족해 확인 질문이 정답인 경우지만, 여기서는 조회 조건이 주어졌으므로 대기만 반환하면 미통과다.','', '## 지역 조건 누락과 불필요한 계열 추가','','07번의 부산 가계대출 정답은 DT_151Y003이다. DT_151Y002를 선택하면 지역 조건을 충족하지 못한다. 10번에서 원계열과 계절조정 계열을 함께 반환하면 필요한 표를 포함했더라도 불필요한 계열이 추가된 것이다. 전자는 다른 표로 대체한 오류이고 후자는 정답에 다른 계열을 섞은 오류다. 이번 실제 선택은 문항별 보고서에서 확인한다.','', '## 증거 보완과 해석의 한계','','이전 실행은 KOSIS 응답 전체를 저장하지 않았다. 이번 실행은 수신 즉시 원문을 저장했고 최종 반환 수치가 실제 공식 응답에 포함되는지도 오프라인으로 검증한다. 정답의 독립 검증용 응답은 별도 gold_verification 폴더에 두고 실행 증거와 혼용하지 않는다.','', '이 평가는 349개 전부의 정확도나 특정 LLM 단독 지능 점수가 아니다. 20문항의 제품 조회 흐름 평가다. 규칙·기간 파서·캐시 준비·외부 서비스 상태까지 영향을 준다. 실제 UI 평가와 다운로드 파일 검증은 이번 범위에 없다. 검토된 개발 문항이므로 미공개 블라인드 일반화 성능으로 주장하지 않는다.','']
put(A/'결과 상세 설명.md','\n'.join(D))
G='''# 재평가 자료 안내

질문·정답과 이전 실행은 구분하여 보존했다. 이 폴더는 새 실행 결과이며 로컬 자료다.

- questions.jsonl / questions.txt: 모델 입력 질문 20개
- answer_key.jsonl: 실행 종료 후 채점기에만 제공한 고정 정답
- execution/: 새 실행의 모델 출력·호출 로그·검사 기록·응답 원문
- scoring/: 7개 항목 판정 및 점수
- gold_verification/: 정답 조건을 별도로 호출한 공식 자료 검증
- run_manifest.json: 제품 소스·질문·정답 고정 해시와 실행 조건
- checksums.json: 이 폴더의 실제 파일 바이트 해시

## 오프라인 검증

프로젝트 루트에서 실행한다.

```powershell
.venv/Scripts/python.exe "데이터 조회 평가 재평가/scripts/verify_evidence.py"
.venv/Scripts/python.exe "데이터 조회 평가 재평가/scripts/verify_official.py" --evidence "데이터 조회 평가 재평가/gold_verification"
```

같은 실행의 재채점:

```powershell
.venv/Scripts/python.exe "데이터 조회 평가 재평가/scripts/score_saved.py" --output ".local-tmp/raw-rerun-rescore-new"
```

새 모델 실행은 키·349개 메타데이터·제품 의존성이 준비된 환경에서 run_model.py --run-dir 새경로로 수행한다. 실행 프로세스가 정상 종료한 후 score_saved.py로 채점한다. 새 실행 결과는 라이브 API·모델 변화에 따라 달라질 수 있다.

## 피드백 반영

1. 질문·정답·관측의 실제 해시를 LF 파일 바이트 기준으로 통일했다.
2. 실행 당시 KOSIS 응답과 모델 응답을 본문 바이트 그대로 보존했다.
3. 요청 인자·시각·상태·문항 ID·응답 해시를 함께 저장했다.
4. 채점 및 증거 검증 스크립트를 제공했다.
5. 60문항 예시처럼 문항별 기대 조건·실제 결과·실패 근거·검증 범위를 명시했다.

이번에는 제품 코드 변경이 없어 전체 pytest와 프런트엔드 빌드를 다시 실행하지 않았다. 이전 전체 pytest는 완료되지 않았으며 이를 통과로 기재하지 않는다. 이번 검증은 응답 저장·비밀키 제외 시험, 파일 해시, 실제 응답과 최종 행 연결, 20문항 재채점, 정답 공식 응답 대조에 집중했다. ai-assisted.
'''
put(A/'읽어주세요.md',G)
manifest=json.loads((A/'run_manifest.json').read_text(encoding='utf8'))
for p,h in manifest['source_hashes'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
checks={p.relative_to(A).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in A.rglob('*') if p.is_file() and p.name!='checksums.json' and '__pycache__' not in p.parts}
put(A/'checksums.json',json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':s['passed'],'failed':s['failed'],'period_only':len(P),'query_errors':len(E),'pending':len(W),'files':len(checks)},ensure_ascii=False))
