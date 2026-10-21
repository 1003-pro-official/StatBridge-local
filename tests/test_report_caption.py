"""Synthetic observations only; the reference PDF supplies style, never values."""
import json

import pytest

from report_caption import build_caption, display_number


def series():
    return [dict(label='검증 지표', unit='%', frequency='M', points=[
        {'date': '202605', 'value': -5}, {'date': '202606', 'value': -3}, {'date': '202607', 'value': -4}])]


class Model:
    configured = True
    def __init__(self, result): self.result = result
    def request(self, system, context, **kwargs):
        assert 'input_image' not in context
        assert kwargs['json_mode']
        return json.dumps(self.result), {}


def test_growth_rate_chart_uses_displayed_percent_and_percentage_point_change():
    draft = build_caption(series(), transform='year_over_year')
    assert len(draft['paragraphs']) == 1
    text = draft['paragraphs'][0]
    assert '2026년 7월 전년동기 대비 증감률은 -4 %' in text
    assert '전월보다 1 %p 하락' in text
    assert draft['claims'][0]['fact_ids'] == ['s0-latest', 's0-previous']
    assert draft['scope']['basis'] == 'displayed_observations'


def test_caption_rounds_for_readability_without_turning_a_small_change_into_zero():
    assert display_number(-8.036809815950907) == '-8.04'
    assert display_number(4.665283251760233) == '4.67'
    assert display_number(0.001) == '0.001'


@pytest.mark.parametrize('proposal', [
    {'focus_ids': ['fake']}, {'focus_ids': ['s0-latest']}, {'focus_ids': []},
    {'focus_ids': ['s0-previous', 's0-period']},
    {'focus_ids': ['s0-previous'], 'text': '임의 전망 999%'}])
def test_model_cannot_invent_text_or_omit_or_duplicate_series(proposal):
    expected = build_caption(series())
    actual = build_caption(series(), Model(proposal))
    assert actual['paragraphs'] == expected['paragraphs']
    assert actual['method'] == 'validated_chart_observations'


def test_model_can_choose_a_computed_period_comparison_only():
    draft = build_caption(series(), Model({'focus_ids': ['s0-period']}))
    assert draft['method'] == 'model_selected_chart_observations'
    assert '조회 시작 시점보다 1 %p 상승' in draft['paragraphs'][0]


def test_all_series_covered_single_observation_and_zero_are_preserved():
    other = dict(label='다른 지표', unit='개', frequency='M', points=[{'date': '202607', 'value': 0}])
    draft = build_caption([*series(), other], Model({'focus_ids': ['s0-previous']}))
    assert len(draft['paragraphs']) == 2
    assert '0 개입니다.' in draft['paragraphs'][1]
    assert draft['claims'][1]['fact_ids'] == ['s1-latest']
    with pytest.raises(ValueError): build_caption([])


def test_calendar_gaps_never_become_previous_month_comparisons():
    item = series()[0]
    item['points'] = [item['points'][0], item['points'][2]]
    draft = build_caption([item])
    assert '전월' not in draft['paragraphs'][0]
    assert '조회 시작 시점' in draft['paragraphs'][0]


def test_chart_brief_endpoint_uses_transformed_series_and_checks_revision(monkeypatch, tmp_path):
    import account_auth as auth
    import bridge_api as api
    from fastapi.testclient import TestClient
    from test_account_auth import login, fixture_graph

    store = auth.AccountStore(tmp_path / 'accounts.sqlite3')
    monkeypatch.setattr(auth, 'STORE', store)
    client, user = login('test1')
    session = fixture_graph(monkeypatch, store, user, 'caption-test')
    session['sessions'] = [{'period': {'start': '2026-05-01', 'end': '2026-07-31'}}]
    session['output']['chartState']['transform'] = 'year_over_year'
    monkeypatch.setattr(api.agent.output_agent, 'ncp_client', None)
    monkeypatch.setattr(api.agent.output_agent, '_display_series', lambda result, spec: series())
    payload = dict(edit_session_id='caption-test', revision=session['output'].get('editVersion', 0), mode='chart_brief')
    assert TestClient(api.app).post('/api/report/interpret', json=payload).status_code == 401
    result = client.post('/api/report/interpret', json=payload)
    assert result.status_code == 200, result.text
    draft = result.json()
    assert draft['plotlyFigure'] == session['output']['plotlyFigure']
    assert '증감률은 -4 %' in draft['paragraphs'][0]
    assert draft['scope']['basis'] == 'displayed_observations'
    assert client.post('/api/report/interpret', json={**payload, 'revision': payload['revision']+1}).status_code == 409

    def changing(series, model, **kwargs):
        session['output']['editVersion'] = payload['revision'] + 1
        return build_caption(series, None, **kwargs)
    monkeypatch.setattr('report_caption.build_caption', changing)
    assert client.post('/api/report/interpret', json=payload).status_code == 409
