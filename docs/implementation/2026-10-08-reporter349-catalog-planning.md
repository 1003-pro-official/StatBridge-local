# 349개 표 조회 계획과 기자 골든셋 v3

정본 표 이름에 포함된 분류명·연도가 사용자 분류·기간 지시로 해석되고, 복수 요청이 일부 계열로 축소되는 문제를 수정했다. 명시한 표 참조와 사용자 지시를 분리하고 분류별 요청값·고정값의 조합을 유지한다. 일부 표의 ID는 해당 표만 구분하며 공백만 다른 정본 이름은 정확한 표기를 우선한다.

공개 카탈로그 기반 기자 질문 v2 30개를 보존하고 v3 1,104문항을 추가했다. 단수 349, 표 간 비교 349, 표 내 분류 비교 348, 동명 확인 28, v2 원본 30이다. 분류값이 하나인 표 1개는 표 내 비교의 명시적 예외다. 생성기, 전수 검증기, 실제 API 실행기 및 변조 탐지 테스트를 제공한다. 실행기에는 질문만 전달하고 추론 완료 후 골드로 채점한다.

## 검증

- 실제 FastAPI TestClient POST /api/query(query, execute=false): 1104/1104 통과. 상태·표·항목·분류·주기·기간·exact params·역질문 및 기간 입력 대기 경계를 확인했다.
- pytest: 519 passed, 355 subtests passed.
- v4.1, 기자 v2, 기자 v3 검증기 통과. v3 전수 오류 0건.
- pnpm build와 git diff --check 통과. 기존 대형 번들 경고가 있다.
- 패치 중 정답과 채점 기준은 유지했다. 실패 실행은 진단 JSON을 보존하고 최종 Markdown은 1104/1104일 때만 저장한다.

수치 조회, CSV 값, 그래프 생성, 수정이 편집은 이번 평가 범위가 아니다. 기존 NCP 분류·검색 fallback은 실제 설정된 환경에서 사용했다. 공개 dev / ai-assisted / human_approved=false이며, 카탈로그 명칭 기반 구조적 회귀 결과로 블라인드 자연어 성능을 뜻하지 않는다. 실행 로그와 결과는 Git에서 제외된 evaluation_runs/에만 둔다.

## 재현

```powershell
$env:PYTHONPATH='src/backend;src/agent'
.venv/Scripts/python.exe -m pytest -q tests eval/table-discovery/v4.1/tests eval/reporter-table-discovery-30/v2/tests eval/reporter-table-discovery-30/v3/tests
.venv/Scripts/python.exe eval/reporter-table-discovery-30/v3/scripts/validate.py
.venv/Scripts/python.exe eval/reporter-table-discovery-30/v3/scripts/evaluate_runtime.py
```

AI-assisted 변경이며 사람의 검토와 승인이 필요하다.
