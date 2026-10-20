"""Synthetic observations; attached writing examples are never runtime evidence."""
import copy
import json

import pytest

from statistical_question import answer_question


def item(label='대출금리', values=('5.10', '5.00'), unit='연%', dates=('202605', '202606'), source='SYNTHETIC', frequency='M'):
    return dict(label=label, unit=unit, frequency=frequency, sourceId=source,
                points=[dict(date=d, value=v) for d, v in zip(dates, values)])


class Planner:
    configured = True
    def __init__(self, analysis='observation', ids=(0,), **overrides):
        self.plan = dict(analysis=analysis, series_ids=list(ids), **overrides)
    def request(self, system, context, **kwargs):
        assert kwargs['json_mode']
        assert 'value' not in json.loads(context)['series'][0]
        return json.dumps(self.plan), {}


def text(answer): return ' '.join(answer['paragraphs'])


def test_speed_uses_decimal_percentage_points_and_evidence():
    result = answer_question('하락 속도가 같은가?', [item(), item('수신금리', ('3.50', '3.30'))], Planner('speed', (0, 1)))
    assert result['status'] == 'answered'
    assert '0.1 %p' in text(result) and '0.2 %p' in text(result)
    assert '하락 속도에는 차이' in text(result)
    assert result['facts'][0]['result'] == '-0.10'
    assert all(c['fact_ids'] and set(c['fact_ids']) <= {f['id'] for f in result['facts']} for c in result['claims'])
    assert result['scope']['basis'] == 'original_observations'


def test_bond_gap_is_signed_with_bp_and_absolute_width():
    result = answer_question('금리차는?', [item('회사채', ('4.1', '4.0')), item('국고채', ('3.2', '3.0'))], Planner('gap', (0, 1)))
    assert '0.9 %p에서 1 %p' in text(result)
    assert '100bp' in text(result)
    assert result['facts'][-1]['result'] == '1.0'
    assert '신용 여건이 개선' not in text(result)


@pytest.mark.parametrize('analysis', ['speed', 'gap', 'components'])
def test_mixed_units_cannot_be_subtracted(analysis):
    result = answer_question('비교', [item(), item('다른 지표', unit='조원')], Planner(analysis, (0, 1)))
    assert result['status'] == 'insufficient_data'
    assert not result['facts'] and result['requiredData']


@pytest.mark.parametrize('other', [item('수신금리', dates=('202604', '202606')), item('수신금리', dates=('202604', '202605')), item('수신금리', frequency='Q')])
def test_missing_calendar_interval_mismatched_latest_and_frequency(other):
    result = answer_question('속도 비교', [item(), other], Planner('speed', (0, 1)))
    assert result['status'] == 'insufficient_data'
    assert not result['facts']


def test_price_and_transactions_can_have_different_units_without_false_subtraction():
    result = answer_question('가격 상승을 거래 회복으로 해석해도 되는가?',
                             [item('가격 상승률', ('0.2', '0.4'), '%'), item('거래량', ('900', '800'), '호')], Planner('divergence', (0, 1)))
    assert result['status'] == 'answered'
    assert '변화 방향이 다릅니다' in text(result)
    assert all(f['formula'] == 'target - baseline' for f in result['facts'])


def test_components_do_not_turn_levels_into_official_contributions():
    result = answer_question('증가를 주도한 항목은?', [item('가계대출', ('100', '104'), '조원'), item('주택담보대출', ('70', '75'), '조원'), item('기타대출', ('30', '29'), '조원')], Planner('components', (0, 1, 2)))
    assert '전체 증가는 주택담보대출의 변화에 가장 크게 집중되었습니다' in text(result)
    assert '합계 관계를 확인' in text(result)
    assert '성장기여도' in ' '.join(result['limitations'])


def test_official_contribution_series_and_growth_composition():
    result = answer_question('성장 구성이 달라졌는가?', [item('성장률', ('0.6', '0.6'), '%'), item('내수 기여도', ('0.1', '0.5'), '%p'), item('수출 기여도', ('0.5', '0.1'), '%p')], Planner('divergence', (0, 1, 2)))
    assert '같은 수준을 유지' in text(result) and '0.4 %p 상승' in text(result) and '0.4 %p 하락' in text(result)


def test_inflation_rate_and_published_contributions_compare_percentage_point_changes():
    result = answer_question('물가 둔화가 어느 품목에서 나타났는가?',
        [item('소비자물가 상승률', ('3.0', '2.4'), '%'), item('에너지 기여도', ('0.8', '0.3'), '%p'), item('근원물가 상승률', ('2.3', '2.3'), '%')],
        Planner('components', (0, 1, 2)))
    assert result['status'] == 'answered'
    assert '0.6 %p 하락' in text(result) and '0.5 %p 하락' in text(result)
    assert '같은 수준을 유지' in text(result)


def test_threshold_only_applies_to_interest_coverage_ratio():
    result = answer_question('기준선을 넘었는가?', [item('중소기업 이자보상배율', ('1.1', '0.7'), '배')], Planner('threshold'))
    assert '영업이익이 이자비용에 미달' in text(result)
    assert '모든 개별 기업' in text(result)
    wrong = answer_question('기준선', [item('부채비율', ('1.1', '0.7'), '%')], Planner('threshold'))
    assert wrong['status'] == 'insufficient_data' and wrong['facts'] == []


def test_forecasts_and_causes_require_documents_even_if_model_misroutes():
    for question in ['성장 전망이 달라졌는가?', '금리 하락의 원인은?']:
        result = answer_question(question, [item()], Planner())
        assert result['status'] == 'insufficient_data' and not result['facts']


@pytest.mark.parametrize('overrides', [dict(series_ids=[9]), dict(series_ids=[-1]), dict(series_ids=[0, 0]), dict(series_ids=[True]), dict(text='999% 전망'), dict(analysis='execute_python')])
def test_model_cannot_inject_text_or_invalid_series(overrides):
    model = Planner(); model.plan.update(overrides)
    result = answer_question('대출금리 변화는?', [item()], model)
    assert result['method'] == 'rules'
    assert '999' not in text(result)
    assert '0.1 %p' in text(result)


def test_key_free_fallback_does_not_answer_unrelated_subjects():
    assert answer_question('대출금리 변화는?', [item()])['status'] == 'answered'
    assert answer_question('소비자물가 상승률은?', [item()])['status'] == 'insufficient_data'
    assert answer_question('대출금리 2024년 변화는?', [item()])['status'] == 'insufficient_data'
    assert answer_question('현재 그래프 요약', [item(f'계열{i}') for i in range(9)])['status'] == 'insufficient_data'


def test_explicit_periods_single_observation_and_zero_are_preserved():
    result = answer_question('대출금리 값은?', [item(values=('0',), dates=('202605',))], Planner())
    assert result['status'] == 'answered' and '0 연%' in text(result)
    data = item(values=('3.5', '3.2', '3.1'), dates=('202604', '202605', '202606'))
    result = answer_question('이전 시점 비교', [data], Planner(target_period='202605', baseline_period='202604'))
    assert result['facts'][0]['result'] == '-0.3'
    assert '2026년 6월' not in text(result)
    assert answer_question('시점 비교', [data], Planner(target_period='202501'))['status'] == 'insufficient_data'


def test_yearly_comparison_never_uses_zero_as_missing_or_an_older_month():
    data = item(values=('0', '2', '3'), dates=('202506', '202605', '202606'))
    result = answer_question('전년동기 비교', [data], Planner(comparison='yearly'))
    assert result['status'] == 'answered' and result['facts'][0]['result'] == '3'
    assert result['facts'][0]['observations'][0]['date'] == '202506'


def test_non_finite_observations_and_missing_series_are_not_invented():
    assert answer_question('값은?', [item(values=('NaN', 'Infinity'))], Planner())['status'] == 'insufficient_data'
    result = answer_question('비교할 지표가 더 필요함', [item()], Planner('speed', needs_data=True))
    assert result['facts'] == [] and result['requiredData']


def test_endpoint_auth_revision_scope_and_race(monkeypatch, tmp_path):
    import account_auth as auth
    import bridge_api as api
    from fastapi.testclient import TestClient
    from test_account_auth import login, fixture_graph

    store = auth.AccountStore(tmp_path / 'accounts.sqlite3')
    monkeypatch.setattr(auth, 'STORE', store)
    client, user = login('test1')
    session = fixture_graph(monkeypatch, store, user, 'question-test')
    session['output']['chartState'].update(transform='cumulative', period_start='202601', period_end='202602', display_names={'계열0': '표시 별명'})
    monkeypatch.setattr(api.agent.output_agent, 'ncp_client', Planner())
    payload = dict(edit_session_id='question-test', revision=0, question='현재 자료의 변화는?')
    assert TestClient(api.app).post('/api/report/question', json=payload).status_code == 401
    other, _ = login('test2')
    assert other.post('/api/report/question', json=payload).status_code == 404
    before = copy.deepcopy(session)
    response = client.post('/api/report/question', json=payload)
    assert response.status_code == 200, response.text
    assert response.json()['revision'] == 0 and response.json()['scope']['basis'] == 'original_observations'
    assert response.json()['status'] == 'answered'
    assert response.json()['facts'][0]['result'] == '1.0'
    assert [p['value'] for p in response.json()['facts'][0]['observations']] == ['16.0', '17.0']
    assert response.json()['scope']['series'][0]['label'] == '계열0'
    # Read-only questions preserve the analysis, while request telemetry may append.
    assert {k: v for k, v in session.items() if k != 'observability'} == {
        k: v for k, v in before.items() if k != 'observability'
    }
    assert client.post('/api/report/question', json={**payload, 'revision': 1}).status_code == 409
    for bad in ('', '  ', 'a' * 1001):
        assert client.post('/api/report/question', json={**payload, 'question': bad}).status_code == 422

    def changing(*args, **kwargs):
        session['output']['editVersion'] = 1
        return answer_question(*args, **kwargs)
    monkeypatch.setattr('statistical_question.answer_question', changing)
    assert client.post('/api/report/question', json=payload).status_code == 409
