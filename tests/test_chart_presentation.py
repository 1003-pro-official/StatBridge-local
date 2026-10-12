import pytest
from test_research_chart_edit import source
from output_agent import OutputAgent
from output_schema import ChartSpec
from plotly_renderer import render_plotly
from chart_availability import inspect_charts


def series(count):
    return OutputAgent()._series(source(count)['execution']['rows'])


@pytest.mark.parametrize('kind',['line','bar','stacked_bar','area','scatter','bubble','pie','donut','histogram','box','heatmap','treemap','waterfall'])
def test_all_types_have_safe_layout_and_original_values(kind):
    items=series(1 if kind=='waterfall' else 3 if kind=='bubble' else 2)
    original=[p.copy() for s in items for p in s['points']]
    fig=render_plotly(items,ChartSpec(chart_type=kind,title='아주 긴 통계표 이름을 여러 개 비교하는 그래프 제목이며 줄바꿈이 필요합니다'))
    assert fig['data'] and fig['layout']['margin']['t']>=100
    assert '<br>' in fig['layout']['title']['text']
    assert original==[p for s in items for p in s['points']]
    if kind not in {'pie','donut','treemap'}:
        assert fig['layout']['xaxis']['title']['text']
        assert fig['layout']['yaxis']['title']['text']


def test_separate_panels_have_gap_and_unit_axes():
    items=series(2);items[0]['unit']='%';items[1]['unit']='천건'
    for item in items:item['label']='아주 긴 예금은행 고정 및 변동금리대출 비중 및 신용카드 내역 '+item['label']
    fig=render_plotly(items,ChartSpec(chart_type='area',layout='separate'))
    layout=fig['layout']
    assert layout['height']>=800
    assert layout['yaxis']['domain'][0]-layout['yaxis2']['domain'][1]>=.17
    assert layout['yaxis']['title']['text']=='%' and layout['yaxis2']['title']['text']=='천건'
    assert all('<br>' in a['text'] for a in layout['annotations'])


def test_scatter_explains_axes_time_values_and_units():
    items=series(2);items[0]['unit']='%';items[1]['unit']='천건'
    fig=render_plotly(items,ChartSpec(chart_type='scatter'))
    assert '계열0' in fig['layout']['xaxis']['title']['text']
    assert '천건' in fig['layout']['yaxis']['title']['text']
    trace=fig['data'][0]
    assert '시점:' in trace['hovertemplate'] and '계열1' in trace['hovertemplate']
    assert trace['customdata'][0][1:4]==['202401',10,10]


def test_actual_blocker_counts_and_units_and_dates():
    items=series(2);items[0]['unit']='%';items[1]['unit']='천건'
    allowed,blocked=inspect_charts(items)
    assert 'scatter' in allowed
    assert '현재 2개' in blocked['bubble'] and '1개 지표를 추가' in blocked['bubble']
    assert '%' in blocked['pie'] and '천건' in blocked['pie']
    for point in items[1]['points']:point['date']='2030'+point['date'][4:]
    allowed,blocked=inspect_charts(items)
    assert '관측값이 0개' in blocked['scatter'] and '2030' in blocked['scatter']


def test_extra_scatter_series_are_not_silently_dropped():
    with pytest.raises(ValueError,match='현재 3개'):
        render_plotly(series(3),ChartSpec(chart_type='scatter'))


def test_heatmap_keeps_wrapped_category_ticks():
    items=series(2)
    for item in items:item['label']='아주 긴 통계표 이름과 항목의 전체 이름 '+item['label']
    axis=render_plotly(items,ChartSpec(chart_type='heatmap'))['layout']['yaxis']
    assert axis['tickmode']=='array' and all('<br>' in t for t in axis['ticktext'])


def test_waterfall_accumulates_changes_not_observed_levels():
    items=series(1)
    items[0]['points']=[{'date':'2020','value':100},{'date':'2021','value':120},{'date':'2022','value':110}]
    trace=render_plotly(items,ChartSpec(chart_type='waterfall'))['data'][0]
    assert trace['y']==[100,20,-10]
    assert trace['measure']==['absolute','relative','relative']
    assert [row[2] for row in trace['customdata']]==[100,120,110]


def test_mixed_unit_histograms_do_not_share_numeric_axis():
    items=series(2);items[0]['unit']='%';items[1]['unit']='천건'
    layout=render_plotly(items,ChartSpec(chart_type='histogram',layout='separate'))['layout']
    assert not layout['xaxis'].get('matches') and not layout['xaxis2'].get('matches')
    assert layout['yaxis']['title']['text']=='관측 수'
    assert '%' in layout['xaxis']['title']['text'] and '천건' in layout['xaxis2']['title']['text']


@pytest.mark.parametrize('kind',['pie','donut','treemap'])
@pytest.mark.parametrize('show_legend',[True,False])
def test_composition_has_visible_name_value_unit_date_without_hover(kind,show_legend):
    items=series(2)
    fig=render_plotly(items,ChartSpec(chart_type=kind,show_legend=show_legend,display_names={'계열0':''}))
    info=next(a['text'] for a in fig['layout']['annotations'] if '기준 시점:' in a['text'])
    assert all(word in info for word in ['계열0','계열1','202405','값:','구성비:','25'])
    assert items[0]['unit'] in info
    assert fig['data'][0]['labels'][0]=='계열0'
    assert '기준 시점: 202405' in fig['data'][0]['hovertemplate']
    assert fig['layout']['margin']['b']>=150


@pytest.mark.parametrize("kind", ["line", "area", "bar", "waterfall", "heatmap"])
def test_period_codes_have_ordered_categorical_axis_by_default(kind):
    items=series(2 if kind=="heatmap" else 1)
    fig=render_plotly(items, ChartSpec(chart_type=kind))
    assert fig["layout"]["xaxis"]["type"]=="category"
    assert fig["layout"]["xaxis"]["categoryarray"]==["202401","202402","202403","202404","202405"]
    assert list(fig["data"][0]["x"])==[p["date"] for p in items[0]["points"]]


def test_horizontal_bars_use_period_axis_without_categorizing_values():
    fig=render_plotly(series(1), ChartSpec(chart_type="bar", presentation={"bar_orientation":"horizontal"}))
    assert fig["layout"]["yaxis"]["type"]=="category"
    assert fig["layout"]["xaxis"].get("type")!="category"


def test_numeric_period_highlights_and_notes_use_category_positions():
    fig=render_plotly(series(1), ChartSpec(chart_type="line", highlights=[{"start":"202402","end":"202405"}],
        annotations=[{"period":"202403","text":"확인"}],
        notes=[{"label":"계열0","period":"202404","text":"관측값"}],
        guides=[{"orientation":"vertical","value":"202403"}]))
    highlight=fig["layout"]["shapes"][0]
    assert (highlight["x0"],highlight["x1"])==(1,4)
    assert fig["layout"]["shapes"][1]["x0"]==2
    assert {a["x"] for a in fig["layout"]["annotations"] if a.get("xref","x")=="x"}=={2,3,4}
