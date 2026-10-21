"""Combined lending/deposit requests must retain both measured rates (ai-assisted)."""
from types import SimpleNamespace

import pytest

from agent_runtime import StatBridgeAgent
from request_match_guard import missing_requested_scopes, structure_request


@pytest.fixture(scope='module')
def agent():
    return StatBridgeAgent(object(), ncp_client=SimpleNamespace(
        configured=False, settings=SimpleNamespace(classifier_model='disabled'),
        clarify_question=lambda q, r, s: r.get('question', '기준을 선택해 주세요.')))


@pytest.mark.parametrize('phrase', ['여수신 금리', '여수신금리', '여·수신 금리', '여/수신 금리'])
def test_combined_rate_requires_both_measures(agent, phrase):
    query = f'은행 {phrase}'
    assert set(structure_request(query)['metrics']) == {'대출금리', '수신금리'}
    assert structure_request(query)['comparison']
    assert '대출금리' in missing_requested_scopes(
        query, [{'table_id': 'DT_121Y002'}], agent.resolver.tables)
    assert not missing_requested_scopes(query, [
        {'table_id': 'DT_121Y002'}, {'table_id': 'DT_121Y006'}], agent.resolver.tables)


@pytest.mark.parametrize('institution,ids', [
    ('예금은행', {'DT_121Y002', 'DT_121Y006'}),
    ('비은행금융기관', {'DT_121Y004', 'DT_121Y007'}),
])
@pytest.mark.parametrize('phrase', ['여수신 금리', '여수신금리', '여·수신 금리', '여/수신 금리'])
def test_combined_rates_keep_shared_scope_and_period(agent, institution, ids, phrase):
    query = f'{institution} {phrase}를 신규취급액 기준으로 2024년부터 2025년까지 월별로 보여줘'
    result = agent.resolve(query)
    for _ in range(12):
        if result['status'] == 'resolved':
            break
        assert result['status'] == 'need_clarification', result
        options = result['options']
        choice = next((o['value'] for o in options if o['value'] in ids), options[0]['value'])
        result = agent.resolve(query, state=result['state'], clarification={
            'clarification_id': result['clarification_id'], 'value': choice})
    assert result['status'] == 'resolved', result
    assert {p['table_id'] for p in result['api_plans']} == ids
    assert all(p['start_period'].startswith('2024') and p['end_period'].startswith('2025')
               for p in result['api_plans'])
    assert result['request_query'] == query
    incomplete = {**result, 'api_plans': [result['api_plans'][0]]}
    assert agent.validate_resolution(query, incomplete)['status'] == 'no_match'


def test_rate_distribution_is_not_expanded_into_two_rates():
    assert set(structure_request('예금은행 금리수준별 여수신 비중')['metrics']) != {'대출금리', '수신금리'}


def test_reported_query_through_ui_selection_and_chart(monkeypatch):
    import bridge_api as api
    from authenticated_client import TestClient

    calls = []
    def synthetic_data(**kwargs):
        calls.append(kwargs)
        return {'status': 'success', 'source': 'synthetic-test', 'rows': [
            {'PRD_DE': p, 'DT': v, 'ITM_NM': '합성 테스트 금리', 'UNIT_NM': '연%'}
            for p, v in [('202401', '3.0'), ('202402', '3.1')]]}

    monkeypatch.setattr(api.service, 'get_statistics', synthetic_data)
    monkeypatch.setattr(api.agent, '_classify', lambda q: pytest.fail('compound rates need no model'))
    monkeypatch.setattr(api.agent.ncp, 'clarify_question', lambda q, r, s: r['question'])
    monkeypatch.setattr(api.agent.output_agent, 'ncp_client', None)
    monkeypatch.setattr(api, '_availability_from_table_ids', lambda ids: {'min': '2000-01-01', 'max': '2025-12-31'})
    monkeypatch.setattr(api, '_availability_from_plans', lambda plans: {'min': '2000-01-01', 'max': '2025-12-31'})
    monkeypatch.setattr(api, '_table_card', lambda tid: {'tableId': tid})
    query = '은행 여수신 금리'
    with TestClient(api.app) as client:
        payload = {'query': query, 'execute': True, 'period_start': '2024-01-01', 'period_end': '2024-02-29'}
        for _ in range(12):
            response = client.post('/api/query', json=payload)
            assert response.status_code == 200, response.text
            result = response.json()
            if result['status'] == 'need_output_config':
                break
            assert result['status'] == 'need_clarification', result
            clarification = result['clarification']
            choices = clarification['options']
            choice = next((o['value'] for o in choices if o['value'] in
                           {'DT_121Y006', 'DT_121Y002', '신규취급액'}), choices[0]['value'])
            payload.update(state=result['state'], selections=[{
                'clarification_id': clarification['id'], 'values': [choice]}])
        assert result['status'] == 'need_output_config', result
        assert {t['tableId'] for t in result['tables']} == {'DT_121Y006', 'DT_121Y002'}
        assert len(calls) == 2
        output = client.post('/api/output', json={
            'session_ids': [result['outputSessionId']], 'chart_type': 'line', 'natural_language': query})
        assert output.status_code == 200, output.text
        rendered = output.json()
        assert rendered['seriesCount'] == 2
        assert len(rendered['outputSpec']['plotlyFigure']['data']) == 2
        assert len(calls) == 2
        api.EDIT_SESSIONS.pop(rendered['editSessionId'], None)
        api.OUTPUT_SESSIONS.pop(result['outputSessionId'], None)
