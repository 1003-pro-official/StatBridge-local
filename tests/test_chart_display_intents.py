import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'StatBridge-official/src/agent'))
from chart_edit_intents import display_commands, selected_style
from output_schema import ChartSpec, SeriesStyle, PaperShape, Highlight
from output_agent import OutputAgent
from test_research_chart_edit import source


def test_first_output_has_no_model_invented_highlight():
    agent=OutputAgent()
    agent._propose_spec=lambda series,raw: {'highlights':[{'start':'202401','end':'202405','color':'#ffff00'}]}
    result=agent.prepare(source(1),{'chart_type':'line'})
    assert not result['chartState']['highlights']
    layout=result['plotlyFigure']['layout']
    assert layout['paper_bgcolor']==layout['plot_bgcolor']=='#ffffff'
    assert not layout.get('shapes')


def test_global_grid_and_regular_quarter_ticks():
    commands=display_commands('격자 무늬는 없애주고 기간은 일관적으로 해줘',ChartSpec(),[{'frequency':'Q'}])
    assert [(c.label,c.params) for c in commands]==[('x',{'show_grid':False,'zero_line':False}),('y',{'show_grid':False,'zero_line':False}),('x',{'tick_step':4})]


def test_selected_color_and_alpha_are_authoritative():
    instruction='사용자가 고른 RGB 색상: 화살표 이후 차트 #ef4444 불투명도 0.8, 박스 강조 #95989d 불투명도 0.4'
    from types import SimpleNamespace
    assert selected_style(instruction,'set_series_style',SimpleNamespace(tool='arrow'))=={'color':'#ef4444','opacity':.8}
    assert selected_style(instruction,'add_shape',SimpleNamespace(tool='rectangle'))=={'color':'#95989d','opacity':.4}


def test_full_transparency_is_valid():
    assert SeriesStyle(opacity=0).opacity==0
    assert PaperShape(type='rect',x0=0,x1=1,y0=0,y1=1,opacity=0).opacity==0
    assert Highlight(start='202401',end='202402',opacity=0).opacity==0


def test_picker_supersedes_old_mark_color_and_model_opacity():
    from test_chart_edit_agent import FakeEditModel
    from chart_edit_agent import ChartEditAgent
    agent=OutputAgent(); data=source(1)
    initial=agent.prepare(data,{'chart_type':'line'})
    model=FakeEditModel({'commands':[{'operation':'set_series_color','label':'계열0','value':'#90ee90','mark_id':'m'}]})
    mark={'id':'m','tool':'arrow','target':'chart','text':'빨간색으로 변경해줘','points':[{'x':.2,'y':.3},{'x':.4,'y':.5}],'selection':{'label':'계열0','scope':'series'}}
    output=ChartEditAgent(model,agent).edit(data,initial,'선 색 변경\n사용자가 고른 RGB 색상: 화살표 이후 차트 #22c55e 불투명도 0.4',{'marks':[mark]})
    assert '빨간색' not in model.context['visual']['marks'][0]['text']
    style=output['chartState']['series_styles']['계열0']
    assert style['color']=='#22c55e' and style['opacity']==.4


def test_render_regular_annual_quarter_ticks_and_no_vertical_grid():
    import plotly.graph_objects as go
    from research_plotly_styles import decorate
    periods=[str(y)+'0'+str(q) for y in range(2020,2027) for q in range(1,5)][:26]
    fig=go.Figure(go.Scatter(x=periods,y=list(range(26))))
    series=[{'label':'s','frequency':'Q','points':[{'date':d,'value':v} for v,d in enumerate(periods)]}]
    spec=ChartSpec(axes={'x':{'tick_step':4,'show_grid':False,'zero_line':False},'y':{'show_grid':False,'zero_line':False}})
    decorate(fig,series,spec,False)
    assert list(fig.layout.xaxis.tickvals)==[str(y)+'01' for y in range(2020,2027)]
    assert list(fig.layout.xaxis.ticktext)==[str(y)+'년' for y in range(2020,2027)]
    assert not fig.layout.xaxis.showgrid and not fig.layout.yaxis.showgrid


import pytest

@pytest.mark.parametrize("operation",["set_series_color","update_note"])
def test_draw_arrow_adds_visible_arrow_without_recoloring_series(operation):
    from test_chart_edit_agent import FakeEditModel
    from chart_edit_agent import ChartEditAgent
    agent=OutputAgent();data=source(1);initial=agent.prepare(data,{'chart_type':'line'})
    model=FakeEditModel({'commands':[{'operation':operation,'label':'계열0','value':'#ff0000'}]})
    mark={'id':'m','tool':'arrow','target':'chart','text':'','points':[{'x':.2,'y':.3},{'x':.4,'y':.5}],'selection':{'label':'계열0','scope':'segment','start':'202402','end':'202403'}}
    output=ChartEditAgent(model,agent).edit(data,initial,'화살표 부분에 크게 빨간색 화살표를 그려줘\n사용자가 고른 RGB 색상: 화살표 기호 #ef4444 불투명도 0.8',{'marks':[mark]})
    assert not output['chartState']['range_styles'] and not output['chartState']['series_styles']
    note=output['chartState']['notes'][-1]
    assert note['arrow'] and note['arrow_width']==5 and note['color']=='#ef4444'
    assert output['plotlyFigure']['layout']['annotations'][-1]['arrowwidth']==5


@pytest.mark.parametrize('symbol',['→','↗','↘','↔','★','●','■','▲','✓','!','♥','◆'])
def test_catalog_symbols_are_notes_not_wrong_shapes(symbol):
    from chart_edit_intents import symbol_note
    command=symbol_note(f'그래프 가운데에 {symbol} 기호를 크게 넣어줘')
    assert command.operation=='add_note' and command.params['text']==symbol and command.params['font_size']==30
