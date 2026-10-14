import copy

import pytest

from output_agent import OutputAgent
from quick_output import requested_chart


def result():
    return {'status': 'resolved', 'api_plan': {'table_id': 'fixture', 'table_name': '검증 지표', 'frequency': 'M'},
            'request_validation': {'valid': True, 'table_ids': ['fixture']},
            'execution': {'status': 'success', 'rows': [
                {'_SOURCE_SERIES_ID': 'fixture', '_SERIES_LABEL': '검증 지표', '_FREQUENCY': 'M', 'PRD_DE': f'2024{i:02}', 'DT': str(i), 'UNIT_NM': '지수'} for i in range(1, 13)]}}


def test_quick_output_does_not_call_models_or_change_observations(monkeypatch):
    agent = OutputAgent()
    monkeypatch.setattr(agent, '_propose_spec', lambda *_: pytest.fail('basic chart must not call a presentation model'))
    monkeypatch.setattr(agent, '_explain', lambda *_: pytest.fail('basic summary must use verified facts'))
    source = result(); original = copy.deepcopy(source)
    output = agent.prepare(source, {'quick_output': True, 'chart_type': 'auto', 'natural_language': '검증 지표를 막대 그래프로 보여줘'})
    assert output['chartState']['chart_type'] == 'bar'
    assert output['table']['rows'][-1]['value'] == 12
    assert source == original
    assert '입니다' in output['summary']


def test_quick_output_preserves_validation_and_explicit_invalid_chart():
    source = result(); source['request_validation']['valid'] = False
    with pytest.raises(ValueError, match='일치하지'):
        OutputAgent().prepare(source, {'quick_output': True})
    with pytest.raises(ValueError):
        OutputAgent().prepare(result(), {'quick_output': True, 'natural_language': '산점도로 보여줘'})


def test_quick_output_separates_mixed_units_and_frequencies():
    source = result()
    source['api_plans'] = [source['api_plan'], {'table_id': 'quarter', 'table_name': '분기 지표', 'frequency': 'Q'}]
    source['request_validation']['table_ids'].append('quarter')
    source['execution']['rows'] += [{'_SOURCE_SERIES_ID': 'quarter', '_SERIES_LABEL': '분기 지표', '_FREQUENCY': 'Q', 'PRD_DE': f'2024{i:02}', 'DT': '2', 'UNIT_NM': '%'} for i in range(1, 5)]
    output = OutputAgent().prepare(source, {'quick_output': True})
    assert output['chartState']['layout'] == 'separate'
    assert len(output['table']['rows']) == 16


@pytest.mark.parametrize('text,expected', [('원계열 실질 추이', None), ('누적 막대 그래프', 'stacked_bar'), ('선 그래프', 'line'), ('도넛 그래프', 'donut'), ('트리맵', 'treemap')])
def test_chart_words_never_change_statistical_terms(text, expected):
    assert requested_chart(text) == expected


def test_complex_chart_request_is_not_silently_reinterpreted():
    with pytest.raises(ValueError, match='복합 차트'):
        requested_chart('금리는 선 그래프, 물가는 막대 그래프로')
