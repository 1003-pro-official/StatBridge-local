# 네 표 요청 증강과 ID 연결 패치

제목 앞에 통계표 ID를 놓은 네 표 요청에서, 다음 표의 ID가 현재 표에 연결되어 불필요한 역질문이 발생했다. 제목 바로 앞/뒤에 있는 ID만 해당 표에 연결하고, 상충하거나 연결되지 않은 ID가 있으면 임의의 정본 계획을 확정하지 않도록 수정했다. ID와 전체 제목이 명시된 요청은 따옴표나 괄호가 없어도 처리한다.

## 공개 질문과 검수

[질문 목록](../../eval/reporter-table-discovery-30/v3-four-tables/questions.md)과 [정답·실행 안내](../../eval/reporter-table-discovery-30/v3-four-tables/README.md)를 제공한다. 원본 v3 1104문항은 변경하지 않고 별도 주제 조합 12개 × 문장형·번호형·ID 선행 역순형 3개 = 36문항을 추가했다. 한국은행 기관 코드 301의 서로 다른 표 48개, 총 144개 계열 계획을 다룬다.

36개 질문을 직접 읽고 전체 제목·동명 표 ID·네 표/네 계열·대표 분류·기간 미지정·원래 주기 보존을 대조했다. 동명 본원통화 표는 관측 기간이 다르지만 독립 자료 탐색 요청이므로 공통 기간을 가정하지 않는다. 혼합 주기 조합도 월·분기·연간을 강제로 통일하지 않는다. 공개 dev / ai-assisted / human_approved=false이며 사람의 승인이나 자유 자연어 일반화 성능을 뜻하지 않는다.

## 관측한 검증 결과

| 검증 | 결과 |
|---|---|
| 별도 네 표 증강 실제 API | 최초 35/36 → 패치 후 36/36 (100%) |
| 실제 반환 표 목록 | 36/36, 각 응답에서 정확한 네 표의 ID와 개수 확인 |
| 기존 v3 실제 API 회귀 | 1104/1104, 원본 골드 해시 유지 |
| 전체 pytest | 529 passed, 355 subtests passed |
| v4.1 / v2 / v3 / 별도 증강 전수 검사 | 통과, 별도 증강 오류 0건 |
| pnpm build / git diff --check | 통과, 기존 대형 번들 경고 |

실제 FastAPI TestClient의 POST /api/query(query, execute=false)에 질문만 전달하고 전체 추론 후 고정된 골드로 채점했다. HTTP/Agent/API 상태, 표·계열 집합, exact API params, 기간 입력 대기 및 API 반환 표 목록이 모두 일치해야 통과한다. 골드와 기존 통과 조건은 패치 중 변경하지 않았고 반환 표 목록 검사를 추가했다. 실패 실행은 진단 JSON만 보존하며 36/36일 때만 전체 질문·패치·기대/실제 계획을 담은 최종 Markdown을 저장한다.

실행 결과 원본과 로그는 저장소 규칙에 따라 Git에서 제외한 evaluation_runs/에 로컬 보존한다. 위 표는 PR 검토용 작업 요약이다. 수치 조회·CSV 값·그래프 생성·수정이 편집은 검증 범위 밖이며, 수치 호출과 출력 호출은 각각 0건이다.

## 재현

```powershell
$env:PYTHONPATH='src/backend;src/agent'
.venv/Scripts/python.exe -m pytest -q tests eval/table-discovery/v4.1/tests eval/reporter-table-discovery-30/v2/tests eval/reporter-table-discovery-30/v3/tests eval/reporter-table-discovery-30/v3-four-tables/tests
.venv/Scripts/python.exe eval/reporter-table-discovery-30/v3-four-tables/scripts/validate.py
.venv/Scripts/python.exe eval/reporter-table-discovery-30/v3-four-tables/scripts/evaluate_runtime.py
.venv/Scripts/python.exe eval/reporter-table-discovery-30/v3/scripts/evaluate_runtime.py
```

AI-assisted 변경이며 사람의 diff·골드 검수와 승인이 필요하다.
