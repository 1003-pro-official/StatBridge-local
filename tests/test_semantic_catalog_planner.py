"""Metadata selection regressions; no evaluation answers are imported."""
from types import SimpleNamespace
import pytest
from semantic_catalog_planner import matches, selections, catalog_paths
from agent_runtime import StatBridgeAgent


def dimension(*names):
    return {'api_param':'objL1','values':[{'value_id':str(i),'value_name':name} for i,name in enumerate(names)]}


def names(query,*values):
    return {v['value_name'] for v in matches(query,dimension(*values))}


def test_coordinated_shared_modifiers_and_footnotes():
    assert names('개인·법인 이용금액 비교','개인 이용금액','법인 이용금액','개인 이용건수')=={'개인 이용금액','법인 이용금액'}
    assert names('영업활동·투자활동·재무활동 현금흐름 비교','Ⅰ. 영업활동으로 인한 현금흐름','Ⅱ. 투자활동으로 인한 현금흐름 주2)','Ⅲ. 재무활동으로 인한 현금흐름')=={'Ⅰ. 영업활동으로 인한 현금흐름','Ⅱ. 투자활동으로 인한 현금흐름 주2)','Ⅲ. 재무활동으로 인한 현금흐름'}


def test_valuation_and_independent_exclusion_members():
    assert names('원화 기준에서 비교','원화기준','달러기준')=={'원화기준'}
    assert names('IT 품목과 IT 이외 품목 비교','IT','IT이외')=={'IT','IT이외'}
    assert names('자동차·부품 비교','자동차및부품','자동차부품')=={'자동차및부품'}


def test_ratio_coordination_does_not_turn_enterprise_size_into_ratio():
    assert names('제조업 기업 현금흐름 대비 매출액·총부채 비율','제조업','제조업 대기업')=={'제조업'}
    assert names('영업활동현금흐름 대비 매출액·총부채 비율','영업활동현금흐름대매출액','영업활동현금흐름대총부채')=={'영업활동현금흐름대매출액','영업활동현금흐름대총부채'}


@pytest.fixture(scope='module')
def agent():
    return StatBridgeAgent(object(),ncp_client=SimpleNamespace(configured=False,settings=SimpleNamespace(classifier_model="disabled")))


def test_stock_and_flow_rate_bases_remain_separate(agent):
    result=agent.resolve('예금은행 가계대출 금리를 신규취급액 기준과 잔액 기준으로 월별 비교해줘')
    assert result['status']=='resolved'
    assert {plan['table_name'] for plan in result['api_plans']}=={'예금은행 대출금리(신규취급액 기준)','예금은행 대출금리(잔액 기준)'}


@pytest.mark.parametrize('query',['취약차주 가계대출 비중','다주택자 주택담보대출 만기연장 제한 조건','예금자보호한도와 보호대상 예금 범위','GDP 대비 가계부채 비율','소상공인 체감경기','미시간 소비심리지수'])
def test_missing_subject_does_not_become_adjacent_statistics(agent,query):
    result=agent.resolve(query)
    assert result['status']=='no_match'
    assert not result.get('api_plans')


def test_duplicate_catalog_titles_use_local_lineage_not_identifier_order(agent):
    result=agent.resolve('2021년 1분기부터 2024년 4분기까지 30대와 40대 주택담보대출 잔액 비교')
    assert result['status']=='resolved'
    assert all('잔액' in catalog_paths()[plan['table_id']] and '신규취급액' not in catalog_paths()[plan['table_id']] for plan in result['api_plans'])


def test_shared_rate_basis_is_not_a_bare_rate_comparison(agent):
    result=agent.resolve('2022년 1월부터 2025년 12월까지 예금은행 기업대출 금리와 가계대출 금리를 신규취급액 기준으로 월별 비교')
    assert result['status']=='resolved'
    assert len(result['api_plans'])==2
    assert all('신규취급액' in plan['table_name'] for plan in result['api_plans'])
