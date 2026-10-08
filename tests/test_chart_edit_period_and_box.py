import sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "src/agent"))
import pytest
from chart_edit_period import period_redraw,revise_period
from chart_edit_agent import ChartEditAgent
from output_agent import OutputAgent
from output_schema import ChartSpec
from test_chart_edit_agent import FakeEditModel
from test_research_chart_edit import source


def test_box_uses_entire_projected_region_not_model_guessed_corners():
    data=source(1);output=OutputAgent();initial=output.prepare(data,{"chart_type":"line"})
    region={"x0":.2,"x1":.8,"y0":.1,"y1":.9,"data_anchor":{"label":"계열0","start":"202402","end":"202404","start_offset":-.4,"end_offset":.4,"y0":11,"y1":31}}
    mark={"id":"box","tool":"rectangle","target":"chart","text":"박스 전체에 색을 넣어 강조해줘","points":[{"x":.2,"y":.1},{"x":.8,"y":.9}],"selection":{"label":"계열0","scope":"segment","start":"202403","end":"202404"},"region":region}
    model=FakeEditModel({"commands":[{"operation":"add_shape","mark_id":"box","params":{"type":"rect","x0":.4,"x1":.5,"y0":.4,"y1":.5,"fill":"#00ff00"}}]})
    result=ChartEditAgent(model,output).edit(data,initial,"박스 전체를 강조해줘",{"marks":[mark]})
    shape=result["chartState"]["paper_shapes"][0]
    assert (shape["x0"],shape["x1"],shape["y0"],shape["y1"])==(.2,.8,.1,.9)
    rendered=result["plotlyFigure"]["layout"]["shapes"][0]
    assert (rendered["x0"],rendered["x1"],rendered["y0"],rendered["y1"])==(.6,3.4,11,31)
    expanded=copy.deepcopy(data);expanded["execution"]["rows"].insert(0,{**data["execution"]["rows"][0],"PRD_DE":"201501","DT":"8"})
    redraw=output._build(expanded,ChartSpec.model_validate(result["chartState"]),generate_explanation=False)
    newshape=redraw["plotlyFigure"]["layout"]["shapes"][0]
    assert newshape["x0"]==pytest.approx(rendered["x0"]+1)
    assert newshape["x1"]==pytest.approx(rendered["x1"]+1)
    assert newshape["y0"]==11 and newshape["y1"]==31


@pytest.mark.parametrize("instruction",["날짜를 수정하자 2015년부터 2026년까지 그려줘","2015년부터 2026년까지 그려줘","기간을 2015년부터 2026년까지 변경해줘"])
def test_period_redraw_understands_followup(instruction):
    result=period_redraw(instruction)
    assert result["start"]=="2015-01-01" and result["end"]=="2026-12-31" and result["only_period"]


def test_partial_color_instruction_does_not_change_the_query_period():
    assert period_redraw("2024년 1분기부터 2024년 4분기까지 빨간색으로 그려줘") is None
    assert period_redraw("고용률을 2015년부터 2026년까지 그려줘") is None


def fixture_session():
    data=source(1)
    plan=data["api_plan"]
    plan.update(frequency="Q",start_period="202001",end_period="202602",classifications={"A":"same"},exact_params={"startPrdDe":"202001","endPrdDe":"202602","itemId":"ITEM"})
    data["execution"]["rows"]=[{**data["execution"]["rows"][0],"PRD_DE":p,"DT":str(10+i),"_FREQUENCY":"Q"} for i,p in enumerate(["202001","202101","202201","202301","202401","202501","202601","202602"])]
    output=OutputAgent()
    spec=ChartSpec(chart_type="line",title="주택담보대출 신규취급액",show_legend=False,presentation={"title_x":.5},axes={"x":{"show_grid":False},"y":{"show_grid":False}},range_styles=[{"label":"계열0","start":"202401","end":"202602","style":{"color":"#ff0000"}}])
    initial=output._build(data,spec,generate_explanation=False)
    initial["editHistory"]=[{"operation":"set_title","kind":"STYLE_EDIT","value":spec.title}]
    return output,{"result":data,"output":initial,"sessions":[{"query":"주택담보대출 2020년부터 2026년까지","table_name":"테스트 표","frequency":"Q","period":{"start":"2020-01-01","end":"2026-06-30"}}],"undo":[],"redo":[]}


def api_period(date,frequency,end=False):
    year,month,_=date.split("-")
    return year+str((int(month)-1)//3+1).zfill(2)


def test_widen_period_requeries_same_plan_and_retains_style_and_context():
    output,session=fixture_session();before=copy.deepcopy(session)
    def execute(**kwargs):
        assert kwargs["query"]==session["sessions"][0]["query"]
        assert kwargs["period_overrides"]=={"DT_TEST":("201501","202602")}
        plan=kwargs["resolution"]["api_plan"]
        assert plan["table_id"]=="DT_TEST" and plan["item_id"]=="ITEM" and plan["classifications"]=={"A":"same"}
        assert kwargs["generate_answer"] is False
        data=kwargs["resolution"]
        data["execution"]["rows"]=[{**data["execution"]["rows"][0],"PRD_DE":"201501","DT":"5"},*data["execution"]["rows"]]
        return data
    result=revise_period(session,"날짜를 수정하자 2015년부터 2026년까지 그려줘",output,execute,lambda plans:{"min":"2010-01-01","max":"2026-06-30"},api_period)
    assert session==before
    assert result["output"]["table"]["rows"][0]["period"]=="201501"
    assert result["output"]["chartState"]==session["output"]["chartState"]
    assert result["sessions"][0]["period"]=={"start":"2015-01-01","end":"2026-06-30"}
    assert result["output"]["editHistory"][0]==session["output"]["editHistory"][0]
    assert result["warnings"]


def test_fetch_failure_preserves_original_graph_and_context():
    output,session=fixture_session();before=copy.deepcopy(session)
    with pytest.raises(ValueError,match="原|원자료"):
        revise_period(session,"2015년부터 2026년까지 그려줘",output,lambda **kw:{"execution":{"status":"error","error":"provider failed"}},lambda plans:{"min":"2010-01-01","max":"2026-06-30"},api_period)
    assert session==before


def test_explicit_box_move_updates_geometry_instead_of_using_old_data_anchor():
    from output_schema import ChartEditCommand
    output=OutputAgent();data=source(1)
    spec=ChartSpec(chart_type="line",paper_shapes=[{"id":"box1","x0":.1,"x1":.3,"y0":.1,"y1":.3,"data_anchor":{"label":"계열0","start":"202402","end":"202404","y0":11,"y1":31}}])
    initial=output._build(data,spec,generate_explanation=False)
    result=output.apply_edits(data,initial,[ChartEditCommand(operation="update_shape",kind="STYLE_EDIT",value="box1",params={"x0":.5,"x1":.7})])
    shape=result["chartState"]["paper_shapes"][0]
    assert shape["data_anchor"] is None and shape["x0"]==.5
    assert result["plotlyFigure"]["layout"]["shapes"][0]["xref"]=="paper"


def test_http_period_edit_undo_redo_restore_data_and_style(monkeypatch):
    from fastapi.testclient import TestClient
    import bridge_api as api
    output, session = fixture_session()
    original = copy.deepcopy(session)
    monkeypatch.setattr(api.agent, "output_agent", output)
    monkeypatch.setattr(api, "_table_card", lambda tid: {"tableId": tid})
    monkeypatch.setattr(api, "_availability_from_plans", lambda plans: {"min":"2010-01-01","max":"2026-06-30"})
    def execute(**kwargs):
        data = copy.deepcopy(kwargs["resolution"])
        data["execution"]["rows"].insert(0, {**data["execution"]["rows"][0],"PRD_DE":"201501","DT":"5"})
        return data
    monkeypatch.setattr(api.agent, "execute_resolution", execute)
    monkeypatch.setitem(api.EDIT_SESSIONS, "period-http", session)
    client = TestClient(api.app)
    def request(**payload):
        response = client.post("/api/output/edit", json={"edit_session_id":"period-http", **payload})
        assert response.status_code == 200, response.text
        return response.json()
    edited = request(instruction="2015년부터 2026년까지 그려줘", revision=0)
    assert edited["period"]["start"] == "2015-01-01"
    assert edited["outputSpec"]["table"]["rows"][0]["period"] == "201501"
    assert edited["outputSpec"]["chartState"] == original["output"]["chartState"]
    undone = request(action="undo", revision=1)
    assert session["result"] == original["result"]
    assert undone["period"] == original["sessions"][0]["period"]
    redone = request(action="redo", revision=2)
    assert redone["period"] == edited["period"]
    assert redone["outputSpec"]["chartState"] == edited["outputSpec"]["chartState"]
    assert redone["outputSpec"]["table"] == edited["outputSpec"]["table"]
