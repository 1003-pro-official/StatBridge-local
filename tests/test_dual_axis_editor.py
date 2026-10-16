import copy
import pytest
from output_agent import OutputAgent
from output_schema import ChartEditCommand, ChartSpec
from report_export import render_file
from test_research_chart_edit import source

def command(op,**kwargs):return ChartEditCommand(operation=op,kind='STYLE_EDIT',**kwargs)

@pytest.mark.parametrize('text',['이중축 혼합차트로 비교해줘','잔액은 왼쪽 Y축, 증가율은 오른쪽 Y축으로 보여줘','선 그래프와 막대 그래프를 좌우 축에 그려줘','Y축 2개로 비교해줘'])
def test_explicit_initial_dual_axis_intent_works_without_model(text):
    data=source(2)
    for row in data['execution']['rows']:row['UNIT_NM']='조원' if row['ITM_NM']=='계열0' else '%'
    original=copy.deepcopy(data)
    result=OutputAgent().prepare(data,{'quick_output':True,'natural_language':text})
    assert result['chartState']['secondary_axis_series']==['계열1']
    assert result['chartState']['layout']=='combined'
    assert result['chartState']['series_chart_types']=={'계열0':'line','계열1':'bar'}
    assert any(t['type']=='bar' and t.get('yaxis')=='y2' for t in result['plotlyFigure']['data'])
    assert data==original

def test_dual_axis_intent_rejects_incompatible_data_and_respects_negation():
    from quick_output import dual_axis_requested
    assert not dual_axis_requested('이중축 없이 그려줘')
    assert not dual_axis_requested('이중축 사용하지 말고 한 축으로')
    data=source(2)
    for row in data['execution']['rows']:
        if row['ITM_NM']=='계열1':row['_FREQUENCY']='Q'
    with pytest.raises(ValueError,match='같은 주기'):
        OutputAgent().prepare(data,{'quick_output':True,'natural_language':'이중축으로 비교'})

def test_report_dual_axis_selection_and_separation_keep_editor_state_consistent():
    agent=OutputAgent();data=source(2)
    for row in data['execution']['rows']:row['UNIT_NM']='조원' if row['ITM_NM']=='계열0' else '%'
    first=agent.prepare(data,{'quick_output':True})
    dual=agent.apply_edits(data,first,[command('set_chart_type',value='line'),command('set_layout',value='combined'),command('set_report',params={'patch':{'kind':'dual_axis','right_axis':['계열1']}}),command('set_series_chart_types',params={'types':{'계열0':'line','계열1':'bar'}})],generate_explanation=False)
    assert dual['chartState']['secondary_axis_series']==['계열1']
    assert dual['chartState']['report']['right_axis']==['계열1']
    separate=agent.apply_edits(data,dual,[command('remove_secondary_axis',value='계열1'),command('set_layout',value='separate')],generate_explanation=False)
    assert separate['chartState']['secondary_axis_series']==[]
    assert separate['chartState']['layout']=='separate'
    assert separate['table']==first['table']

def test_dual_axis_titles_positions_export_and_removal():
    agent=OutputAgent();data=source(2);before=copy.deepcopy(data)
    first=agent.prepare(data,{'chart_type':'line'})
    edits=[command('set_series_chart_type',label='계열1',value='bar'),command('set_secondary_axis',value='계열1'),command('set_axis_style',label='y',params={'title':'잔액 (조원)','title_position':.9,'title_standoff':10}),command('set_axis_style',label='y2',params={'title':'증가율 (%)','minimum':-4,'maximum':12,'title_position':1,'title_standoff':15}),command('set_axis_style',label='x',params={'title':'조회 기간','title_position':1,'title_standoff':20})]
    result=agent.apply_edits(data,first,edits,generate_explanation=False)
    fig=result['plotlyFigure'];assert fig['layout']['yaxis2']['range']==[-4,12]
    assert any(t.get('yaxis')=='y2' and t['type']=='bar' for t in fig['data'])
    assert fig['layout']['yaxis']['overlaying']=='y2'
    titles={a['name']:a for a in fig['layout']['annotations'] if a.get('name','').startswith('statbridge-axis-title:')}
    assert titles['statbridge-axis-title:xaxis']['x']==1
    assert titles['statbridge-axis-title:yaxis2']['y']==1
    assert titles['statbridge-axis-title:yaxis2']['text']=='증가율 (%)'
    svg=render_file(agent._series(data['execution']['rows']),ChartSpec.model_validate(result['chartState']),data,'svg').decode()
    assert all(x in svg for x in ['잔액 (조원)','증가율 (%)','조회 기간'])
    assert data==before
    with pytest.raises(ValueError,match='왼쪽 축'):
        agent.apply_edits(data,result,[command('set_secondary_axis',value='계열0')],generate_explanation=False)
    reset=agent.apply_edits(data,result,[command('remove_secondary_axis',value='계열1')],generate_explanation=False)
    assert not reset['chartState']['secondary_axis_series']
    assert 'y2' not in reset['chartState']['axes']

@pytest.mark.parametrize('field,value',[('title_position',1.1),('title_standoff',100)])
def test_axis_position_bounds(field,value):
    with pytest.raises(ValueError):ChartSpec.model_validate({'axes':{'x':{field:value}}})

def test_dual_axis_auto_titles_use_only_assigned_units():
    agent=OutputAgent();data=source(2)
    for row in data['execution']['rows']:
        row['UNIT_NM']='조원' if row['ITM_NM']=='계열0' else '%'
    first=agent.prepare(data,{'chart_type':'line','layout':'separate'})
    result=agent.apply_edits(data,first,[command('set_secondary_axis',value='계열1'),command('set_layout',value='combined')],generate_explanation=False)
    assert result['plotlyFigure']['layout']['yaxis']['title']['text']=='조원'
    assert result['plotlyFigure']['layout']['yaxis2']['title']['text']=='%'
