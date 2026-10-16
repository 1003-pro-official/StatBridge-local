# StatBridge

현재 작업 저장소는 [Engineer3rd-Class-Kimmin/StatBridge-local1](https://github.com/Engineer3rd-Class-Kimmin/StatBridge-local1)이다. Windows에서는 `scripts/windows/START_STATBRIDGE.cmd`로 실행한다. 통합 HTTP 실행 모듈은 `src/agent/agent_runtime.py`이며 기존 `statbridge_agent/` 패키지도 보존한다.

오늘의 출력 에이전트·Jev 패치·평가 기록은 [통합 작업 요약](docs/운영/2026-10-01-통합-작업-요약.md), 저장소 이전 과정은 [저장소 이전 기록](docs/운영/2026-10-01-저장소-이전.md)에 정리했다.

한국은행 통계표를 자연어로 탐색하고, 선택한 계열의 관측값과 출처를 확인하는 로컬 애플리케이션입니다.

기여·브랜치·리뷰·검증 규칙은 [CONTRIBUTING.md](CONTRIBUTING.md)를, 에이전트용 요약 규칙은 [AGENTS.md](AGENTS.md)를 참고하세요.

## 코드와 데이터

| 위치 | 역할 |
|---|---|
| `src/backend/statbridge_mcp/` | 통계표 검색, 메타데이터, KOSIS·로컬 CSV 조회, MCP 도구 |
| `src/agent/bridge_api.py` | 화면용 FastAPI (`/api/query`, `/api/catalog`, `/api/health`) |
| `src/agent/agent_runtime.py`, `src/agent/stat_dictionary/` | 질의 해석, 역질문, 통계표·계열 선택 |
| `src/agent/frontend/` | React 화면 |
| `data/processed/` | 한국은행 349개 지원 표의 목록·항목·분류·기간 메타데이터 |
| `data/tables/` | 별도 원본에서 공급하는 347개 통계표 CSV; Git에 포함하지 않음 |
| `eval/table-discovery/` | 질의 해석~통계표 탐색 평가 v1·v2·v3·v4.1 |
| `eval/end-to-end/` | 별도 계열의 전체 흐름 평가 v1·v2 초안 |

화면의 주 API는 `src/agent/bridge_api.py`입니다. `src/backend/query_api.py`도 같은 앱을 실행합니다. 이전 `/api/analyze` 계약은 제공하지 않으므로 해당 클라이언트는 새 `/api/query` 응답에 맞춰 수정해야 합니다. `analysis_service.py`는 기존 평가 도구 참고용으로 남아 있습니다.

## 설치와 실행

### Windows: 다운로드 후 더블클릭

GitHub의 **Code → Download ZIP**으로 받은 파일을 먼저 압축 해제한 뒤, scripts/windows 폴더의 **`scripts/windows/START_STATBRIDGE.cmd`**를 더블클릭합니다. ZIP 내부에서 직접 실행하지 마세요.

루트의 **`START_STATBRIDGE.cmd`** 또는 `scripts/windows/START_STATBRIDGE.cmd`를 실행합니다. Python 3.11~3.13 64비트와 Node.js 20.19+ 또는 22.12+를 확인하고, 이 PC의 가상환경 및 잠금 파일 기준 패키지를 준비합니다. 지원되는 Python이나 Node.js가 없으면 `winget`으로 설치를 시도하며, 사용할 수 없으면 설치할 항목을 안내합니다. 인터넷과 패키지 설치 권한은 최초 설치에 필요합니다.

기존 API·UI 프로세스가 패키지 파일을 잠그지 않도록 이 폴더에서 기록한 서비스부터 종료하고 설치합니다. 복사된 가상환경이 맞지 않으면 보존한 뒤 다시 만들며, 프런트엔드 네이티브 패키지와 실제 Vite 실행도 검사합니다. `RUN_AGENT.cmd`, `RUN_FRONTEND.cmd`, `RUN_MCP.cmd`는 같은 준비·실행 경로로 연결됩니다.

API 키가 없으면 `.env.example`에서 이 폴더의 `.env`를 준비하고 화면·로그인·카탈로그를 먼저 실행합니다. 실제 KOSIS 수치 조회, NCP 자연어 해석·벡터 검색, OpenAI 그래프 수정은 해당 키가 있어야 사용할 수 있습니다. 키 이름과 설정 여부만 출력하며 값은 출력하지 않습니다. `scripts/windows/EDIT_API_KEYS.cmd`로 이 프로젝트의 설정을 입력할 수 있습니다.

벡터 인덱스가 없는 첫 실행에는 사전 검색을 사용합니다. NCP 키와 사용 권한을 준비한 후 `START_STATBRIDGE.cmd --build-index` 또는 `scripts/windows/RUN_VECTOR_BUILD.cmd`를 실행하면 임베딩 인덱스를 생성합니다. 인덱스 생성 실패가 일반 화면 실행을 막지 않도록 분리했습니다.

환경만 확인하려면 **`CHECK_STATBRIDGE.cmd`**를 실행합니다. 설치나 서비스를 변경하지 않고 가상환경, Python 패키지·버전·import, Node.js, 프런트 패키지·네이티브 실행, 키 설정 여부를 검사합니다. 종료는 `STOP_STATBRIDGE.cmd`입니다. 런처는 실행 파일과 생성 시각이 일치하는 기록된 프로세스만 종료하며 다른 프로그램이 포트를 사용하면 안내합니다. 로그는 `.venv/cache/evaluation_runs/`에 있습니다.

팀원에게 소스를 전달할 때는 `.venv`, `.venv.invalid.*`, `node_modules`, 실제 `.env`, 계정 DB와 저장 그래프를 포함하지 마세요. 실행 환경과 키는 팀원 PC에서 새로 준비합니다. 지원 버전·최초 설치·두 폴더 검증 기록은 [CMD 실행 환경 점검](docs/implementation/2026-10-13-windows-launcher-reliability.md)에 있습니다.

### 그래프 출력과 수정

보고서 요약은 현재 조회된 원자료와 표시 기간을 근거로 존댓말로 작성합니다. 최신 수준, 전월·전분기 대비 변화, 전년동기 비교 또는 관측된 상승·하락 전환과 변화폭을 우선하며 최고·최저 값만 나열하지 않습니다. 비교 시점이 없으면 해당 비교를 생략합니다. 서버가 수치와 문장을 계산하고 GPT-5.4는 검증된 문장의 ID만 선택합니다. 모델의 자유 서술·외부 지식·원인·전망은 표시하지 않으며, 응답이 잘못되거나 연결이 실패하면 같은 근거의 기본 요약을 사용합니다. 누적·평균 등 그래프 변환값을 원자료 수치로 설명하지 않습니다. 제목·색상처럼 요약 근거가 같은 수정에서는 기존 요약을 유지합니다.

10월 6일 팀원 작업과 로컬 후속 패치를 [통합 기록](docs/implementation/2026-10-06-chart-editing-integration.md)에 정리했습니다. 정본 경로와 기존 Windows 런처를 유지합니다.

입력 UI에서 질의·통계표·기간을 확정하면 `/api/query`가 MCP 데이터를 조회하고 `need_output_config`와 `outputSessionId`를 반환합니다. 화면에서 그래프 종류, 제목·축·범례, 자연어 요청을 선택한 뒤 `/api/output`으로 `session_ids`, `chart_type`, `chart_mode`, `natural_language` 등을 전달합니다. LangGraph의 출력 단계가 별도 `OutputAgent`를 호출하며, 화면은 응답의 `outputSpec.plotlyFigure`를 Plotly로 표시합니다.

`outputSpec.chartState`는 검증된 그래프 상태이고 `editSessionId`는 수정 세션입니다. `/api/output/edit`에 `edit_session_id`, `instruction`, 선택적으로 `conversation`을 보내면 현재 상태와 대화 맥락으로 편집합니다. 스타일 수정은 기존 조회 데이터를 사용합니다. 조회 기간을 변경하면 확정된 통계표·항목·분류를 유지해 원자료를 재조회하고, 되돌리기/다시 적용은 데이터와 그래프 상태를 함께 복원합니다. 자연어 모델 해석에는 CLOVA 키가 필요하며, 잘못된 그래프 요청은 HTTP 422의 `detail`로 표시합니다. 수정 세션은 최대 100개로 제한하고 초과 시 가장 먼저 만들어진 세션을 제거합니다. 서버를 재시작하면 세션은 사라집니다.

선·막대·누적 막대·영역·산점·버블·파이·도넛·히스토그램·박스·히트맵·트리맵·워터폴을 지원합니다. 계열 수와 단위 등 조건을 만족하지 못하는 명시적 선택은 오류로 안내하며, 자동 선택만 안전한 선/막대 그래프로 재시도합니다. 재시도 시 설명 모델은 성공한 그래프에 대해서만 호출합니다.

그래프 선택 화면은 현재 조회된 값으로 **지원되는 종류와 지원되지 않는 종류를 분리**합니다. 지원되지 않는 종류를 누르면 필요한 계열 수·공통 시점·단위·값 조건을 안내합니다. 서로 다른 단위를 한 그래프로 요청한 경우 자동으로 별도 그래프로 바꾸지 않으며, 가능한 배치 또는 명시적인 보조축 설정을 확인해야 합니다. 원·도넛에는 항목명·기준 시점·값·단위·구성비를 표시합니다.

입력한 통계표 이름·ID·측정 조건을 정본 사전에 대조하고, 복수 요청은 원문과 모든 조회 계획을 유지합니다. 이름이 맞지 않거나 요청한 지표가 누락된 경우 다른 표를 대신 출력하지 않습니다. 텍스트에 명확한 기간이 있으면 `periodSelection`으로 확인하고 별도 날짜 선택을 생략합니다. 조합이 모호하거나 자료가 없으면 확인 질문/오류를 반환합니다.

금액 요청을 비중(%)·금리로, 신규취급액을 잔액으로 대체하지 않습니다. 별칭은 주제를 찾는 보조이며 실제 측정 개념은 정본 표·항목 이름으로 확인합니다. “비중 대신 금액”, “비중이 아니라 금액” 같은 교체 표현과 지표별 비교 구간을 분리해 검사하고, 검색으로 재진입한 후보와 실제 조회 직전에도 같은 조건을 적용합니다. 모델이 추가한 비중·비교·기간·분류 조건은 이미 정본에서 확인한 원문 조건을 변경할 수 없습니다. `주택담보대출 신규취급액`에 대응하는 금액 표 `DT_181Y011`은 **차주당 금액(십만원)**이며 전체 총액과 다릅니다. 총액을 명시한 요청을 차주당 금액으로 대신 조회하지 않습니다.

복수 기관·산업·지출 항목·국제수지 항목·지급 수단 및 건수/금액 요청은 `catalog_request_planner.py`에서 측정 개념과 정본 분류값을 대조해 각 계열의 조회 계획을 만듭니다. 문맥상 상위 합계와 명시한 하위 항목을 중복 선택하지 않으며, 주기·지역·명목/실질·조정 조건을 확인합니다. 명시 표 ID, 모호한 후보와 불완전한 복수 요청은 기존 탐색 경로를 유지합니다. 정본에 없는 연체율·전망치·채권 금리를 인접 지표로 대체하지 않습니다. API 재검증은 전체 정본 계획과 확정 조건을 대조합니다. 이 경로는 평가 정답이나 문항 ID를 읽지 않습니다.

기자 질의 공개 dev 골든셋 v2의 실제 API 종료 경계 평가는 아래 명령으로 재현합니다. 새 `evaluation_runs/` 폴더에 문항별 HTTP 반환 직후 로그를 남기고, **30문항의 모든 체크가 통과할 때만** `scores.json`과 `PASS-30-of-30.md`를 저장합니다. 실패 실행은 진단 로그와 `diagnostic_scores.json`을 남기고 종료 코드 1을 반환합니다. `execute=false`로 표·항목·분류·주기·기간·역질문/기간 대기 상태를 검증하며 수치 조회, 그래프·수정이 동작과 블라인드 일반화 성능을 검증하지 않습니다.

```powershell
.\.venv\Scripts\python.exe eval/reporter-table-discovery-30/v2/scripts/evaluate_runtime.py
```

편집 화면에서 **그래프 수정은 수정이에게 맡겨 보세요** 안내의 캐릭터를 누르면 기존 수정 세션에 연결된 채팅이 열립니다. 투명 GIF 버튼은 드래그 또는 포커스 후 방향키로 이동할 수 있고 같은 브라우저 주소에서는 위치가 저장됩니다. 펜·화살표·사각형·원·텍스트 표시를 선택해 이동/크기 조절하고, 실제 계열·관측 시점에 연결한 뒤 요청합니다. 부분 편집을 전체 계열로 확대하지 않습니다. 수정 중에는 작업 동작, 평상시에는 8가지 동작 GIF를 표시합니다. 움직임 줄이기 설정에서는 PNG를 사용합니다.

수정 해석은 별도 `ChartEditAgent`와 모델 어댑터를 사용하며 현재 `HCX-007`로 고정합니다. HCX는 손글씨·이미지를 읽지 않고 텍스트와 검증된 표시 범위를 해석합니다. 미래 이미지 지원 모델은 어댑터를 교체해 연결할 수 있지만 아직 구현·검증되지 않았습니다. 명확한 단독 그래프 종류 변경 및 지원 색상 변경은 결정적으로 처리합니다. 실제 조회값은 생성/변경하지 않으며, 실패 시 기존 그래프를 유지합니다.

추가 API 계약: `POST /api/output/options`에 `{session_ids:[...]}`를 보내면 현재 세션의 그래프 지원 조건을 반환합니다. `/api/output/edit`은 기존 필드 외에 선택적 `visual`(marks, selected_target, selection, graph_image, marked_image), `action`(`edit`/`undo`/`redo`), `revision`을 받습니다. 수정 이력은 최대 20개이며 오래된 revision은 409, 적용 불가 요청은 422로 안내합니다. 전체 종류 변경은 기존 부분 스타일 중 호환되지 않는 설정만 정리하고 안내합니다. 프런트 계약은 `src/agent/frontend/src/api/types.ts`가 정본입니다.

“경상수지와 구성 항목”을 명시하면 같은 검증된 통계표의 계정코드로 경상수지·상품수지·서비스수지·본원소득수지·이전소득수지 5개 계열을 조회합니다. 월별 `YYYYMM` 관측점은 Plotly 날짜좌표로 표시하되 원자료 ID와 편집 선택 ID는 그대로 보존합니다.

KOSIS 키가 있으면 로컬 원자료 CSV 없이도 349개 표의 OpenAPI 자료를 조회할 수 있습니다. 개별 분류의 결측값이나 수록기간 차이까지 없어지는 것은 아닙니다. 카탈로그에서 분류를 선택하고 기간을 지정한 뒤, 수신한 자료의 그래프 종류와 편집 항목을 선택합니다.

자세한 변경·검증 범위는 [10월 1일 저녁 작업 기록](docs/2026-10-01-evening-349-update.md)에 정리했습니다.

### 수동 개발 환경

Python 3.12 이상, Node.js, pnpm이 필요합니다. 저장소 루트에서 실행합니다.

**로컬 원자료 CSV:** 이 저장소를 clone해도 `data/tables/`의 통계표 CSV 347개는 포함되지 않습니다. KOSIS가 아닌 로컬 CSV로 수치를 조회할 때 필요하며, 별도 원본의 CSV를 `data/tables/`에 두거나 `STATBRIDGE_TABLES_DIR`로 그 디렉터리를 지정합니다. KOSIS OpenAPI 조회에는 이 CSV가 필요하지 않습니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r src/backend/requirements.txt pytest
cd src/agent/frontend && pnpm install --frozen-lockfile && cd ../../..
```

Windows PowerShell에서는 `.venv/bin/python` 대신 `.venv\Scripts\python.exe`를 사용합니다.
의존성 설치 후 `scripts\windows\START_STATBRIDGE.cmd`로 Agent API와 화면을 함께 시작할 수 있습니다.

CSV가 없어도 메타데이터로 검색과 카탈로그는 확인할 수 있습니다. KOSIS 조회에는 `KOSIS_API_KEY`, HCX·임베딩·재순위화에는 `NCP_CLOVA_API_KEY`가 필요합니다. 키는 루트 `.env`에 두며 Git에 추가하지 않습니다. 예시는 `.env.example`을 참고합니다.

```bash
PYTHONPATH=src/backend:src/agent .venv/bin/python -m uvicorn bridge_api:app --host 127.0.0.1 --port 8000
```

다른 터미널에서 화면을 실행합니다.

```bash
cd src/agent/frontend
pnpm dev
```

`http://127.0.0.1:5173`을 열면 Vite가 `/api` 요청을 8000번 Agent API로 전달합니다. MCP stdio 서버는 저장소 루트에서 별도로 실행합니다.

```bash
PYTHONPATH=src/backend .venv/bin/python src/backend/server.py
```

MCP 도구에는 검색, 메타데이터·수치 조회, 배치 검증, 상태 확인이 포함됩니다. API 키가 없으면 KOSIS·NCP 네트워크 기능은 사용할 수 없지만 사전 기반 질의와 메타데이터 탐색은 가능합니다. 벡터 인덱스는 별도 생성물이며 필요할 때 `tools/build_stat_vector_index.py`로 빌드합니다.

## 검증과 평가

### 그래프 이미지 이모티콘

이모티콘 바깥을 클릭하면 선택만 해제하며 배치 좌표를 바꾸지 않습니다. 미적용 배치를 조정한 상태에서 수정이에게 텍스트 편집을 보내면 배치와 텍스트 수정을 함께 적용합니다. 사이드바를 닫았다 다시 열어도 같은 그래프의 미적용 배치를 이어서 조정할 수 있습니다. 새 편집 결과나 되돌리기로 그래프 버전이 바뀌면 해당 버전의 저장 배치를 사용합니다.

수정이 사이드바에서 **그림판 편집 → 이미지 이모티콘**을 열면 6개 카테고리의 148종 PNG를 검색하고 선택할 수 있습니다. 선택한 이미지를 그래프 위에서 끌어 이동하고, 회전·크기 조절점이나 슬라이더·숫자 입력으로 조정한 뒤 **이모티콘 적용**을 누르세요. 투명도 조절, 선택 삭제, 개별 PNG 다운로드도 지원합니다. 적용하면 사이드바가 닫히고 그래프에 반영됩니다. 다시 열면 저장한 배치를 재편집할 수 있으며, 편집 취소·다시 적용과 그래프 PNG 내보내기에도 포함됩니다.

이미지는 `src/agent/frontend/public/stickers/`에 개별 투명 배경 PNG로 저장하고 `catalog.json`에서 목록을 관리합니다. 이모티콘은 원자료를 변경하지 않는 장식이며 그림판의 수정 지시용 표시와 별개입니다. 그래프당 최대 40개, 크기 2~100%, 회전 -360~360도를 지원합니다. 크기는 그래프 영역의 짧은 변에 대한 회전용 정사각형 크기입니다. 위치는 그래프 영역 비율로 유지되므로 조회 기간 변경 후에도 같은 화면 위치에 남습니다. 표현 스타일 초기화는 이모티콘도 제거합니다.

`GET /api/stickers`는 허용된 이미지 목록을 반환합니다. `POST /api/output/edit`의 `stickers` 배열로 배치 전체를 적용하며, `revision` 충돌 검사와 기존 취소 이력을 사용합니다. 이모티콘 적용은 텍스트·표시 수정과 별도로 실행하며 모델·통계 재조회 없이 처리합니다. 서버는 목록에 없는 이미지, 외부 URL, 중복 ID와 범위를 벗어난 값을 거부합니다. PNG 내보내기는 이미지를 그래프에 내장해 외부 URL에 의존하지 않습니다. 편집 상태는 기존 출력 편집 세션에서 유지하며 서버를 재시작한 뒤의 복구는 지원하지 않습니다.

Windows 실행 파일: `scripts/windows/START_STATBRIDGE.cmd` (종료: `scripts/windows/STOP_STATBRIDGE.cmd`). 이 기능은 StatBridge-local1에만 적용했습니다.

```bash
PYTHONPATH=src/backend:src/agent .venv/bin/python -m pytest -q tests
.venv/bin/python eval/table-discovery/v4.1/scripts/validate_v41.py
.venv/bin/python tools/evaluate_golden_v41.py --dataset eval/table-discovery/v4.1/dev.jsonl --output /tmp/statbridge-v41-dev.json
cd src/agent/frontend && pnpm build
```

두 평가 계열은 버전 번호와 점수를 공유하지 않습니다. 각 버전의 범위·검토 상태·실행 명령은 [평가 자료 안내](eval/README.md)를 참고하세요. v4.1의 비공개 holdout 정답과 평가기는 별도 접근 제한 저장소에서 관리하며, 공개 holdout 파일에는 질문만 있습니다.

[349개 표 증강 골든셋 v3](eval/reporter-table-discovery-30/v3/README.md)는 기자 질의 v2 30문항을 보존하고 단수·표 간 복수·표 내 분류 비교·동명 표 확인 질문을 합해 1,104문항을 구성합니다. 단수와 표 간 복수에서 349개 표를 모두 다루며, 분류값이 하나인 표 1개는 같은 표 내 두 분류 비교에서 제외합니다. 생성기·전수 검증기·변조 탐지 테스트·실제 API 실행기를 함께 제공합니다. 카탈로그 명칭 기반 공개 개발 회귀셋이며 자유 자연어 일반화 성능이나 수치·그래프의 정확도를 뜻하지 않습니다. 실패 실행은 `evaluation_runs/`에 진단 JSON과 종료 로그로 기록합니다. 최종 Markdown은 1,104문항이 모두 통과한 경우에만 전체 질문과 기대·실제 결과를 포함해 저장합니다.

명시한 정본 표 이름은 분류와 기간 지시에서 분리합니다. 표 이름에 포함된 역사 연도, 분류 코드와 분류 이름의 기준 연도를 사용자 조회 기간으로 해석하지 않습니다. 각 표의 대표 분류를 기본으로 사용하고 명시한 복수 분류와 고정 분류는 메타데이터 코드로 조합합니다. 여러 표의 일부에 붙인 ID는 해당 표만 구분하며, 공백만 다른 정본 이름은 원래 표기를 먼저 확인합니다.

## 보고서형 고급 통계 그래프

조회 결과의 그래프 편집 워크스페이스에서 오른쪽 **고급 차트 · 인쇄 · 출처**를 펼치세요. 12개 차트 구성과 별도의 6개 디자인, 다중 패널·이중 축·기여도·워터폴·산점도/OLS·제공된 신뢰구간 등 13종을 지원합니다. 제목·축·선·색·폰트·출처·각주를 직접 편집하거나 그래프 아래 자연어 입력으로 지시하고 PNG/SVG/PDF/JSON을 저장할 수 있습니다. 전망값과 신뢰구간은 생성하지 않으며 실제 제공한 자료만 표시합니다. JSON 복원은 동일 원자료와 버전 명세를 검증합니다. 일부 ECharts/인쇄 스타일은 지원하지 않는 이유를 알립니다.

[구현 결과와 제한사항](docs/chart_implementation_report.md), [아키텍처](docs/advanced_chart_architecture.md), [공통 명세](docs/chart_specification.md), [샘플 분석·템플릿](docs/chart_templates.md), [편집 명령](docs/chart_edit_commands.md), [품질·실측](docs/chart_quality_validation.md), [기존 명세 마이그레이션](docs/chart_migration.md)을 참고하세요. 합성 자료로 12종 예시 파일을 생성하는 명령은 `scripts/render_report_examples.py`입니다. PDF는 `output/pdf/statbridge-report-template-examples.pdf`에 생성됩니다.

[네 표 요청 별도 증강셋](eval/reporter-table-discovery-30/v3-four-tables/README.md)은 원본 v3를 유지하면서 12개 주제 조합의 문장형·번호형·ID 선행형 36문항을 추가합니다. ID를 제목 앞뒤에서 해당 표에 연결하고 다음 표의 ID가 현재 표에 섞이지 않도록 검증합니다. 네 표·네 계열·정확한 API 파라미터와 기간 대기 상태가 모두 일치한 36/36 실행에만 최종 보고서를 저장합니다.

## 그래프 편집 워크스페이스

실행 화면에서 로그인 또는 회원가입을 선택하세요. 테스트 아이디 `test1`·`test2`·`test3`의 비밀번호는 모두 `1234`입니다. 로그인은 12시간 후 만료되고, 계정별 수정 그래프는 최대 5개 저장할 수 있습니다. 같은 그래프 재저장은 기존 항목을 갱신합니다. 상단 분석 보관함에서 다시 열거나 삭제할 수 있습니다. 서버 API도 로그인과 그래프 소유권을 검사합니다. [인증·계정 격리 검증](docs/account_auth_validation.md)을 참고하세요.

그래프를 생성하면 데이터·중앙 그래프·속성의 세 패널과 하단 자연어 입력을 사용합니다. 설정을 바꾼 상태에서 계속 수정하고 최근 20개 변경을 되돌리거나 다시 실행할 수 있습니다. 분석 저장은 그래프를 계정에, 대화와 편집 기록을 이 브라우저에 보관합니다. JSON 파일은 파일 내보내기에서 별도로 내려받습니다. 저장 자료는 최신 통계 자동 조회가 아닌 저장 당시 스냅샷입니다.

[사용 흐름](docs/chart_workspace_ux.md), [종합 검증](docs/chart_ui_validation_report.md), [실행 증거 및 제한사항](docs/chart_e2e_evidence.md), [디자인 비교](docs/chart_template_comparison.md), [상태 검증](docs/chart_edit_state_validation.md)을 참고하세요. 실제 API 검증 실행기는 `scripts/validate_chart_workspace_live.py`이며 증거는 기존 ignored `evaluation_runs/chart_workspace_live/`, `evaluation_runs/chart_workspace_browser/`에 보관합니다.

## 2026-10-12 업데이트

통합 그래프 워크스페이스, 12시간 로그인·계정별 최대 5개 저장, 반복 편집 렌더링 안정화와 CMD 동기화는 [오늘 작업 정리](docs/implementation/2026-10-12-workspace-auth-render-sync.md)를 참고하세요. 자연어 편집은 그래프 하단 상시 입력창으로 연결하며 별도 채팅 창을 기본 편집 동선으로 사용하지 않습니다. 이전 148종 이미지 대신 보고서 표기를 참고해 만든 화살표 2종을 제공합니다.

Windows 첫 설치와 기존 설치의 의존성 검사 보완 및 새 환경 검증은 [의존성 검증 기록](docs/implementation/2026-10-12-dependency-clean-install-validation.md)을 참고하세요.

역질문으로 실패 작업을 이어가는 흐름, 출력·수정 GPT-5.4 설정, 참고 이미지/PDF 업로드는 [구현 및 검증 기록](docs/implementation/2026-10-12-agent-recovery-openai-reference.md)을 참고하세요. 키는 루트 .env의 OPENAI_API_KEY에 설정하고 재시작합니다.

## 그래프 대화와 편집 기록

그래프 워크스페이스의 왼쪽에는 데이터와 편집 설정, 오른쪽에는 그래프별 채팅이 있습니다. 직접 바꾼 설정도 편집 기록에 남습니다. `새 채팅`이나 새 분석을 시작하면 이전 대화를 이 브라우저에 임시 보관하며, `분석 보관함`에서 다시 열거나 삭제할 수 있습니다. 대화는 이 브라우저의 로그인 계정별로 저장되며 다른 PC와 자동 동기화되지 않습니다. 대화 저장 시 서버 그래프 저장도 시도합니다(계정당 기존 한도 5개). 자세한 동작과 검증은 [그래프 대화 작업 기록](docs/implementation/2026-10-13-graph-chat-workspace.md)을 참고하세요.

로고·분석 홈 또는 새로고침은 입력과 출력 그래프를 비우고 새 분석 화면으로 돌아갑니다. 이전 대화는 저장한 대화에서 명시적으로 다시 열 수 있습니다.

`전체 실행 근거 보기` 또는 워크스페이스의 `실행 흐름`에서 분석·출력·편집의 실제 실행 단계와 데이터 근거를 확인할 수 있습니다. 기록은 새 분석/편집부터 누적되며, 이전 버전의 저장 그래프에는 기록이 없을 수 있습니다. 여러 계열의 개별 그래프는 중앙 영역에서 스크롤해 확인합니다.

349개 표의 공통 이름 검색, 누락 분류 안내와 오류별 복구 화면은 [2026-10-13 변경 기록](docs/implementation/2026-10-13-catalog-recovery-349.md)을 참고하세요. `need_details` 응답은 표·기간을 유지한 채 실제 분류 입력을 기다립니다.

그래프 화면은 계열 수에 따라 확대됩니다. [계열 수별 크기 변경 기록](docs/implementation/2026-10-13-chart-series-size.md)을 참고하세요.

차트 종류 제한과 출처·축 간격 수정은 [차트 배치 변경 기록](docs/implementation/2026-10-13-chart-caption-layout.md)을 참고하세요.

실제 조회 가능한 추천 질문, 메뉴 정리와 PNG 저장 동작은 [추천 질문·PNG 변경 기록](docs/implementation/2026-10-13-examples-menu-png.md)을 참고하세요.


### 카탈로그 근거 선택과 지표 보완 질문 (2026-10-13)

자연어 조회는 이 체크아웃의 `stat_language_dictionary.json`에 등록된 표와 분류를 선택합니다. 동명이표의 잔액/신규취급액 구분에는 같은 체크아웃의 `data/processed/bok_table_master.csv` 계보를 사용합니다. 평가 데이터는 실행 코드에서 읽지 않습니다. 공통 수식어를 가진 여러 항목, 금액/물량, 금리의 신규취급액/잔액 기준을 각각 보존하며 지원하지 않는 주기·지역·차주·기관의 지표를 인접한 표로 대체하지 않습니다.

`POST /api/query`의 `no_match` 응답에는 `requiresQueryRefinement: true`와 `refinementQuestion`이 추가됩니다. UI는 해당 지표를 보완할 입력란을 표시합니다. 기존 그래프와 대화는 유지하며, 보완된 질문은 새 요청으로 보내 이전 확정 조건을 잘못 적용하지 않습니다. 호출 장애의 다시 시도 버튼과 지표 보완 질문은 별도로 처리합니다.

공개 reporter200 평가 재현 도구는 `scripts/evaluate_reporter200_local.py`입니다. `--goldset-root`, `--source-catalog`, `--output-dir`를 지정하고 모델 비사용 비교에는 `--offline`을 추가합니다. 통계표 탐색 평가이므로 실제 `/api/query`를 `execute=false`로 호출하고 수치 조회와 출력 실행은 차단합니다. 원본 동결 점수와 local1의 동일 분류명에 맞춘 점수를 모두 보관합니다. 카탈로그와 골드의 원본은 수정하지 않습니다.

## 간소화된 분석 흐름

조건이 충분한 질문은 자료 조회 후 기본 그래프까지 자동 생성합니다. 입력이 모호하면 필요한 조건만 확인하고, 지원되지 않는 그래프 요청은 조회 자료를 보존한 채 선택 화면을 표시합니다. 명확한 기본 색상·HEX·RGB는 추가 색상 확인 없이 적용합니다. 그래프 종류와 제목·색상은 생성 후 왼쪽에서 수정하며 디자인 미리보기는 접힌 메뉴에 있습니다.

`POST /api/output`의 선택적 `quick_output: true`는 기본 그래프·관측값 기반 존댓말 요약을 모델 호출 없이 생성합니다. 원래 질문에 명시한 지원 차트 종류를 유지하고, 복합 차트에는 설정 선택을 요구합니다. 요청·출처·차트 적합성 검증을 생략하지 않습니다. 이 필드의 기본값은 false로 기존 호출 계약을 유지합니다. `/api/query`의 `execute=false` 계획 조회·골드 평가 경로는 변경하지 않았습니다.

[워크플로우 간소화와 200문항 검증](docs/implementation/2026-10-14-workflow-simplification.md)에 변경 범위와 평가 한계를 기록합니다.

## 보고서용 표 작성

분석 결과의 **그래프 / 표** 버튼으로 조회한 관측값을 표로 확인합니다. 질문에 "표로 보여줘" 또는 "비교표를 만들어줘"를 넣으면 표 화면을 먼저 엽니다. 왼쪽에서 제목·행/열 배치·항목/순서·소수점·최근 시점 수·최신값 강조·추가 주석을 설정한 뒤 **표 설정 적용**을 누릅니다. 표 채팅은 "소수점 한 자리로 바꿔줘", "최근 4분기만 보여줘", "기간을 행으로 바꿔줘"처럼 지원하는 표시 설정을 변경합니다. 불명확한 요청은 현재 표를 유지하고 가능한 수정 예를 안내합니다.

표는 현재 분석의 조회값(또는 명시적으로 적용한 서버 계산값)을 재사용하며 모델이 수치를 생성하지 않습니다. 월·분기·연 자료는 주기별로 나누고, 임의의 집계·보간은 하지 않습니다. 결측값은 `—`로 표시합니다. 표 설정은 분석 저장·JSON 복원·되돌리기에 포함되며 대화는 기존과 같이 브라우저에 보관됩니다.

표 CSV는 화면의 행·열·항목·기간·표시 자릿수와 같은 값으로 저장합니다. CSV는 색상·글꼴·셀 서식을 저장하지 못하므로 서식이 필요하면 XLSX·PNG·PDF를 사용합니다. XLSX는 조회 수치의 원래 정밀도를 유지하고 숫자 셀과 표시 자릿수를 분리합니다. PNG·PDF는 지정 자릿수로 표시하며 긴 표를 행·열 방향으로 분할합니다. 여러 PNG 페이지는 ZIP으로 받습니다. 인쇄 표가 120페이지를 넘으면 기간·항목을 줄이도록 안내합니다. 증감·증감률 요약표와 월→연 집계는 이번 범위에 포함하지 않습니다.

API: `/api/output/edit`의 `set_table` 명령(검증된 `STYLE_EDIT params.patch`) 및 `/api/table/export` (`edit_session_id`, 최신 `revision`, `format=xlsx/csv/png/pdf`). 기존 세션 소유권·로그인 검사를 적용하며 외부 자료를 재조회하지 않습니다. XLSX는 표준 OOXML로 생성하므로 실행 환경에 추가 Excel 라이브러리가 필요하지 않습니다.

분석 요청과 자동 출력은 합쳐 20초 동안 기다립니다. 결과·역질문·조회 조건 안내가 도착하지 않으면 질문과 기존 분석을 유지하고 통계표 직접 선택·질문 수정·재시도를 안내합니다. 지연을 no_match로 판정하지 않으며, 늦은 응답은 현재 화면을 덮어쓰지 않습니다. 브라우저 대기를 종료하는 기능이며 서버에서 이미 시작한 작업의 강제 종료를 보장하지는 않습니다.

참고 그림 첨부 후 `이렇게 그려줘`로 형식을 적용할 수 있습니다. 현재 조회한 수치·기간·지표 이름을 유지하며 변경 기록은 한국어로 표시합니다. 실제 한국은행 그림 3개를 사용한 진단과 반복 실패의 한계는 [참고 그래프 검증 기록](docs/implementation/2026-10-14-vlm-reference-harness.md), 실행 방법은 [진단 하네스](eval/chart-reference/v1/README.md)를 확인하세요.

새 출력의 기본 디자인은 `스냅샷 보고서형`입니다. 마지막 값 표시, 간결한 범례, 좌우 축, 화면 폭별 날짜 눈금과 PNG·SVG·PDF 표현을 현재 조회 자료에 맞춰 사용합니다. 기존 저장 설정과 원자료는 유지합니다. [스냅샷 품질 변경·검증 기록](docs/implementation/2026-10-14-snapshot-report-quality.md)과 [실제 참고 그림 진단](eval/chart-reference/snapshot-v1/README.md)을 확인하세요.

## 첨부 표 스타일 팩

표 보기의 **보고서 표 편집 → 표 양식**에서 기본 3선형·다단 머리글·시계열 비교·부록형·항목 강조·주석 결합 6종을 선택합니다. `set_table`의 `params.patch.template`은 `default` 또는 `BOK-T01`~`BOK-T06`, `emphasized_labels`는 조회된 강조 항목 이름 목록입니다. 원자료 수치를 유지하며 이전 저장 설정도 열 수 있습니다. 첨부 시안 기반 제안 양식으로, 공식 인증 양식이나 전망 생성 기능은 아닙니다. [구현 및 검증](docs/implementation/2026-10-14-bok-table-style-pack.md).

## 혼합 차트 선택

그래프 편집의 차트 종류에서 선·막대·영역 혼합 7종을 선택하고 지표별 모양을 수정합니다. 데이터의 주기·단위·시점·지표 수를 충족하는 조합만 표시합니다. 실제 관측쌍이 있는 두 지표에는 산점도·회귀선도 표시합니다. `set_series_chart_types` 명령은 `STYLE_EDIT params.types={조회된 지표 이름: line/bar/area}`로 모양을 일괄 지정하며 수치를 변경하지 않습니다. [점검·검증 기록](docs/implementation/2026-10-14-mixed-chart-and-output-audit.md).


### 보고서 검토 후 보완 (2026-10-15)

- ID에 소괄호 또는 대괄호를 붙여도 같은 통계표·분류로 해석합니다. 요약은 현재 표시 계열의 원자료만 사용합니다. 연%·연리% 차이는 %p, 기준년 지수 차이는 포인트로 표시합니다.
- 월·분기 분리 패널은 각 주기의 독립 범주 축을 사용합니다. 축약 종료 월과 최신 제공 시점을 기준으로 한 최근 N년을 해석합니다.
- 표는 금리·지수 기본 2자리, 중복 없는 기관 출처, 표시명 축약·확대 보기, 표 번호, 인쇄 배치를 지원합니다. 화면의 표 문서를 그대로 내보냅니다. PDF는 고정 5열 대신 폭 기반으로 분할하고 Excel에는 인쇄 영역·반복 머리글·배율을 기록합니다.
- `TableOptions.comparison`은 `none`, `previous_change`, `yearly_change`, `period_change`, `period_growth`를 지원합니다. 계산 열은 지표를 행으로 놓을 때만 사용할 수 있고, 기준 관측값이 없으면 결측으로 남깁니다. 증가율의 기준값이 0 이하이면 자동 계산하지 않습니다. 원자료를 변경하거나 다른 주기를 합산하지 않습니다.
- `POST /api/report/interpret`: 로그인한 편집 세션의 `edit_session_id`, 최신 `revision`, 선택적 ISO 날짜 `as_of`를 받습니다. 응답은 검토용 `headline`, `paragraphs`, 근거 ID가 있는 `claims`, `passages`, `limitations`, `needsHumanReview`를 제공합니다. 계열·기간 변경 시 기존 초안은 화면에서 해제됩니다.
- 기본 빠른 출력은 계속 모델 문장 작성 없이 관측 요약을 만듭니다. 별도 초안 버튼에서만 모델 작성을 요청합니다. 검수 원문이 없으면 관측 사실만 허용하며, 모델 응답 검증 실패 시 서버 관측 문장으로 대체합니다. 모든 초안은 담당자의 원문·문장 검토가 필요합니다.
- 원문 검색은 선택 설정 `STATBRIDGE_REPORT_PASSAGES`의 JSONL 인덱스만 읽습니다. 각 레코드는 `id`, `title`, `publication_date`, `period_start`, `period_end`, 원본 PDF 물리 페이지 `page`, `text`, 원본 위치 `reference`, `kind` (`observation/factor/forecast`), `verified:true`가 필요합니다. **본문·각주·그림·표 연결과 개인정보 제거를 원본 PDF로 대조한 발췌만** 등록합니다. 에이전트 대조는 `verification_method`로 표시하고 `human_reviewed:false`를 유지합니다. 담당자 검수 전 자료를 사람의 승인 완료로 표시하지 않습니다. 자동 OCR/추정 md를 검수 근거로 승격하지 마세요. 설정이 비어 있으면 프로젝트 `.venv/cache/report-evidence/reviewed.jsonl`을 확인합니다. 인덱스는 서버 로컬 파일이며 공개 저장소에 원문을 포함하지 않습니다.
- 발간일이 `as_of` 이후이거나 분석 기간과 겹치지 않는 발췌는 검색에서 제외합니다. 기본 기준일은 조회 종료일이며, 사용자가 이후 기준일을 지정하면 사후 해석임을 표시합니다. 원본 PDF 자동 수집·OCR·검수, 경제 원인 자체의 자동 판정, 의미상 원문 함의의 완전한 검증은 구현했다고 주장하지 않습니다.
- 공식 자료의 잠정·속보·전망 상태, 상하위 분류·공식 소계, 복합 주기 열의 집계 정의는 원천 메타데이터와 담당자 검수 없이는 만들지 않습니다. 다른 주기 표는 별도 섹션 정책을 유지합니다.
