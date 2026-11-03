"""Render the reviewed contracts and evidence-limited audit, never manufacture run results."""
from pathlib import Path
from html import escape
import json
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def write(p,v):
    f=ROOT/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
cases=[json.loads(l) for l in (ROOT/'oracle/cases.jsonl').read_text(encoding='utf-8').splitlines()]
by={c['id']:c for c in cases};diff=read('audit/changes/case_diff.json');source=read('audit/evidence/full_source_read_index.json')
reported=['QT21-08','QT21-10','CQ21-15','D25','D27','D38','E26','E28','E33','E39','F26','F27','F34','F37']
local={'E26','E28','E39','F27','F34'};changed={'E40','F34'}
priority=['QT21-08','QT21-10','CQ21-15','DA21-19','DA21-20']
pending=['F21','F22','F23','F25','F28','F29','F33','F35','F36','F38']
def cell(s):return str(s).replace('|','\\|').replace('\n','<br>')
def reference(c):
    e=c['expected'];g=c['group']
    if g=='QT':return e['label']+' — '+e['rationale']
    if g=='CQ':return ('확인 필요: '+e['question_target'] if e['clarification_required'] else '재질문 불필요')+'; 유지: '+', '.join(e['preserve_conditions'])
    if g=='DA':
        d=read(e['snapshot_file']);return json.dumps(e['sources'],ensure_ascii=False)+'; '+'; '.join(r['period']+': '+r['value']+' '+str(r['unit']) for r in d['rows'])
    return c['reference_text']
rows=[];audit=[]
for c in cases:
    cid=c['id'];cats=[]
    if cid in changed:cats.append('DATASET_ERROR')
    if cid in local:cats.append('PRODUCT_DEFECT: local component reproduction')
    elif cid in reported:cats.append('REVIEW_REQUIRED: reported product issue')
    if cid in priority:cats.append('EVIDENCE_GAP: Judge claims unavailable')
    if cid in pending:cats.append('REVIEW_REQUIRED: human artifact review')
    cats=cats or ['REVIEW_REQUIRED: execution evidence unavailable']
    audit.append({'id':cid,'group':c['group'],'query':c['query'],'expected_answer':reference(c),'actual_result':None,'actual_result_status':'EVIDENCE_GAP: original response/checkpoint/file unavailable','categories':cats,'expected_query_type':c['expected_query_type'],'predicted_query_type':None,'expected_indicator_ids':c['expected_indicator_ids'],'requested_operations':c['requested_operations'],'calculation_input_series':c['calculation_input_series'],'display_only_series':c['display_only_series'],'unused_defined_series':c['unused_defined_series'],'clarification_required':c['clarification_required'],'clarification_reason':c['clarification_reason'],'question_unchanged':True,'numeric_gold_unchanged':True,'local_contract_validation':'see VALIDATION_REPORT.md','evidence_links':c['evidence_links'],'patch_reason':c['audit']['changes'],'contract_patch_required':bool(cid in changed),'human_semantic_approval':'REVIEW_REQUIRED','actual_run_evidence_available':False,'original_human_approval_reported':True,'original_human_approval_verified':False,'new_judge_executed':False})
    rows.append('| '+ ' | '.join(map(cell,[cid,c['group'],c['expected_query_type'],'미관측',','.join(c['calculation_input_series']) or '해당 없음',','.join(c['display_only_series']) or '해당 없음','; '.join(cats)]))+' |')
write('audit/case_audit.json',audit)
write('audit/reported_run_inventory.json',{'evidence_level':'narrative_reports_only_not_locally_reverified','host':r'C:\Users\<user>\Desktop\hcx_test\StatBridge-local','commit':'a8eb830397c679360f02f0627be12ffd0519422d','unique_cases':120,'live_QT_CQ_DA_D':80,'fixed_replay_DA_D':40,'UI_E_F':40,'reported_UI_steps':144,'reported_downloads':40,'formats':{'csv':8,'xlsx':5,'svg':9,'png':13,'pdf':5},'reported_final_selection':{'default':'ui-full2','E29':'adapter5','F37':'adapter5','F32':'adapter6'},'selection_warning':'Preserve reported selections as provenance. No best-score reselection or regenerated original observations. Overlapping execution timings cannot establish comparative performance.'})
write('01_질의전용_120문항.md','# 질의 전용 120문항\n\n정답·평가 기준을 실행 모델에 전달하지 않는다. E/F는 runner/scenarios.json의 순서대로 실행한다.\n\n'+'\n\n'.join('### '+c['id']+'\n\n'+c['query'] for c in cases)+'\n')
write('02_질의와_정답_120문항.md','# 질의와 정답 — Reviewed vNext\n\n기계 판정의 완전한 계약은 oracle/cases.jsonl이다. E40/F34의 초기 상태는 같은 실행의 실제 최초 조회 스냅샷이다.\n\n| 지표 | 질의 | 정답 |\n|---|---|---|\n'+'\n'.join('| '+ ' | '.join(map(cell,[c['id'],c['query'],reference(c)]))+' |' for c in cases)+'\n')
write('04_정답_사람검토_120문항.md','# 정답 승인 — 120문항\n\n원 보고서의 승인 주장과 이 패치 계약의 승인은 별개다. 승인자는 계약 SHA-256, 이름, 날짜를 함께 기록한다.\n\n| ID | 상태 | 검토자 | 날짜 | 계약 해시 | 이유 |\n|---|---|---|---|---|---|\n'+'\n'.join('| '+c['id']+' | 검토 대기 | | | | |' for c in cases)+'\n')
write('EVALUATION_AUDIT.md','''# 통합 평가 정합성 감사

대상은 StatBridge/StatBridge-local1과 통합 평가 120문항(QT/CQ/DA/D/E/F 각 20개)이다. 2026-10-29에 로컬 자체 텍스트 1,292개(101,466,012 bytes)를 완독 인덱싱하고 실행 경로를 추적했다. 의존성·바이너리·비밀 파일·런타임·비공개 holdout은 제외했다. Python 430개 AST 파싱 오류는 0개였다. 세부 범위와 해시는 audit/evidence/full_source_read_index.json에 있다. 제품 소스는 변경하지 않았다.

질의 120개와 수치 정답은 그대로 보존했다. E40/F34 두 건은 fixture 준비 상태를 제품 초기 상태로 가정한 잘못된 전제를 수정했다. D25/D27/D38 원본 plan.sources는 이미 A만 요구한다. A/B를 정의했더라도 실제 수식이 A만 사용하면 B는 필수 계산 입력이 아니다. 이 세 건을 데이터셋 오류로 바꾸거나 보고서 실패를 통과로 변경하지 않았다.

원본 58개 파일과 두 보고서를 보존했다. 지정된 원본 폴더에는 10월 29일 run manifest, 실제 응답 JSON, Judge 주장 분해, Playwright checkpoint, 실제 다운로드·화면 캡처가 없다. 보고서의 실행 호스트 PC-1과 현재 로컬 체크아웃도 다르다. 따라서 새 제품 E2E, 원 RAGAS 재채점, 실제 40개 다운로드 재검증은 NOT_EXECUTED다. 보고서 수치는 보고서 기반으로만 보존한다.

| 구분 | 확인 수량 | 해석 |
|---|---:|---|
| 검토한 계약 | 120 | 코드·메타데이터·기존 fixture 기준 정합성 |
| 질문 변경 / 수치 정답 변경 | 0 / 0 | 점수 상승을 위한 변경 없음 |
| 초기 상태 전제 수정 | 2 | E40, F34 |
| 로컬 컴포넌트 재현 결함 | 2종, 관련 5문항 | E26/E39/F34 표 숨김, E28/E39/F27 점 비가시성 |
| 보고서상 제품 문제 후보 | 14문항 | 원 실행 재현 확정 수량 아님; 로컬 관련 5개 포함 |
| Judge 오류 확정 | 0 | 우선 검토 5문항은 주장·판정 원본 필요 |
| 보고서상 사람 검토 대기 | 10문항, 14파일 | 실패 문항에 포함된 4파일까지 PNG/PDF 18개 전부 승인 미확인 |

분류는 PRODUCT_DEFECT, DATASET_ERROR, DATASET_AMBIGUITY, JUDGE_ERROR, EVIDENCE_GAP, HARNESS_ERROR, REVIEW_REQUIRED를 사용한다. 하나의 문항에 데이터셋 오류와 제품 결함이 동시에 있을 수 있다(F34). 증거 부족을 곧바로 제품 실패나 Judge 오류로 확정하지 않는다.

Golden Set v4.1의 개발 50/공개 테스트 70/비공개 holdout 30은 별도의 검색·발견 벤치마크다. 공개 120과 본 통합 120은 같은 집합이 아니다. 비공개 정답은 읽거나 실행 모델에 제공하지 않았다. 검색 지표를 본 E2E·계산·Faithfulness 수치와 합산하지 않는다.

## 120문항별 감사표

계산 입력/표시 계열의 빈칸은 누락이 아니라 해당 평가 범위에 역할이 없음을 뜻한다. QT의 후보 지표군은 모든 항목 동시 조회 요구가 아니다. 모든 예측 유형은 실제 관측이 없어 미관측으로 남긴다.

| ID | 범주 | 기대 유형 | 관측 유형 | 계산 입력 | 표시 전용 | 판정·근거 수준 |
|---|---|---|---|---|---|---|
'''+ '\n'.join(rows)+'\n')
ch=['# 데이터셋 변경 이력\n\n원본 보존: baseline_reference/cases.original.jsonl 및 원본 패키지. 질문 변경 0개, D 수치·단위 변경 0개. 모든 120개 전후 JSON은 audit/changes/case_diff.json에 있다.\n\n## 의미가 바뀐 정답 2개\n\n| ID | 기존 질의 | 패치 질의 | 기존 정답 | 패치 정답 | 이유 |\n|---|---|---|---|---|---|']
for d in diff:
    if d['id'] in changed:ch.append('| '+' | '.join(map(cell,[d['id'],d['before']['query'],d['after']['query'],d['before']['reference_text'],d['after']['reference_text'],'초기 조회와 fixture 준비 상태를 분리. 실제 초기 스냅샷 미수집은 검토 대기. F34 표 독립성 결함은 면제하지 않음']))+' |')
ch.append('\n## 전체 계약 변경 목록\n\n120개 모두 provenance·유형·계열 역할·승인 계약을 추가했다. 아래 목록은 변경 이유이며 전후 전문은 JSON diff에 있다.\n\n| ID | 질의 변경 | 의미 변경 | 패치 내용 |\n|---|---|---|---|')
ch.extend('| '+' | '.join(map(cell,[d['id'],False,d['semantic_contract_changed'],'; '.join(d['reasons'])]))+' |' for d in diff)
write('DATASET_CHANGELOG.md','\n'.join(ch)+'\n')
write('CODE_FLOW.md','''# 코드 실행 경로와 평가 기준

분석 대상: C:/Users/<user>/Desktop/경진대회/StatBridge/StatBridge-local1. 전체 읽기 인덱스에 파일별 SHA-256·행 수·Python 함수 호출·JS/TS import/API 경로가 기록되어 있다. 자동 인덱싱과 주요 경로의 수동 추적을 병행했다. 비밀 .env 값과 비공개 holdout은 읽기 대상에서 제외했다.

1. Windows 시작 스크립트와 bootstrap/portable_runtime이 MCP, uvicorn bridge_api:app, Vite 프런트엔드를 준비한다. 프런트엔드 client.ts가 /api/query → /api/output → /api/output/edit를 호출하며 계정·세션·revision을 유지한다.
2. bridge_api.query는 query_conditions의 확인 질문을 파생 분류보다 먼저 처리한다. 따라서 QT21-11처럼 API가 먼저 확인 질문으로 끝난 경우 분류 함수의 결과와 실제 API 경로 관측을 구분해야 한다. 미관측을 오분류로 세지 않는다.
3. 일반 질의는 langgraph_workflow의 resolve_request → 확인 질문/미해결 또는 execute_statistics → prepare_output 순서다. 파생 질의는 분류 → 계획 → 표현식 검증 → 메타데이터·원자료 수집 → 계산 → 출력 순서이며 중간 blocked/error는 완료 응답이 아니다.
4. derived_indicator_planner.is_derived_request는 요청 연산과 공표 지표명을 구분한다. QT는 분류 전용이며 median/max-min 같은 질의의 엔진 연산 지원까지 이 지표의 정답으로 강제하지 않는다. expected_query_type과 predicted_query_type을 독립 보존하고 component_function / actual_api_route의 accuracy, precision, recall, F1, coverage를 각각 계산한다.
5. derived_indicator_runtime은 실제 inventory preflight와 expression_tree_validator를 통과한 계획을 가져온다. 실 API fetch는 prefer_local=False, allow_fallback=False 경로다. expression_tree_schema → validator의 과거 필요 구간 → DynamicExpressionExecutor가 연산 순서·시차·윈도·단위를 결정한다. D25/D27/D38의 B는 정의만 된 계열이며 원본 계획도 A만 사용한다. D32의 비율 이동평균과 D33의 이동평균 비율은 다르므로 정답을 합치지 않는다.
6. OutputAgent는 summary·display series를 만든 다음 table/chart의 출력 대상을 나눈다. 그러나 앞선 _apply_data_edits의 hidden label 필터가 이미 공통 series를 제거한다. 그래프 B 숨김이 표 B도 제거되는 현상을 직접 컴포넌트 실행으로 확인했다. 표 선택과 그래프 표시를 독립 검사한다.
7. 편집의 restore_initial은 세션의 최초 조회 초기 스냅샷을 복원한다. fixture 준비를 위해 수행한 제목·색상 편집은 초기 스냅샷을 바꾸지 않는다. E40/F34는 actual initial_query_snapshot과 fixture_ready_snapshot을 같은 실행에서 각각 수집해야 한다. 초기 상태를 fixture로 주입하지 않는다.
8. research_plotly_styles.cartesian_traces는 markers가 꺼져 있으면 marker size를 0으로 만든다. 점 색상만 지정하는 직접 명령에서 색상 저장과 크기 0을 확인했다. 자연어 명령 생성은 이번에 실행하지 않았다. 렌더된 크기·색상·위치·가림 여부를 함께 검사한다.
9. SVG/PDF는 report_export와 Matplotlib 경로, 화면 PNG는 workspaceDownload/Plotly 경로를 사용한다. 파일 존재·해시만으로 화면 일치를 승인하지 않는다. 로컬 합성 SVG probe에서는 바깥 구간 기본색을 보존했으므로 PC-1의 F26/F37 색 변경을 로컬 재현했다고 주장하지 않는다. 원 SVG의 요소·범위·색과 당시 화면이 필요하다.

DA는 현재 승인 메타데이터와 보존된 공식 스냅샷의 지표·분류·기간·단위를 검사한다. 현재 카탈로그에 SNA 기준이 있다는 사실을 과거 RAGAS context에 소급 삽입하지 않는다. 이 코드 경로 검토는 로그인·자연어 모델·실 API·브라우저 E2E의 성공 증거가 아니다.
''')
write('PRODUCT_DEFECTS.md','''# 제품 결함 및 미확정 후보

제품 소스는 수정하지 않았다. 로컬 증거: audit/evidence/local_component_probes.json, 재현 스크립트: scripts/probe_product_contracts.py. 합성 2계열·3개월 데이터로 실제 OutputAgent/렌더러를 실행했으며 모델·API·브라우저는 호출하지 않았다.

| 우선순위 | 문제 | 관련 문항 | 재현·기대·실제 | 상태 |
|---|---|---|---|---|
| P1 | 그래프 숨김이 표 선택까지 제거 | E26 E39 F34 | 두 계열 출력 후 B의 그래프 표시만 숨김. 표 A/B 유지 기대, 실제 표 A만 남음. OutputAgent 공통 _apply_data_edits에서 제거 | 로컬 컴포넌트 확정 |
| P1 | 점 색상 저장 후 화면에서 안 보임 | E28 E39 F27 | 선그래프 특정 점 색상만 지정. 색상 강조 기대, 실제 해당 색상은 있으나 marker size 전부 0 | 직접 색상 명령 기준 로컬 확정; 자연어 생성 미실행 |
| P1 | 단일 A 연산이 불필요한 확인 질문/실패 | D25 D27 D38 | 보고서 live 3건/replay 2건. 원본 gold는 이미 A만 요구. 계산 의존성·선행 메타데이터·모델 계획을 분리 확인 필요 | 보고서 기반, 원 trace 필요 |
| P2 | 요약의 지표/지역 범위 누락 | QT21-08 QT21-10 CQ21-15 | 가계신용 구성·부산+대구 합계·원계열/순환변동치 명칭 문제 주장 | 원 응답과 Judge 주장 분해 필요 |
| P2 | 강조 방식 확인 질문 누락 | E33 | 계열·시점은 질문했으나 강조 방식 슬롯 누락 주장. revision 불변과 질문 의미를 따로 검사 | 원 화면/응답 필요; gold 완화하지 않음 |
| P1 | SVG 선택 구간 밖 기본색 변형 | F26 F27 F37 | 보고서 F26 A #2563EB→#4568FF, F27 B #F97316→#FF805E 등. 로컬 합성 SVG는 기본색 보존 | 원 SVG·화면·revision 필요; 로컬 재현 미확정 |

14개 보고서 후보 중 위 로컬 재현과 연결되는 문항은 5개다. 같은 원인 여러 문항을 결함 5종으로 부풀리지 않는다. F34의 초기 상태 전제 오류를 수정해도 표 숨김 결함은 남는다. 운영 API 또는 모델이 원인인지 확인하려면 당시 commit/config, 요청·응답, plan·fetch·checkpoint·다운로드 manifest를 함께 확보하고 새 run_id로 재현해야 한다.
''')
app=[]
for group,count,known in [('QT',9,['QT21-11']),('CQ',10,[]),('D',3,['D25','D27','D38'])]:
    for i in range(count):app.append({'reported_slot':group+'-NA-'+str(i+1),'case_id':known[i] if i<len(known) else None,'case_binding':'reported' if i<len(known) else 'unknown_without_raw_json','status':'REVIEW_REQUIRED','classification':'EVIDENCE_GAP','new_judge_score':None})
write('audit/ragas_applicability.json',{'scope':'22 report-only NA slots, not reconstructed actual observations','records':app})
write('audit/ragas_regrade.json',{'original_reported':{'ragas':'0.4.3','judge':'gpt-6.1-sol','live_scored':58,'live_na':22,'live_mean':0.943350,'groups':{'QT':{'scored':11,'mean':0.818182,'na':9},'CQ':{'scored':10,'mean':0.971429,'na':10},'DA':{'scored':20,'mean':0.95,'na':0},'D':{'scored':17,'mean':1.0,'na':3}},'replay_DA_mean':0.95,'replay_D_scored':18,'replay_D_na':2,'replay_D_mean':1.0},'new_judge_executed':False,'new_score':None,'delta':None,'reason':'Actual responses, captured contexts, original claim verdicts and manifest missing','original_scores_unchanged':True,'priority_case_ids':priority})
write('RAGAS_AUDIT.md','''# RAGAS 증거와 적용성 감사

원 점수는 수정하지 않았다. 아래는 보고서가 제시한 값이며 원시 JSON으로 재계산한 값이 아니다. RAGAS 0.4.3 collections Faithfulness, Judge gpt-6.1-sol. live 58개 채점 평균 0.943350, 22개 N/A. QT 11개 평균 0.818182/NA9, CQ 10개 0.971429/NA10, DA 20개 0.95/NA0, D 17개 1.0/NA3. replay DA20개 0.95, D18개 1.0/NA2. live/replay는 합산하지 않는다.

분류 함수 QT 20/20과 API 경로 19개 일치+1개 미관측은 별개다. Faithfulness는 retrieval context가 응답 주장을 뒷받침하는지를 평가하며 query type 정답률이나 데이터 계산 정확도와 대체 관계가 아니다. CQ의 확인 필요 결정이 맞더라도 질문 대상·기존 조건 보존은 별도 의미 검토가 필요하다.

| 우선 검토 ID | 보고서의 주장 | 이번 판정 | 필요한 직접 증거 |
|---|---|---|---|
| QT21-08 | 0점; 대출·판매신용을 가계신용으로만 요약 | PRODUCT_DEFECT/JUDGE_ERROR 미확정 | 실제 응답, 원 지표 context, 주장 분해와 supported 판정 |
| QT21-10 | 0점; 부산+대구 합계를 부산으로만 요약 | PRODUCT_DEFECT/JUDGE_ERROR 미확정 | 지역별 원자료, 합계 실행 결과, 요약 주장 |
| CQ21-15 | 0.714286; 원계열/순환변동치 명칭 혼동 | 의미 검토 필요 | 실제 확인 질문/응답, 명칭 메타데이터, 주장 분해 |
| DA21-19 | live 0점; SNA2008 context 누락 가능 | EVIDENCE_GAP | 당시 DT_284Y001 메타데이터 경로·입력 context |
| DA21-20 | replay 0점; 질문에서 SNA 기준 보충 가능 | EVIDENCE_GAP/Judge 검토 | 당시 DT_284Y002 context, 질문 제외 후 주장 판정 |

현재 로컬 메타데이터의 자금순환표 경로에는 2008 SNA 기준·상세자금순환표(2018~)가 존재한다. 이는 현재 카탈로그 사실이며 과거 Judge가 이를 받았다는 증거가 아니다. 응답이 맞고 context가 빠졌다면 EVIDENCE_GAP, context가 충분한데 unsupported라면 JUDGE_ERROR 후보, context와 응답이 실제 충돌하면 PRODUCT_DEFECT 후보로 분리한다. 이번 Judge 오류 확정은 0개다.

원본 22개 NA의 경우별 응답·이유 JSON은 없다. audit/ragas_applicability.json은 보고서 수량을 22개 슬롯으로 보존하고 식별되지 않은 case_id는 null로 둔다. QT21-11 및 D25/D27/D38만 보고서 기반 연결이며 나머지 ID를 추정하지 않는다. 확인 질문 자체 무주장, 메타데이터 확인 중, 제공자 실패, 계산 미완료, Judge 오류는 서로 다른 적용 제외 사유다. NA를 0점이나 1점으로 환산하지 않는다.

scripts/export_reviewed_ragas.py는 같은 run_id/case_id의 실제 response 캡처와 API·검색·메타데이터·실제 계산 증거만 받는다. 파일 SHA-256과 payload selector를 검증하며 질문/정답/생성 설명을 context로 넣지 않는다. scripts/reviewed_evidence.py가 출처·실행 결합을 검증한다. 새 입력·Judge 버전·원 점수·재채점 점수는 별도로 보존해야 한다.

재채점 상태: NOT_EXECUTED. 변경 전 점수는 audit/ragas_regrade.json에 보고서 값으로 보존했고 변경 후 점수·차이는 null이다. 원 JSON·캡처가 없으므로 실제 주장별 supported/unsupported 판정을 생성하지 않았다. AI가 사람 시각 승인도 대신하지 않는다.
''')
review=[]
for c in cases:
    if c['group']!='F':continue
    for d in c['expected']['downloads']:
        if d['format'] in ['png','pdf']:
            review.append({'id':c['id'],'step':d['step'],'ordinal':d['ordinal'],'format':d['format'],'reported_case_status':'human_pending' if c['id'] in pending else 'mismatch','actual_file':None,'artifact_sha256':None,'screen_capture':None,'reference_state':d.get('expected_state',{'ref':d.get('expected_state_ref')}),'actor_type':None,'reviewer':None,'approved_at':None,'approval':'REVIEW_REQUIRED','matches':None,'reason':'Actual download/screenshot unavailable; do not approve from AI review'})
write('human_review/artifact_checklist.json',review)
html=['<!doctype html><meta charset="utf-8"><title>StatBridge 실제 파일 대조 검토</title><style>body{font-family:system-ui;max-width:1300px;margin:auto}section{border:1px solid #ccc;padding:16px;margin:16px 0}.row{display:grid;grid-template-columns:1fr 1fr;gap:20px}pre{white-space:pre-wrap;background:#f6f7f8;padding:10px}.missing{border:2px dashed #aaa;padding:30px}</style><h1>PNG/PDF 사람 검토: 실제 파일 미수신</h1><p>기대 상태와 실제 파일을 나란히 비교할 준비 양식입니다. 오른쪽은 미수신 표시이며 합성 화면이 아닙니다. 아직 비교·승인하지 않았습니다.</p>']
for r in review:html.append('<section><h2>'+r['id']+' / '+r['format']+' / step '+str(r['step'])+'</h2><div class="row"><div><h3>기대 상태</h3><pre>'+escape(json.dumps(r['reference_state'],ensure_ascii=False,indent=2))+'</pre></div><div><h3>실제 다운로드·동일 revision 화면</h3><div class="missing">미수신 — 비교 미실행 / 승인 대기</div><p>확인: 제목·축·단위·기간·범례·계열·구간 밖 기본색·점 크기/위치·가림·페이지 잘림. 표·CSV는 그래프 숨김과 별도 확인.</p></div></div></section>')
write('human_review/side_by_side.html',''.join(html))
write('HUMAN_REVIEW_REQUIRED.md','# 사람 검토 필요 항목\n\n보고서에서 사람 검토 대기인 10문항은 '+', '.join(pending)+'이다. 이 10개에 PNG/PDF 14개가 있으며 실패 문항 F26/F27/F34/F37의 4개를 포함하면 총 18개다. 전체 파일의 사람 승인 원자료가 없어 모두 미승인으로 보존한다.\n\n[나란히 비교 양식](human_review/side_by_side.html)과 [18개 파일 체크리스트](human_review/artifact_checklist.json)를 제공한다. 실제 파일·화면이 없어 오른쪽은 미수신 상태이며 비교 완료를 주장하지 않는다. 파일/화면 SHA-256, 동일 revision, 검토자, 승인 날짜, 일치/불일치, 근거를 입력해야 한다. AI 검토는 human 승인으로 인정하지 않는다. 하나의 파일에 확정 불일치가 있으면 다른 파일이 대기여도 문항 실패를 보존한다.\n\n120개 gold의 원 승인도 보고서 주장만 있으며 서명 manifest가 없다. 04_정답_사람검토_120문항.md에서 이름·날짜·계약 해시를 확인한다. E40/F34의 바뀐 계약은 원 승인과 별도 승인해야 한다. 이는 실행 질문을 다시 쓰거나 점수를 높이기 위한 승인이 아니다.\n\n3인 분담: 1인은 지표·단위·계산 의존성을, 1인은 화면·실제 파일을, 나머지 1인은 독립 교차 검토 및 불일치 조정을 맡는다. 본인이 작성한 변경 계약은 다른 사람이 승인한다. 검토 전에는 PASS를 부여하지 않는다.\n')
write('README.md','''# StatBridge EvalSet Reviewed vNext

원본 120문항을 보존하고 지정 local1의 코드 실행 경로에 맞춰 정합성·증거·평가 계약을 패치했다. 원본/제품 소스는 변경하지 않았다. 질문·수치 정답 변경 0개, 초기 상태 전제 수정 E40/F34 두 개다.

- EVALUATION_AUDIT.md: 120개 문항 감사표와 확인 범위
- CODE_FLOW.md: 코드 실행 경로와 평가의 연결
- DATASET_CHANGELOG.md: 전후 질문/정답 및 전체 diff
- RAGAS_AUDIT.md: 원 점수 보존, NA·context·Judge 검토
- PRODUCT_DEFECTS.md: 로컬 재현 2종과 보고서 후보 구분
- HUMAN_REVIEW_REQUIRED.md: 실제 PNG/PDF 18개 사람 검토 양식
- VALIDATION_REPORT.md: 이번 오프라인 검증의 실제 결과

현재 제품 API/자연어 모델/브라우저 E2E 및 RAGAS Judge 재실행은 하지 않았다. 로컬 순수 컴포넌트 probe와 오프라인 수식·계약·평가기 회귀 검증만 실행했다. 원 보고서에 등장하는 실제 다운로드·응답·Judge JSON은 지정 폴더에 없다. 이를 원본 고정 fixture나 합성 테스트로 대체하지 않는다.

실행 모델에는 runner/questions.jsonl과 필요한 시나리오만 전달한다. oracle·baseline_reference·보고서·정답은 전달하지 않는다. 새 관측 결과는 새 run_id로 저장한다.

```powershell
python -B scripts/validate_reviewed.py
python -B scripts/score_reviewed.py --predictions runs/NEW_RUN/observations.jsonl --artifacts runs/NEW_RUN --output runs/NEW_RUN/rules.json
python -B scripts/export_reviewed_ragas.py --predictions runs/NEW_RUN/observations.jsonl --artifacts runs/NEW_RUN --output runs/NEW_RUN/ragas_input.jsonl
```

기존 v1 생성·마감 스크립트는 잘못된 계약 덮어쓰기를 막기 위해 비활성화했다. 원 v1 검증 617건은 이번 결과가 아니며 baseline_reference 및 audit/validation의 historical 파일로만 보존한다. 공개 Golden Set v4.1 검색 벤치마크도 통합120과 별개다.
''')
write('03_평가지표.md','''# Reviewed 정량 평가 지표

QT: 함수 분류와 실제 API 경로를 분리해 accuracy/per-class precision/recall/F1/macro-F1 및 관측 coverage를 보고한다. 미관측은 실패로 임의 변환하지 않는다.

CQ: 확인 필요 결정, 확인 대상·슬롯의 의미, 기존 조건 보존, 불필요한 조회/연산 방지, revision 불변을 따로 검사한다. 의미 검토는 실제 응답 해시에 결합된 사람 판단이 필요하다.

DA: 지표·분류·기간·단위·원자료 수치와 UI 표 표시를 별도로 검사한다. 보존된 스냅샷의 일치는 현재 live API 일치나 실제 UI 성공이 아니다.

D: 계산 입력/정의만 된 계열/표시 전용 계열을 구분하고 연산 트리·과거 필요 구간·시차·이동평균·수치·단위를 검사한다. 추가로 조회한 계열을 계산 필수 입력으로 강제하지 않는다.

E/F: 같은 run의 initial_query/fixture_ready 스냅샷과 단계별 실제 capture를 보존한다. 그래프 가시성과 표 선택을 독립 검사한다. 점은 size>0·색상·위치·가림 여부를 검사한다. SVG는 선택 구간 밖 기본색·선폭·대시·범례·기간 좌표를 비교한다. PNG/PDF에는 실제 파일/동일 revision 화면과 사람 승인이 필요하다. 확정 실패가 있으면 대기 항목이 실패를 숨기지 못한다.

Faithfulness: 같은 실행에서 실제 수집된 context와 응답만 입력한다. 질문·gold·생성 설명은 사실 근거가 아니다. 무주장/확인 질문/메타데이터 대기/제공자 오류/계산 미완료/Judge 오류를 구분하며 NA는 평균 분모에서 분리한다. 원점수·새 입력 해시·새점수·모델/버전·판정 근거를 보존한다. 현재 Judge 재채점 미실행.

규칙 결과와 oracle 승인 상태를 분리한다. 규칙 일치라도 사람 승인 계약이 없으면 최종 PASS 대신 REVIEW_REQUIRED로 남긴다. 데이터셋 검증 통과를 제품 성능으로 발표하지 않는다.
''')
print(json.dumps({'rendered_cases':len(cases),'artifact_human_review_items':len(review),'reported_pending_items':sum(r['id'] in pending for r in review)},ensure_ascii=False))
