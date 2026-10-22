import json
from types import SimpleNamespace

from report_summary import explain, facts_for
from output_agent import OutputAgent
from output_schema import ChartSpec


def series(values, dates=None, frequency='M', unit='개'):
    return [{'label': '관측지표', 'unit': unit, 'frequency': frequency,
             'points': [{'date': date, 'value': value} for date, value in
                        zip(dates or ['202501', '202502', '202503'], values)]}]


def test_recent_level_change_and_pace_in_honorifics():
    result = explain(series([10, 12, 15]))
    assert '2025년 3월 관측값은 15 개입니다.' in result['text']
    assert '전월(2025년 2월, 12 개) 대비 3 개 상승하였습니다.' in result['text']
    assert '상승폭은 직전 기간보다 확대되었습니다.' in result['text']
    assert '최고' not in result['text']


def test_gaps_never_become_previous_period_or_consecutive_run():
    facts = facts_for(series([10, 20, 30], ['202501', '202503', '202505']))
    assert not {'previous', 'run', 'pace', 'turn'} & {f['kind'] for f in facts}


def test_quarters_yearly_and_percentage_points():
    text = explain(series([2.5, 3, 3.25], ['202401', '202404', '202501'], 'Q', '%'))['text']
    assert '2025년 1분기' in text and '전분기' in text
    assert '0.25 %p 상승하였습니다' in text
    assert '전년동기' in text and '0.75 %p' in text


def test_zero_negative_single_missing_and_mixed_units():
    data = series([0, -2, -2]) + series([100], ['202503'], unit='원')
    text = explain(data)['text']
    assert '같은 수준을 유지하였습니다.' in text
    assert '100 원입니다.' in text
    assert '성장률' not in text
    assert explain([])['source'] == 'rules'


class Model:
    configured = True
    settings = SimpleNamespace(main_model='mock-gpt')

    def __init__(self, response):
        self.response = response

    def chat_main(self, system, user, **kwargs):
        self.context = json.loads(user)
        assert '존댓말' in system
        assert '원인·전망' in system
        return self.response, {}


def test_model_selects_evidence_but_cannot_write_claims():
    data = series([10, 12, 15])
    model = Model('{"fact_ids":["s0-latest","s0-previous","s0-run"]}')
    result = explain(data, model)
    assert result['source'] == 'mock-gpt'
    assert '2개월 연속 상승하였습니다.' in result['text']
    assert set(model.context) == {'facts'}
    for bad in ['정책 효과로 앞으로 성장합니다.', '{"fact_ids":["invented"]}',
                '{"fact_ids":["s0-latest"],"text":"금리 인하로 증가합니다."}',
                '{"fact_ids":["s0-previous","s0-latest"]}']:
        rejected = explain(data, Model(bad))
        assert rejected['source'] == 'rules'
        assert rejected['text'] == explain(data)['text']


def test_summary_uses_original_rows_and_plan_frequency_not_chart_transform():
    result = {'api_plan': {'table_id': 'T', 'frequency': 'Q'}, 'execution': {'rows': [
        {'PRD_DE': date, 'DT': str(value), 'ITM_NM': '지표', 'UNIT_NM': '개'}
        for date, value in [('202501', 10), ('202502', 20), ('202503', 30)]]}}
    output = OutputAgent()._build(result, ChartSpec(chart_type='line', transform='cumulative'))
    assert output['table']['rows'][-1]['value'] == 60
    assert '3분기 관측값은 30 개입니다.' in output['summary']
    assert '60' not in output['summary']


def test_style_edit_preserves_summary_and_evidence():
    from output_schema import ChartEditCommand
    agent = OutputAgent(Model('{"fact_ids":["s0-latest","s0-previous","s0-run"]}'))
    result = {'api_plan': {'table_id': 'T', 'frequency': 'M'}, 'execution': {'rows': [
        {'PRD_DE': date, 'DT': str(value), 'ITM_NM': '지표', 'UNIT_NM': '개'}
        for date, value in [('202501', 10), ('202502', 12), ('202503', 15)]]}}
    output = agent._build(result, ChartSpec(chart_type='line'))
    assert output['explanation']['source'] == 'mock-gpt'
    edited = agent.apply_edits(result, output, [ChartEditCommand(operation='set_title', kind='STYLE_EDIT', value='새 제목')],
                               generate_explanation=False)
    assert edited['summary'] == output['summary']
    assert edited['explanation'] == output['explanation']


def test_direction_reversal_is_observed_not_a_forecast():
    result = explain(series([10, 8, 9]))
    assert '하락에서 2025년 3월에 상승으로 전환하였습니다.' in result['text']
    assert '전망' not in result['text']


def test_kosis_annual_frequency():
    text = explain(series([10, 12, 15], ['2023', '2024', '2025'], 'Y'))['text']
    assert '전년(2024년' in text
    assert '상승폭은 직전 기간보다 확대되었습니다.' in text


def test_shared_number_formatter_preserves_small_nonzero_changes():
    from report_summary import display_number
    assert display_number(-8.036809815950907) == "-8.04"
    assert display_number(4.665283251760233) == "4.67"
    assert display_number(0.001) == "0.001"
