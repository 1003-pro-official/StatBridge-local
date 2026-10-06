"""Offline request/renderer contracts; no provider keys or real data needed."""
import copy
import pytest
from test_research_chart_edit import source, multi_marks
from test_chart_edit_agent import FakeEditModel
from chart_edit_agent import ChartEditAgent
from output_agent import OutputAgent


def run(commands, visual, instruction=""):
    data=source(); agent=OutputAgent(); initial=agent.prepare(data,{"chart_type":"line"})
    before=copy.deepcopy(initial)
    try:
        return ChartEditAgent(FakeEditModel({"commands":commands}),agent).edit(data,initial,instruction,visual)
    finally:
        assert initial==before


def element(identifier, target, text):
    return {"id":identifier,"tool":"text","points":[{"x":.4,"y":.2}],"target":target,"text":text}


def test_all_three_marks_apply_with_arrow_note_onward():
    arrow=multi_marks()["marks"][0];arrow["text"]="이 위치부터 뒤로 빨간색으로"
    result=run([
        {"operation":"set_series_color","label":"계열0","value":"#ff0000","mark_id":"arrow1"},
        {"operation":"set_title","value":"수출 추이","mark_id":"title"},
        {"operation":"set_axis_style","label":"x","params":{"tick_step":12,"tick_angle":0},"mark_id":"axis"},
    ],{"marks":[arrow,element("title","title","제목을 수출 추이로"),element("axis","x_axis","가로축 눈금을 12개월 간격으로")]})
    assert result["chartState"]["range_styles"][0]["start"]=="202402"
    assert result["chartState"]["range_styles"][0]["end"]=="202405"
    assert result["plotlyFigure"]["layout"]["xaxis"]["dtick"]==12
    assert len(result["editChanges"])==3
    assert "수출 추이" in result["editChanges"][1]


@pytest.mark.parametrize("target,text",[("title","제목"),("x_axis","간소하게")])
def test_incomplete_notes_ask_before_provider(target,text):
    with pytest.raises(ValueError,match="구체적으로"):
        run([{"operation":"set_title","value":"제목"}],{"marks":[element("m",target,text)]})


def test_missing_mark_is_not_silently_ignored():
    with pytest.raises(ValueError,match="일부 표시"):
        run([{"operation":"set_title","value":"새 제목","mark_id":"a"}],
            {"marks":[element("a","title","제목을 새 제목으로"),element("b","x_axis","눈금 간격 12")]})


@pytest.mark.parametrize("commands",[
    [{"operation":"set_title","value":"잘못된 대상","mark_id":"axis"}],
    [{"operation":"set_axis_style","label":"y","params":{"tick_step":12},"mark_id":"axis"}],
    [{"operation":"set_axis_style","label":"x","params":{"tick_step":12},"mark_id":"unknown"}],
])
def test_wrong_target_or_unknown_mark_id_is_rejected(commands):
    with pytest.raises(ValueError):
        run(commands,{"marks":[element("axis","x_axis","12개월 간격")]})


def test_title_and_axis_recover_unique_explicit_target_without_provider_ids():
    result=run([{"operation":"set_title","value":"새 제목"},
                {"operation":"set_axis_style","label":"x","params":{"tick_angle":0}}],
        {"marks":[element("t","title","제목을 새 제목으로"),element("a","x_axis","눈금을 수평으로")]})
    assert result["chartState"]["title"]=="새 제목"


def test_unbound_arrow_cannot_borrow_another_arrows_range():
    arrow=multi_marks()["marks"][0]
    loose={**arrow,"id":"loose"};loose.pop("selection")
    with pytest.raises(ValueError,match="해당 표시"):
        run([{"operation":"set_series_color","label":"계열0","value":"#ff0000","mark_id":"loose"}],
            {"marks":[arrow,loose]},"두 번째 화살표만 빨강")


def test_duplicate_ids_fail_closed():
    mark=element("same","title","제목을 새 제목으로")
    with pytest.raises(ValueError,match="중복"):
        run([{"operation":"set_title","value":"새 제목"}],{"marks":[mark,mark]})


def test_series_name_alone_does_not_authorize_whole_series_restyle():
    mark=element("m","계열0","빨간색으로")
    with pytest.raises(ValueError,match="해당 표시"):
        run([{"operation":"set_series_color","label":"계열0","value":"#ff0000"}],{"marks":[mark]})


def test_provider_dates_inside_params_are_normalized_not_discarded():
    arrow=multi_marks()["marks"][0]
    result=run([{"operation":"set_segment_style","label":"계열0","params":{"color":"#ff0000","start":"202401","end":"202402"}}],{"marks":[arrow]})
    assert result["chartState"]["range_styles"][0]["end"]=="202402"


def test_conflicting_top_level_and_params_dates_are_rejected():
    arrow=multi_marks()["marks"][0]
    with pytest.raises(ValueError,match="시점 필드"):
        run([{"operation":"set_segment_style","label":"계열0","start":"202401","params":{"color":"#ff0000","start":"202402"}}],{"marks":[arrow]})


def test_empty_axis_command_cannot_claim_mark_handled():
    with pytest.raises(ValueError,match="새 축 이름"):
        run([{"operation":"set_axis_labels","value":{"tick_step":2},"mark_id":"x"}],
            {"marks":[element("x","x_axis","눈금 간격 2")]})


def test_no_change_is_not_reported_as_success():
    data=source();output=OutputAgent();initial=output.prepare(data,{"chart_type":"line"})
    with pytest.raises(ValueError,match="변경된 내용이 없습니다"):
        ChartEditAgent(FakeEditModel({"commands":[{"operation":"set_title","value":initial["chartState"]["title"]}]}),output).edit(data,initial,"같은 제목")


def test_model_prompt_exposes_all_supported_operations():
    class Model(FakeEditModel):
        def interpret(self, system, context):
            assert "set_axis_style" in system.split("계열은")[0]
            assert "params" in system and "marks의 text" in system
            return super().interpret(system,context)
    data=source();output=OutputAgent();initial=output.prepare(data,{"chart_type":"line"})
    ChartEditAgent(Model({"commands":[{"operation":"set_title","value":"프롬프트 검증"}]}),output).edit(data,initial,"제목 변경")


def test_missing_mark_with_global_instruction_also_rejected():
    with pytest.raises(ValueError,match="일부 표시"):
        run([{"operation":"set_title","value":"새 제목","mark_id":"a"}],
            {"marks":[element("a","title","제목을 새 제목으로"),element("b","x_axis","눈금 간격 12")]},"모두 적용")


def test_http_incomplete_multi_mark_preserves_session(monkeypatch):
    from fastapi.testclient import TestClient
    import bridge_api as api
    data=source();output=OutputAgent();initial=output.prepare(data,{"chart_type":"line"})
    record={"result":data,"output":initial,"sessions":[]}
    monkeypatch.setitem(api.EDIT_SESSIONS,"edit-safety",record)
    monkeypatch.setattr(api,"edit_agent",ChartEditAgent(FakeEditModel({"commands":[{"operation":"set_title","value":"새 제목","mark_id":"a"}]}),output))
    before=copy.deepcopy(record)
    response=TestClient(api.app).post("/api/output/edit",json={"edit_session_id":"edit-safety","instruction":"모두 적용",
        "visual":{"marks":[element("a","title","제목을 새 제목으로"),element("b","x_axis","눈금 간격 12")]}})
    assert response.status_code==422
    assert record==before
