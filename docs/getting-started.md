# StatBridge 실행 안내

[프로젝트 소개](../README.md) · [기술 문서](README.md)

## Windows에서 시작하기

1. 저장소를 복제하거나 GitHub의 **Code → Download ZIP**으로 내려받아 압축을 풉니다.
2. 저장소 루트의 [`START_STATBRIDGE.cmd`](../START_STATBRIDGE.cmd)를 실행합니다. 처음에는 인터넷 연결과 패키지 설치 권한이 필요합니다. 실행기는 64비트 Python 3.11~3.13과 Node.js 20.19+ 또는 22.12+ 환경을 확인합니다.
3. 브라우저에서 `http://127.0.0.1:5173`을 엽니다. API 키 없이도 화면과 통계표 카탈로그를 확인할 수 있습니다.
4. 환경 점검은 [`CHECK_STATBRIDGE.cmd`](../CHECK_STATBRIDGE.cmd), 종료는 [`STOP_STATBRIDGE.cmd`](../STOP_STATBRIDGE.cmd)를 사용합니다.

## 데이터와 API 연결

최초 실행 시 [`.env.example`](../.env.example)을 바탕으로 루트에 `.env`가 준비됩니다. Windows에서는 [`EDIT_API_KEYS.cmd`](../scripts/windows/EDIT_API_KEYS.cmd)로 값을 설정할 수 있습니다.

| 사용하려는 기능 | 준비 사항 |
| --- | --- |
| KOSIS에서 원자료 조회 | `KOSIS_API_KEY` |
| CLOVA 기반 질의 해석, 임베딩, 재순위화 | `NCP_CLOVA_API_KEY` |
| 파생지표 계획, 자연어 그래프 편집, 보고서 대화 | `OPENAI_API_KEY` |
| 로컬 원자료 조회 | 별도 공급받은 통계표 CSV를 `data/tables/`에 두거나 `STATBRIDGE_TABLES_DIR`에 경로 지정 |

저장소에는 공개 메타데이터가 들어 있습니다. 원자료 CSV는 별도로 공급하며 KOSIS 조회는 API 키로 사용할 수 있습니다. API 키는 로컬 `.env`에서 관리합니다.

벡터 인덱스가 없으면 사전 기반 검색을 사용할 수 있습니다. NCP 키와 사용 권한을 준비한 후 Windows에서 `START_STATBRIDGE.cmd --build-index`를 실행하면 인덱스 생성을 시도합니다. [Windows 실행 환경 상세](implementation/2026-10-13-windows-launcher-reliability.md)

## 개발 환경에서 수동 실행

다음 명령은 Bash 기준입니다. Python 3.12, Node.js 22.12 이상(22 계열), pnpm 10으로 시작할 수 있습니다. 저장소 루트에서 백엔드 의존성을 설치하고 API를 실행합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r src/backend/requirements.txt pytest
PYTHONPATH=src/backend:src/agent .venv/bin/python -m uvicorn bridge_api:app --host 127.0.0.1 --port 8000
```

다른 터미널에서 화면을 실행합니다.

```bash
cd src/agent/frontend
pnpm install --frozen-lockfile
pnpm dev
```

`http://127.0.0.1:5173`을 엽니다. 개발 서버가 `/api` 요청을 Agent API의 8000번 포트로 전달합니다. Windows PowerShell에서 Python 명령을 실행할 때는 `.venv/bin/python` 대신 `.\.venv\Scripts\python.exe`를 사용하고, `$env:PYTHONPATH = 'src/backend;src/agent'`로 경로를 지정합니다.

### 독립 MCP 서버

외부 MCP 클라이언트에 연결할 경우 저장소 루트에서 stdio 서버를 별도로 실행합니다.

```bash
PYTHONPATH=src/backend .venv/bin/python src/backend/server.py
```

통계 도구는 `search_tables`, `get_table_metadata`, `get_statistics`, `get_statistics_batch`입니다. [MCP 실행 및 도구 상세](implementation/MCP_RUNTIME_GUIDE.md)

## 검증

저장소 루트에서 실행합니다.

```bash
PYTHONPATH=src/backend:src/agent .venv/bin/python -m pytest -q tests eval/table-discovery/v4.1/tests
.venv/bin/python eval/table-discovery/v4.1/scripts/validate_v41.py
(cd src/agent/frontend && pnpm build)
```

외부 KOSIS·NCP 호출과 로컬 원자료 조회는 키와 데이터가 있는 환경에서 별도로 확인합니다. [검증 및 기여 규칙](../CONTRIBUTING.md) · [평가 자료](../eval/README.md)
