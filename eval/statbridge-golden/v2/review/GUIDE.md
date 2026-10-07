# 사람 검수 안내

**골든 정답 검수와 실행 응답 해석 검수는 서로 다릅니다.**

## 1. 골든 정답 승인

gold-review-ui-template.jsonl은 현재 공개 72건을 위한 빈 검수 양식입니다.
기존 gold-review-template.jsonl은 수정 전 양식으로 현재 개정본 승인에 사용하지 않습니다.
UI_REVISION.md의 변경 사례 24건은 이전 승인·응답 검수를 재사용하지 마세요.
새 양식의 input_sha256은 검수한 입력을 식별합니다. 질문·행동을 바꾸면 다시 검수합니다.
새 응답 검수 대기본은 results/dev-ui-review.jsonl과 results/test-ui-review.jsonl입니다.
각각 관측된 응답 중 해석 또는 역질문 의미 검수가 필요한 14건·19건이며,
자동 통과 17건만 담은 목록은 아닙니다. 실패 응답도 검토 대상으로 포함됩니다.
각 사례에서 질문의 조건, 원본 locator, 숫자·단위·주기, 역질문 선택지, 허용 표 집합을 확인합니다.
purpose_reconstruction을 보고서 그림의 정확한 복제로 오해하지 않았는지 확인합니다.
오류가 있으면 사례를 반려하고 수정 근거를 기록합니다. 앱이 틀렸다는 이유로 골든 정답을 바꾸지 않습니다.
승인자가 실제 검수한 후에만 사례 review.status=approved, human_approved=true, reviewer를 기록합니다.
이후 검증기와 manifest.py를 재실행합니다. 작성자는 자신의 PR을 머지하지 않습니다.

## 2. 실행 응답 해석 검수

review_packet.py가 실제 prediction hash에 연결된 results/*-review.jsonl을 만듭니다.
실행 결과, claims의 필수 사실, fixture, 출처를 나란히 확인합니다.

- facts_correct: 응답에 등장하는 시점·값·단위·변화 방향이 모두 맞는가?
- no_contradiction: 서로 모순되는 진술이 없는가?
- no_unsupported_claim: 자료에 없는 인과·전망·수치를 확정적으로 말하지 않았는가?
- claims_covered: 요청한 모든 계열의 첫/마지막 값과 변화, 해당 결측 사실을 설명했는가?

최소·최대는 추가 주장이 있을 때 사실성을 판정하는 기준이며 질문이 요구하지 않았다면
모든 극값을 반드시 언급해야 한다는 뜻은 아닙니다.
틀린 항목은 false, 검수하지 않은 항목은 null로 남깁니다.
검수가 끝난 경우에만 실제 reviewer를 적고 human_approved=true로 바꿉니다.
검수 완료와 응답 정답 여부는 다르므로 오답도 검수 완료로 표시할 수 있습니다.
점수는 네 판정의 true 여부로 계산됩니다. notes에 근거와 실제 문장을 짧게 남깁니다.
그림·데이터 자동 검사 실패는 사람이 해석을 승인해도 성공으로 바뀌지 않습니다.
prediction이 변경되면 hash가 달라져 이전 검수는 적용되지 않습니다.

해석 검수 전 자동 통과는 pending_review입니다.
현재 템플릿의 reviewer=null과 human_approved=false는 미검수이며 승인을 뜻하지 않습니다.
# 역질문 선택지 의미 검수

정답 단어가 포함되어도 선택지 의미가 불명확하면 clarification_semantics_unreviewed로 보류됩니다.
새 review_packet.py 검수 파일의 expected_clarification과 actual_clarification을 비교하고
clarification_options_correct를 true/false로 기록하세요. reviewer와 human_approved는 검수 수행 기록입니다.
선택지가 틀린 응답도 검수 완료이면 human_approved는 true, 정오 판단은 false입니다.
관측 해시가 다른 응답에는 해당 판정을 적용하지 않습니다.
편집 문구 계약과 단위 표기 규칙의 한계는 ../HARDENING.md를 참고하세요.

