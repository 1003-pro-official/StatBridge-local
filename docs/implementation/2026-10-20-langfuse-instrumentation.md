# Langfuse 계측과 실행 흐름 UI (ai-assisted)

## 실제 적용

수동 observation을 실제 함수·HTTP 경계에 추가했다. 계측을 위해 모델을 추가 호출하지 않는다. Langfuse 설정이 없어도 로컬 단계별 시간·오류 UI는 동작한다. 질문·프롬프트·모델 출력·API 인증 헤더·업로드 내용·관측값 전체를 외부로 보내지 않는다.

- 질문: 요청 전체, 일반/파생 분기, resolve_request, 추가 조건 대기.
- 검색: 승인 카탈로그 검색·메타데이터·선택 검증.
- 계획: 계획 생성, 수식/DAG·단위·자원 한도 검증.
- 모델: 실제 OpenAI Responses 요청과 NCP HTTP 요청. 실제 HTTP 직전에 호출 수를 증가시킨다. 설정 없음으로 호출 전에 중단한 경우는 0회다. 토큰은 공급자가 반환한 명시적 토큰 필드만 사용하며 미제공 값은 추정하지 않는다.
- 원자료: StatisticsService와 KOSIS 실제 HTTP·메타데이터·통계 조회. 병렬 배치 실행은 요청 ContextVar를 각 작업에 복사하여 원래 trace와 연결한다.
- 파일: 업로드·파싱·추가 자료 검증·계속 진행.
- 계산: DAG 실행·개별 노드·연산·단위·캐시 재사용 수·실제 계산 작업량·결측 이슈 수.
- 출력/편집: OutputAgent 준비·적용·생성, Plotly 렌더링, 표 구성, 문서 복원·버전 검증.
- 보존/파일: 근거 저장, 분석 저장·복원, 표/보고서 내보내기.

수치·수식·출처 검증 로직과 원자료는 변경하지 않았다. 콜백/데코레이터는 실행 중인 요청에서만 기록한다. 기존 `executionRuns`는 유지하고 새 `observability`를 응답/명시적 분석 저장에 함께 둔다. 원래 다운로드 파일은 JSON이라도 수정하지 않는다.

## UI

기존 '실행 흐름' 모달 왼쪽에 요청 기록을 추가하고, 오른쪽에 전체/단계별 ms, 시작·종료, 성공·실패·조건 확인 대기·자료 부족, 실제 모델 HTTP 요청 수, 토큰, 캐시·처리 정보, 오류 코드와 종류를 표시한다. 중첩 시간은 합산하지 않는다고 명시한다. 서버 응답을 받지 못한 경우 브라우저 관측을 따로 표시하고 서버 모델 호출 수는 미확인으로 둔다.

첫 질문이 실패하거나 조건 확인 단계라 그래프가 없어도 '실행 흐름 · 요청 기록 확인'으로 연다. 편집 실패 후 기존 그래프는 유지하며 해당 실패 trace도 조회할 수 있다. 실패 메시지는 검증/공급자/API/버전 충돌/권한/시간 초과 등을 구분하며 예외 원문은 기록하지 않는다.

## Langfuse 설정

프로젝트 루트 .env에만 다음 값을 설정한다. OpenAI 키와 다른 키다.

```dotenv
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
# 선택: 기본값은 실행 폴더를 기준으로 local1 / statbridge1
STATBRIDGE_TRACE_ENVIRONMENT=local1
```

Langfuse Cloud 가입 → 프로젝트 생성 → Settings / API Keys에서 발급한다. BASE_URL은 프로젝트의 연결 예시에 나온 지역 주소와 맞춘다. 두 프로젝트 .env는 복사·교체하지 않는다. 키가 들어 있는 파일은 커밋하지 않는다. 설정 변경 후 서버를 재시작한다.

SDK는 langfuse==4.18.0을 사용하며 OpenTelemetry 구성요소의 호환 패치 버전을 맞췄다. 앱 요청당 flush를 기다리지 않고 SDK 배치 전송을 사용한다. 종료 시 전송을 정리한다. 별도 TracerProvider를 사용해 다른 자동 계측의 요청 본문/헤더가 섞이지 않도록 했다.

연결 확인:

```powershell
.venv/Scripts/python.exe tools/check_langfuse_connection.py
```

누락 설정은 SKIPPED다. 설정이 있으면 인증 확인 → 모델 없는 진단 trace 전송 → trace 조회로 수신 확인을 수행한다. `configured`는 SDK 구성 완료이며 실제 수신 확인 성공을 뜻하지 않는다. 키가 없을 때 UI의 'Langfuse 미연결 · 로컬 기록'은 정상 상태다. 자동 LLM 평가를 켜지 않는다.

## 범위·제한

- 한 요청 최대 128개 상세 단계, 서버의 소유자별 조회는 전체 200개/1시간, 분석 세션 및 브라우저 메모리는 최신 30개 요청으로 제한한다. 브라우저 영구 캐시에는 자동 저장하지 않는다.
- GET /api/observability/{trace_id}는 로그인과 기록 소유자를 검사한다. 다른 계정에는 404, 비로그인에는 401을 반환한다.
- JSON 응답 메타데이터 주입은 8MiB 버퍼 한도 내에서 수행한다. 큰/바이너리 응답은 파일을 보존하고 trace header로 별도 조회한다.
- 내부 추론, 비밀번호, API 키, 파일명·내용, 질문 원문, 모델 답변 원문은 계측하지 않는다. 허용한 표/항목/분류 ID·기간·주기·단위와 집계 메타데이터만 남긴다.
- 요청 밖에서 독립적으로 실행되는 공용 메타데이터 갱신 작업의 전체 수명은 현재 요청의 소요시간으로 합치지 않는다. 해당 요청이 실제로 기다린 구간과 캐시 사용 여부를 기준으로 해석해야 한다.
- Langfuse 장애 시 계산은 계속되고 UI 로컬 기록이 유지된다. 외부 로그 수신 여부와 로컬 계측 성공 여부를 구분한다.

## 검증

- 신규 Python 검사 13건: 실제 시간·중첩·개인정보 필터·병렬 컨텍스트·기록 한도·오류·조건 대기·권한·파일 보존·SDK 메모리 내 전송·실제 HTTP 시도 수.
- tools/run_observability_eval.py: 별도 DB/고정 첨부 자료에서 실제 HTTP 성공·실패·타 계정·비로그인·원자료 불변·XLSX 내보내기 검사. 실제 KOSIS/실제 GPT 평가가 아니다.
- 신규 프런트엔드 검사: 계정 전환 정리, 오래된 비동기 응답 차단, 기록 상한, 구독 해제, 조회 실패가 원래 요청을 깨뜨리지 않는지.
- 실행 결과는 `.venv/cache/langfuse-20261020/` 아래에 저장한다. 외부 Langfuse 연결 확인 결과는 live-langfuse-check.json에 별도로 기록한다.

공식 근거: https://langfuse.com/docs/observability/sdk/instrumentation , https://langfuse.com/docs/observability/features/url


## 2026-10-20 실제 Cloud 연결 및 운영 UI 재검증

사용자가 각 루트 .env에 일본 리전 연결 값을 설정한 후 두 운영 백엔드만 신원을 대조하여 재시작했다. API 8000(local1), 8001(StatBridge1)의 health는 모두 HTTP 200이다. 프런트엔드 5173/5174는 유지했다.

새 Langfuse 조직은 기존 GET /api/public/traces/{id} 조회가 HTTP 410으로 거부되어 인증 성공과 수신 확인 실패가 섞였다. 연결 검사 스크립트를 공식 Observations API v2로 변경했다. 시간 범위와 trace_id를 지정하고 비동기 수집 지연 동안 최대 20회 제한 재조회한다. 운영 앱의 SDK OTEL 전송 로직은 변경하지 않았다. 두 폴더의 검사 스크립트는 동일하다.

이번 실제 검증 결과:

| 검증 | local1 | StatBridge1 |
| --- | --- | --- |
| 키 인증 + 진단 로그 Cloud 수신 조회 | PASS | PASS |
| 운영 UI에서 저장 분석 복원 | 788.9ms, 13단계 | 567.9ms, 13단계 |
| 잘못된 보고서 JSON 업로드 검증 오류 | 12.5ms, 2단계 | 7.3ms, 2단계 |
| Cloud에서 동일한 운영 성공/실패 trace 조회 | 13단계 / ERROR 2단계 확인 | 13단계 / ERROR 2단계 확인 |
| 기존 계정 / 저장 분석 내용 보존 | 5계정 / 9개, 내용 해시 동일 | 4계정 / 5개, 내용 해시 동일 |
| 위 진단/복원/오류 검증의 모델 호출 | 0회 | 0회 |

실제 운영 UI의 기본 테스트 계정으로 기존 저장 분석을 열었다. 분석 저장 버튼은 누르지 않았다. 오류 재현은 형식이 잘못된 테스트 설정 파일을 업로드했으며 기존 그래프와 원자료가 유지되는 것을 확인했다. 이는 저장 자료 복원과 편집 오류 계측 검증이며 신규 GPT 질의나 KOSIS 관측값 재조회 검증은 아니다.

UI의 'Langfuse SDK 활성 · 수신 확인 전'은 요청 시점의 로컬 SDK 상태다. 앱 요청마다 Cloud 수신 조회를 추가하지 않으므로 나중의 별도 수신 검사 결과로 해당 문구를 자동 변경하지 않는다. 실제 Cloud 수신은 별도 v2 API 조회로 확인했다.

검증 증거는 각 폴더 .venv/cache/langfuse-20261020/connected/ 아래 connection.json, app-readback.json, preservation.json, ui-success.png, ui-error.png에 저장한다. 키와 .env는 문서·로그에 복사하지 않는다.

공식 조회 API: https://langfuse.com/docs/api-and-data-platform/features/public-api
