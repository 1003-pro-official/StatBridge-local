"""Available choices must render on the exact rows that were queried."""
import copy
import pytest
from test_research_chart_edit import source
from test_chart_edit_agent import FakeEditModel
from chart_edit_agent import ChartEditAgent
from output_agent import OutputAgent
from output_schema import ChartSpec
from plotly_renderer import render_plotly


def test_one_series_hides_unsupported_types():
    options=OutputAgent().inspect(source())
    assert {'bubble','scatter','pie','donut','treemap','heatmap'}.isdisjoint(options['supportedChartTypes'])
    assert {'line','bar','area','box','histogram','waterfall'}<=set(options['supportedChartTypes'])
    assert '3' in options['unavailableChartTypes']['bubble']


def test_mixed_units_layout_is_explicit_and_no_silent_split():
    data=source(2)
    for row in data['execution']['rows']:
        row['UNIT_NM']='%' if row['ITM_NM']=='계열0' else '천건'
    output=OutputAgent();options=output.inspect(data)
    assert '%' in options['combinedLayoutReason'] and '천건' in options['combinedLayoutReason']
    assert 'line' in options['supportedChartTypes'] and 'scatter' in options['supportedChartTypes']
    with pytest.raises(ValueError,match='같은 축'):
        output.prepare(data,{'chart_type':'line','layout':'combined'})
    with pytest.raises(ValueError,match='같은 축'):
        render_plotly(output._series(data['execution']['rows']),ChartSpec(chart_type='line'))
    assert output.prepare(data,{'chart_type':'line','layout':'separate'})['chartState']['layout']=='separate'
    assert output.prepare(data,{'chart_type':'scatter'})['chartState']['layout']=='combined'


@pytest.mark.parametrize('count',[1,2,3])
def test_every_advertised_choice_actually_renders(count):
    output=OutputAgent();data=source(count)
    for kind in output.inspect(data)['supportedChartTypes']:
        result=output.prepare(data,{'chart_type':kind})
        assert result['status']=='ready' and result['plotlyFigure']['data']


def test_negative_latest_values_disable_composition():
    data=source(2)
    for row in data['execution']['rows']:
        if row['ITM_NM']=='계열0' and row['PRD_DE']=='202405':row['DT']='-1'
    assert {'pie','donut','treemap'}.isdisjoint(OutputAgent().inspect(data)['supportedChartTypes'])


def test_no_common_period_disables_scatter_and_bubble():
    data=source(3)
    for row in data['execution']['rows']:
        if row['ITM_NM']=='계열1':row['PRD_DE']='2030'+row['PRD_DE'][4:]
    assert {'scatter','bubble','pie','donut','treemap'}.isdisjoint(OutputAgent().inspect(data)['supportedChartTypes'])


def test_zero_sum_composition_and_no_numeric_data():
    data=source(2)
    for row in data['execution']['rows']:row['DT']='0'
    assert {'pie','donut','treemap'}.isdisjoint(OutputAgent().inspect(data)['supportedChartTypes'])
    for row in data['execution']['rows']:row['DT']='-'
    assert OutputAgent().inspect(data)['supportedChartTypes']==[]


def test_non_finite_values_are_not_plottable_numeric_data():
    data=source()
    for index,row in enumerate(data['execution']['rows']):row['DT']=['NaN','Infinity','-Infinity'][index%3]
    assert OutputAgent().inspect(data)['supportedChartTypes']==[]


def test_options_endpoint_checks_combined_session_rows(monkeypatch):
    import bridge_api as api
    from fastapi.testclient import TestClient
    all_data=source(3)
    for index in range(3):
        data=copy.deepcopy(all_data)
        data['execution']['rows']=[r for r in data['execution']['rows'] if r['ITM_NM']==f'계열{index}']
        monkeypatch.setitem(api.OUTPUT_SESSIONS,f'options-{index}',{'result':data})
    client=TestClient(api.app)
    assert 'bubble' not in client.post('/api/output/options',json={'session_ids':['options-0']}).json()['supportedChartTypes']
    assert 'bubble' in client.post('/api/output/options',json={'session_ids':['options-0','options-1','options-2']}).json()['supportedChartTypes']
    assert client.post('/api/output/options',json={'session_ids':['not-existing']}).status_code==404


def test_title_creation_at_mark_and_legend_move_need_no_period():
    output=OutputAgent();data=source();initial=output.prepare(data,{'chart_type':'bar'})
    visual={'marks':[
        {'id':'t','tool':'text','target':'chart','text':'제목을 만들어서 이 위치에 넣어줘','points':[{'x':.4,'y':.1}]},
        {'id':'l','tool':'rectangle','target':'legend','text':'오른쪽 위로 위치 이동 시켜줘','points':[{'x':.1,'y':.1},{'x':.3,'y':.2}]},
    ]}
    model=FakeEditModel({'commands':[{'operation':'set_title','value':'조회한 계열의 추이'}, {'operation':'set_legend','value':'top-right'}]})
    result=ChartEditAgent(model,output).edit(data,initial,'',visual)
    assert result['plotlyFigure']['layout']['title']['x']==.4
    assert result['plotlyFigure']['layout']['title']['y']==.9
    assert result['chartState']['legend_position']=='top-right'
    assert result['plotlyFigure']['layout']['legend']['xanchor']=='right'
    assert result['table']==initial['table']
