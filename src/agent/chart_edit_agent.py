from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any, Protocol, get_args

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from ncp_clova_client import NcpClovaClient
from output_schema import ChartEditCommand, ChartSpec, VisualEditContext, SeriesStyle, AxisStyle, PresentationStyle, PositionedNote, Guide, PaperShape, Highlight
from research_chart_editing import EDIT_HELP
from edit_request_validation import bind_command, compatible, validate_visual
from chart_availability import data_requirements
from edit_request_coverage import request_sources, validate_coverage, normalize_parameter_names, CoverageContractError, REVIEW_SYSTEM


CHART_NAMES = {
    "선": "line", "선 그래프": "line", "꺾은선": "line", "꺾은선 그래프": "line",
    "막대": "bar", "막대 그래프": "bar", "누적 막대": "stacked_bar", "누적 막대 그래프": "stacked_bar",
    "영역": "area", "영역 그래프": "area", "산점도": "scatter", "버블": "bubble", "버블 그래프": "bubble",
    "원": "pie", "원 그래프": "pie", "파이": "pie", "도넛": "donut", "도넛 그래프": "donut",
    "히스토그램": "histogram", "상자": "box", "상자 그림": "box", "상자 그래프": "box",
    "히트맵": "heatmap", "트리맵": "treemap", "워터폴": "waterfall", "워터폴 그래프": "waterfall",
    "폭포": "waterfall", "폭포 그래프": "waterfall", "버블 차트": "bubble", "파이 그래프": "pie",
}


def explicit_chart_change(instruction: str) -> str | None:
    # Only a complete, standalone global request bypasses sketch targeting.
    # Compound requests and individual-series changes still go through the model.
    names = {re.sub(r"\s+", "", name): kind for name,kind in CHART_NAMES.items()}
    names.update({kind:kind for kind in CHART_NAMES.values()})
    text = re.sub(r"\s+", "", instruction.strip().rstrip(".!。 "))
    pattern = r"(?:(?:전체)?그래프(?:를|는)?)?(" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")(?:로|으로)(?:변경(?:해)?|바꿔|바꾸어)(?:줘|주세요)?"
    match = re.fullmatch(pattern, text, re.IGNORECASE)
    return names.get(match[1].lower()) if match else None


def explicit_color_change(instruction: str) -> str | None:
    """Only an unambiguous standalone color request skips provider inference."""
    colors = {"빨간색":"#e53935", "빨강":"#e53935", "붉은색":"#e53935",
              "파란색":"#2563eb", "파랑":"#2563eb", "초록색":"#16a34a", "초록":"#16a34a",
              "녹색":"#16a34a", "노란색":"#eab308", "노랑":"#eab308", "보라색":"#9333ea",
              "보라":"#9333ea", "검은색":"#111827", "검정":"#111827", "주황색":"#f97316", "주황":"#f97316"}
    text = re.sub(r"\s+", "", instruction.strip().rstrip(".!。 "))
    names = "|".join(sorted(colors,key=len,reverse=True))
    match = re.fullmatch(r"(?:(?:이부분|표시한부분|선택한부분|전체)(?:을|의)?)?(?:그래프)?(?:색|색상)?(?:을|를)?("+names+r"|#[0-9a-fA-F]{6})(?:로|으로)(?:바꿔|변경해|변경)(?:줘|주세요)?",text)
    return colors.get(match[1],match[1].lower()) if match else None


class EditModel(Protocol):
    """Replace this adapter to enable VLM image messages without changing orchestration."""
    model_name: str
    supports_images: bool

    def interpret(self, system: str, context: dict[str, Any]) -> dict[str, Any]: ...


class Hcx007EditModel:
    model_name = "HCX-007"
    supports_images = False

    def __init__(self, client: NcpClovaClient) -> None:
        # Editing is pinned independently of the query/output model environment.
        self.client = NcpClovaClient(replace(client.settings, main_model="HCX-007",
                                          main_api_version="v3", main_url=""))

    def interpret(self, system: str, context: dict[str, Any]) -> dict[str, Any]:
        if not self.client.configured:
            raise ValueError("자연어 그래프 수정에는 NCP_CLOVA_API_KEY가 필요합니다.")
        # No base64 image is disguised as text or sent to a text-only model.
        context = {**context, "visual": {k: v for k, v in context["visual"].items()
                                       if k not in {"graph_image", "marked_image"}}}
        try:
            text, _ = self.client.chat_main(system, json.dumps(context, ensure_ascii=False),
                                            max_tokens=4000, thinking_effort="low")
        except Exception as exc:
            raise ValueError("HCX-007 수정 요청에 실패했습니다. 기존 그래프는 유지됩니다.") from exc
        return self.client._json_object(text)

    def review(self, system: str, context: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
        # A fresh pass checks all input sources, including multiple requests in
        # one drawing. It does not see the interpreter's internal reasoning.
        # Review accounting/output requirements follow interpretation rules so
        # the earlier commands-only format cannot override source coverage.
        reviewed = self.interpret(system + "\n" + REVIEW_SYSTEM, {**context, "candidateProposal":proposal})
        # Source identity and command links carry the review contract. Preserve
        # the provider's interpretation separately and quote authoritative input
        # on the server, rather than asking the model to copy Korean verb endings.
        sources = {s["id"]: s["text"] for s in context.get("sources", [])}
        coverage = reviewed.get("coverage")
        commands = reviewed.get("commands")
        if isinstance(coverage, list) and isinstance(commands, list):
            visual = VisualEditContext.model_validate(context.get("visual") or {})
            labels = set(context.get("seriesLabels") or [])
            for command in commands:
                if not isinstance(command, dict) or command.get("mark_id"):
                    continue
                bind_command(command, visual, labels)
                if command.get("mark_id"):
                    continue
                op = command.get("operation")
                tool = None
                if op == "add_shape":
                    tool = "ellipse" if (command.get("params") or {}).get("type") == "circle" else "rectangle"
                elif op == "highlight_period":
                    tool = "rectangle"
                elif op in {"set_segment_style","set_point_style","set_series_color","set_series_style","set_series_dash","set_line_width"} and re.search(r"화살표.*(?:부터|뒤로|이후)",context.get("instruction", "")):
                    tool = "arrow"
                matches = [m for m in visual.marks if m.tool == tool and m.selection and (not command.get("label") or command["label"] == m.selection.label)] if tool else []
                if len(matches) == 1:
                    command["mark_id"] = matches[0].id
            for entry in coverage:
                if isinstance(entry, dict) and entry.get("source_id") in sources:
                    entry["interpretation"] = entry.get("text")
                    entry["text"] = sources[entry["source_id"]]
            seen = {e.get("source_id") for e in coverage if isinstance(e, dict)}
            for source_id, text in sources.items():
                if source_id in seen or not source_id.startswith("mark:"):
                    continue
                indices = [i for i, c in enumerate(commands) if isinstance(c, dict) and c.get("mark_id") == source_id[5:]]
                if indices:
                    coverage.append({"source_id":source_id,"text":text,"status":"covered","command_indices":indices})
        return reviewed


class EditState(TypedDict, total=False):
    result: dict[str, Any]
    current: dict[str, Any]
    instruction: str
    visual: dict[str, Any]
    commands: list[ChartEditCommand]
    output: dict[str, Any]
    coverage: list[dict[str, Any]]
    review_context: dict[str, Any]
    review_system: str
    proposal: dict[str, Any]


class ChartEditAgent:
    """Interpret edits only; the output agent remains the owner of rendering."""

    def __init__(self, model: EditModel, output_agent: Any) -> None:
        self.model = model
        self.output_agent = output_agent
        graph = StateGraph(EditState)
        graph.add_node("interpret_edit", self._interpret)
        graph.add_node("render_output", self._render)
        graph.add_edge(START, "interpret_edit")
        graph.add_edge("interpret_edit", "render_output")
        graph.add_edge("render_output", END)
        self.graph = graph.compile(name="statbridge-chart-edit")

    def _interpret(self, state: EditState) -> dict[str, Any]:
        kind = explicit_chart_change(state["instruction"])
        if kind and not (state.get("visual") or {}).get("marks"):
            series = self.output_agent._series((state["result"].get("execution") or {}).get("rows") or [])
            displayed = self.output_agent._apply_data_edits(series, ChartSpec.model_validate(state["current"]["chartState"]))
            blockers = data_requirements(displayed, kind)
            if blockers:
                raise ValueError("요청한 그래프로 변경할 수 없습니다. " + " / ".join(blockers))
            return {"commands": [ChartEditCommand(operation="set_chart_type", value=kind, kind="STYLE_EDIT")]}
        visual = VisualEditContext.model_validate(state.get("visual") or {})
        from chart_edit_intents import selected_style
        for mark in visual.marks:
            choice=selected_style(state["instruction"],"add_shape" if mark.tool in {"rectangle","ellipse"} else "set_series_style",mark)
            if choice and mark.text.strip():
                # A later color-picker decision supersedes color words saved on
                # a sketch, while retaining all other instructions on that mark.
                mark.text=re.sub(r"#[0-9a-fA-F]{6}|rgb\([^)]*\)|(?:빨간색|빨강|파란색|파랑|노란색|노랑|초록색|녹색|보라색|주황색|회색|검은색|흰색)",choice["color"],mark.text)
                mark.text+=f" (최종 선택 색 {choice['color']}, 불투명도 {choice['opacity']})"
            if mark.target in {"", "chart"} and re.search(r"제목", mark.text):
                mark.target="title"
                mark.selection=None
        validate_visual(visual, state["instruction"])
        series = self.output_agent._series((state["result"].get("execution") or {}).get("rows") or [])
        labels = {s["label"] for s in series}
        displayed = self.output_agent._apply_data_edits(series, ChartSpec.model_validate(state["current"]["chartState"]))
        from chart_edit_intents import display_commands
        required_display=display_commands(state["instruction"],ChartSpec.model_validate(state["current"]["chartState"]),displayed)
        from chart_edit_intents import arrow_note
        arrow_marks=[m for m in visual.marks if m.tool=="arrow"]
        if len(arrow_marks)==1 and not re.search(r"박스|사각형|제목|범례|원 부분|펜",state["instruction"]):
            arrow_command=arrow_note(state["instruction"],arrow_marks[0])
            if arrow_command:return {"commands":[arrow_command,*required_display]}
        if required_display and not visual.marks and not re.search(r"색|제목|범례|배경|도형|화살표|박스|사각형",state["instruction"]):
            return {"commands":required_display}
        from chart_edit_intents import symbol_note
        if not visual.marks and not re.search(r'제목|격자|박스|범례|기간|날짜',state['instruction']):
            symbol_command=symbol_note(state['instruction'])
            if symbol_command:return {'commands':[symbol_command]}
        from highlight_followup import expand_highlight
        if not visual.marks:
            expansion=expand_highlight(state["instruction"],ChartSpec.model_validate(state["current"]["chartState"]),displayed,state["current"].get("editHistory",[]))
            if expansion:
                return {"commands":[expansion]}
        # An explicit "after the arrow" request extends from its bound tip,
        # never from an invented screen-coordinate date.
        arrows = [m for m in visual.marks if m.tool == "arrow" and m.selection]
        for mark in arrows:
            onward = re.search(r"(?:부터|이후|뒤로|끝까지)", mark.text) or (
                len(arrows) == 1 and re.search(r"화살표.*(?:부터|이후|뒤로|끝까지)", state["instruction"]))
            if not onward:
                continue
            selected = mark.selection
            item = next((s for s in displayed if s["label"] == selected.label), None)
            if item and selected.scope == "segment":
                mark.selection = selected.model_copy(update={"start":selected.end,"end":item["points"][-1]["date"],"scope":"point" if selected.end==item["points"][-1]["date"] else "segment"})
        mark_selections = {m.id:m.selection for m in visual.marks if m.selection}
        selections = list(mark_selections.values()) or ([visual.selection] if visual.selection else [])
        for selection in selections:
            item = next((s for s in displayed if s["label"] == selection.label), None)
            if not item:
                raise ValueError("부분 선택 계열이 현재 그래프에 없습니다.")
            periods = [p["date"] for p in item["points"]]
            if selection.scope != "series" and (selection.start not in periods or selection.end not in periods):
                raise ValueError("부분 선택 시점을 현재 관측값에서 찾지 못했습니다.")
        targets = labels | {"title", "legend", "x_axis", "y_axis", "chart"}
        if visual.selected_target and visual.selected_target not in targets:
            raise ValueError("선택한 수정 대상이 현재 그래프에 없습니다.")
        for mark in visual.marks:
            if mark.target and mark.target not in targets:
                raise ValueError("그림 표시의 수정 대상이 현재 그래프에 없습니다.")
        if not state["instruction"].strip() and not any(m.text.strip() for m in visual.marks) and not (self.model.supports_images and visual.marks):
            raise ValueError("표시에 대한 수정 설명을 입력해 주세요. 현재 HCX-007은 손글씨·이미지를 읽지 않습니다.")
        if visual.marks and not self.model.supports_images:
            if any(not m.text.strip() for m in visual.marks) and not state["instruction"].strip():
                raise ValueError("각 표시의 설명 또는 전체 수정 지시를 입력해 주세요.")
        system = (
            "너는 그래프 수정 명령 분류기다. 사용자 텍스트와 구조화된 그림 표시를 편집 명령으로 해석한다. "
            "Python 코드와 통계값을 생성하지 마라. JSON {commands:[...], clarification:null 또는 확인질문}만 반환한다. "
            "각 명령의 필드는 operation,value,params,start,end,label,x_axis_label,y_axis_label,mark_id이다. "
            "여러 표시가 있으면 각 명령의 mark_id에 해당 visual.marks의 id를 반드시 넣는다. "
            "수정 지시용 화살표 표시는 기존 저장 메모가 아니다. 화살표를 그려달라는 명시적인 지시가 있으면 현재 차트에 화살표가 없어도 새로 추가하고 승인 질문을 하지 마라. 화살표를 크게 그려달라는 요청은 차트 선 색 변경이 아니라 add_note의 arrow=true로 실제 화살표 주석을 추가한다. 기호/이모티콘 추가도 add_note를 사용하며 text에 해당 기호를 넣는다. 화살표 이후 차트 색을 바꾸라는 요청에만 계열 스타일 명령을 사용한다. 화살표 색상/점선 변경과 사각형 구간 강조는 서로 다른 명령이다. 사각형 강조는 highlight_period를 사용한다. "
            "허용 operation은 " + ",".join(get_args(ChartEditCommand.model_fields["operation"].annotation)) + "이다. "
            "계열은 seriesLabels의 정확한 이름을 사용한다. set_series_color와 set_series_dash는 label에 계열 이름, "
            "value에 #RRGGBB 색상 또는 solid/dot/dash/longdash/dashdot을 넣는다. "
            "set_series_chart_type은 label=계열 이름,value=line/bar/area이다. set_secondary_axis는 value=계열 이름이다. "
            "좌표는 그래프 전체 화면 기준 x=왼쪽0~오른쪽1,y=위0~아래1이며 통계 시점·값이 아니다. "
            "좌표만으로 시점/수치/계열을 추측하지 마라. target과 입력 설명을 우선한다. "
            "그림은 최종 주석이 아닌 수정 지시이다. 명시적으로 주석 추가 요청일 때만 add_annotation을 사용한다. "
            "시점과 수정 대상을 확정할 수 없거나 추가 데이터가 필요하면 commands=[]와 clarification으로 질문한다. "
            "여러 수정은 최대 12개 명령에 모두 포함한다. 알 수 없는 지시를 무시하거나 임의로 대체하지 마라. "
            "marks의 text도 각각 독립된 사용자 지시이다. 모든 표시의 지시를 처리하고, 모호하면 전체 요청을 확인 질문으로 돌린다. "
            "제목/축/범례는 관측 시점 선택이 필요 없다. '제목'은 새 제목이 아니고 '간소하게'는 눈금 간격이 아니다. "
            "명확한 새 제목·축 설정을 물어라. 명시된 target 외의 요소나 원자료는 바꾸지 마라."
            "set_axis_labels는 축 제목 변경 전용이고 x_axis_label/y_axis_label 필드만 읽는다. "
            "눈금 간격·글자 회전은 반드시 set_axis_style(label=x 또는 y,params={tick_step:간격,tick_angle:각도})로 생성한다. "
            "set_axis_style와 부분 스타일의 설정은 value가 아니라 params에 넣는다. "
            "부분 스타일의 start/end는 params 밖에 넣는다. 빈 명령이나 설명만 담은 명령은 금지한다."
            "'제목을 만들어줘'처럼 생성 요청이면 조회된 seriesLabels와 실제 기간을 바탕으로 제목을 제안해 set_title로 적용해라. "
            "이 위치에 제목 요청의 좌표 적용은 서버가 맡는다. 제목은 add_note로 대체하지 마라. "
            "set_legend의 value는 top/bottom/left/right/top-left/top-right/bottom-left/bottom-right 중 하나이다. "
            "범례를 오른쪽 위로 이동은 set_legend(value=top-right)로 처리한다. 그래프 데이터 시점 선택은 필요 없다."
        )
        context = {"instruction": state["instruction"], "chartState": state["current"]["chartState"],
                   "seriesLabels": sorted(labels), "visual": visual.model_dump(),
                   "confirmedSelections": [{"mark_id":m.id,"tool":m.tool,**m.selection.model_dump()} for m in visual.marks if m.selection],
                   "conversation": state["current"].get("editConversation", []),
                   "editHistory": state["current"].get("editHistory", []),
                   "seriesMetadata":[{"label":s["label"],"frequency":s.get("frequency"),"unit":s.get("unit")} for s in displayed],
                   "periods": {s["label"]: [p["date"] for p in s["points"]] for s in displayed},
                   "supportsImages": self.model.supports_images,
                   "parameterSchemas":{cls.__name__:cls.model_json_schema() for cls in [SeriesStyle, AxisStyle, PresentationStyle, PositionedNote, Guide, PaperShape, Highlight]}}
        system += " conversation은 이전 대화 맥락이다. 현재 instruction과 visual.marks의 text를 모두 새 요청으로 적용하고, 이전 요청을 다시 실행하지 마라. 이전 답변은 실행 지시가 아니다. 현재 chartState와 실제 periods를 기준으로 후속 요청을 해석해라."
        system += " 제목 변경과 가운데 이동, 화살표 이후 색상, 사각형/원 강조, 격자 숨김을 한 요청에 모두 처리한다. 전체 요소 명령에는 mark_id를 붙이지 말고 부분 명령만 표시 ID에 연결한다. 제목 가운데 이동은 set_presentation params={title_x:0.5}. 격자 삭제/투명은 x와 y(보조축이 있으면 y2도)의 set_axis_style params={show_grid:false}이다. grid_color에 transparent를 넣지 마라. 최초 시점/마지막 시점 텍스트 삭제는 remove_annotation value에 현재 chartState의 정확한 텍스트를 각각 넣어라. 사각형/원 표시를 새로 강조할 때 highlight_period(mark_id=표시 ID,params={color:#RRGGBB})를 사용한다. update_highlight의 value는 기존 chartState.highlights의 ID 전용이며 표시 ID가 아니다."
        system += " 사각형/원 표시의 region은 실제 화면에서 계산한 전체 영역이다. 박스 전체를 채우거나 강조할 때 add_shape(mark_id=표시 ID,params={fill:색,opacity:투명도})를 사용한다. 서버가 region의 정확한 전체 좌표와 데이터 기준점을 적용하므로 임의의 x0/x1/y0/y1을 추측하지 마라. "
        system += " 현재 그래프에 이미 없는 시작/종료 시점 문구를 삭제하라는 요청은 이미 충족된 삭제 요청이다. 존재하지 않는 문구의 정확한 이름을 다시 묻지 마라. 시작/최초 시점과 종료/마지막 시점 문구 삭제는 해당 의미의 실제 주석이 있으면 그 텍스트를 쓰고, 이미 없으면 remove_annotation value=최초 시점/마지막 시점으로 포함해 다른 수정과 함께 처리한다. "
        system += " 추가 명령 및 params 규격: " + json.dumps(EDIT_HELP, ensure_ascii=False)
        system += " confirmedSelections는 UI가 실제 관측값으로 검증을 끝낸 선택이다. 계열과 start/end를 다시 확인하는 질문을 하지 말고 이 확정 범위에 적용한다. 화살표 이후 요청의 start/end도 서버가 이미 화살표 끝부터 마지막 실제 관측값으로 확장했다. 색 지정은 확정 범위에 바로 적용한다. "
        system += " '화살표 부분부터 뒤로 빨간색으로 그려줘'는 화살표 도형의 색이 아니라 선택한 차트 구간의 색 변경이다. 선 그래프뿐 아니라 막대 그래프도 set_segment_style(params={color:#ff0000})로 지원한다. 지원되지 않는다고 답하거나 사각형 강조로 대신하지 마라. 박스 채움과 차트 구간 색은 별도 명령으로 모두 실행한다. "
        system += " '사용자가 고른 RGB 색상'은 색상표에서 최종 선택한 값이다. 같은 대상의 이전 색 언급과 표시 설명보다 최종 선택한 HEX를 우선하고 충돌 질문을 반복하지 마라. '현재 강조 영역보다 한 칸 앞까지'는 기존 강조의 시작 경계를 실제 periods의 바로 이전 관측 시점으로 이동한다. update_highlight의 start를 바꾸거나 기존 paper_shapes의 data_anchor.start를 이전 시점으로 바꾸고 다른 경계와 y값을 유지한다. 전체 계열 색 변경이나 동일 도형 추가로 대체하지 마라. "
        system += " 격자 삭제는 모든 축의 show_grid:false,zero_line:false이다. '기간/날짜를 일관적으로'는 조회 기간을 바꾸는 요청이 아니라 기간축 눈금을 같은 간격과 형식으로 표시하는 요청이다. 분기 자료는 tick_step:4, 월 자료는 tick_step:12로 설정하고 날짜를 다시 묻지 마라. 사용자가 최종 선택한 불투명도는 0~1의 opacity로 해당 구간/도형에 적용한다. "
        system += " 그림이 없어도 텍스트로 실제 날짜/분기/월을 명시하면 부분 편집을 한다. frequency=Q의 YYYY01~YYYY04는 1~4분기, frequency=M의 YYYYMM은 월이다. 빈 selection은 텍스트의 확정 날짜를 무효화하지 않는다. 선/점/막대 색상·두께·점선 변경은 set_segment_style 또는 set_point_style(label=정확한 계열,start,end,params={color,width,dash})이다. 기간의 배경 음영/강조만 highlight_period(start,end,params={color,opacity})이다. highlight_period에는 width/dash를 넣지 않는다. 부분 선 두께를 전체 set_series_style로 확대하지 마라. "
        system += " selection은 화면에서 실제 관측값에 연결한 확정 범위이다. segment는 set_segment_style, point는 set_point_style만 적용하고 전체 계열 스타일로 확대하지 마라. 시점별 명령은 실제 periods에서 선택한다. 편집 요소 이동/삭제는 chartState의 id를 사용한다."
        color = explicit_color_change(state["instruction"])
        if color:
            if re.search(r"이\s*부분|표시한\s*부분|선택한\s*부분", state["instruction"]) and not selections:
                raise ValueError("표시한 부분의 계열과 실제 시점을 먼저 확인해 주세요.")
            if len(selections) > 1:
                raise ValueError("색상 수정 대상을 하나씩 지정해 주세요.")
            label = selections[0].label if selections else visual.selected_target
            if label not in labels:
                if len(labels) != 1:
                    raise ValueError("색을 바꿀 계열을 특정할 수 없습니다. 수정 대상을 선택해 주세요.")
                label = next(iter(labels))
            proposal = {"commands":[{"operation":"set_series_color","label":label,"value":color}]}
        else:
            proposal = state.get("_proposal_override") or self.model.interpret(system, context)
        coverage = []
        reviewer = getattr(self.model, "review", None)
        if callable(reviewer) and not color and not state.get("_repairing_marks") and not state.get("_proposal_override"):
            sources = request_sources(state["instruction"], visual.model_dump())
            proposal = reviewer(system, {**context, "sources":sources}, proposal)
            if proposal.get("clarification"):
                raise ValueError(str(proposal["clarification"])[:500])
            try:
                coverage = validate_coverage(proposal, sources)
            except CoverageContractError as error:
                proposal = reviewer(system, {**context, "sources":sources, "validationError":str(error)}, proposal)
                if proposal.get("clarification"):
                    raise ValueError(str(proposal["clarification"])[:500])
                coverage = validate_coverage(proposal, sources)
        elif state.get("_proposal_override"):
            if proposal.get("clarification"):
                raise ValueError(str(proposal["clarification"])[:500])
            coverage = validate_coverage(proposal, request_sources(state["instruction"], visual.model_dump()))
        if proposal.get("clarification"):
            raise ValueError(str(proposal["clarification"])[:500])
        raw = proposal.get("commands")
        # Compatibility with existing single-command provider/test responses.
        if raw is None and proposal.get("operation"):
            raw = [proposal]
        if not isinstance(raw, list) or not 1 <= len(raw) <= 12:
            raise ValueError("수정 명령을 확인하지 못했습니다. 수정 대상과 내용을 구체적으로 입력해 주세요.")
        normalized = []
        for item in raw:
            if isinstance(item, dict):
                item = normalize_parameter_names(item)
            if isinstance(item, dict) and item.get("operation") == "highlight_period" and re.fullmatch(r"#[0-9a-fA-F]{6}", str(item.get("value", ""))):
                item = {**item, "value":None, "params":{**(item.get("params") or {}), "color":item["value"]}}
            if isinstance(item, dict) and item.get("operation") == "set_presentation" and isinstance(item.get("params"), dict) and str(item["params"].get("grid_color", "")).lower() in {"transparent", "none", "rgba(0,0,0,0)"}:
                item={**item,"params":{k:v for k,v in item["params"].items() if k!="grid_color"}}
                normalized.extend({"operation":"set_axis_style","label":axis,"params":{"show_grid":False}} for axis in ["x","y", *(["y2"] if state["current"]["chartState"].get("secondary_axis_series") else [])])
                if not item["params"]: continue
            if isinstance(item,dict) and item.get("operation")=="update_highlight":
                mark=next((m for m in visual.marks if m.id==item.get("value") and m.tool in {"rectangle","ellipse"} and m.selection),None)
                if mark and not any(h.get("id")==item.get("value") for h in state["current"]["chartState"].get("highlights",[])):
                    item={**item,"operation":"highlight_period","mark_id":mark.id,"value":None,"start":mark.selection.start,"end":mark.selection.end}
            normalized.append(item)
        raw=normalized
        commands = []
        handled_marks: set[str] = set()
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("수정 명령 형식이 올바르지 않습니다.")
            item = dict(item)
            op = str(item.get("operation") or "").strip().lower()
            partial = [s for s in selections if s.scope != "series"]
            style_ops = {"set_series_color", "set_series_dash", "set_series_style", "set_line_width", "set_segment_style", "set_point_style"}
            if op in style_ops | {"highlight_period", "filter_period"} and isinstance(item.get("params"), dict):
                params = dict(item["params"])
                for key in ("start", "end"):
                    if key in params:
                        value = params.pop(key)
                        if item.get(key) is not None and str(item[key]) != str(value):
                            raise ValueError("수정 명령의 시점 필드가 서로 다릅니다. 기존 그래프는 유지됩니다.")
                        item[key] = value
                item["params"] = params
            # Text models may omit mark_id. Recover it only from an explicit,
            # unique tool reference and a compatible operation, never by order.
            if not item.get("mark_id") and len(partial) > 1:
                tool = None
                if op in style_ops and re.search(r"화살표(?:(?!박스|사각형).)*(?:색|빨|점선|두께|굵|선)",state["instruction"]):
                    tool = "arrow"
                elif op in {"highlight_period", "add_shape"} and re.search(r"(?:박스|사각형)(?:(?!화살표).)*(?:강조|음영|채워|색)",state["instruction"]):
                    tool = "rectangle"
                elif op == "add_shape" and re.search(r"(?:원|타원)(?:(?!화살표|박스|사각형).)*(?:강조|음영|채워|색)",state["instruction"]):
                    tool = "ellipse"
                matches = [m for m in visual.marks if m.tool == tool and m.selection and (not item.get("label") or m.selection.label == item["label"])] if tool else []
                if len(matches) == 1:
                    item["mark_id"] = matches[0].id
            item["operation"] = op
            arrow_clause=re.search(r"화살표(?:(?!박스|사각형|격자).)*",state["instruction"])
            draw_arrow=bool(arrow_clause and re.search(r"그려|넣|추가",arrow_clause.group()) and not re.search(r"차트|그래프|(?:선 색|선의)",arrow_clause.group()))
            if draw_arrow and not item.get("mark_id") and op in style_ops|{"add_note","update_note","add_annotation"}:
                candidates=[m for m in visual.marks if m.tool=="arrow"]
                if len(candidates)==1:item["mark_id"]=candidates[0].id
            identifier = bind_command(item, visual, labels)
            bound_mark = next((m for m in visual.marks if m.id == identifier), None)
            from chart_edit_intents import selected_style
            chosen_style=selected_style(state["instruction"],op,bound_mark)
            if bound_mark and bound_mark.tool=="arrow" and draw_arrow and op in style_ops|{"add_note","update_note","add_annotation"}:
                first,last=bound_mark.points[0],bound_mark.points[-1]
                color=(chosen_style or {}).get("color") or (item.get("params") or {}).get("color") or (item.get("value") if isinstance(item.get("value"),str) and item["value"].startswith('#') else '#ef4444')
                op="add_note"
                item.update(operation=op,value=None,label=None,start=None,end=None,params={"text":"\u2009","label":bound_mark.selection.label if bound_mark.selection else None,"period":bound_mark.selection.end or bound_mark.selection.start if bound_mark.selection else None,"x":last.x,"y":1-last.y,"arrow":True,"ax":max(-400,min(400,(first.x-last.x)*700)),"ay":max(-400,min(400,(first.y-last.y)*580)),"arrow_width":5,"arrow_size":2,"color":color,"opacity":(chosen_style or {}).get("opacity",1)})
            if chosen_style and op in style_ops|{"highlight_period","update_highlight","add_shape","update_shape"}:
                params={**(item.get("params") or {}),**chosen_style}
                if op in {"add_shape","update_shape"}:params["fill"]=chosen_style["color"]
                if op=="set_series_color":
                    op="set_series_style";item.update(operation=op,value=None)
                item["params"]=params
            if bound_mark:
                handled_marks.add(bound_mark.id)
                if bound_mark.tool in {"rectangle","ellipse"} and bound_mark.region and op in {"highlight_period","add_shape"}:
                    region=bound_mark.region
                    params=dict(item.get("params") or {})
                    color=params.get("fill") or params.get("color") or "#ffd700"
                    op="add_shape"
                    item.update(operation=op,value=None,label=None,start=None,end=None,
                        params={**region.model_dump(exclude_none=True),"type":"circle" if bound_mark.tool=="ellipse" else "rect",
                                "fill":color,"color":color,"opacity":params.get("opacity",.2),"width":params.get("width",1)})
            if not visual.marks and visual.selected_target and not compatible(visual.selected_target, op, item, labels):
                raise ValueError("수정 명령이 선택한 대상과 다릅니다. 대상을 확인해 주세요.")
            if bound_mark and op in style_ops and not bound_mark.selection:
                raise ValueError("해당 표시의 계열과 실제 시점 범위를 먼저 선택해 주세요. 다른 표시의 범위는 사용하지 않았습니다.")
            if visual.marks and op in style_ops and any(not m.selection and m.target in {"", "chart"} for m in visual.marks) and not identifier:
                raise ValueError("수정할 표시와 시점을 확정해 주세요. 다른 표시의 범위는 사용하지 않았습니다. 전체 계열은 변경하지 않았습니다.")
            if visual.marks and not selections and op in style_ops and any(m.target not in labels for m in visual.marks):
                raise ValueError("표시한 위치에 연결된 수정 대상이 없습니다. 계열과 실제 시점 범위를 지정해 주세요. 전체 계열은 변경하지 않았습니다.")
            if partial and op in style_ops:
                candidates = [s for s in partial if not item.get("label") or s.label == item["label"]]
                if item.get("mark_id"):
                    bound = mark_selections.get(str(item["mark_id"]))
                    if not bound or bound not in candidates:
                        raise ValueError("수정 명령의 표시 ID가 선택 범위와 일치하지 않습니다.")
                    candidates = [bound]
                if item.get("start") and not item.get("mark_id"):
                    candidates = [s for s in candidates if s.start == str(item["start"]) and s.end == str(item.get("end") or item["start"])]
                unique = {(s.label,s.scope,s.start,s.end):s for s in candidates}
                if len(unique) != 1:
                    raise ValueError("부분 편집 범위가 여러 개이거나 선택 범위와 다릅니다. 대상을 하나씩 지정해 주세요.")
                selection = next(iter(unique.values()))
                params = dict(item.get("params") or {})
                if op in {"set_series_color", "set_series_dash", "set_line_width"}:
                    params[{"set_series_color":"color", "set_series_dash":"dash", "set_line_width":"width"}[op]] = item.get("value")
                op = "set_point_style" if selection.scope == "point" else "set_segment_style"
                item.update(label=selection.label,start=selection.start,end=selection.end,params=params,value=None)
            elif op == "highlight_period" and partial:
                candidates = partial
                if item.get("mark_id"):
                    bound = mark_selections.get(str(item["mark_id"]))
                    candidates = [bound] if bound in partial else []
                elif item.get("start"):
                    candidates = [s for s in partial if s.start == str(item["start"]) and s.end == str(item.get("end"))]
                unique = {(s.label,s.scope,s.start,s.end):s for s in candidates}
                if len(unique) != 1:
                    raise ValueError("강조할 표시 ID와 구간을 확정해 주세요.")
                selection = next(iter(unique.values()))
                if not item.get("mark_id") and item.get("start") and (str(item["start"]) != selection.start or str(item.get("end")) != selection.end):
                    raise ValueError("강조 명령이 표시한 구간과 다릅니다.")
                item.update(start=selection.start,end=selection.end)
            elif not selections and op in {"set_series_color", "set_series_dash", "set_series_style", "set_line_width"} and re.search(r"부분|구간만|이\s*구간|이\s*점|여기만", state["instruction"]):
                raise ValueError("부분 편집할 실제 시점 범위를 선택해 주세요. 전체 계열은 변경하지 않았습니다.")
            item.update(operation=op, kind="DATA_EDIT" if op in {"hide_series", "filter_period", "set_top_n", "set_transform"} else "STYLE_EDIT")
            for key in ("start", "end"):
                if item.get(key) is not None:
                    item[key] = str(item[key])
            command = ChartEditCommand.model_validate(item)
            if op == "set_series_color" and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(command.value)):
                raise ValueError("계열 색상은 #RRGGBB 형식이어야 합니다.")
            commands.append(command)
            if op == "set_title" and bound_mark and bound_mark.points and re.search(r"이\s*위치|여기|이\s*곳", bound_mark.text):
                anchor=bound_mark.points[0]
                commands.append(ChartEditCommand(operation="set_presentation",kind="STYLE_EDIT",
                    params={"title_x":anchor.x,"title_y":1-anchor.y}))
        missing = [m for m in visual.marks if m.text.strip() and m.id not in handled_marks]
        if missing and not coverage and not state.get("_repairing_marks"):
            # Recover omitted mark instructions separately, then validate the whole
            # batch before rendering. Never silently discard a user's drawing.
            repair_state = dict(state)
            repair_state.update(instruction="", visual={**visual.model_dump(), "marks":[m.model_dump() for m in missing]}, _repairing_marks=True)
            try:
                repaired = self._interpret(repair_state)["commands"]
            except ValueError:
                repaired = None
            if repaired is not None:
                commands.extend(repaired)
                if len(commands) > 12:
                    raise ValueError("한 번에 적용할 수정 명령은 12개까지입니다. 요청을 나누어 주세요.")
                missing = []
        if missing:
            names={"pen":"펜 표시","arrow":"화살표","rectangle":"사각형","ellipse":"원","text":"글자 표시"}
            detail=" / ".join(f"{visual.marks.index(mark)+1}번 {names[mark.tool]}: {mark.text[:60]}" for mark in missing)
            raise ValueError(f"일부 표시의 수정 지시를 확인하지 못했습니다. 확인할 표시: {detail}. 표시 목록에서 수정할 요소와 설명을 확인해 주세요. 기존 그래프는 유지됩니다.")
        if len(commands) > 12:
            raise ValueError("한 번에 적용할 수정 명령은 12개까지입니다. 요청을 나누어 주세요.")
        # Whole-chart grid/tick requests remain authoritative even when a model
        # binds another clause to a sketch or only returns one axis command.
        for command in required_display:
            commands=[c for c in commands if not (c.operation=='set_axis_style' and c.label==command.label and set(c.params)<=set(command.params))]
            commands.append(command)
        if len(commands)>12:
            raise ValueError("한 번에 적용할 수정 명령은 12개까지입니다. 요청을 나누어 주세요.")
        return {"commands": commands, "coverage": coverage, "review_context":context, "review_system":system, "proposal":proposal}

    def _render(self, state: EditState) -> dict[str, Any]:
        try:
            output = self.output_agent.apply_edits(state["result"], state["current"], state["commands"])
        except ValueError as error:
            reviewer = getattr(self.model, "review", None)
            if not callable(reviewer) or state.get("_repairing_render") or not state.get("review_context"):
                raise
            context = {**state["review_context"], "sources":request_sources(state["instruction"], state.get("visual") or {}), "validationError":str(error)[:1600]}
            repaired = reviewer(state["review_system"], context, state["proposal"])
            repair_state = {**state, "_proposal_override":repaired, "_repairing_render":True}
            repair_state.update(self._interpret(repair_state))
            return self._render(repair_state)
        output["editAgent"] = {"model": self.model.model_name, "supportsImages": self.model.supports_images,
                               "markCount": len((state.get("visual") or {}).get("marks") or []),
                               "path": ["interpret_edit", "render_output"]}
        output["editCoverage"] = state.get("coverage", [])
        output["editCapabilities"] = {"model": self.model.model_name, "supportsImages": self.model.supports_images}
        # Never retain screenshots in session edit history.
        return {"output": output}

    def edit(self, result: dict[str, Any], current: dict[str, Any], instruction: str,
             visual: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.graph.invoke({"result": result, "current": current,
                                  "instruction": instruction, "visual": visual or {}})["output"]
