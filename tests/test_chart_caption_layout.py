from output_schema import ChartSpec
from plotly_renderer import render_plotly
import pytest


def sample(count):
    return [{'id':str(i),'label':f'검증 지표 {i+1}','color':'#005b96','unit':'%','frequency':'M','points':[{'date':f'2020{m:02d}','value':10+i+m} for m in range(1,13)]} for i in range(count)]


@pytest.mark.parametrize('count', range(1, 11))
def test_long_heading_and_top_legend_have_separate_pixel_lanes(count):
    spec = ChartSpec(title='긴 통계 제목 ' * 15, legend_position='top')
    layout = render_plotly(sample(count), spec)['layout']
    title_bottom = .04 * layout['height'] + (layout['title']['text'].count('<br>') + 1) * (spec.presentation.title_size + 5)
    rows = (count + 1) // 2
    plot_height = layout['height'] - layout['margin']['t'] - layout['margin']['b']
    legend_top = layout['margin']['t'] - (layout['legend']['y']-1)*plot_height - rows * (spec.presentation.legend_size + 12)
    assert legend_top >= title_bottom + 16
    assert layout['height'] - layout['margin']['t'] - layout['margin']['b'] >= 320

@pytest.mark.parametrize('count',range(1,11))
@pytest.mark.parametrize('mode',['combined','separate','horizontal','grid'])
def test_caption_lanes_are_below_ticks_axis_title_and_legend(count,mode):
    fig=render_plotly(sample(count),ChartSpec(chart_type='line',layout=mode,legend_position='bottom',presentation={'notes':'자료: KOSIS · '+('통계표 코드와 출처 ' * 12)}))
    footer=[a for a in fig['layout']['annotations'] if str(a.get('name','')).startswith('statbridge-footer:')]
    assert len(footer)==1
    assert footer[0]['y']==0 and footer[0]['yshift']<-120
    assert '<br>' in footer[0]['text']
    assert fig['layout']['margin']['b']>-footer[0]['yshift']+20
    assert fig['layout']['height']>fig['layout']['margin']['t']+fig['layout']['margin']['b']

@pytest.mark.parametrize('count',range(2,11))
@pytest.mark.parametrize('kind',['pie','donut','treemap'])
def test_category_plot_and_each_caption_have_their_own_space(count,kind):
    fig=render_plotly(sample(count),ChartSpec(chart_type=kind,presentation={'notes':'자료: KOSIS'}))
    footers=[a for a in fig['layout']['annotations'] if str(a.get('name','')).startswith('statbridge-footer:')]
    assert len(footers)==2 and footers[1]['yshift']<footers[0]['yshift']
    assert fig['layout']['height']-fig['layout']['margin']['t']-fig['layout']['margin']['b']>=320
    assert len(fig['data'][0]['values'])==count

@pytest.mark.parametrize('count',range(1,11))
@pytest.mark.parametrize('kind',['forecast','panels'])
def test_report_source_caption_reserves_axis_lanes(count,kind):
    from advanced_chart_render import plotly_report
    fig=plotly_report(sample(count),ChartSpec(chart_type='line',report={'kind':kind}),{'api_plan':{'table_id':'DT_LAYOUT'},'execution':{'sources':[{'source':'kosis_api'}]}})
    footers=[a for a in fig['layout']['annotations'] if str(a.get('name','')).startswith('statbridge-footer:')]
    assert len(footers)==1 and 'KOSIS' in footers[0]['text']
    assert footers[0]['y']==0 and footers[0]['yshift']<-120
    assert fig['layout']['margin']['b']>-footers[0]['yshift']+20
