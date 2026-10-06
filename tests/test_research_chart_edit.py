"""Research presentation and partial-selection regressions with synthetic data."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/agent"))
from output_agent import OutputAgent
from output_schema import ChartEditCommand
from chart_edit_agent import ChartEditAgent
from test_chart_edit_agent import FakeEditModel
from test_output_agent_migration import fixture_result


def source(count=1):
    data=fixture_result(count)
    data["execution"]["rows"]=[{**r,"PRD_DE":period,"DT":str(value)} for r in data["execution"]["rows"][::3]
        for period,value in [("202401",10),("202402",20),("202403",15),("202404",30),("202405",25)]]
    return data


def edit(agent, data, initial, op, **kwargs):
    kind="DATA_EDIT" if op in {"hide_series","filter_period","set_top_n","set_transform"} else "STYLE_EDIT"
    return agent.apply_edits(data, initial, [ChartEditCommand(operation=op,kind=kind,**kwargs)])


def test_only_selected_edges_change_no_solid_under_dash():
    agent=OutputAgent(); data=source(); original=copy.deepcopy(data)
    initial=agent.prepare(data,{"chart_type":"line"})
    result=edit(agent,data,initial,"set_segment_style",label="계열0",start="202402",end="202404",params={"color":"#ff0000","dash":"dash"})
    lines=[t for t in result["plotlyFigure"]["data"] if t["mode"]=="lines"]
    assert [t["x"] for t in lines]==[["2024-01-01","2024-02-01"],["2024-02-01","2024-03-01","2024-04-01"],["2024-04-01","2024-05-01"]]
    assert [t["line"]["dash"] for t in lines]==["solid","dash","solid"]
    assert lines[0]["line"]["color"]==lines[2]["line"]["color"]!="#ff0000"
    assert result["table"]==initial["table"] and data==original
    assert sum(t.get("showlegend",True) for t in result["plotlyFigure"]["data"])==1


def test_point_style_does_not_restyle_edges():
    agent=OutputAgent(); data=source(); initial=agent.prepare(data,{"chart_type":"line"})
    result=edit(agent,data,initial,"set_point_style",label="계열0",start="202403",params={"color":"#ff0000","marker_symbol":"diamond","marker_size":18,"show_values":True})
    traces=result["plotlyFigure"]["data"]
    assert all(t["line"]["dash"]=="solid" and t["line"]["color"]!="#ff0000" for t in traces if t["mode"]=="lines")
    marker=traces[-1]
    assert marker["marker"]["symbol"]==["circle","circle","diamond","circle","circle"]
    assert marker["text"]==["","","15.0","",""]


@pytest.mark.parametrize("kind",["line","area","bar","stacked_bar","scatter","bubble"])
def test_partial_supported_charts(kind):
    agent=OutputAgent();data=source(3 if kind=='bubble' else 2 if kind=='scatter' else 1)
    initial=agent.prepare(data,{"chart_type":kind})
    result=edit(agent,data,initial,"set_point_style",label="계열0",start="202403",params={"color":"#ff0000","opacity":.5,"show_values":True})
    assert result["table"]==initial["table"]
    assert any("rgba(255,0,0,0.5)" in str(t) for t in result["plotlyFigure"]["data"])


def test_model_whole_series_command_is_scoped_to_explicit_selection():
    agent=OutputAgent();data=source();initial=agent.prepare(data,{"chart_type":"line"})
    model=FakeEditModel({"commands":[{"operation":"set_series_color","label":"계열0","value":"#ff0000"},{"operation":"set_series_dash","label":"계열0","value":"dash"}]})
    result=ChartEditAgent(model,agent).edit(data,initial,"이 구간만 빨간 점선",{"selection":{"label":"계열0","scope":"segment","start":"202402","end":"202404"}})
    assert not result["chartState"]["series_colors"]
    assert result["chartState"]["range_styles"][-1]["end"]=="202404"
    assert result["plotlyFigure"]["data"][0]["line"]["dash"]=="solid"


def multi_marks():
    return {"marks":[
        {"id":"arrow1","tool":"arrow","points":[{"x":.2,"y":.2},{"x":.3,"y":.4}],"target":"chart","text":"빨간 선", "selection":{"label":"계열0","scope":"segment","start":"202401","end":"202402"}},
        {"id":"box1","tool":"rectangle","points":[{"x":.3,"y":.2},{"x":.9,"y":.8}],"target":"chart","text":"구간 강조", "selection":{"label":"계열0","scope":"segment","start":"202403","end":"202405"}},
    ]}


def test_multiple_mark_ids_bind_different_commands_atomically():
    agent=OutputAgent();data=source();initial=agent.prepare(data,{"chart_type":"line"})
    original=copy.deepcopy(initial)
    model=FakeEditModel({"commands":[
        {"operation":"set_series_color","label":"계열0","mark_id":"arrow1","value":"#ff0000"},
        {"operation":"highlight_period","mark_id":"box1","value":"#ffeecc"},
    ]})
    result=ChartEditAgent(model,agent).edit(data,initial,"화살표 구간은 빨강, 박스는 강조",multi_marks())
    assert result["chartState"]["range_styles"][-1]["end"]=="202402"
    assert result["chartState"]["highlights"][-1]["start"]=="202403"
    assert initial==original


def test_arrow_onward_is_bound_to_tip_and_last_real_observation():
    agent=OutputAgent();data=source();initial=agent.prepare(data,{"chart_type":"line"})
    model=FakeEditModel({"commands":[{"operation":"set_series_color","label":"계열0","mark_id":"arrow1","value":"#ff0000"}]})
    result=ChartEditAgent(model,agent).edit(data,initial,"화살표부터 뒤로 빨간색으로 바꿔줘",{"marks":multi_marks()["marks"][:1]})
    style=result["chartState"]["range_styles"][-1]
    assert (style["start"],style["end"])==("202402","202405")
    assert result["plotlyFigure"]["data"][0]["line"]["color"]!="#ff0000"


def test_provider_without_mark_id_uses_explicit_unique_tool_references():
    agent=OutputAgent();data=source();initial=agent.prepare(data,{"chart_type":"line"})
    model=FakeEditModel({"commands":[
        {"operation":"set_series_color","label":"계열0","value":"#ff0000"},
        {"operation":"highlight_period","label":"계열0","value":"202403-202405"},
    ]})
    result=ChartEditAgent(model,agent).edit(data,initial,"화살표부터 뒤로 빨간색으로 바꿔주고 박스 부분 강조해줘",multi_marks())
    assert result["chartState"]["range_styles"][-1]["start"]=="202402"
    assert result["chartState"]["highlights"][-1]["start"]=="202403"


@pytest.mark.parametrize("mark_id",[None,"unknown"])
def test_multiple_mark_unbound_command_remains_fail_closed(mark_id):
    agent=OutputAgent();data=source();initial=agent.prepare(data,{"chart_type":"line"})
    command={"operation":"set_series_color","label":"계열0","value":"#ff0000"}
    if mark_id:command["mark_id"]=mark_id
    with pytest.raises(ValueError):
        ChartEditAgent(FakeEditModel({"commands":[command]}),agent).edit(data,initial,"빨갛게",multi_marks())


@pytest.mark.parametrize("visual",[{}, {"selection":{"label":"계열0","scope":"segment","start":"209901","end":"209902"}},
    {"selection":{"label":"계열0","scope":"point","start":"202402","end":"202402"}}])
def test_partial_ambiguity_and_invalid_point_dash_fail_atomic(visual):
    agent=OutputAgent();data=source();initial=agent.prepare(data,{"chart_type":"line"});before=copy.deepcopy(initial)
    model=FakeEditModel({"commands":[{"operation":"set_series_dash","label":"계열0","value":"dash"}]})
    with pytest.raises(ValueError):ChartEditAgent(model,agent).edit(data,initial,"이 부분만 점선",visual)
    assert initial==before


@pytest.mark.parametrize("op,kwargs",[
    ("set_segment_style",dict(label="계열0",start="202402",end="209901",params={"color":"#ff0000"})),
    ("set_point_style",dict(label="계열0",start="202402",params={"dash":"dash"})),
    ("set_series_style",dict(label="계열0",params={"width":100})),
    ("set_axis_style",dict(label="y",params={"minimum":3,"maximum":2})),
    ("set_axis_style",dict(label="x",params={"scale":"log"})),
    ("set_presentation",dict(params={"height":99999})),
    ("add_note",dict(params={"label":"계열0","period":"209901","text":"없는 점"})),
    ("add_guide",dict(params={"orientation":"vertical","value":"209901"})),
    ("add_shape",dict(params={"type":"rect","x0":2,"x1":.8,"y0":.2,"y1":.8})),
    ("reorder_series",dict(value=["없는 계열"])),
])
def test_invalid_edits_preserve_existing_graph(op,kwargs):
    agent=OutputAgent();data=source();initial=agent.prepare(data,{"chart_type":"line"});before=copy.deepcopy(initial)
    with pytest.raises(ValueError):edit(agent,data,initial,op,**kwargs)
    assert initial==before


def test_axes_presentation_and_series_properties_render():
    agent=OutputAgent();data=source(2);result=agent.prepare(data,{"chart_type":"line"})
    for op,kwargs in [
        ("set_series_style",dict(label="계열0",params={"color":"#123456","width":6,"dash":"dot","markers":False})),
        ("rename_series",dict(label="계열0",value="새 표시 이름")),
        ("reorder_series",dict(value=["계열1","계열0"])),
        ("set_axis_style",dict(label="y",params={"minimum":1,"maximum":40,"show_grid":False,"tick_step":5,"decimals":2})),
        ("set_presentation",dict(params={"font_size":16,"background":"#eeeeee","height":600,"margin_left":100,"notes":"출처: 합성자료"})),
    ]:result=edit(agent,data,result,op,**kwargs)
    figure=result["plotlyFigure"]
    assert figure["data"][1]["name"]=="새 표시 이름"
    assert figure["data"][1]["line"]=={"color":"#123456","dash":"dot","width":6.0,"shape":"linear"}
    assert figure["layout"]["yaxis"]["range"]==[1,40]
    assert figure["layout"]["yaxis"]["showgrid"] is False
    assert figure["layout"]["font"]["size"]==16 and figure["layout"]["height"]==600
    assert figure["layout"]["annotations"][-1]["text"]=="출처: 합성자료"


@pytest.mark.parametrize("layout",["separate","horizontal","grid"])
def test_panels(layout):
    agent=OutputAgent();data=source(3);initial=agent.prepare(data,{"chart_type":"line"})
    result=edit(agent,data,initial,"set_layout",value=layout)
    figure=result["plotlyFigure"]
    assert figure["data"][2]["xaxis"]=="x3"
    if layout=="horizontal":assert figure["layout"]["yaxis"]["domain"]==figure["layout"]["yaxis3"]["domain"]
    if layout=="grid":assert figure["layout"]["yaxis"]["domain"]!=figure["layout"]["yaxis3"]["domain"]


@pytest.mark.parametrize("suffix,params,update,field",[
    ("note",{"text":"관측점","label":"계열0","period":"202403","arrow":True},{"text":"변경","ax":50,"color":"#ff0000"},"notes"),
    ("guide",{"value":20,"text":"기준"},{"value":25,"dash":"dot"},"guides"),
    ("shape",{"type":"rect","x0":.1,"x1":.3,"y0":.2,"y1":.4},{"x0":.2,"color":"#ff0000"},"paper_shapes"),
])
def test_add_move_style_remove_decorations(suffix,params,update,field):
    agent=OutputAgent();data=source();initial=agent.prepare(data,{"chart_type":"line"})
    added=edit(agent,data,initial,f"add_{suffix}",params=params);identifier=added["chartState"][field][0]["id"]
    changed=edit(agent,data,added,f"update_{suffix}",value=identifier,params=update)
    assert all(changed["chartState"][field][0][key]==value for key,value in update.items())
    assert identifier in str(changed["plotlyFigure"])
    removed=edit(agent,data,changed,f"remove_{suffix}",value=identifier)
    assert not removed["chartState"][field] and identifier not in str(removed["plotlyFigure"])
    assert initial["table"]==removed["table"]


def test_highlight_edit_remove_and_reset():
    agent=OutputAgent();data=source();result=agent.prepare(data,{"chart_type":"line"})
    result=edit(agent,data,result,"highlight_period",start="202402",end="202404",label="강조")
    identifier=result["chartState"]["highlights"][0]["id"]
    result=edit(agent,data,result,"update_highlight",value=identifier,params={"color":"#ff0000","opacity":.3})
    assert result["plotlyFigure"]["layout"]["shapes"][0]["fillcolor"]=="#ff0000"
    result=edit(agent,data,result,"remove_highlight",value=identifier)
    result=edit(agent,data,result,"set_point_style",label="계열0",start="202402",params={"color":"#ff0000"})
    identifier=result["chartState"]["range_styles"][0]["id"]
    result=edit(agent,data,result,"remove_range_style",value=identifier)
    result=edit(agent,data,result,"set_series_style",label="계열0",params={"color":"#ff0000"})
    result=edit(agent,data,result,"reset_styles")
    assert not result["chartState"]["series_styles"] and not result["chartState"]["range_styles"]


def test_hide_show_preserves_style_and_secondary_axis():
    agent=OutputAgent();data=source(2);result=agent.prepare(data,{"chart_type":"line"})
    result=edit(agent,data,result,"set_series_style",label="계열0",params={"color":"#ff0000"})
    result=edit(agent,data,result,"hide_series",value="계열0")
    result=edit(agent,data,result,"show_series",value="계열0")
    assert result["plotlyFigure"]["data"][0]["line"]["color"]=="#ff0000"
    result=edit(agent,data,result,"set_secondary_axis",value="계열1")
    result=edit(agent,data,result,"set_axis_style",label="y2",params={"minimum":0,"maximum":100})
    assert result["plotlyFigure"]["layout"]["yaxis2"]["range"]==[0,100]
    # Explicitly clear y2 customization before removing its axis.
    result=edit(agent,data,result,"reset_styles")
    result=edit(agent,data,result,"remove_secondary_axis",value="계열1")
    assert not result["chartState"]["secondary_axis_series"]


def test_edit_api_undo_redo_and_stale_revision(monkeypatch):
    import bridge_api as api
    from fastapi.testclient import TestClient
    agent=OutputAgent();data=source();initial=agent.prepare(data,{"chart_type":"line"})
    monkeypatch.setattr(api.agent,"output_agent",agent)
    monkeypatch.setattr(api,"edit_agent",ChartEditAgent(FakeEditModel({"commands":[{"operation":"set_title","value":"수정"}]}),agent))
    monkeypatch.setattr(api,"_table_card",lambda identifier:{"tableId":identifier})
    api.EDIT_SESSIONS["research-test"]={"result":data,"output":initial,"sessions":[{"query":"합성","table_name":"합성표","period":{"start":"202401","end":"202405"},"frequency":"M"}]}
    client=TestClient(api.app)
    def request(**kwargs):return client.post("/api/output/edit",json={"edit_session_id":"research-test",**kwargs})
    try:
        changed=request(instruction="제목 수정",revision=0).json()
        assert changed["outputSpec"]["canUndo"] and changed["outputSpec"]["editVersion"]==1
        assert request(instruction="다시",revision=0).status_code==409
        undone=request(action="undo",revision=1).json()
        assert undone["outputSpec"]["chartState"]["title"]==initial["chartState"]["title"]
        redone=request(action="redo",revision=2).json()
        assert redone["outputSpec"]["chartState"]["title"]=="수정"
        assert redone["outputSpec"]["table"]==initial["table"]
    finally:api.EDIT_SESSIONS.pop("research-test",None)


def test_clear_ranges_highlight_and_horizontal_bar():
    agent=OutputAgent();data=source(2);result=agent.prepare(data,{"chart_type":"bar"})
    result=edit(agent,data,result,"set_point_style",label="계열0",start="202402",params={"color":"#ff0000","width":4})
    assert result["plotlyFigure"]["data"][0]["marker"]["line"]["width"]==[0,4,0,0,0]
    result=edit(agent,data,result,"clear_range_styles",label="계열0")
    result=edit(agent,data,result,"highlight_series",value="계열0")
    result=edit(agent,data,result,"clear_highlight")
    result=edit(agent,data,result,"set_presentation",params={"bar_orientation":"horizontal","bar_mode":"relative","bar_gap":.1})
    result=edit(agent,data,result,"set_axis_style",label="x",params={"minimum":0,"maximum":40})
    assert result["plotlyFigure"]["data"][0]["orientation"]=="h"
    assert result["plotlyFigure"]["data"][0]["x"]==[10,20,15,30,25]
    assert result["plotlyFigure"]["layout"]["xaxis"]["range"]==[0,40]


def test_heatmap_palette():
    agent=OutputAgent();data=source(2);result=agent.prepare(data,{"chart_type":"heatmap"})
    result=edit(agent,data,result,"set_presentation",params={"color_scale":"RdBu","reverse_colors":True,"show_colorbar":False})
    trace=result["plotlyFigure"]["data"][0]
    assert trace["reversescale"] and not trace["showscale"] and len(trace["colorscale"])>2


@pytest.mark.parametrize("chart_type",["pie","donut","treemap","histogram","box","waterfall"])
def test_special_category_color_is_actually_rendered(chart_type):
    agent=OutputAgent();data=source(1 if chart_type=="waterfall" else 2)
    initial=agent.prepare(data,{"chart_type":chart_type})
    result=edit(agent,data,initial,"set_series_style",label="계열0",params={"color":"#ff0000","opacity":.5})
    assert "#ff0000" in str(result["plotlyFigure"]) or "rgba(255,0,0,0.5)" in str(result["plotlyFigure"])


def test_overlapping_rules_and_curve_keep_values():
    agent=OutputAgent();data=source();result=agent.prepare(data,{"chart_type":"line"});table=copy.deepcopy(result["table"])
    result=edit(agent,data,result,"set_segment_style",label="계열0",start="202402",end="202404",params={"color":"#ff0000"})
    result=edit(agent,data,result,"set_segment_style",label="계열0",start="202403",end="202404",params={"color":"#00ff00","line_shape":"hv"})
    traces=[t for t in result["plotlyFigure"]["data"] if t.get("mode")=="lines"]
    assert traces[2]["line"]["color"]=="#00ff00" and traces[2]["line"]["shape"]=="hv"
    assert result["table"]==table


def test_negative_and_zero_observations_not_changed_and_log_rejected():
    agent=OutputAgent();data=source();data["execution"]["rows"][0]["DT"]="-5";data["execution"]["rows"][1]["DT"]="0"
    result=agent.prepare(data,{"chart_type":"line"})
    edited=edit(agent,data,result,"set_segment_style",label="계열0",start="202401",end="202403",params={"color":"#ff0000"})
    assert edited["table"]==result["table"]
    assert edited["table"]["rows"][0]["value"]==-5 and edited["table"]["rows"][1]["value"]==0
    with pytest.raises(ValueError):edit(agent,data,edited,"set_axis_style",label="y",params={"scale":"log"})
