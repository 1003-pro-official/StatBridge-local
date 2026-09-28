# StatBridge

한국은행 KOSIS 통계표를 자연어로 찾고, 사용자가 선택한 계열을 그래프로 확인하는 프로젝트입니다. 349개 표 목록과 347개 로컬 CSV를 사용합니다.

## 구성

| 경로 | 역할 |
|---|---|
| `src/backend/statbridge_mcp/` | 표 검색, 메타 조회, 로컬 CSV·KOSIS 자료 조회, MCP 도구 |
| `src/backend/query_api.py`, `analysis_service.py` | 화면용 검색·분석 API |
| `src/agent/statbridge_agent/` | HCX 질의 해석과 Backend 후보 검색 파이프라인 |
| `src/agent/frontend/` | 후보·계열 선택, 그래프, 관측값 표를 보여주는 React 화면 |
| `data/processed/` | 이전 코드에서 가져온 349표용 작은 메타 인덱스 |
| `data/tables/` | 기존 347개 CSV. 이식 과정에서 다시 복사하지 않음 |
| `eval/golden-set/` | 한국은행 간행물 기반 150개 평가 사례와 30개 고정 그래프 fixture |

## 실행

Python 3.12+와 Node.js·pnpm이 필요합니다. 프로젝트 루트에서 Backend 의존성을 설치합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r src/backend/requirements.txt
```

Windows PowerShell에서는 `py -m venv .venv` 후 `.venv\Scripts\python.exe -m pip install -r src\backend\requirements.txt`를 사용합니다.

검색·분석 API를 실행합니다.

```bash
.venv/bin/python src/backend/query_api.py
```

다른 터미널에서 화면을 실행하고 `http://localhost:5173`을 엽니다.

```bash
cd src/agent/frontend
pnpm install --frozen-lockfile
pnpm dev
```

PowerShell의 API 실행 경로는 `.venv\Scripts\python.exe src\backend\query_api.py`입니다. Vite가 `/api/query`와 `/api/analyze`를 로컬 8000번 API로 전달합니다.

MCP stdio 서버는 별도로 실행할 수 있습니다.

```bash
.venv/bin/python src/backend/server.py
```

제공 도구는 `search_tables`, `get_meta`, `fetch_data`와 상태 확인용 `healthcheck`입니다. 검색은 349개 표를 대상으로 하며, 결과의 `local_csv_available`로 2개 목록 전용 표를 구분합니다. `fetch_data`가 로컬 CSV에서 값을 찾지 못하면 KOSIS API를 사용하므로 그때 `KOSIS_API_KEY`가 필요합니다.

## 현재 범위와 확인

화면은 후보를 보여준 뒤 사용자가 표·항목·분류·기간을 선택하게 합니다. `/api/analyze`는 선택 ID를 검증하고 KOSIS를 기본으로 한 번 조회합니다. KOSIS 실패 시 로컬 수치를 자동으로 대신 표시하지 않으며, 사용자가 직접 로컬 저장본을 선택할 수 있습니다. HCX 해석 코드는 별도로 존재하지만 현재 화면 API 경로에는 연결되지 않습니다.

```bash
PYTHONPATH=src/backend:src/agent .venv/bin/python -m pytest -q tests
cd src/agent/frontend && pnpm build
```

Python 테스트 실행에는 `pytest`가 필요합니다. 설치 환경에 없으면 `.venv/bin/python -m pip install pytest`를 실행합니다.

## 보고서 기반 골든셋

한국은행 정기 간행물 6종의 질문을 사용한 150개 평가 코퍼스는 [`eval/golden-set`](eval/golden-set/README.md)에 있습니다. 30개 고정 그래프 데이터, 출처, 평가 범위와 실행 방법을 포함합니다.

```bash
.venv/bin/python tools/evaluate_golden_set.py
```
