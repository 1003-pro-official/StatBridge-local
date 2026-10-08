# v3 별도 네 표 요청 증강셋

원본 v3 1104문항은 그대로 두고 주제 조합 12개 × 표현 3개, 총 36문항을 별도로 구성했다. 서로 다른 표 48개를 다루며 모든 질문은 서로 다른 표 네 개에서 대표 분류 한 계열씩을 요청한다. 표 이름 전체를 적고 동명 표는 ID로 구분한다. 문장형·번호 목록형·ID 선행 역순 목록형을 사용한다.

36개 원문을 직접 읽어 제목, ID, 서로 다른 네 표, 대표 분류, 조회 기간 미지정, 주기 보존을 검수했다. 동명 본원통화는 서로 다른 실제 ID를 명시한다. 혼합 주기의 네 표는 원래 주기로 독립 조회하므로 같은 주기·단위나 공통 기간을 가정하지 않는다. 자동 검증은 모든 항목·분류·기관·주기·기간·exact params와 원본 v3 해시를 대조한다.

공개 dev / ai-assisted / human_approved=false. 에이전트의 직접 검수와 자동 감사가 사람의 승인이나 블라인드 자연어 일반화 성능을 뜻하지 않는다. 기존 v3 점수와 혼용하지 않는다.

생성기는 v3의 메타데이터 기반 고정 조회 정책을 재사용하고 런타임 예측을 읽지 않는다. 실행기는 질문만 실제 API에 전달한 뒤 전체 추론 종료 후 정답으로 채점한다. 네 표 집합·네 계열·exact params·상태·기간 입력 대기가 모두 일치해야 통과한다. 실제 숫자·CSV·그래프·수정이는 범위 밖이다.

```powershell
.venv/Scripts/python.exe eval/reporter-table-discovery-30/v3-four-tables/scripts/build.py
.venv/Scripts/python.exe eval/reporter-table-discovery-30/v3-four-tables/scripts/validate.py
.venv/Scripts/python.exe eval/reporter-table-discovery-30/v3-four-tables/scripts/evaluate_runtime.py
```

실패 시 진단 JSON과 HTTP 종료 로그만 보존하고 36/36 통과 시 전체 질문·패치 내용·기대/실제 결과를 포함한 REPORT.md를 evaluation_runs/에 저장한다. 골드와 통과 기준은 패치 중 변경하지 않는다.
