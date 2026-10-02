# 출력 에이전트 리뷰 보완 및 Windows 실행 검증

## 무엇을 바꾸나요

`StatBridge-local1`을 원본 저장소의 최신 `main`(8139e15) 기준으로 맞췄다. 이 커밋에는 팀원의 출력 에이전트 PR #14가 이미 병합되어 있어 출력 관련 코드를 다시 복사하거나 런타임 폴더를 중복 생성하지 않았다. 이번 변경은 남은 리뷰 보완과 기존 설치에서 그래프 의존성이 누락되는 문제에 한정한다.

- `scripts/windows/START_STATBRIDGE.cmd`: Python Plotly와 프런트 `plotly.js-dist-min`을 추가 검사한다. 기존 Vite 설치가 있어도 Plotly가 없으면 프런트 의존성을 설치한다. 서버 시작·종료, 포트, API 키 확인, 정본 경로는 유지했다.
- `src/agent/output_agent.py`: 렌더링 검증을 설명 생성보다 먼저 실행한다. 자동 선택의 잘못된 명세가 선/막대 그래프로 재시도될 때 실패한 그래프에 대한 설명 호출을 하지 않는다. 정상 준비 단계의 명세 제안과 설명 생성은 서로 다른 호출이므로 이 둘은 유지한다.
- `src/agent/frontend/src/App.tsx`: 선택적인 `visualization` 필드에도 안전하게 접근한다.
- `tests/test_output_agent_review.py`: 기존 수동 V2 테스트를 pytest에서 실행하고, 자동 재시도 설명 호출 수, 명시적 잘못된 그래프, 세션 100개 상한, 오류 이후 재시도, 편집 시 기존 행 재사용, 런처 의존성 검사를 검증한다.
- `README.md`: 출력·수정 API 계약과 실행 순서, 세션 수명 및 의존성 검사 안내를 추가했다. API 필드는 변경하지 않았다.

## 관련 이슈

원본 저장소 PR #14의 리뷰 후속 보완. PR #14는 이미 병합되어 새 기능 브랜치에서 후속 PR로 제출한다.

## 리뷰 사항 처리

1. 필수 루트 테스트 이동: 최신 main에는 이미 `tests/TEST_OUTPUT_AGENT_V2.py`로 이동되어 있고 루트 계산은 `parents[1]`이다. 루트 파일이 없으므로 추가 `git mv`를 수행하지 않았다. 기존 파일은 수정하지 않았으며 레이아웃 가드와 직접 실행 모두 통과했다.
2. `langgraph` 중복: 최신 main의 requirements에는 한 줄만 있다. 추가 변경 없음.
3. 출력 422 오류: `submitOutput`이 이미 문자열 `detail`을 파싱하고 있다. 추가 변경 없음. 백엔드 오류 상세와 입력 세션 유지에 대한 회귀 테스트를 추가했다.
4. 수정 세션: 최신 main에 이미 최대 100개, 생성 순서상 가장 오래된 세션 제거가 구현되어 있다. 상한 동작을 회귀 테스트로 확인했다. 영속화·외부 저장소·만료 시간을 추가하지 않았다.
5. 설명 모델: 자동 차트 재시도에서 중복 호출이 발생할 수 있던 순서를 수정했다. 설명은 성공한 렌더링에 대해 한 번 호출한다.

## 평가 계열

공개 table-discovery v4.1의 스키마 검증 및 기존 회귀 테스트만 실행했다. 새로운 탐색 성능 점수는 산출하지 않았다. end-to-end 평가 계열과 혼용하지 않는다.

## 검증

Windows PowerShell, Python 3.11, Plotly 6.9.0, pnpm 12.4.2, Vite 8.3.0 환경에서 2026-10-02 실행했다. POSIX 명령의 가상환경 경로와 PYTHONPATH 구분자만 Windows에 맞게 바꿨다.

- [x] `PYTHONPATH=src/backend:src/agent .venv/bin/python -m pytest -q tests eval/table-discovery/v4.1/tests`
  - 실제 명령: `$env:PYTHONPATH='src/backend;src/agent'; .venv/Scripts/python.exe -m pytest -q tests eval/table-discovery/v4.1/tests`
  - `64 passed, 355 subtests passed in 46.56s`.
- [x] `.venv/bin/python eval/table-discovery/v4.1/scripts/validate_v41.py`
  - `VALIDATION OK`; `dev/test/holdout = 50/70/30; public holdout has no gold leakage`.
- [x] `cd src/agent/frontend && pnpm build`
  - 타입 검사 및 프로덕션 빌드 성공. `19 modules transformed`, `built in 2.00s`.
  - Plotly가 포함된 JS 약 4.87 MB, gzip 약 1.46 MB. 500 kB 초과 경고는 남아 있으며 빌드 실패는 아니다.
- [x] `.venv/Scripts/python.exe tests/TEST_OUTPUT_AGENT_V2.py`
  - `OUTPUT AGENT V2 OK: HCX spec/explanation, safe edits, 13 Plotly chart types and mixed axes`.
  - 수동 스크립트의 모델 호출은 FakeHCX를 사용한다.
- [x] 실제 Windows CMD 및 UI 실행
  - `STATBRIDGE_API_PORT=8012`, `STATBRIDGE_UI_PORT=5178`, `STATBRIDGE_NO_BROWSER=1`로 `scripts/windows/START_STATBRIDGE.cmd` 실행.
  - 기존 가상환경·설치 의존성·API 키·벡터 인덱스 확인 후 Agent API, MCP, UI 시작 성공. 브라우저는 검증용으로 별도 열었다.
  - `/api/health`: `status=ok`, `dictionary_tables=349`, `supported_tables=349`.
  - UI에서 `2025년 경제심리지수` → 2025-01-01~2025-12-31 → 데이터 조회 → 그래프 종류 `line` → 그래프 생성. `DT_513Y001`의 12개 관측치가 실제 Plotly 그래프로 표시되었다.
  - 자연어 `제목을 경제심리지수 검증 완료로 바꿔줘`를 입력해 제목 변경 성공. 기간 및 12개 관측치 유지. `/api/output`과 `/api/output/edit` 서버 로그의 응답은 모두 200.
- [x] 외부 KOSIS·NCP 호출
  - 위 경제심리지수 UI 사례에서 기존 KOSIS 키와 CLOVA 설정을 사용한 실제 조회·출력·자연어 편집을 확인했다.
  - 349개 표 전체를 다시 조회한 것은 아니며, 로컬 CSV 347개 전체 조회도 이번 검증 범위가 아니다.
- [x] `git diff --check`: 오류 없음.

## 공개·비공개 경계

- [x] 비공개 저장소 자료와 holdout 정답을 열람하거나 포함하지 않았다.
- [x] `.env`, API 키, 원자료 CSV, 벡터 DB, 생성된 평가 결과, 런타임 로그 및 화면 캡처를 커밋에 포함하지 않는다.
- [x] 데이터·사전·검색·KOSIS 선택 경로 및 정본 폴더 구조를 변경하지 않았다.

## 에이전트 사용

- [x] LLM·에이전트로 만든 변경이다 (`ai-assisted`).
- [ ] 사람이 diff 전체를 확인하고 승인해야 한다. 이 문서는 사람의 검토 완료를 대신하지 않는다.

## 리뷰어에게

깨끗한 새 컴퓨터에서 Python·Node 자동 설치와 API 키 입력, 신규 벡터 인덱스 생성까지 처음부터 수행하지는 않았다. 현재 설치가 있는 로컬 환경에서 CMD의 실행 단계와 실제 그래프 생성·편집을 검증했다. 13종 전체는 Mock 데이터 렌더링 검증이며 실제 외부 데이터 UI 검증은 선 그래프와 제목 편집 한 사례다. PNG·CSV 다운로드는 이번 검증에서 실행하지 않았다.

원본 main에 직접 푸시하거나 강제 푸시하지 않는다. 최소 한 명의 사람 승인 이후 승인자가 병합해야 한다.
