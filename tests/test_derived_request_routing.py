"""Intent contracts, independent of any model output or evaluation answers."""
import pytest
from derived_indicator_planner import is_derived_request
from derived_intent_router import is_calculation_edit

OPERATIONS=[
 '실질 비용으로 조정해줘','명목 매출을 실질 매출로 바꿔줘','증감률을 구해줘','증가율을 보여줘',
 '감소율을 구해줘','증감액을 보여줘','상승폭을 비교해줘','금리 스프레드를 보여줘','점유율을 구해줘',
 '구성비를 보여줘','비중을 계산해줘','몇 배인지 배율을 구해줘','정규화해줘','표준화해줘',
 '재지수화해줘','누적해줘','가중 평균을 구해줘','연율화해줘','수익률을 구해줘',
 '상관계수를 구해줘','표준편차를 보여줘','기여도를 구해줘','중앙값을 구해줘',
 '생산자물가지수로 나눠줘','두 지수를 곱해줘','두 지수를 더해줘','두 지수 합계를 보여줘',
 '두 지수 차이를 보여줘','앞 지수에서 뒤 지수를 빼서 보여줘','전월 대비를 보여줘',
 '전년 대비를 보여줘','역수를 보여줘','자연로그를 구해줘','거듭제곱을 보여줘',
 '이동평균을 보여줘','평균값을 보여줘','기준연도를 100으로 바꿔줘',
]
@pytest.mark.parametrize('operation',OPERATIONS)
@pytest.mark.parametrize('prefix',['2023년부터 2025년까지 ', '2020년 월별 '])
def test_calculation_language_never_falls_into_plain_observation(prefix,operation):
 assert is_derived_request(prefix+operation)

@pytest.mark.parametrize('query',[
 '생산자물가지수 총지수 월별 추이 보여줘','한국은행 기준금리 조회',
 '2023년부터 2025년까지 원달러 환율 보여줘','경제심리지수 원자료를 표로 보여줘',
 '예금은행 대출금리 최근 수준','국제수지 경상수지 조회',
 '예금은행 고정 및 변동금리대출 비중과 신용카드 지급 내역을 2020년부터 2025년까지 그래프 그려줘',
 '예금은행 고정 및 변동금리대출 비중과 예금은행 대출금리 그래프 그려줘',
])
def test_plain_observations_keep_existing_resolver(query):
 assert not is_derived_request(query)

@pytest.mark.parametrize('instruction',[
 '제목을 "전년 대비 변화율"로 바꿔줘','범례 색상을 파란색으로 바꿔줘',
 '제목을 "매출 계산 결과"로 바꿔줘',
])
def test_visual_edit_does_not_replan_quoted_text(instruction):
 assert not is_calculation_edit(instruction)

@pytest.mark.parametrize('instruction',[
 '색상을 파란색으로 바꾸고 전년 변화율로 변경해줘',
 '제목을 바꾸고 두 계열을 나눠줘','계산식을 역수로 바꾸고 색상도 바꿔줘',
])
def test_mixed_visual_math_edit_keeps_math(instruction):
 assert is_calculation_edit(instruction)
