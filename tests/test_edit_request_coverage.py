"""Whole-request accounting, correction and no-partial-success contracts."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "src/agent"))
import copy
import json
from pathlib import Path
from typing import get_args
import pytest
from chart_edit_agent import ChartEditAgent, Hcx007EditModel
from edit_request_coverage import request_sources, validate_coverage
from output_agent import OutputAgent
from output_schema import ChartEditCommand
from research_chart_editing import EDIT_HELP
from test_chart_edit_agent import FakeEditModel
from test_research_chart_edit import source


def report(commands, sources):
    return {"commands":commands,"coverage":[{"source_id":s["id"],"text":s["text"],"status":"covered","command_indices":list(range(len(commands)))} for s in sources]}


def test_help_and_review_catalog_cover_every_schema_operation():
    operations=set(get_args(ChartEditCommand.model_fields["operation"].annotation))
    catalog=json.loads((Path(__file__).resolve().parents[1] / "src/agent/frontend/src/chartEditHelp.json").read_text(encoding="utf-8"))
    assert operations==set(EDIT_HELP)
    assert operations=={op for group in catalog for op in group["operations"]}


def test_coverage_quote_accepts_only_whitespace_normalization():
    sources=request_sources("제목은 주택담보대출 신규취급액으로 변경해줘",{})
    response=report([{"operation":"set_title","value":"주택담보대출 신규취급액"}],sources)
    response["coverage"][0]["text"]="주택담보대출신규취급액으로 변경해줘"
    assert validate_coverage(response,sources)
    response["coverage"][0]["text"]="주택담보대출 잔액으로 변경해줘"
    with pytest.raises(ValueError): validate_coverage(response,sources)


def test_provider_review_accounts_for_explicit_mark_links_only():
    sources=[{"id":"text:0","text":"제목 가운데"},{"id":"mark:box","text":"박스 전체 강조"},{"id":"mark:other","text":"다른 표시 변경"}]
    commands=[{"operation":"set_presentation","params":{"title_x":.5}},{"operation":"add_shape","mark_id":"box"}]
    model=object.__new__(Hcx007EditModel)
    model.interpret=lambda system,context: {"commands":commands,"coverage":[{"source_id":"text:0","text":"제목을 중앙으로 이동","status":"covered","command_indices":[0]}]}
    reviewed=model.review("rules",{"sources":sources}, {})
    assert reviewed["coverage"][0]["text"]=="제목 가운데"
    assert reviewed["coverage"][0]["interpretation"]=="제목을 중앙으로 이동"
    assert reviewed["coverage"][1]["source_id"]=="mark:box"
    with pytest.raises(ValueError): validate_coverage(reviewed,sources)
    assert validate_coverage(reviewed,sources[:2])


def test_provider_review_recovers_unique_arrow_and_box_before_coverage():
    marks=[{"id":"a","tool":"arrow","target":"chart","text":"여기부터 빨간색","points":[{"x":.1,"y":.1},{"x":.2,"y":.2}],"selection":{"label":"s","scope":"segment","start":"202402","end":"202404"}},
           {"id":"b","tool":"rectangle","target":"chart","text":"박스 채움","points":[{"x":.3,"y":.3},{"x":.6,"y":.6}],"selection":{"label":"s","scope":"segment","start":"202403","end":"202404"}}]
    sources=request_sources("화살표부터 뒤로 빨간색으로, 박스 채움",{"marks":marks})
    model=object.__new__(Hcx007EditModel)
    model.interpret=lambda system,context:{"commands":[{"operation":"set_segment_style","label":"s","params":{"color":"#ff0000"}},{"operation":"add_shape","params":{"type":"rect","fill":"#00ff00"}}],"coverage":[{"source_id":"text:0","text":"요약","status":"covered","command_indices":[0,1]}]}
    reviewed=model.review("rules",{"sources":sources,"instruction":sources[0]["text"],"visual":{"marks":marks},"seriesLabels":["s"]},{})
    assert [c['mark_id'] for c in reviewed['commands']]==['a','b']
    assert validate_coverage(reviewed,sources)


@pytest.mark.parametrize("operation",get_args(ChartEditCommand.model_fields["operation"].annotation))
def test_coverage_contract_accepts_every_supported_operation(operation):
    sources=request_sources("이 요소를 수정해줘",{})
    response=report([{"operation":operation}],sources)
    assert validate_coverage(response,sources)


@pytest.mark.parametrize("mutation",["missing_source","invalid_index","unmapped_command","blocked","invented_source","changed_quote"])
def test_incomplete_review_never_claims_success(mutation):
    sources=request_sources("제목 변경\n범례 숨김",{})
    response=report([{"operation":"set_title","value":"제목"}],sources)
    if mutation=="missing_source": response["coverage"].pop()
    elif mutation=="invalid_index": response["coverage"][0]["command_indices"]=[99]
    elif mutation=="unmapped_command": response["commands"].append({"operation":"set_legend","value":False})
    elif mutation=="blocked": response["coverage"][0].update(status="blocked",reason="새 제목이 없습니다")
    elif mutation=="invented_source": response["coverage"][0]["source_id"]="other"
    elif mutation=="changed_quote": response["coverage"][0]["text"]="없는 지시"
    with pytest.raises(ValueError): validate_coverage(response,sources)


def test_text_only_batch_reviewer_recovers_multiple_omitted_categories():
    data=source(1); output=OutputAgent(); initial=output.prepare(data,{"chart_type":"line"})
    before=copy.deepcopy(initial)
    class Model(FakeEditModel):
        def review(self,system,context,proposal):
            assert not context["visual"]["marks"]
            assert len(context["sources"])==5
            commands=[{"operation":"set_title","value":"신규취급액"},
                      {"operation":"set_presentation","params":{"title_x":.5,"background":"#eeeeee","font_size":16}},
                      {"operation":"set_legend","value":False},
                      {"operation":"set_axis_style","label":"x","params":{"show_grid":False}},
                      {"operation":"set_axis_style","label":"y","params":{"show_grid":False}},
                      {"operation":"set_series_style","label":"계열0","params":{"color":"#ff0000","width":4,"dash":"dash"}}]
            return report(commands,context["sources"])
    model=Model({"commands":[{"operation":"set_title","value":"신규취급액"}]})
    result=ChartEditAgent(model,output).edit(data,initial,"제목을 신규취급액으로 바꾸고 가운데로\n배경은 회색, 글자는 16\n범례 숨김\n격자 삭제\n선을 빨간색, 두께 4, 점선으로")
    s=result["chartState"]
    assert s["title"]=="신규취급액" and s["presentation"]["title_x"]==.5
    assert s["presentation"]["background"]=="#eeeeee" and s["presentation"]["font_size"]==16
    assert not s["show_legend"] and not s["axes"]["y"]["show_grid"]
    assert s["series_styles"]["계열0"]["width"]==4 and s["series_styles"]["계열0"]["dash"]=="dash"
    assert result["table"]==initial["table"] and initial==before
    assert len(result["editCoverage"])==5


def test_multiple_requests_on_same_pen_mark_are_reviewed_separately():
    data=source(1);output=OutputAgent();initial=output.prepare(data,{"chart_type":"line"})
    class Model(FakeEditModel):
        def review(self,system,context,proposal):
            sources=context["sources"]
            assert sources[0]["id"]=="mark:pen"
            return {"commands":[{"operation":"set_segment_style","mark_id":"pen","label":"계열0","params":{"color":"#ff0000","width":4,"dash":"dash"}}],"coverage":[{"source_id":"mark:pen","text":text,"status":"covered","command_indices":[0]} for text in ["빨간색","두께 4","점선"]]}
    model=Model({"commands":[{"operation":"set_segment_style","mark_id":"pen","label":"계열0","params":{"color":"#ff0000"}}]})
    marks=[{"id":"pen","tool":"pen","target":"chart","text":"빨간색, 두께 4, 점선으로 바꿔줘","points":[{"x":.2,"y":.3},{"x":.5,"y":.4}],"selection":{"label":"계열0","scope":"segment","start":"202402","end":"202403"}}]
    result=ChartEditAgent(model,output).edit(data,initial,"",{"marks":marks})
    assert result["chartState"]["range_styles"][0]["style"]["width"]==4
    assert len(result["editCoverage"])==3


def test_graph_kind_fast_path_does_not_skip_drawing_text():
    data=source(1);output=OutputAgent();initial=output.prepare(data,{"chart_type":"line"})
    mark={"id":"title","tool":"text","target":"title","text":"제목을 새 제목으로","points":[{"x":.4,"y":.2}]}
    model=FakeEditModel({"commands":[{"operation":"set_chart_type","value":"bar"},{"operation":"set_title","mark_id":"title","value":"새 제목"}]})
    result=ChartEditAgent(model,output).edit(data,initial,"막대 그래프로 바꿔줘",{"marks":[mark]})
    assert result["chartState"]["chart_type"]=="bar" and result["chartState"]["title"]=="새 제목"


def test_blocked_review_preserves_whole_current_chart():
    data=source(1);output=OutputAgent();initial=output.prepare(data,{"chart_type":"line"});before=copy.deepcopy(initial)
    class Model(FakeEditModel):
        def review(self,system,context,proposal):
            response=report(proposal["commands"],context["sources"])
            response["coverage"][-1].update(status="blocked",reason="미래 수치를 생성할 수 없습니다")
            return response
    with pytest.raises(ValueError,match="미래 수치"):
        ChartEditAgent(Model({"commands":[{"operation":"set_title","value":"새 제목"}]}),output).edit(data,initial,"제목을 새 제목으로\n미래 수치를 추가해줘")
    assert initial==before


def test_unknown_command_and_unused_legacy_params_are_not_discarded():
    with pytest.raises(ValueError): ChartEditCommand.model_validate({"operation":"set_title","kind":"STYLE_EDIT","value":"제목","font_size":24})
    data=source(1);output=OutputAgent();initial=output.prepare(data,{"chart_type":"line"})
    with pytest.raises(ValueError,match="적용할 수 없는"):
        ChartEditAgent(FakeEditModel({"commands":[{"operation":"set_legend","value":False,"params":{"font_size":24}}]}),output).edit(data,initial,"범례 숨김과 글자 크기")


def test_renderer_validation_rechecks_the_whole_batch_once():
    data=source(1);output=OutputAgent();initial=output.prepare(data,{"chart_type":"line"});before=copy.deepcopy(initial)
    class Model(FakeEditModel):
        reviews=0
        def review(self,system,context,proposal):
            self.reviews+=1
            commands=[{"operation":"set_title","value":"수정 결과"},
                      {"operation":"set_series_style","label":"계열0","params":{"width":99 if self.reviews==1 else 4}}]
            if self.reviews==2:
                assert "validationError" in context
                assert len(context["sources"])==2
            return report(commands,context["sources"])
    model=Model({"commands":[{"operation":"set_title","value":"수정 결과"}]})
    result=ChartEditAgent(model,output).edit(data,initial,"제목은 수정 결과로\n선 두께는 4로")
    assert model.reviews==2 and initial==before
    assert result["chartState"]["title"]=="수정 결과" and result["chartState"]["series_styles"]["계열0"]["width"]==4
    assert len(result["editHistory"])==2


def test_invalid_repair_is_bounded_and_does_not_commit_any_edit():
    data=source(1);output=OutputAgent();initial=output.prepare(data,{"chart_type":"line"});before=copy.deepcopy(initial)
    class Model(FakeEditModel):
        reviews=0
        def review(self,system,context,proposal):
            self.reviews+=1
            return report([{"operation":"set_title","value":"새 제목"},{"operation":"set_series_style","label":"계열0","params":{"width":99}}],context["sources"])
    model=Model({"commands":[]})
    with pytest.raises(ValueError): ChartEditAgent(model,output).edit(data,initial,"제목 변경\n선 두께 변경")
    assert model.reviews==2 and initial==before


def test_common_parameter_aliases_do_not_drop_requested_settings():
    from edit_request_coverage import normalize_parameter_names
    assert normalize_parameter_names({"operation":"set_segment_style","params":{"line_width":5,"line_dash":"dash"}})["params"]=={"width":5,"dash":"dash"}
    assert normalize_parameter_names({"operation":"set_axis_style","params":{"showgrid":False,"dtick":2}})["params"]=={"show_grid":False,"tick_step":2}
    with pytest.raises(ValueError): normalize_parameter_names({"operation":"set_series_style","params":{"width":4,"line_width":5}})


def test_incomplete_request_accounting_is_corrected_as_a_whole():
    data=source(1);output=OutputAgent();initial=output.prepare(data,{"chart_type":"line"})
    class Model(FakeEditModel):
        reviews=0
        def review(self,system,context,proposal):
            self.reviews+=1
            result=report([{"operation":"set_title","value":"새 제목"},{"operation":"set_legend","value":False}],context["sources"])
            if self.reviews==1: result["coverage"][0]["command_indices"]=[0];result["coverage"][1]["command_indices"]=[0]
            else: assert "validationError" in context
            return result
    model=Model({"commands":[]})
    result=ChartEditAgent(model,output).edit(data,initial,"제목은 새 제목으로\n범례는 숨겨줘")
    assert model.reviews==2 and not result["chartState"]["show_legend"]


# Each public operation reaches the actual output renderer, rather than only
# checking whether its name appears in the model prompt.
OPERATION_CASES={
 "set_title":{"value":"새 제목"}, "set_subtitle":{"value":"새 부제"},
 "set_axis_labels":{"x_axis_label":"기간","y_axis_label":"값"},
 "set_chart_type":{"value":"bar"}, "set_layout":{"value":"separate"},
 "set_legend":{"value":False}, "set_line_width":{"value":5},
 "highlight_period":{"start":"202401","end":"202404","params":{"color":"#ff0000"}},
 "highlight_series":{"value":"계열0"}, "add_annotation":{"start":"202403","value":"새 주석"},
 "remove_annotation":{"value":"기존 주석"}, "add_reference_line":{"value":17},
 "hide_series":{"value":"계열0"}, "show_series":{"value":"계열0"},
 "filter_period":{"start":"202402","end":"202404"}, "set_top_n":{"value":1},
 "set_transform":{"value":"cumulative"}, "set_series_chart_type":{"label":"계열0","value":"bar"},
 "set_secondary_axis":{"value":"계열0"}, "remove_secondary_axis":{"value":"계열0"},
 "set_series_color":{"label":"계열0","value":"#ff0000"}, "set_series_dash":{"label":"계열0","value":"dash"},
 "set_segment_style":{"label":"계열0","start":"202402","end":"202403","params":{"color":"#ff0000","width":5}},
 "set_point_style":{"label":"계열0","start":"202402","end":"202402","params":{"color":"#ff0000","marker_size":10}},
 "remove_range_style":{"value":"range1"}, "clear_range_styles":{},
 "set_series_style":{"label":"계열0","params":{"width":5,"dash":"dash"}},
 "rename_series":{"label":"계열0","value":"표시 계열"}, "reorder_series":{"value":["계열1","계열0"]},
 "clear_highlight":{}, "set_axis_style":{"label":"x","params":{"show_grid":False}},
 "set_presentation":{"params":{"font_size":18,"title_x":.5}},
 "add_note":{"params":{"text":"새 메모","x":.6,"y":.8}},
 "update_note":{"value":"note1","params":{"text":"변경된 메모","color":"#ff0000"}}, "remove_note":{"value":"note1"},
 "add_guide":{"params":{"value":18,"orientation":"horizontal","text":"새 기준선"}},
 "update_guide":{"value":"guide1","params":{"value":17,"color":"#ff0000"}}, "remove_guide":{"value":"guide1"},
 "update_highlight":{"value":"highlight1","params":{"color":"#ff0000"}}, "remove_highlight":{"value":"highlight1"},
 "add_shape":{"params":{"type":"circle","x0":.4,"x1":.5,"y0":.4,"y1":.5}},
 "update_shape":{"value":"shape1","params":{"color":"#ff0000"}}, "remove_shape":{"value":"shape1"},
 "reset_styles":{}
}


@pytest.mark.parametrize("operation",get_args(ChartEditCommand.model_fields["operation"].annotation))
def test_every_supported_edit_operation_applies_and_renders(operation):
    from output_schema import ChartSpec
    data=source(2);before=copy.deepcopy(data);output=OutputAgent()
    settings=dict(chart_type="line",title="기존 제목",subtitle="기존 부제",
        annotations=[{"period":"202401","text":"기존 주석"}],
        notes=[{"id":"note1","text":"기존 메모","x":.5,"y":.9}],
        guides=[{"id":"guide1","orientation":"horizontal","value":15}],
        highlights=[{"id":"highlight1","start":"202402","end":"202403"}],
        paper_shapes=[{"id":"shape1","type":"rect","x0":.1,"x1":.2,"y0":.1,"y1":.2}])
    if operation in {"remove_range_style","clear_range_styles"}:
        settings["range_styles"]=[{"id":"range1","label":"계열0","start":"202402","end":"202403","style":{"color":"#ff0000"}}]
    if operation=="show_series": settings["hidden_series"]=["계열0"]
    if operation=="clear_highlight": settings["highlighted_series"]="계열0"
    if operation=="remove_secondary_axis": settings["secondary_axis_series"]=["계열0"]
    initial=output._build(data,ChartSpec(**settings))
    kind="DATA_EDIT" if operation in {"hide_series","filter_period","set_top_n","set_transform"} else "STYLE_EDIT"
    command=ChartEditCommand(operation=operation,kind=kind,**OPERATION_CASES[operation])
    result=output.apply_edits(data,initial,[command])
    assert result["chartState"]!=initial["chartState"]
    assert result["plotlyFigure"]!=initial["plotlyFigure"]
    assert result["editChanges"] and data==before


def test_multiple_literal_deletions_share_their_exact_request_source():
    sources=request_sources("최초 시점과 마지막 시점 텍스트를 삭제해줘",{})
    response=report([{"operation":"remove_annotation","value":"최초 시점"},{"operation":"remove_annotation","value":"마지막 시점"}],sources)
    response["coverage"][0]["command_indices"]=[0]
    result=validate_coverage(response,sources)
    assert result[0]["command_indices"]==[0,1]
