# 데이터셋 변경 이력

원본 보존: baseline_reference/cases.original.jsonl 및 원본 패키지. 질문 변경 0개, D 수치·단위 변경 0개. 모든 120개 전후 JSON은 audit/changes/case_diff.json에 있다.

## 의미가 바뀐 정답 2개

| ID | 기존 질의 | 패치 질의 | 기존 정답 | 패치 정답 | 이유 |
|---|---|---|---|---|---|
| E40 | ① 수신금리를 #E53935·dash로 바꾸고 범례를 아래로 내려줘. → ② 제목을 ‘복원 전 금리’로 바꿔줘. → ③ [UI] 분석 저장 후 같은 계정에서 재개. ④ [UI] 처음 상태 복원. | ① 수신금리를 #E53935·dash로 바꾸고 범례를 아래로 내려줘. → ② 제목을 ‘복원 전 금리’로 바꿔줘. → ③ [UI] 분석 저장 후 같은 계정에서 재개. ④ [UI] 처음 상태 복원. | ③ 저장한 A 빨강·dash·아래 범례·제목 복원 전 금리 유지. ④ 기준 그래프 전체 복구: A 파랑·B 주황·두 계열 선/solid/두께2, 기준 제목·크기20·위 범례·1~6월 12값. 저장 직전 상태가 최초 상태로 오인되지 않음. | ③ 저장 직전의 fixture-ready 편집 상태를 같은 계정에서 재개한다. ④ 실제 최초 조회 직후 캡처한 초기 스냅샷으로 복원한다. fixture 준비 후 제목·색상과 초기 조회 스냅샷을 혼동하지 않는다. 초기 스냅샷 미수집 시 REVIEW_REQUIRED. 원자료 불변 조건은 유지한다. | 초기 조회와 fixture 준비 상태를 분리. 실제 초기 스냅샷 미수집은 검토 대기. F34 표 독립성 결함은 면제하지 않음 |
| F34 | ① 수신금리를 #E53935로 바꾸고 대출금리를 숨겨줘. ② 제목을 ‘초기화 대상’으로 바꿔줘. ③ [UI] 처음 상태 복원→PNG·CSV 다운로드. | ① 수신금리를 #E53935로 바꾸고 대출금리를 숨겨줘. ② 제목을 ‘초기화 대상’으로 바꿔줘. ③ [UI] 처음 상태 복원→PNG·CSV 다운로드. | PNG는 기준 제목·양계열·A파랑·B주황·위범례. CSV는기준12값. 숨김·제목·색상 잔여가 없음. | 숨김·제목 편집 후 실제 최초 조회 직후 캡처한 초기 스냅샷으로 복원하고, PNG·CSV를 해당 시점 화면·원자료와 비교한다. fixture-ready 제목·색상을 최초 스냅샷으로 강제하지 않는다. 그래프 B 숨김이 표의 선택 계열까지 바꾸는지는 별도 독립 검사한다. | 초기 조회와 fixture 준비 상태를 분리. 실제 초기 스냅샷 미수집은 검토 대기. F34 표 독립성 결함은 면제하지 않음 |

## 전체 계약 변경 목록

120개 모두 provenance·유형·계열 역할·승인 계약을 추가했다. 아래 목록은 변경 이유이며 전후 전문은 JSON diff에 있다.

| ID | 질의 변경 | 의미 변경 | 패치 내용 |
|---|---|---|---|
| QT21-01 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-02 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-03 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-04 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-05 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-06 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-07 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-08 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-09 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-10 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-11 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-12 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-13 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-14 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-15 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-16 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-17 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-18 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-19 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| QT21-20 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-01 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-02 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-03 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-04 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-05 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-06 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-07 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-08 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-09 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-10 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-11 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-12 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-13 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-14 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-15 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-16 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-17 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-18 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-19 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| CQ21-20 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-01 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-02 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-03 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-04 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-05 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-06 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-07 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-08 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-09 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-10 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-11 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-12 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-13 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-14 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-15 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-16 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-17 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-18 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-19 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| DA21-20 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| E21 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| E22 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| E23 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| E24 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| E25 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| E26 | False | False | HARNESS_ERROR prevention: graph visibility and table selection are separate; preserve independently at every step. |
| E27 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| E28 | False | False | HARNESS_ERROR: stored point color alone cannot demonstrate visible point emphasis; require rendered size, color, position and visibility. |
| E29 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| E30 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| E31 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| E32 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| E33 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| E34 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| E35 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| E36 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| E37 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| E38 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| E39 | False | False | HARNESS_ERROR prevention: graph visibility and table selection are separate; preserve independently at every step.; HARNESS_ERROR: stored point color alone cannot demonstrate visible point emphasis; require rendered size, color, position and visibility. |
| E40 | False | True | DATASET_ERROR: fixture-ready title/color was assumed to be the product initial snapshot; replace nonexistent initial-state premise with a same-run observed initial snapshot, not product behavior relaxation. |
| F21 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| F22 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| F23 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| F24 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| F25 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| F26 | False | False | HARNESS_ERROR prevention: independently verify SVG base styles outside selected range; never waive transformed colors because highlighted segment matches. |
| F27 | False | False | HARNESS_ERROR: stored point color alone cannot demonstrate visible point emphasis; require rendered size, color, position and visibility.; HARNESS_ERROR prevention: independently verify SVG base styles outside selected range; never waive transformed colors because highlighted segment matches. |
| F28 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| F29 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| F30 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| F31 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| F32 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| F33 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| F34 | False | True | DATASET_ERROR: fixture-ready title/color was assumed to be the product initial snapshot; replace nonexistent initial-state premise with a same-run observed initial snapshot, not product behavior relaxation.; HARNESS_ERROR prevention: graph visibility and table selection are separate; preserve independently at every step. |
| F35 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| F36 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| F37 | False | False | HARNESS_ERROR prevention: independently verify SVG base styles outside selected range; never waive transformed colors because highlighted segment matches. |
| F38 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| F39 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| F40 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D21 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D22 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D23 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D24 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D25 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D26 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D27 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D28 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D29 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D30 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D31 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D32 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D33 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D34 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D35 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D36 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D37 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D38 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D39 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
| D40 | False | False | Schema/evidence provenance strengthening only; original question and expected arithmetic preserved. |
