"""Measured quantities cannot be substituted by aliases, HCX or vector scores."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from request_match_guard import measured_intent_matches
from stat_dictionary.stat_language_resolver import StatLanguageResolver

ROOT = Path(__file__).resolve().parents[1]
QUESTION = '주택담보대출 신규취급액 2020년1월1일부터 2025년12월31일까지 그래프 그려줘'


@pytest.fixture(scope='module')
def resolver():
    return StatLanguageResolver(ROOT / 'src/agent/stat_dictionary/stat_language_dictionary.json')


@pytest.mark.parametrize('query,expected,forbidden', [
    (QUESTION, 'DT_181Y011', ['DT_181Y015', 'DT_181Y012', 'DT_121Y006']),
    ('주택담보대출 신규취급액 비중', 'DT_181Y015', ['DT_181Y011', 'DT_181Y016']),
    ('주택담보대출 신규취급액 비율', 'DT_181Y015', ['DT_181Y011', 'DT_181Y016']),
    ('주택담보대출 신규취급액 구성비', 'DT_181Y015', ['DT_181Y011', 'DT_181Y016']),
    ('주택담보대출 잔액', 'DT_181Y012', ['DT_181Y011', 'DT_181Y016', 'DT_121Y008']),
    ('비중 말고 주택담보대출 신규취급액', 'DT_181Y011', ['DT_181Y015']),
    ('주택담보대출 신규취급액 비중 대신 금액', 'DT_181Y011', ['DT_181Y015']),
    ('주택담보대출 신규취급액 비중이 아니라 금액', 'DT_181Y011', ['DT_181Y015']),
])
def test_amount_share_stock_and_negation(resolver, query, expected, forbidden):
    result = resolver.resolve(query)
    assert result['status'] == 'resolved'
    assert result['selected_table']['table_id'] == expected
    assert not set(forbidden) & {t['table_id'] for t in result['candidates']}
    if expected == 'DT_181Y011':
        assert resolver.parse_query_state(query).measure_basis == '신규취급액'


@pytest.mark.parametrize('requested,wrong', [
    ('주택담보대출 신규취급액', '주택담보대출 신규취급액 비중'),
    ('주택담보대출 잔액', '주택담보대출 잔액 비중'),
    ('대출금리 신규취급액 기준', '차주당 주택담보대출 신규취급액'),
    ('대출금리 잔액 기준', '예금은행 대출금리 신규취급액 기준'),
    ('수출금액지수', '수출물량지수'),
    ('수입물량지수', '수입물가지수'),
    ('명목 GDP', '국내총생산 실질'),
    ('실질 GDP', '국내총생산 명목'),
    ('원계열 GDP', '국내총생산 계절조정'),
    ('통화량 평잔', '통화량 말잔'),
    ('기업경기 실적', '기업경기 전망'),
    ('주택담보대출 신규취급액 총액', '차주당 주택담보대출 신규취급액'),
])
def test_alias_does_not_change_the_quantity(requested, wrong):
    assert not measured_intent_matches(requested, {'table_name': wrong, 'aliases': [requested]})


def test_all_catalog_titles_keep_their_own_quantity(resolver):
    rejected = [t['table_id'] for t in resolver.tables if not measured_intent_matches(t['table_name'], t)]
    assert not rejected, rejected


@pytest.mark.parametrize('term', ['비중', '구성비', '비율'])
def test_share_is_outer_measure_and_new_lending_is_its_basis(resolver, term):
    assert resolver.parse_query_state('주택담보대출 신규취급액 ' + term).measure_basis == '비중'
    assert measured_intent_matches('예금은행 대출금리 신규취급액 기준', resolver.tables_by_id['DT_121Y006'])


def test_model_expansion_and_wrong_vector_top_cannot_select_share(monkeypatch):
    from agent_runtime import StatBridgeAgent
    agent = StatBridgeAgent(SimpleNamespace(), ncp_client=SimpleNamespace(configured=False))
    monkeypatch.setattr(agent, '_classify', lambda q: (q + ' 신규취급액 비중', {'status': 'success'}))
    wrong = agent.resolver.candidate_shell('DT_181Y015')
    wrong['score'] = 9999
    monkeypatch.setattr(agent.hybrid, 'rank', lambda *args, **kwargs: [wrong])
    result = agent.resolve(QUESTION)
    assert result['status'] == 'resolved', result
    assert result['api_plan']['table_id'] == 'DT_181Y011'
    assert result['request_validation']['valid']
    assert result['dictionary_query'] == QUESTION


def test_model_cannot_turn_single_amount_request_into_a_comparison(monkeypatch):
    from agent_runtime import StatBridgeAgent
    agent = StatBridgeAgent(SimpleNamespace(), ncp_client=SimpleNamespace(configured=False))
    hallucination = {'status': 'success', 'series': [
        {'label': '금액', 'query': '차주당 주택담보대출 신규취급액'},
        {'label': '비중', 'query': '주택담보대출 신규취급액 비중'},
    ]}
    monkeypatch.setattr(agent, '_classify', lambda q: (q + ' 비중 비교', hallucination))
    monkeypatch.setattr(agent.hybrid, 'rank', lambda *args, **kwargs: [])
    result = agent.resolve(QUESTION)
    assert result['status'] == 'resolved', result
    assert result['api_plan']['table_id'] == 'DT_181Y011'
    assert not result.get('api_plans') or len(result['api_plans']) == 1


def test_execute_rechecks_original_amount_before_network_call():
    from agent_runtime import StatBridgeAgent
    calls = []
    agent = StatBridgeAgent(SimpleNamespace(get_statistics=lambda **kw: calls.append(kw)), ncp_client=SimpleNamespace(configured=False))
    wrong = agent.resolver.candidate_shell('DT_181Y015')
    result = agent.execute_resolution(QUESTION, {
        'status': 'resolved', 'selected_table': wrong,
        'api_plan': agent.build_api_plan('주택담보대출 신규취급액 비중', wrong).as_dict(),
    }, generate_answer=False)
    assert result['status'] == 'no_match'
    assert not calls


def test_vector_recall_cannot_reintroduce_rejected_share(resolver, monkeypatch):
    from hybrid_retriever import HybridStatRetriever
    client = SimpleNamespace(configured=True, embed=lambda q: [1.0],
        rerank=lambda *args: {'DT_181Y015': 1.0})
    retriever = HybridStatRetriever(resolver, client=client)
    collection = SimpleNamespace(query=lambda **kw: {
        'documents': [['주택담보대출 신규취급액 비중']],
        'metadatas': [[{'table_id': 'DT_181Y015'}]], 'distances': [[0.0]],
    })
    monkeypatch.setattr(retriever, '_load', lambda: [collection])
    result = retriever.rank(QUESTION)
    assert result and result[0]['table_id'] == 'DT_181Y011'
    assert 'DT_181Y015' not in {table['table_id'] for table in result}
