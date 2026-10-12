import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'StatBridge-official/src/agent'))
from output_agent import OutputAgent
from output_schema import ChartSpec
from test_research_chart_edit import source
from research_plotly_styles import arrange_top_captions, cartesian_traces
import plotly.graph_objects as go


def test_default_title_is_centered_in_container_and_explicit_position_remains():
    output=OutputAgent()
    result=output._build(source(1),ChartSpec(title='제목'),generate_explanation=False)
    title=result['plotlyFigure']['layout']['title']
    assert (title['x'],title['xref'],title['xanchor'])==(.5,'container','center')
    result=output._build(source(1),ChartSpec(title='제목',presentation={'title_x':0}),generate_explanation=False)
    assert result['plotlyFigure']['layout']['title']['xanchor']=='left'


def test_duplicate_captions_removed_and_nearby_distinct_captions_stacked():
    fig=go.Figure()
    for x,text in [(0,'시작 시점'),(0,'시작 시점'),(1,'최솟값'),(25,'종료 시점'),(24,'최댓값')]:
        fig.add_annotation(x=x,y=1,yref='paper',text=text,showarrow=False)
    fig.add_annotation(name='user-note',x=0,y=1,yref='paper',text='사용자 메모',showarrow=False,yshift=7)
    arrange_top_captions(fig,26)
    assert len(fig.layout.annotations)==5
    assert fig.layout.annotations[0].yshift!=fig.layout.annotations[1].yshift
    assert fig.layout.annotations[2].yshift!=fig.layout.annotations[3].yshift
    assert fig.layout.annotations[4].yshift==7


def test_arrow_range_color_supported_for_bar_and_preserves_outside():
    spec=ChartSpec(chart_type='bar',range_styles=[{'label':'s','start':'202402','end':'202404','style':{'color':'#ff0000'}}])
    item={'label':'s','color':'#4568ff','points':[{'date':f'20240{i}','value':i} for i in range(1,5)]}
    trace=cartesian_traces(item,spec,'bar')[0]
    assert trace.marker.color[0]=='rgba(69,104,255,1)'
    assert list(trace.marker.color[1:])==['rgba(255,0,0,1)']*3


def test_explicit_bar_selection_overrides_model_series_type():
    output=OutputAgent()
    output._propose_spec=lambda series,raw: {'chart_type':'line','series_chart_types':{'계열0':'line'}}
    result=output.prepare(source(1),{'chart_type':'bar'})
    assert result['chartState']['chart_type']=='bar'
    assert not result['chartState']['series_chart_types']
    assert result['plotlyFigure']['data'][0]['type']=='bar'


def test_real_plotly_highlight_domain_captions_share_lanes_with_annotations():
    fig=go.Figure(go.Scatter(x=[0,1,2],y=[1,2,3]))
    fig.add_vrect(x0=0,x1=1,annotation_text='시작 시점')
    fig.add_annotation(x=1,y=1,yref='paper',text='최솟값',showarrow=False)
    arrange_top_captions(fig,3)
    assert len(fig.layout.annotations)==2
    assert fig.layout.annotations[0].yshift!=fig.layout.annotations[1].yshift


def test_followup_expands_current_anchored_box_one_actual_period():
    from highlight_followup import expand_highlight
    from output_schema import ChartEditCommand
    data=source(1);output=OutputAgent()
    spec=ChartSpec(chart_type='line',paper_shapes=[{'type':'rect','x0':.4,'x1':.8,'y0':.1,'y1':.9,'fill':'#ff0000','data_anchor':{'label':'계열0','start':'202403','end':'202405','y0':10,'y1':30}}])
    initial=output._build(data,spec,generate_explanation=False)
    command=expand_highlight('현재 강조되어있는 부분보다 한칸 앞까지 색을 넣어줘\n사용자가 고른 RGB 색상: 강조 영역 #22c55e',spec,output._series(data['execution']['rows']))
    edited=output.apply_edits(data,initial,[command])
    shape=edited['chartState']['paper_shapes'][0]
    assert shape['data_anchor']['start']=='202402' and shape['data_anchor']['end']=='202405'
    assert shape['fill']=='#22c55e' and shape['data_anchor']['y0']==10
    assert len(edited['chartState']['paper_shapes'])==1


def test_latest_user_box_is_current_region_instead_of_automatic_extrema():
    from highlight_followup import expand_highlight
    data=source(1);output=OutputAgent()
    spec=ChartSpec(paper_shapes=[{'type':'rect','x0':.3,'x1':.8,'y0':.1,'y1':.9,'fill':'#ff0000','data_anchor':{'label':'계열0','start':'202403','end':'202405','y0':10,'y1':30}}],highlights=[{'start':'202401','end':'202405','label':'전체 기간'},{'start':'202402','end':'202402','label':'최솟값'}])
    command=expand_highlight('현재 강조된 부분보다 한 칸 앞까지 색을 넣어줘 #22c55e',spec,output._series(data['execution']['rows']),[{'operation':'add_shape'}])
    assert command.operation=='update_shape' and command.value==spec.paper_shapes[0].id
    assert command.params['data_anchor']['start']=='202402'


def test_repeated_unit_subtitle_is_not_rendered_again():
    result=OutputAgent()._build(source(1),ChartSpec(title='신규취급액 (단위: 원)',subtitle='단위: 원'),generate_explanation=False)
    assert result['plotlyFigure']['layout']['title']['text'].count('단위: 원')==1
