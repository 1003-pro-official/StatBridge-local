# v4 → v4.1 변경 기록

- 150개 케이스 유지, ID 유지
- 질문 연도와 불일치한 slots.period 일괄 교정
- no_match/catalog_only의 명시적 기간·주기 슬롯 보강
- followup의 현재/이전 발화에서 명시된 기간·주기만 상속
- split을 type-stratified 50/70/30으로 재배치
- holdout 정답을 공개 패키지에서 제거
- language_style을 formal/colloquial/abbreviated/indirect로 재분포
- followup의 context dependency를 별도 boolean으로 분리
- difficulty를 easy/medium/hard로 재산정
- expected_items.item_by_table 추가(근거가 정확한 경우만)
- dimension value Gold는 생성하지 않고 not_labeled 선언
- semantic sibling hard negative 일부 수동 보강 + 기존 neighbor fallback
- Codex 자기승인을 human approval로 표시하지 않도록 review provenance 수정
- self-contained validator, scorer, tests 추가
