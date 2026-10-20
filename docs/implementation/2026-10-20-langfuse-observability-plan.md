# StatBridge Langfuse 기록 지점 설계 (ai-assisted)

현재 코드 조사에 따른 설계안이다. 이번 작업에서 Langfuse SDK 설치·프로젝트 연결·외부 로그 전송은 수행하지 않았다. 기존 `execution_trace.py`와 `ExecutionEvidence.tsx`는 실제 노드 경로와 편집 결과를 보여 주지만 단계별 시작/종료·소요시간·모델 사용량을 모두 계측하는 구조는 아니다.

## 한 요청을 하나의 trace로

질문, 추가 조건 답변, 편집, 파일 연결, 재계산, 내보내기는 각각 별도 요청 trace를 만든다. 사용자 답변을 기다리는 시간을 실행 시간으로 합치지 않는다. 같은 분석의 재요청은 익명화된 session ID와 previous_trace_id / edit revision / calculation ID로 연결한다. local1과 StatBridge1은 environment 구분을 둔다.

| 구간 / observation 이름 | 실제 연결 지점 | 기록할 정보 |
|---|---|---|
| request.query / request.edit / request.export | bridge_api.py의 각 API 진입·종료 | request ID, 경로, 상태, 총 시간, 응답 종류, 요청 취소·타임아웃 |
| intent.route / request.resolve | StatBridgeWorkflow._route_start, _resolve_request | 일반/파생/범위 밖 경로, 결정론 처리 여부, 보완 질문 사유 |
| catalog.search / metadata.verify | DerivedCatalogTools.search_approved_tables, get_table_metadata, 실제 KOSIS 메타데이터 조회 | 카탈로그 버전, 후보 표 ID, 승인 범위 검증, 분류·항목·주기·기간 확인 결과, 캐시 여부 |
| planner.generate (generation) | derived_indicator_planner.py의 실제 GPT 호출 경계 | 실제 모델, 호출 목적, 시도 횟수, 공급자 request ID, 입력/출력/캐시 토큰, 소요시간, 출력 JSON 파싱 상태 |
| planner.semantic_review (generation 또는 guardrail) | 실제 의미 검토 수행 분기 | 수행/생략 사유, 모델 사용량, 검토 결과. 검토하지 않은 요청에 span을 지어내지 않는다 |
| plan.validate (guardrail) | _validate_derived_plan → DerivedIndicatorRuntime.validate | 연산·DAG 깊이·계열 수·자원·단위·주기·승인 ID 검증, 위반 코드 |
| source.fetch (tool) | _execute_statistics / _execute_derived_sources → StatisticsService | 표별 org/table/item/class ID, 실제 요청 기간·주기, 반환 행수, 출처 API/파일/캐시, 재시도, HTTP 상태, 오류 종류 |
| file.parse / file.validate | DerivedSupplementService의 업로드·계산 진입 | 형식, 크기, 행수, 열 검증, 단위·주기, 원자료 부족 상태. 파일 내용은 원칙적으로 전송하지 않음 |
| dag.execute / node.execute | DerivedIndicatorRuntime.calculate → DynamicExpressionExecutor | DAG 해시, 연산명, 입력·출력 길이, 결측·분모0 건수, 한도 적용, 재계산 노드·캐시 재사용 수 |
| output.build / chart.render / table.build | _prepare_output 및 OutputAgent의 명세·Plotly·표 생성 | 그래프 종류, 계열·관측 수, ChartSpec 검증, 렌더링 시간, 단위·출처 보존 여부 |
| edit.validate / edit.apply / history.restore | /api/output/edit의 버전·소유권 검사와 적용, undo/redo | 결정론/모델 경로, operation 목록, 전후 revision, 충돌, 되돌리기 결과. 셀 위치별 포인터 이동은 제외 |
| evidence.save / analysis.save / export.render | DerivedIndicatorEvidence, 보관함 저장·내보내기 | 근거 ID, revision, 파일 형식·바이트 수, 저장 성공 여부, 내보내기 소요시간 |

node.execute는 최대 노드 수 제한 내에서만 상세 기록한다. 대형 원자료의 개별 관측값·프레임별 스크롤·마우스 이동·셀 hover를 Langfuse에 보내지 않는다. 진단에 필요한 행수·단위·결측 수·노드/수식 해시를 기록한다.

## 상태와 실패 분류

- completed, needs_clarification, missing_data, unsupported_scope, validation_failed, provider_error, source_api_error, cancelled, timeout을 구분한다.
- 추가 질문과 부족 자료는 사용자 오류/서버 ERROR로 표시하지 않는다.
- API 장애·공급자 잔액 부족·JSON 실패·원자료 없음·검증 거절을 별도 error_code로 기록한다.
- 캐시·결정론 경로는 model_call_count=0, cache_hit=true 등으로 명시한다. 모델을 호출한 것처럼 generation을 만들지 않는다.
- 토큰은 실제 공급자 응답에서 가져온다. 모델 비용은 확인된 가격표가 있는 경우에만 계산하고, 없으면 null이다.

## UI

앱의 기존 '실행 흐름' 모달에 단계별 상태·시작/종료·ms·캐시·모델 호출 수를 추가하는 것이 적합하다. 사용자는 한국어 단계명과 부족 자료/재시도 사유를 본다. 개발자만 권한 확인 후 'Langfuse 상세 보기'로 해당 trace를 연다. Langfuse 프로젝트 접근권한과 앱의 계산 근거 소유권을 각각 적용한다. Langfuse 키를 프런트엔드에 내려주지 않는다.

운영자 대시보드에는 요청 지연 p50/p95, 구간별 지연, 모델 호출/토큰, API 실패율, JSON 실패율, 검증 중단율, 자료 부족률, 캐시 적중률, 편집 충돌률을 둔다. 첫 적용 우선순위는 API 전체 → 모델 호출 → KOSIS 조회 → DAG 검증/실행 → 편집/출력 → 저장/내보내기다.

## 구현 조건

- 프로젝트 루트 .env의 LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL을 서버에서만 읽는다. 키는 채팅에 입력하지 않는다.
- 외부 전송 기본값은 질문 원문·파일 내용·응답 전체 제외. 비밀번호, 쿠키, Authorization, API 요청의 인증 키는 항상 제외한다. 외부 서비스에 실제 질문을 보낼 경우 별도 마스킹·수집 범위를 먼저 확정한다.
- SDK 배치 전송을 사용하고 요청마다 flush를 기다리지 않는다. 정상 종료 시 flush/shutdown하며, 관측 서버 장애가 분석·계산 실패를 유발하지 않게 한다.
- 불필요한 GPT 호출을 늘리는 자동 LLM 평가를 켜지 않는다. 기록 자체에는 GPT 호출이 필요하지 않다.

공식 문서 확인: https://langfuse.com/docs/observability/sdk/instrumentation , https://langfuse.com/docs/observability/features/url , https://langfuse.com/docs/observability/features/observation-types
