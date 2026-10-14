# CSV 화면 일치와 분석 대기 20초 제한

ai-assisted 구현 기록입니다. local1 및 StatBridge1 보관본에 동일하게 적용했습니다. 비밀 설정·계정 DB·저장 분석을 복사하거나 기존 분석을 삭제하지 않았습니다. 추가 운영 의존성 및 CMD 변경은 필요하지 않았습니다.

## 수정한 문제

표 CSV가 원래 정밀도의 숫자를 출력하여 화면의 반올림·천 단위 구분·0 표시와 달랐습니다. 표 탭에서도 상단 파일 메뉴가 기존 그래프용 CSV 경로를 사용할 수 있었습니다.

CSV를 현재 표의 제목·주기·기간·헤더·항목 순서·행열 배치·표시 숫자로 구성하도록 변경했습니다. 표 전용 CSV 버튼과 상단 CSV 메뉴가 같은 표 출력 경로를 사용합니다. 표 화면의 파일 메뉴는 XLSX·CSV·PNG·PDF·JSON을 제공하며 지원하지 않는 SVG를 표시하지 않습니다. CSV는 색상·글꼴·셀 서식을 저장하지 못하므로 해당 서식은 XLSX·PNG·PDF로 제공합니다. XLSX는 기존처럼 조회값 정밀도를 보존합니다.

서버의 표시 반올림도 브라우저 표시와 일치시켰습니다. 1.25 → 소수점 1자리 1.3, -1.25 → -1.3, 2.675 → 소수점 2자리 2.68을 확인했습니다. 원래 관측값을 수정하지 않습니다. CSV의 텍스트 수식 주입 방어와 UTF-8 BOM은 유지합니다.

분석 요청에는 기존의 브라우저 대기 제한이 없었습니다. `withAnalysisDeadline`을 추가하여 조회 요청부터 자동 출력까지 합쳐 20초 예산을 사용합니다. HTTP 헤더뿐 아니라 응답 본문 읽기도 같은 예산에 포함합니다. 수동 출력·캐시된 자료 출력 재시도에도 20초 제한을 적용합니다.

시간 초과는 `request_failed` / `recovery.issue=timeout`입니다. 조회하지 못했다고 `no_match`로 판정하거나 데이터·지표·기간을 임의로 변경하지 않습니다. 질문·기존 그래프·표를 보존하고 통계표 직접 선택 / 질문 수정 / 같은 요청 다시 시도를 표시합니다. 브라우저 대기를 종료하며, 서버에서 이미 실행 중인 작업을 강제로 종료한다는 보장은 하지 않습니다.

늦은 응답은 완료된 Promise를 다시 완료할 수 없고, 조회 단계 이후의 취소 확인으로 시간 초과 뒤 자동 출력이 새로 시작되는 것도 막습니다. 표 탐색기·카탈로그·백엔드의 질의 해석·지원 표 선택 규칙은 변경하지 않았습니다.

## 검증

- local1 최종 전체 Python 회귀: 915 passed, 355 subtests passed, 470.24초. StatBridge1 전체 회귀는 별도로 재실행하지 않았으며 동일 코드의 관련 61개 테스트와 프런트엔드 101개를 자체 환경에서 확인했습니다.
- 두 폴더 각각 Python 관련 회귀 61 passed: 표·CSV·출력 자동화·프런트엔드 API 연결 계약.
- 두 폴더 각각 프런트엔드 전체 101 passed, TypeScript / Vite build 성공(652 modules). 기존 500kB 번들 경고는 남아 있습니다.
- 두 폴더 v4.1 형식 검사 VALIDATION OK, dev/test/holdout = 50/70/30. 비공개 정답은 사용하지 않았습니다.
- 운영 상수 20,000ms를 사용한 응답 없는 Promise 검사: 20,014ms에 timeout.
- Node 회귀: 빠른 응답, 취소를 무시하는 작업, 조회+출력의 합산 예산, timeout을 no_match로 오인하지 않는 복구 선택지.
- 실제 local1 화면에서 `대출금리와 생산자 물가를 비교해줘` 요청의 정상 역질문(신규취급액 / 잔액 기준)을 확인했습니다. 항상 시간 초과가 나는 질문이라는 주장은 하지 않습니다.
- 독립적인 임시 UI 검사 페이지에서 그 요청의 응답을 25초 지연시켰습니다. 실제 App·로그인·표시 코드로 StatBridge1의 시간 초과 표시가 20,011ms에 나타났고 분석하기가 다시 활성화되었습니다. 25초 후의 검사 응답은 화면을 덮어쓰지 않았습니다. 이 지연 검사는 실제 제공처 장애를 재현했다는 의미가 아닙니다.
- local1 UI 지연 검사에서는 기존 DT_181Y011 표를 먼저 조회하고 시간 초과 후 그대로 남아 있음을 확인했습니다.
- local1 실제 화면의 분기별 표(4행, 소수점 2자리)를 표 CSV 버튼과 상단 CSV 메뉴로 다운로드했습니다. CSV 헤더·셀을 DOM의 표 헤더·셀과 비교하여 모두 일치했습니다.
- StatBridge1에서는 저장한 결제통화 비교표(4개 계열, 최근 6시점)를 열고 CSV를 다운로드했습니다. 화면 4행·7열과 CSV 셀 전체가 일치했습니다.

임시 검사 페이지는 두 폴더의 실제 실행 화면 변경이나 배포 기능이 아닙니다. 검증 뒤 제거하며 스크린샷·진단 JSON·CSV·평가 산출물은 로컬 캐시에만 보관합니다. 새 계정 생성·기존 분석 삭제·커밋·푸시·PR 변경은 하지 않았습니다.

## 실행

```powershell
$env:PYTHONPATH='src/backend;src/agent'
.venv/Scripts/python.exe -m pytest -q tests/test_report_tables.py tests/test_output_agent_migration.py tests/test_workflow_simplification.py
.venv/Scripts/python.exe -m pytest -q tests eval/table-discovery/v4.1/tests
.venv/Scripts/python.exe eval/table-discovery/v4.1/scripts/validate_v41.py
pnpm --dir src/agent/frontend build
# 프런트엔드 폴더에서
node --experimental-strip-types --test test-*.mjs
```
