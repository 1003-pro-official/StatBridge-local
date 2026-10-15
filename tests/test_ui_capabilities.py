"""Discovery choices are executable branches, exports follow current state."""
import pytest
from output_agent import OutputAgent
from output_schema import ChartSpec
from report_export import export_formats, render_file

@pytest.mark.parametrize('basis',['신규취급액','잔액'])
def test_comparison_basis_is_asked_once_and_every_table_choice_resolves(basis):
    from bridge_api import agent
    query='대출금리와 생산자 물가를 비교해줘'
    first=agent.resolve(query)
    assert first['clarification_id']=='comparison:0:interest_basis'
    second=agent.resolve(query,first['state'],{'clarification_id':first['clarification_id'],'value':basis})
    def visit(result,depth=0):
        assert depth<5
        if result['status']=='resolved':
            assert len(result['api_plans'])==2
            assert basis in result['api_plans'][0]['table_name']
            return
        assert result['status']=='need_clarification'
        assert result['clarification_id']!=first['clarification_id']
        assert result['options']
        assert 'DT_404Y017' not in [o['value'] for o in result['options']]
        for option in result['options']:
            visit(agent.resolve(query,result['state'],{'clarification_id':result['clarification_id'],'value':option['value']}),depth+1)
    visit(second)

def test_explicit_period_excludes_historical_comparison_table():
    from bridge_api import agent
    q='신규취급액 기준 대출금리와 생산자 물가를 2020년부터 2025년까지 비교해줘'
    result=agent.resolve(q)
    assert result['status']=='need_clarification'
    assert 'DT_404Y017' not in [o['value'] for o in result['options']]

@pytest.mark.parametrize('kind',['pie','donut','treemap','box','histogram'])
def test_screen_only_chart_does_not_offer_vector_exports(kind):
    series=[{'label':'검증','frequency':'M','unit':'원','points':[{'date':'202001','value':10},{'date':'202002','value':20}]}]
    assert export_formats(series,ChartSpec(chart_type=kind),{})==['png','csv']

def test_export_preflight_and_renderer_share_style_rejection():
    series=[{'label':'검증','frequency':'M','unit':'원','points':[{'date':'202001','value':10},{'date':'202002','value':20}]}]
    spec=ChartSpec(chart_type='line',series_styles={'검증':{'line_shape':'spline'}})
    assert export_formats(series,spec,{})==['png','csv']
    with pytest.raises(ValueError,match='비선형'):
        render_file(series,spec,{},'svg')
