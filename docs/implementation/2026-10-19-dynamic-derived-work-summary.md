> 초기 구현 시점 기록입니다. 이후 입력·출력 12개 및 D 주기, API+파일 보완과 지원 범위 정책으로 확장했습니다. 현재 범위와 평가 한계는 [당일 전체 작업 기록](2026-10-19-complete-derived-worklog.md)을 확인하세요.

# 동적 파생지표 구현·검증 결과 (ai-assisted)

적용 대상: `StatBridge-local1`과 `StatBridge1/StatBridge-official`.
기존 수정사항을 유지하고 선택한 코드·테스트·문서만 동기화했다.
환경 설정, API 키, 포트, 원자료 CSV, 계정 DB, 기존 저장 분석은 복사하지 않았다.
local1 작업 브랜치는 `feat/dynamic-derived-indicators-20261019`이며 커밋·푸시·PR 게시를 하지 않았다.

## 구현 결과

사전 지표 레시피 또는 전체 조합 계산은 없다. GPT-5.4는 승인 카탈로그 검색과
메타데이터 도구 응답을 근거로 입력 계열과 계산 DAG를 매 요청 시 설계한다.
JSON과 실제 ID, 주기, 기간, 단위, 자원 한도를 Python이 검증한다.
필요한 자료가 없거나 의미를 확정하지 못하면 자료명·사유·검색 근거 또는 추가 질문을 반환한다.
모델 장애를 자료 부재로 표시하지 않으며 CPI를 PPI로 대체하지 않는다.

흐름은 `classify_analysis_intent → plan_derived_indicator → validate_derived_plan →
execute_derived_sources → calculate_derived_indicator → prepare_output`이다.
일반 통계 조회의 `resolve_request → execute_statistics → prepare_output`은 유지한다.
기존 OpenAI 연결을 재사용하되 계획 모델은 GPT-5.4로 고정한다.
조회는 기존 McpToolGateway/StatisticsService와 복수 계열의 statistics_batch를 재사용하며
파생지표에서는 `prefer_local=False`, `allow_fallback=False`로 KOSIS API만 허용한다.

초기 기본 연산 14개: add, subtract, multiply, divide, pct_change, yoy_pct, difference,
rolling_mean, cumulative_sum, rebase_100, lag, inverse, log, power.
입력 8개, 노드 48개, 깊이 12, 입력당 20,000점, 중간 셀 500,000개,
rolling 창을 포함한 작업량 2,000,000회, 계획 JSON 128KiB로 제한한다.
시차와 창은 120 이하이며 거듭제곱 지수는 -4~4의 유한 실수다.

결과는 기존 OutputAgent/ChartSpec에 전달한다. 계산 계획, 원자료 관측값, 단위,
전체 중간 결과, 결측·분모 0·정의역 오류, 출처, 카탈로그 해시, 실제 모델 usage를
`runtime_data/derived_evidence/`에 불변 JSON으로 저장한다. 로그에 API 키를 넣지 않는다.
기존 계획을 수정하면 변경 노드와 후손만 다시 계산한다. 기존 자료 범위를 넘을 때는
부족한 앞/뒤 구간만 추가 조회한다. 이전 계산 ID를 연결하며 원래 계산은 덮어쓰지 않는다.

## 신규·변경 파일

신규 Agent 모듈:

- `src/agent/derived_indicator_planner.py`: 도구 기반 계획·독립 의미검토·사용량 추적
- `src/agent/expression_tree_schema.py`: 닫힌 Pydantic DAG 계약
- `src/agent/expression_tree_validator.py`: 주기·기간·참조·단위·자원 검증
- `src/agent/dynamic_expression_executor.py`: 달력 키 기반 15개 허용 연산
- `src/agent/derived_indicator_evidence.py`: 불변 근거 저장·내용 해시
- `src/agent/derived_catalog_tools.py`: 349개 검색·기간 필터·ID 검증
- `src/agent/derived_indicator_runtime.py`: 기존 KOSIS 서비스·배치·출력 및 부분 재계산 조정
- `src/agent/derived_intent_router.py`: 계산 수정과 시각적 수정 구분

기존 연동 파일:

- `src/agent/langgraph_workflow.py`, `bridge_api.py`, `output_agent.py`
- `src/agent/frontend/src/App.tsx`, `SummaryEvidence.tsx`, `RecoveryPanel.tsx`
- `src/agent/frontend/src/accountApi.ts`, `analysisDeadline.ts`, `requestDeadline.ts`
- `src/agent/frontend/src/api/client.ts`, `api/types.ts`, `api/queryFailure.ts`
- 신규 `DerivedEvidence.tsx`, `derivedDeadline.ts`, `test-derived-deadline.mjs`
- 신규 `tests/test_dynamic_derived_indicators.py`, `tools/validate_dynamic_derived.py`
- `.gitignore`, `README.md`, 설계안·실제 생성 사례·이 작업 결과 문서

`/api/query`, `/api/output`, `/api/output/edit`는 기존 요청을 유지한다.
계산 노드의 숫자 매개변수는 `derived_node_patch`로 변경할 수 있다.
연산·원자료 변경은 자연어로 요청해 다시 의미검토한다.
추가 `/api/output/derived-data`는 기존 편집 세션의 계정 소유권 검사를 거쳐
실제 원자료를 페이지 단위로 제공한다. 원자료 보기는 처음 200점, API 한 번에 최대 1,000점이다.

## 검증 결과

- 전체 회귀 실행: **1,543 passed, 355 subtests passed**, 706.85초.
  이 실행 후 실제 UI 편집에서 발견한 문제를 수정하고 영향을 받는 경로를 별도 재검증했다.
- 최종 관련 회귀: **94 passed**. 신규 파생지표 검증 51개와 관련 기존 테스트 43개를 포함한다.
- 두 폴더 프런트엔드 빌드 통과. 파생/일반 조회 대기·취소·회복 테스트 11개 통과.
- 두 폴더 카탈로그 validator 통과. local1 `git diff --check` 통과.
- 실제 GPT-5.4 + KOSIS: PPI yoy 24점, 수출·수입물가 yoy 차이 24점,
  PPI 재지수화 24점과 재지수화 후 3개월 평균 24점 생성.
- 실제 KOSIS 배치 재조회: 수출·수입물가 각각 36개월, 모두 `kosis_api` 출처 확인.
- 원문 API 문자열로 Decimal 정밀도 50 독립 검산: 최대 절대오차 **3.1175e-14**,
  허용오차 1e-10 이하. [실제 사례·검산·사용량](2026-10-19-derived-available-examples.md) 참고.
- 실제 GPT로 월별 CPI 역수 기반 구매력 요청을 검사했다. 필요한 CPI 표·항목을
  승인 카탈로그 검색에서 확정하지 못해 계산을 중단했고 다른 물가 지표로 대체하지 않았다.
- 별도 검증 포트 18019/15179와 별도 검증 계정 DB로 브라우저 점검:
  자연어 분석 → 실제 그래프 → 산식·원자료 보기(36개월) → 저장 → API 재시작 후 복원 →
  자연어로 yoy 뒤에 rolling_mean(window=3) 추가 → 그래프 갱신 → 제목 편집 확인.
  마지막 관측값은 약 1.3607893555%였고 새 계산 ID와 이전 ID 연결을 보존했다.

가상 관측 테스트와 위 실제 공급자 검증은 구분했다. 349개 표의 전체 항목 조합을
라이브로 검증한 결과가 아니다. 실제 사용량·시간은 사례 문서에 기록했으며
전체 세션의 청구 금액은 공급자 청구서를 확인하지 않아 확정하지 않았다.

## 제한과 사용 방법

경제학적 의미는 독립 GPT 검토와 서버의 확인 가능한 규칙으로 검사한다.
임의의 경제 개념에 대한 수학적 증명이나 완전한 의미 검증은 아니다. 불명확하면 질문한다.
일·주 주기, 주기 자동 변환, 임의 상수 시계열, 자유 수식/코드, 회귀·예측은 지원하지 않는다.
M/Q/S/Y 주기만 허용한다. 메모리는 셀 수·작업량으로 제한하며 OS RSS 격리는 아니다.
카탈로그가 349개가 아니면 승인 경계를 다시 검토할 때까지 실행을 차단한다.
복수 독립 파생 세션 병합은 막고 같은 자연어 요청에서 비교 계산을 설계하도록 안내한다.
실제 그림 표시·첨부 변경과 계산 변경은 나누어 요청한다. 실패하면 현재 그래프를 유지한다.
일반 조회 대기는 기존 20초이며 파생 분석에만 최대 120초를 적용한다.

각 폴더의 기존 런처로 재시작한 후 아래 예시를 입력한다.

1. `2023년 1월부터 2024년 12월까지 생산자물가 총지수의 전년동월 대비 상승률을 계산해 주세요.`
2. 그래프의 `파생지표 계산 근거`에서 계산식·항목 ID·조회기간과 `사용한 원자료 보기`를 확인한다.
3. 그래프 대화에 `현재 상승률에 3개월 이동평균을 적용해줘. 조회 기간은 유지해줘.`를 입력한다.
4. `되돌리기`로 이전 그래프와 계산 근거가 함께 복원되는지 확인한다.
5. `월별 CPI의 역수로 정의한 국내 소비자 구매력의 2023~2024년 전년동월 변화율`을
   요청해 필요한 CPI 자료를 확정하지 못할 때의 안내와 대체 금지를 확인한다.

실제 호출에는 각 폴더의 기존 OPENAI_API_KEY와 KOSIS_API_KEY 설정이 필요하다.
CLI 재현: `.venv/Scripts/python.exe tools/validate_dynamic_derived.py --live`.
