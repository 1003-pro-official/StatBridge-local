"""ai-assisted: calendar comparison, presentation, and atomic API edit regressions."""
import copy
from types import SimpleNamespace

import pytest

from chart_comparison_history import ensure_comparison_history
from chart_data_transforms import annual_index_growth
from output_agent import OutputAgent
from output_schema import ChartSpec


def fixture():
    plan = dict(table_id='DT_TEST', table_name='수출물량지수', item_id='ITEM',
                classifications={'A': 'semiconductor'}, frequency='M', org_id='301',
                start_period='202401', end_period='202512', exact_params={})
    rows = [dict(TBL_ID='DT_TEST', PRD_DE=f'{year}{month:02}', DT=str(value), UNIT_NM='2020=100',
                 C1_NM='반도체', _SERIES_LABEL='수출물량지수', _SOURCE_SERIES_ID='DT_TEST', _FREQUENCY='M')
            for year, value in ((2023, 100), (2024, 110), (2025, 99)) for month in range(1, 13)]
    data = {'api_plan': plan, 'execution': {'status': 'success', 'rows': rows[12:]}}
    captured = []
    def batch(requests):
        captured.extend(requests)
        return {'results': [{'status': 'success', 'data': {'status': 'success', 'rows': ([{**rows[0], 'PRD_DE': str(y), 'DT': str(v)} for y,v in ((2023,100),(2024,109),(2025,126.44))] if requests[0]['frequency']=='Y' else rows), 'source': 'synthetic'}}]}
    return data, SimpleNamespace(get_statistics_batch=batch), captured


def spec(**kwargs):
    return ChartSpec(chart_type='bar', title='반도체 수출물량지수 추이', transform='year_over_year',
                     presentation={'publication_yoy': True, 'design_template': 'snapshot', 'latest_values': False}, **kwargs)


def test_publication_canvas_and_plot_follow_compact_reference_ratio():
    original, service, _ = fixture()
    data = ensure_comparison_history(original, service)
    output = OutputAgent()._build(data, spec(), generate_explanation=False)
    layout = output['plotlyFigure']['layout']
    assert (layout['width'], layout['height']) == (715, 662)
    margin = layout['margin']
    plot_ratio = (layout['width']-margin['l']-margin['r'])/(layout['height']-margin['t']-margin['b'])
    assert plot_ratio == pytest.approx(474/360, rel=.01)


@pytest.mark.parametrize('settings,expected', [({'width':1430},(1430,1324)),({'width':1000,'height':700},(1000,700)),({'height':900},(715,900))])
def test_explicit_publication_pixels_override_reference_defaults(settings,expected):
    from publication_chart import publication_image_size
    from output_schema import PresentationStyle
    assert publication_image_size(PresentationStyle(**settings)) == expected


def test_history_preserves_original_plans_and_start_and_is_cached():
    original, service, requests = fixture()
    before = copy.deepcopy(original)
    data = ensure_comparison_history(original, service)
    assert original == before
    assert requests[0]['start_period'] == '202301'
    assert requests[0]['item_id'] == 'ITEM' and requests[0]['classifications'] == {'A': 'semiconductor'}
    assert data['api_plan'] == before['api_plan']
    output = OutputAgent()._build(data, spec(), generate_explanation=False)
    series = output['visualization']['series'][0]
    assert len(series['points']) == 24
    assert series['points'][0]['date'] == '202401'
    assert series['points'][0]['value'] == pytest.approx(10)
    assert series['points'][-1]['value'] == pytest.approx(-10)
    assert series['unit'] == '%'
    assert ensure_comparison_history(data, service) is data and len(requests) == 2
    assert output['table']['rows'][0]['unit'] == '%'
    figure = output['plotlyFigure']
    assert figure['data'][0]['type'] == 'bar'
    assert figure['layout']['yaxis']['range'] == figure['layout']['yaxis2']['range']
    assert figure['layout']['xaxis']['range'] == [-.5, 23.5]
    mirror = next(t for t in figure['data'] if t.get('meta', {}).get('role') == 'axis-mirror')
    assert mirror['y'][0] == series['points'][0]['value']
    assert figure['layout']['showlegend'] is False
    assert [a['value'] for a in series['annualGrowth']] == pytest.approx([9,16])


def test_filter_uses_history_before_cropping_and_raw_restore_is_exact():
    original, service, _ = fixture()
    data = ensure_comparison_history(original, service)
    agent = OutputAgent()
    filtered = agent._build(data, spec(period_start='202407', period_end='202409'), generate_explanation=False)
    assert [r['period'] for r in filtered['table']['rows']] == ['202407', '202408', '202409']
    raw = agent._build(data, ChartSpec(chart_type='line'), generate_explanation=False)
    assert raw['table']['rows'][0]['value'] == 110
    assert len(raw['table']['rows']) == 24 and raw['table']['rows'][0]['unit'] == '2020=100'


def test_fullwidth_index_unit_and_export_use_same_values():
    from report_export import document, restore_document
    data, service, _ = fixture()
    data = ensure_comparison_history(data, service)
    for row in data['execution']['rows'] + data['execution']['chartComparisonHistory'] + data['execution']['chartAnnualIndices']:
        row['UNIT_NM'] = '2020＝100'
    output = OutputAgent()._build(data, spec(), generate_explanation=False)
    assert len(output['visualization']['series'][0]['annualGrowth']) == 2
    exported = document(data, spec())
    assert exported['series'][0]['points'] == output['visualization']['series'][0]['points']
    assert restore_document(data, exported) == spec()
    assert output['exportFormats'] == ['png', 'csv']


def test_partial_years_zero_and_missing_base_are_not_invented():
    original, service, _ = fixture()
    data = ensure_comparison_history(original, service)
    history = data['execution']['chartComparisonHistory']
    history[0]['DT'] = '0'
    history.pop(1)
    output = OutputAgent()._build(data, spec(), generate_explanation=False)
    assert output['table']['rows'][0]['period'] == '202403'
    assert any('2개' in w for w in output['warnings'])
    # Monthly indices never stand in for the independently published annual index.
    points = [{'date': r['PRD_DE'], 'value': float(r['DT'])} for r in history]
    assert annual_index_growth(points, '202401', '202512') == []
    annual = [{'date':'2023','value':0},{'date':'2024','value':109},{'date':'2025','value':126.44}]
    assert [a['value'] for a in annual_index_growth(annual,'202401','202512')] == pytest.approx([16])
    assert annual_index_growth(annual, '202507', '202512') == []
    data['execution']['chartAnnualIndices']=[]
    assert not OutputAgent()._build(data,spec(),generate_explanation=False)['visualization']['series'][0]['annualGrowth']



def test_percentage_cannot_be_transformed_again():
    data, service, _ = fixture()
    for row in data['execution']['rows']:
        row['UNIT_NM'] = '%'
    with pytest.raises(ValueError, match='이미 비율'):
        ensure_comparison_history(data, service)
    with pytest.raises(ValueError, match='이미 비율'):
        OutputAgent()._build(data, spec(), generate_explanation=False)


def test_quarterly_view_keeps_quarter_labels():
    data, _, _ = fixture()
    rows = data['execution']['rows']
    data['execution']['rows'] = [r for r in rows if r['PRD_DE'][-2:] in {'01', '02', '03', '04'}]
    data['api_plan']['frequency'] = 'Q'
    for row in data['execution']['rows']:
        row['_FREQUENCY'] = 'Q'
    output = OutputAgent()._build(data, spec(), generate_explanation=False)
    assert output['plotlyFigure']['layout']['xaxis']['ticktext'] == ['2025 Q1', '2025 Q2', '2025 Q3', '2025 Q4']


def test_api_edit_undo_redo_and_failure_are_atomic(monkeypatch):
    import bridge_api as api
    from authenticated_client import TestClient
    data, service, _ = fixture()
    agent = OutputAgent()
    initial = agent._build(data, ChartSpec(chart_type='line'), generate_explanation=False)
    session = {'result': data, 'output': initial, 'sessions': [{'query': '반도체 수출물량지수 추이',
        'table_name': '수출물량지수', 'frequency': 'M', 'period': {'start': '2024-01-01', 'end': '2025-12-31'}}], 'undo': [], 'redo': []}
    monkeypatch.setattr(api.agent, 'service', service)
    monkeypatch.setattr(api.agent, 'output_agent', agent)
    monkeypatch.setattr(api, '_table_card', lambda tid: {'tableId': tid})
    monkeypatch.setitem(api.EDIT_SESSIONS, 'publication-test', session)
    client = TestClient(api.app)
    commands = [dict(operation='set_transform', kind='DATA_EDIT', value='year_over_year'),
                dict(operation='set_chart_type', kind='STYLE_EDIT', value='bar'),
                dict(operation='set_presentation', kind='STYLE_EDIT', params={'publication_yoy': True, 'latest_values': False})]
    def edit(**payload):
        return client.post('/api/output/edit', json={'edit_session_id': 'publication-test', **payload})
    response = edit(commands=commands, revision=0)
    assert response.status_code == 200, response.text
    assert len(response.json()['chart'][0]['points']) == 24
    csv = client.post('/api/table/export', json={'edit_session_id': 'publication-test', 'format': 'csv', 'revision': 1})
    assert csv.status_code == 200 and '2024' in csv.text
    exported = client.post('/api/report/export', json={'edit_session_id': 'publication-test', 'format': 'json', 'revision': 1})
    assert exported.status_code == 200
    assert len(exported.json()['series'][0]['points']) == 24
    assert edit(action='undo', revision=1).status_code == 200
    assert session['result'] == data and session['output']['chartState']['transform'] == 'raw'
    assert edit(action='redo', revision=2).status_code == 200
    assert session['output']['chartState']['transform'] == 'year_over_year'
    assert edit(action='undo', revision=3).status_code == 200
    before = copy.deepcopy(session)
    monkeypatch.setattr(service, 'get_statistics_batch', lambda _: {'results': [{'status': 'error'}]})
    assert edit(commands=commands, revision=4).status_code == 422
    assert session == before


def test_switching_back_to_raw_and_normal_style_preserves_original_values():
    from output_schema import ChartEditCommand
    data, service, _ = fixture()
    data = ensure_comparison_history(data, service)
    agent = OutputAgent()
    initial = agent._build(data, spec(), generate_explanation=False)
    normal = agent.apply_edits(data, initial, [ChartEditCommand(operation='set_chart_type', kind='STYLE_EDIT', value='line')], generate_explanation=False)
    assert normal['chartState']['transform'] == 'year_over_year'
    assert not normal['chartState']['presentation']['publication_yoy']
    raw = agent.apply_edits(data, initial, [ChartEditCommand(operation='set_transform', kind='DATA_EDIT', value='raw')], generate_explanation=False)
    assert raw['table']['rows'][0]['value'] == 110
    assert raw['chartState']['y_axis_label'] == ''
    assert not raw['chartState']['presentation']['publication_yoy']


def test_reference_api_uses_one_pass_and_commits_comparison_data_atomically(monkeypatch):
    import json
    import bridge_api as api
    from authenticated_client import TestClient
    from chart_edit_agent import ChartEditAgent
    from openai_chart_client import OpenAIChartClient, OpenAIEditModel
    from test_axis_reference_performance import reference, Response
    class Transport:
        calls=0
        def post(self,url,**kwargs):
            self.calls+=1
            return Response(json.dumps({'commands':[], 'reference_style':{'chart_type':'bar',
                'panel_count':1,'columns':1,'comparison':'year_over_year','comparison_label':'전년동기대비, %'}}))
    data,service,_=fixture()
    agent=OutputAgent()
    initial=agent._build(data,ChartSpec(chart_type='line'),generate_explanation=False)
    session={'result':data,'output':initial,'sessions':[{'query':'지수 추이','table_name':'수출물량지수',
        'frequency':'M','period':{'start':'2024-01-01','end':'2025-12-31'}}],'undo':[],'redo':[]}
    transport=Transport()
    monkeypatch.setattr(api,'edit_agent',ChartEditAgent(OpenAIEditModel(OpenAIChartClient(api_key='synthetic',session=transport)),agent))
    monkeypatch.setattr(api.agent,'service',service)
    monkeypatch.setattr(api.agent,'output_agent',agent)
    monkeypatch.setattr(api,'_table_card',lambda tid:{'tableId':tid})
    monkeypatch.setitem(api.EDIT_SESSIONS,'reference-test',session)
    client=TestClient(api.app)
    def edit(**payload):return client.post('/api/output/edit',json={'edit_session_id':'reference-test',**payload})
    payload={'instruction':'이 형식으로 수정해줘','reference_files':[reference()]}
    response=edit(**payload,revision=0)
    assert response.status_code==200,response.text
    assert transport.calls==1
    spec=response.json()['outputSpec']
    assert spec['chartState']['presentation']['publication_yoy']
    assert spec['chartState']['series_colors']['수출물량지수 · 반도체']=='#8eace1'
    assert set(spec['plotlyFigure']['data'][0]['marker']['color'])=={'rgba(142,172,225,1)'}
    assert response.json()['chart'][0]['points'][0]['value']==pytest.approx(10)
    assert [a['value'] for a in spec['visualization']['series'][0]['annualGrowth']]==pytest.approx([9,16])
    assert len(session['result']['execution']['chartAnnualIndices'])==3
    assert 'reference_files' not in str(session['output']['chartState'])
    assert edit(action='undo',revision=1).status_code==200
    assert session['result']==data
    before=copy.deepcopy(session)
    monkeypatch.setattr(service,'get_statistics_batch',lambda _: {'results':[{'status':'error'}]})
    assert edit(**payload,revision=2).status_code==422
    assert session==before
