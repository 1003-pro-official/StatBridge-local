import copy
import pytest
from output_agent import OutputAgent
from output_schema import ChartEditCommand, ChartSpec
from report_export import render_file
from test_research_chart_edit import source

def command(op,**kwargs):return ChartEditCommand(operation=op,kind='STYLE_EDIT',**kwargs)

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
