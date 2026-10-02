# 2026-10-02 공식 폴더 구조 통합

## Git 이력 정리

포크 main을 upstream/main(89b58f2) 위로 rebase했다. 3255d75는 이미 적용된 패치로 자동 제외되었고 충돌은 없었다. 3255d75와 bccca7e의 Git tree는 동일하다. 변경 전 상태는 로컬 `backup/pr13-before-rebase-20261002` 브랜치에 남겼다. 기존 upstream PR #13을 갱신하며 작성자가 직접 병합하지 않는다.

## 정본과 데이터 확인

- 메타데이터: `data/processed/`, 선택적 원자료: `data/tables/`(Git 제외).
- MCP: `src/backend/statbridge_mcp/`, 환경 파일: 루트 `.env`(Git 제외).
- Windows 실행기: `scripts/windows/`, 회귀 테스트: `tests/`.
- 벡터·생성 결과: `.venv/cache/`(Git 제외).

중복 CSV 6종을 각각 비교했다. master/items/sources는 각 349행, periods는 666행, classifications는 23,060행이며 정본과 행 내용이 같다. comments는 양쪽 모두 2,290행이고 672행의 개행 표현만 달랐다. 개행 표현을 정규화하면 전체 행이 같았다. 정본에 잔액표 DT_284Y001·거래표 DT_284Y002와 분류 128행이 이미 들어 있어 정본 데이터는 덮어쓰지 않았다. 비교 후 중복 CSV를 제거했다.

MCP 파일별 비교에서는 정본의 루트 환경 설정, 키 누락 시 fallback, 검색 확장, 추가 healthcheck 필드를 유지했다. 중복 KOSIS 클라이언트의 UTF-8 처리는 정본의 느슨한 JSON 처리와 함께 통합했다. requirements는 정본에 같은 의존성이 모두 있고 MCP SDK는 기존 2.2.0 고정을 유지했다. 샘플 환경 설정의 추가 항목은 루트 `.env.example`에 통합했다.

## 파일 이동과 로컬 보관

- `validate_all_tables_cli.py` → `tools/`.
- `run_mcp.ps1` → `scripts/windows/`.
- MCP README → `docs/implementation/MCP_RUNTIME_GUIDE.md`.
- clarification/Jev/LangGraph/output 및 349개 표 테스트 → pytest가 수집하는 `tests/test_*.py`.
- 기존 Agent/NCP 테스트는 정본의 대응본을 유지했다. Agent 흐름은 pytest 래퍼로 실행한다.
- 루트 문서 3개는 정본 문서와 동일함을 확인한 뒤 제거했다. CMD 7개는 정본 실행기에 휴대용 환경 검사·기동 기능을 통합한 뒤 제거했다.
- 생성된 validation_results는 `.venv/cache/validation_results/`에 로컬 보관한 뒤 Git 추적에서 제거했다. 이전 환경·캐시·런타임 잔여 파일도 `.venv/cache/`에 보관했다. 현재 data 아래 실제 디렉터리는 kosis와 processed뿐이다.

현재 실행 방법은 `scripts/windows/START_STATBRIDGE.cmd` 더블 클릭이다. Python/Node/의존성과 키를 검사하고 필요한 설치 및 키 안내를 거쳐 Agent API·MCP·UI를 시작한다. 종료는 같은 폴더의 `STOP_STATBRIDGE.cmd`로 한다. 새 Windows 컴퓨터 자체에서의 설치는 이번 환경에서 검증하지 않았다.

## 검증 범위

- pytest: 55 passed, 355 subtests passed (40.72초). 정본 및 공개 v4.1 테스트를 실행해 349개 표의 사전·카탈로그 일치와 API 계획을 검사했다.
- 공개 v4.1 검증기: VALIDATION OK (dev 50, test 70, 공개 holdout queries 30). 비공개 정답은 사용하지 않았다.
- 프런트엔드: TypeScript 및 Vite 빌드 통과.
- 정본 CMD 실제 실행: API 8011, UI 5181 정상 기동. 다른 프로젝트의 서버는 종료하지 않았다.
- 실제 HTTP: DT_284Y001, DT_284Y002, DT_404Y017, DT_121Y007의 질의 → 기간 선택 → KOSIS 자료 → 출력 설정 → 막대그래프 응답 통과.

이번에는 349개 표의 모든 기간·분류 조합에 대한 외부 호출을 다시 실행하지 않았다. NCP 모델별 실호출 테스트도 실행하지 않았다. 이전 평가 수치와 이번 회귀 검증은 별개의 관측값이다. 2026-09-30 감사 문서의 구경로는 당시 문제를 기록한 인용이며 현재 실행 경로가 아니다. 애매한 MCP 파일의 이동·통합 및 생성 결과 로컬 보관은 사용자 승인에 따라 처리했다.

변경은 ai-assisted이며 최종 병합은 사람의 diff 검토와 승인 후 진행한다.

## CI 실패 항목 재확인

후속 요청에서 언급한 실패는 정본화 이전 head(57e7842)의 구 MCP 사본 로딩 문제였다. 정본화 head 972555e의 GitHub verify는 completed/success이며 PR #13은 mergeable=true로 확인했다. 최신 upstream/main(89b58f2) 기준 재정렬도 Current branch main is up to date로 끝났다.

같은 문제가 재발하지 않도록 bridge_api 로딩 뒤 config/kosis_client/metadata_store/search_engine/statistics_service/server의 실제 __file__이 src/backend/statbridge_mcp에 있는지 검사하는 회귀 테스트를 추가했다. _loads_lenient 존재도 확인한다. 기존 ImportError·키 없는 탐색·검색 결과·healthcheck 테스트는 그대로 유지했다. 실패 관련 파일과 API 통합 및 정본 회귀 테스트를 묶어 재실행해 11개 테스트가 통과했다. 전체 회귀는 56 passed, 355 subtests passed (49.91초), 공개 v4.1 검증기는 VALIDATION OK, UI 빌드는 TypeScript/Vite 성공이다. 세 검증 모두 푸시 전에 완료했다. README의 중복 정본 경로 표기 한 곳도 수정했다.

이미 통합한 파일은 다시 삭제하거나 메타데이터를 덮어쓰지 않았다. 보류 파일은 없으며 대응본 없는 MCP 파일의 이동·통합과 결과물 로컬 보관은 앞서 받은 승인을 유지한다.
