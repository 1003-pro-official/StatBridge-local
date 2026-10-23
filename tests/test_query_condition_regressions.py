"""Data semantics, calendar and classification regression contracts."""
from request_period import explicit_period
from query_conditions import clarification_question
from request_match_guard import structure_request
from derived_indicator_planner import is_derived_request
from semantic_catalog_planner import family


def test_adjacent_annual_values_form_closed_range_without_filling_missing_years():
    assert explicit_period('2021년과 2022년 연간 값을 보여줘')['end']=='2022-12-31'
    assert explicit_period('2021년과 2024년 연간 값을 보여줘') is None
    assert explicit_period('2008 SNA 기준 상세자금순환표(2018~)의 2021년과 2022년 연간 값')['start']=='2021-01-01'


def test_metadata_classification_aggregate_is_not_new_arithmetic():
    assert not is_derived_request('잔액표의 현금 발행 및 예수금 합계, 제도부문 합계로 선택해 2024년 값을 보여줘')
    assert is_derived_request('2024년 월별 금리 12개를 단순 산술평균해서 보여줘')
    assert is_derived_request('두 계열의 합계를 계산해줘')


def test_demonstrative_data_phrase_does_not_become_interest_metric():
    assert structure_request('이 자료에 수록된 최신 월까지 경제심리지수 원계열을 보여줘')['metrics']==['경제심리']
    assert '통화' not in structure_request('통화를 원화로 정하고 수입물가지수를 조회해줘')['metrics']
    assert '통화' in structure_request('통화량 M2와 수입물가지수를 비교해줘')['metrics']


def test_bank_institution_name_does_not_request_deposit_interest():
    assert family('예금은행가계대출금리신규취급액', '예금은행수신금리신규취급액', {}) is None
    assert family('예금은행저축성수신금리', '예금은행수신금리신규취급액', {})=='수신금리'


def test_missing_basis_asks_but_explicit_basis_or_table_does_not():
    tables=[{'table_name':'M2 상품별 구성내역'}, {'table_name':'경제심리지수'}]
    assert '평잔' in clarification_question('M2 계절조정 총액을 보여줘',tables)
    assert clarification_question('M2 평잔 원계열을 보여줘',tables) is None
    assert clarification_question('통계표 DT_123Y001의 M2를 보여줘',tables) is None
    assert '순환변동치' in clarification_question('경제심리지수를 보여줘',tables)
    assert clarification_question('경제심리지수 원계열과 순환변동치를 둘 다 보여줘',tables) is None
