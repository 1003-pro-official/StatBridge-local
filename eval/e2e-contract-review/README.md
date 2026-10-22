# E2E contract review helpers (ai-assisted)

`review_contract.py`는 실행이 끝난 예측을 사후 검토하는 순수 함수 모듈이다. 데이터셋·정답·키·원자료는 포함하지 않는다. 제품 런타임에서 import하지 않는다.

- `period(value, frequency)`: 달력 날짜와 KOSIS 기간을 구분한다. 분기 말 날짜의 일(day)을 분기로 사용하지 않는다. A/Y, H/S 별칭을 정규화하며 잘못된 날짜는 거부한다.
- `review_derived(prediction, expected, oracle)`: `sources`와 단일 계산 `points` 구조를 읽고 실제 계획의 출처·주기·피연산자 순서·연산·단위·값을 검산한다. 계산 영수증에 기록된 결측 이력만 인정하며 수치를 채우지 않는다.
- `subtract_sources(left, right, frequency)`: 두 계열 차에 대한 검토용 정답 후보를 계산한다. 원본 정답을 교체하지 않는다. 두 계열의 기간이 다르면 중단한다.

허용 오차는 0.000001이다. 정량 충족 상태는 `pending_review`이며 사람의 정성 승인을 만들지 않는다. 미완료 계산은 `blocked`이다. 정답 수정안이 필요한 경우 원본·수정 후보의 해시와 근거, 승인 상태를 별도 기록하고 원본 점수와 구분한다.

합성 입력 회귀: `python -m pytest -q tests/test_e2e_contract_review.py`. 평가 자료의 원본 파일을 수정하거나 holdout 정답을 제공하지 않는다.

`observations.py`는 현재 보고서 API의 `paragraphs`와 실제 출력의 `sourceIdentity`에서 보고서 관측을 만든다. 기대 정답을 인자로 받지 않으며, 출처나 본문이 없는 응답을 성공 관측으로 만들지 않는다. v1.1 실행기의 정답 순서 기반 출처 부착 및 문단 누락을 보완하는 용도이다. 회귀는 `tests/test_e2e_report_observation.py`의 합성 자료로 검증한다.
