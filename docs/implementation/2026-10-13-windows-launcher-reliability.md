# Windows CMD 실행 환경 점검과 수정

## 확인한 대상

- `StatBridge-local1`: 현재 Git 작업 폴더. 기존 미커밋 작업을 유지했습니다.
- `StatBridge1/StatBridge-official`: Git 메타데이터가 없는 실행용 복사본. 바깥 `StatBridge1`의 CMD와 `runtime_scripts`, 기존 별도 backend requirements도 확인했습니다.

## 확인·재현한 문제

1. local1 기본 CMD에서 `Port 8000 is in use`를 재현했습니다. 이전 프로세스 확인이 WMI/CIM에 의존했고 상태를 지우는 경로가 있어 정상 종료를 확인하지 못한 서비스가 남을 수 있었습니다. 현재 PC에서 해당 폴더의 실행 경로와 생성 시각을 확인한 이전 API·UI·MCP 기록을 복구한 후 기본 포트에서 재시작했습니다.
2. StatBridge1에서 실행 중인 Vite 네이티브 파일 때문에 `npm ci`가 `EPERM`으로 실패했습니다. 설치 후에 서비스를 종료하던 순서를 설치 전에 종료하도록 바꿔 재설치·시작을 확인했습니다.
3. 두 가상환경의 FastAPI, Pydantic, LangGraph 버전이 달랐습니다. 핵심 Python 의존성은 검증한 버전으로 고정하고 설치 버전·`pip check`·실제 import를 확인합니다. [FastAPI 버전 관리 지침](https://fastapi.tiangolo.com/deployment/versions/)도 테스트한 버전 고정을 권장합니다. 전이 의존성 전체를 고정한 lock은 아니며 핵심 직접 의존성의 고정입니다.
4. `RUN_FRONTEND.cmd`의 pnpm 의존과 `runtime_scripts`의 전달받지 않은 `PYTHON_EXE`, 바깥 테스트 CMD의 옛 가상환경 경로를 확인했습니다. 실행 CMD는 정본 START로, 테스트·벡터 CMD는 정본 도우미로 연결했습니다. 테스트 CMD는 pytest가 없으면 설치하고, 가상환경 자체가 없으면 START 실행을 안내합니다.
5. CMD의 delayed expansion, findstr 키 재파싱, 필수 KOSIS/NCP 키 및 첫 벡터 생성 강제가 다른 PC의 경로·설정 차이를 실행 실패로 만들 수 있었습니다. `!`를 포함한 경로는 stdlib Python으로 처리하고 키는 dotenv로 읽으며 값은 출력하지 않습니다. NCP 별칭도 지원합니다. 키와 벡터 없이 기본 화면을 실행하고 사용할 기능의 키를 입력하도록 분리했습니다.
6. 프런트 패키지 이름·버전만으로는 복사된 네이티브 패키지를 검증하지 못했습니다. 설치 확인에 OS·아키텍처를 포함하고 실제 Vite 실행을 확인하며 실패 시 `npm ci --include=dev --include=optional`로 복구합니다. [Vite 실행 요구사항](https://vite.dev/guide/)에 맞춰 Node 20.19+ 또는 22.12+를 검사합니다.
7. 사용자 지정 포트가 인증/CORS 허용 목록에 반영되지 않던 경로를 수정했습니다. 허용 호스트는 localhost/127.0.0.1로 유지하며 런처가 선택한 UI/API 포트를 적용합니다. StatBridge1의 쿠키 이름도 구분합니다.
8. SQLite 트랜잭션 context가 연결을 닫지 않아 Windows 파일 잠금이 남을 수 있었습니다. commit/rollback 후 연결을 명시적으로 닫도록 수정하고 계정·동시 저장·파일 이동을 검증했습니다.

## 수정한 실행 흐름

`START_STATBRIDGE.cmd → bootstrap.py → 이 PC의 .venv 확인/보존·재생성 → 이 프로젝트 서비스 종료 → Python 의존성 확인·설치 → Node·프런트 패키지 확인·설치 → 설정 상태 확인 → portable_runtime.py로 API·MCP·UI 시작`

프로세스 식별은 Win32 API로 실행 파일과 생성 시각을 확인합니다. PID가 재사용되었거나 다른 프로젝트의 상태이면 종료하지 않으며, 확인 권한이 없으면 기록을 유지하고 안내합니다. 시작 중 실패한 새 자식 프로세스는 정리합니다. `.venv`가 이 프로젝트 밖을 가리키는 링크이면 대상 폴더를 임의로 이동하지 않고 안내합니다.

환경 확인 전용 `CHECK_STATBRIDGE.cmd`는 설치·서비스 시작·종료를 하지 않습니다. Python이 전혀 없을 때도 확인 모드에서는 winget 자동 설치를 하지 않습니다. 인덱스 생성은 `START_STATBRIDGE.cmd --build-index`로 명시적으로 실행합니다.

## 검증 결과

| 검증 | local1 | StatBridge1 |
|---|---|---|
| 전체 Python 회귀 | 781 passed, 355 subtests passed | 772 passed, 355 subtests passed |
| 추가 KOSIS 키 미설정 안내 | 1 passed | 1 passed |
| 런처·환경·인증 등 집중 회귀 | 34 passed | 34 passed |
| 공개 v4.1 자료 검사 | VALIDATION OK | VALIDATION OK |
| npm production build | 성공 | 성공 |
| pip check 및 런처 환경 검사 | 성공 | 성공 |
| 실제 CMD 시작·재시작 | 성공 | 성공 |
| 실제 브라우저 로그인·349개 카탈로그 | 성공 | 성공 |
| MCP stdio 도구 목록·healthcheck | 6개 도구, 349개 표, 오류 없음 | 6개 도구, 349개 표, 오류 없음 |

전체 회귀는 외부 API 키를 비운 모의 호출 환경입니다. 전체 회귀 이후 키 미설정 안내의 추가 테스트를 별도로 실행했습니다. production build에는 기존 500 kB 이상 bundle 경고가 있습니다.

초기 전체 실행에서 기존 CMD 문자열과 키/루트 alias 규칙을 검사하던 3개 테스트가 실패했습니다. 새 실행 경로와 환경변수 우선순위, CHECK alias에 맞게 테스트를 갱신한 후 위 전체 결과를 확인했습니다.

가상환경·node_modules·실제 .env·계정·저장 그래프를 복사하지 않은 별도 복사본 `팀원 PC !`에서도 최초 CMD 설치와 시작을 확인했습니다. Windows Python 3.11.9 x64와 Node 24.21.0에서 한글·공백·느낌표 경로, 키/벡터가 없는 환경을 검증했습니다. 해당 복사본의 브라우저에서 로그인, 349개 카탈로그, 통계표 ID 탐색과 수치 조회 실패 시 작업 보존을 확인했습니다.

실제 실행 포트는 local1 API/UI 8000/5173, StatBridge1 API/UI 8001/5174입니다. 별도 검증에는 8010/5180, 8011/5181, 신규 설치 8012/5182를 사용했습니다. 다른 PC의 실제 오류 메시지, OS 설치 정책, 보안 프로그램, 전혀 Python/Node가 없는 PC에서의 winget 설치는 직접 검증하지 못했습니다.

## 팀원 전달·실행

1. 소스 폴더 전체를 압축 해제합니다. `.venv`, `.venv.invalid.*`, `node_modules`, 실제 `.env`, 계정 DB와 저장 그래프는 전달하지 않습니다.
2. 각 폴더 루트의 `START_STATBRIDGE.cmd`를 실행합니다. 최초 설치에는 인터넷과 패키지 설치 권한이 필요합니다.
3. 실제 조회·모델 기능에 필요한 키는 해당 프로젝트의 `.env`에 입력하고 START를 다시 실행합니다. 키가 없는 KOSIS 조회는 화면에 `.env`와 `KOSIS_API_KEY` 입력·재실행 방법을 안내합니다.
4. 실패하면 `CHECK_STATBRIDGE.cmd`를 실행하고 console 메시지와 `.venv/cache/evaluation_runs/`의 해당 서비스 로그를 확인합니다. 키 값은 공유하지 않습니다.

이 변경은 ai-assisted이며 원격 게시나 merge는 하지 않았습니다.
