"""Display-period failures found with real model planning; no gold injection."""
import pytest
from request_period import explicit_period
from derived_request_period import requested_display_period


@pytest.mark.parametrize('query',[
    '2025년 1~6월 금리 차이를 계산해줘.',
    '2025년 1월~6월 금리 차이를 계산해줘.',
    '2025년 1～6월 금리 차이를 계산해줘.',
    '2025년 1월=100으로 재지수화해서 1~6월을 보여줘.',
])
def test_closed_month_shorthand_does_not_expand_to_whole_year(query):
    r=requested_display_period(query)
    assert (r['start'],r['end'])==('2025-01-01','2025-06-30')


@pytest.mark.parametrize('query',[
    '2025년 1~3월 월별 공표값을 단순 평균해줘. 결과는 종료 월에 한 점으로 표시해줘.',
    '2025년 1월부터 3월까지 평균해줘. 결과는 3월 한 점으로 표시해줘.',
])
def test_mean_output_month_is_separate_from_source_interval(query):
    r=requested_display_period(query)
    assert (r['start'],r['end'])==('2025-03-01','2025-03-31')


def test_multiple_comparison_intervals_are_not_collapsed():
    assert explicit_period('2024년 1~6월과 2025년 1~6월의 차이') is None


def test_shorthand_rejects_reverse_and_invalid_months():
    with pytest.raises(ValueError):explicit_period('2025년 6~1월')
    with pytest.raises(ValueError):explicit_period('2025년 1~13월')


def test_open_bound_does_not_become_a_closed_interval():
    assert explicit_period('2025년 1월부터') is None
