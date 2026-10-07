"""Bounded presentation edits extracted from the research chart review.

No model code is executed here and no source observations are overwritten.
"""
from __future__ import annotations

from typing import Any

from output_schema import (AxisStyle, ChartEditCommand, ChartSpec, Guide, Highlight,
                           PaperShape, PositionedNote, PresentationStyle, RangeStyle, SeriesStyle)


EDIT_HELP = {
    "set_segment_style": "label,start,end,params={color,dash,width,opacity,marker_size,marker_symbol,markers,show_values,line_shape:linear/spline/hv/vh/hvh/vhv}. 선분 구간만 수정",
    "set_point_style": "label,start=end,params={color,marker_size,marker_symbol,markers,show_values,opacity}. 점/막대만 수정",
    "remove_range_style": "value=range_styles의 id", "clear_range_styles": "label=계열 또는 생략하여 모든 부분 스타일 제거",
    "set_series_style": "label,params={color,dash,width,opacity,marker_size,marker_symbol,markers,show_values,line_shape:linear/spline/hv/vh/hvh/vhv}",
    "rename_series": "label=정본 이름,value=화면 표시 이름(데이터 ID 유지)",
    "reorder_series": "value=[정본 계열 이름,...] 모든 계열을 정확히 한 번 포함",
    "show_series": "value=숨긴 계열의 정본 이름", "clear_highlight": "강조 계열 해제",
    "remove_secondary_axis": "value=계열 이름, 보조축 해제",
    "set_axis_style": "label=x/y/y2,params={minimum,maximum,scale:linear/log,reverse,show_grid,zero_line,tick_angle,tick_step,decimals,title}. x의 수치 범위는 산점도에서만",
    "set_presentation": "params={font_family,font_size,title_size,legend_size,font_color,background,grid_color,height,width,title_x,margin_left,margin_right,margin_top,margin_bottom,bar_mode:group/stack/relative,bar_gap,bar_orientation:vertical/horizontal,number_decimals,shared_y,notes,color_scale:Viridis/Blues/Reds/RdBu/YlOrRd/Greens,reverse_colors,show_colorbar}",
    "add_note": "params={text,label?,period?,x?,y?,ax?,ay?,arrow?,color?,font_size?}. 계열과 시점이 있으면 실제 관측점에 연결, 없으면 paper x/y=0~1(아래0 위1)",
    "update_note": "value=notes의 id,params=변경 필드", "remove_note": "value=notes의 id",
    "add_guide": "params={orientation:horizontal/vertical,value,label?,text?,color?,dash?,width?}. 수평 실제 y값/수직 실제 시점",
    "update_guide": "value=guides의 id,params=변경 필드", "remove_guide": "value=guides의 id",
    "update_highlight": "value=highlights의 id,params={start,end,label,color,opacity}", "remove_highlight": "value=highlights의 id",
    "add_shape": "params={type:rect/circle/line,x0,x1,y0,y1,color,fill,opacity,width,dash}. paper 좌표0~1의 장식, 데이터 선 수정 아님",
    "update_shape": "value=paper_shapes의 id,params=변경 필드", "remove_shape": "value=paper_shapes의 id",
    "reset_styles": "표현 스타일·주석·강조만 초기화, 원자료·조회 기간·변환은 유지",
}


def _patch(model: Any, params: dict) -> Any:
    return type(model).model_validate({**model.model_dump(), **params})


def apply_research_edit(spec: ChartSpec, command: ChartEditCommand, labels: list[str]) -> ChartSpec | None:
    """Return None for legacy commands handled by OutputAgent."""
    op, value, params = command.operation, command.value, command.params
    if op not in EDIT_HELP:
        return None
    updates: dict[str, Any] = {}
    if op in {"set_segment_style", "set_point_style", "set_series_style", "rename_series"} and command.label not in labels:
        raise ValueError("수정할 계열이 조회 결과에 없습니다.")
    if op in {"set_segment_style", "set_point_style"}:
        scope = "point" if op == "set_point_style" else "segment"
        updates["range_styles"] = [*spec.range_styles, RangeStyle(label=command.label, start=command.start or "",
            end=command.end or command.start or "", scope=scope, style=SeriesStyle.model_validate(params))]
    elif op == "set_series_style":
        updates["series_styles"] = {**spec.series_styles, command.label: _patch(spec.series_styles.get(command.label, SeriesStyle()), params)}
    elif op == "rename_series":
        if not isinstance(value, str) or not value.strip() or len(value) > 150:
            raise ValueError("표시 이름은 1~150자로 입력해 주세요.")
        updates["display_names"] = {**spec.display_names, command.label: value}
    elif op == "reorder_series":
        if not isinstance(value, list) or len(value) != len(labels) or set(value) != set(labels):
            raise ValueError("계열 순서는 모든 정본 이름을 중복 없이 지정해야 합니다.")
        updates["series_order"] = value
    elif op == "show_series":
        if value not in labels:
            raise ValueError("표시할 계열이 조회 결과에 없습니다.")
        updates["hidden_series"] = [label for label in spec.hidden_series if label != value]
    elif op == "clear_highlight":
        updates["highlighted_series"] = None
    elif op == "remove_secondary_axis":
        if value not in labels:
            raise ValueError("계열을 확인해 주세요.")
        updates["secondary_axis_series"] = [label for label in spec.secondary_axis_series if label != value]
        if not updates["secondary_axis_series"]:
            updates["axes"] = {name: axis for name, axis in spec.axes.items() if name != "y2"}
    elif op == "clear_range_styles":
        if command.label and command.label not in labels:
            raise ValueError("계열을 확인해 주세요.")
        updates["range_styles"] = [style for style in spec.range_styles if command.label and style.label != command.label]
    elif op == "set_axis_style":
        if command.label not in {"x", "y", "y2"}:
            raise ValueError("축은 x, y, y2 중 하나를 선택해 주세요.")
        updates["axes"] = {**spec.axes, command.label: _patch(spec.axes.get(command.label, AxisStyle()), params)}
    elif op == "set_presentation":
        updates["presentation"] = _patch(spec.presentation, params)
    elif op == "reset_styles":
        updates = {"series_colors": {}, "series_dashes": {}, "series_styles": {}, "range_styles": [],
                   "display_names": {}, "series_order": [], "axes": {}, "presentation": PresentationStyle(),
                   "highlights": [], "annotations": [], "reference_lines": [], "notes": [], "guides": [],
                   "paper_shapes": [], "highlighted_series": None, "line_width": 3, "legend_position": "top", "show_legend": True}
    else:
        field, cls = next((field, cls) for suffix, field, cls in [
            ("range_style", "range_styles", RangeStyle), ("note", "notes", PositionedNote),
            ("guide", "guides", Guide), ("highlight", "highlights", Highlight), ("shape", "paper_shapes", PaperShape)
        ] if op.endswith(suffix))
        items = list(getattr(spec, field))
        if op.startswith("add_"):
            if "id" in params:
                raise ValueError("새 편집 요소의 ID는 서버에서 생성합니다.")
            updates[field] = [*items, cls.model_validate(params)]
        else:
            if not any(item.id == value for item in items):
                raise ValueError("편집 요소 ID를 현재 그래프에서 찾지 못했습니다.")
            if op.startswith("remove_"):
                updates[field] = [item for item in items if item.id != value]
            else:
                if "id" in params:
                    raise ValueError("편집 요소 ID는 변경할 수 없습니다.")
                updates[field] = [_patch(item, params) if item.id == value else item for item in items]
    return ChartSpec.model_validate({**spec.model_dump(), **updates})


def validate_research_spec(series: list[dict[str, Any]], spec: ChartSpec) -> None:
    by_label = {s["label"]: s for s in series}
    if spec.layout != "combined" and spec.chart_type in {"pie", "donut", "treemap", "waterfall", "scatter", "bubble", "heatmap"}:
        raise ValueError("이 그래프의 패널 배치는 지원하지 않습니다. 선·막대·영역·분포 그래프를 사용해 주세요.")
    if spec.secondary_axis_series and spec.layout != "combined":
        raise ValueError("보조축은 합쳐 그리기에서만 지원합니다. 먼저 보조축을 해제해 주세요.")
    if spec.presentation.shared_y and len({s["unit"] for s in series}) > 1:
        raise ValueError("단위가 다른 패널의 세로축을 공유할 수 없습니다.")
    for label, style in spec.series_styles.items():
        if label not in by_label:
            continue
        kind = spec.series_chart_types.get(label, spec.chart_type)
        props = set(style.model_dump(exclude_none=True))
        if kind in {"pie", "donut", "treemap", "histogram", "box", "waterfall"} and props - {"color", "opacity"}:
            raise ValueError("이 그래프의 계열 스타일은 색상·투명도만 지원합니다.")
        if kind == "heatmap":
            raise ValueError("히트맵 색상은 set_presentation의 color_scale로 변경해 주세요.")
        if kind in {"bar", "stacked_bar"} and props & {"dash", "marker_size", "marker_symbol", "markers", "line_shape"}:
            raise ValueError("막대는 색상·투명도·테두리·값 표시를 사용해 주세요.")
        if kind in {"scatter", "bubble"} and (props & {"dash", "width", "line_shape"} or label != series[0]["label"]):
            raise ValueError("산점도 스타일 대상은 첫 번째 좌표 계열입니다. 점 스타일을 사용해 주세요.")
    for style in spec.range_styles:
        item = by_label.get(style.label)
        if not item:
            continue  # Hidden series retain their style for show_series.
        periods = [p["date"] for p in item["points"]]
        if style.start not in periods or style.end not in periods:
            raise ValueError("부분 편집 시점이 표시된 실제 관측 시점에 없습니다.")
        chart_type = spec.series_chart_types.get(style.label, spec.chart_type)
        if chart_type == "auto":
            chart_type = "line" if len(periods) > 6 else "bar"
        if chart_type not in {"line", "area", "bar", "stacked_bar", "scatter", "bubble"}:
            raise ValueError("이 그래프는 시점별 부분 편집을 지원하지 않습니다. 선·막대·산점도를 선택해 주세요.")
        if style.scope == "segment" and style.start == style.end and chart_type in {"line", "area"}:
            raise ValueError("선분은 두 시점을 선택해야 합니다. 한 시점은 점 편집을 사용해 주세요.")
        props = style.style.model_dump(exclude_none=True)
        if style.scope == "point" and set(props) & {"dash", "width", "line_shape"} and chart_type not in {"bar", "stacked_bar"}:
            raise ValueError("점 편집에는 점선·선 굵기를 적용할 수 없습니다. 선분 편집을 선택해 주세요.")
        if chart_type in {"bar", "stacked_bar"} and set(props) & {"dash", "marker_size", "marker_symbol", "markers", "line_shape"}:
            raise ValueError("막대 부분 편집은 색상·투명도·테두리 굵기·값 표시를 지원합니다.")
        if chart_type in {"scatter", "bubble"} and set(props) & {"dash", "width", "line_shape"}:
            raise ValueError("산점도는 점의 색상·크기·모양을 수정할 수 있습니다.")
        if chart_type in {"scatter", "bubble"} and style.label != series[0]["label"]:
            raise ValueError("산점도의 점 선택은 첫 번째 좌표 계열을 사용해 주세요.")
    for note in spec.notes:
        if bool(note.label) != bool(note.period):
            raise ValueError("관측점 주석에는 계열과 시점을 함께 지정해야 합니다.")
        if note.label in spec.hidden_series:
            continue
        if note.label and (note.label not in by_label or note.period not in {p["date"] for p in by_label[note.label]["points"]}):
            raise ValueError("주석을 연결할 실제 관측점을 찾지 못했습니다.")
        if note.label and spec.chart_type not in {"line", "bar", "stacked_bar", "area", "auto"}:
            raise ValueError("관측점 주석은 선·막대·영역 그래프에서 사용해 주세요. 다른 그래프는 화면 메모를 사용할 수 있습니다.")
    if spec.presentation.bar_orientation == "horizontal" and any(n.label for n in spec.notes):
        raise ValueError("관측점 주석은 세로 막대에서 사용해 주세요. 가로 막대는 화면 메모를 지원합니다.")
    if spec.presentation.bar_orientation == "horizontal" and spec.guides:
        raise ValueError("가로 막대의 기준선은 현재 지원하지 않습니다. 세로 막대로 전환해 주세요.")
    if spec.axes.get("y2") and not spec.secondary_axis_series:
        raise ValueError("보조축 계열을 지정한 뒤 y2축을 수정해 주세요.")
    if spec.axes.get("x") and (spec.axes["x"].minimum is not None or spec.axes["x"].scale == "log") and spec.chart_type not in {"scatter", "bubble", "histogram"} and spec.presentation.bar_orientation != "horizontal":
        raise ValueError("기간축은 수치 범위·로그축 대신 조회 기간 필터를 사용해 주세요.")
    if spec.presentation.bar_orientation == "horizontal" and spec.axes.get("y") and (spec.axes["y"].minimum is not None or spec.axes["y"].scale == "log"):
        raise ValueError("가로 막대의 세로축은 기간축입니다. 수치 범위는 x축에 지정해 주세요.")
    for axis_name, axis in spec.axes.items():
        if axis.scale != "log":
            continue
        selected = series[:1] if axis_name == "x" else ([s for s in series if s["label"] in spec.secondary_axis_series] if axis_name == "y2" else [s for s in series if s["label"] not in spec.secondary_axis_series])
        if any(p["value"] <= 0 for s in selected for p in s["points"]):
            raise ValueError("0·음수 관측값은 로그축에 표시할 수 없습니다.")
    if spec.presentation.bar_orientation == "horizontal" and (spec.secondary_axis_series or spec.series_chart_types or spec.chart_type not in {"bar", "stacked_bar"}):
        raise ValueError("가로 막대는 혼합 그래프·보조축과 함께 사용할 수 없습니다.")
    for guide in spec.guides:
        if guide.label in spec.hidden_series:
            continue
        if spec.chart_type not in {"line", "area", "bar", "stacked_bar", "auto"}:
            raise ValueError("시점/값 기준선은 선·막대·영역 그래프에서 사용해 주세요. 다른 그래프는 화면 도형을 사용할 수 있습니다.")
        selected = [by_label[guide.label]] if guide.label in by_label else series
        if guide.label and guide.label not in by_label:
            raise ValueError("기준선을 적용할 계열을 찾지 못했습니다.")
        if guide.orientation == "vertical" and str(guide.value) not in {p["date"] for s in selected for p in s["points"]}:
            raise ValueError("수직 기준선은 실제 표시 시점을 지정해 주세요.")
        if guide.orientation == "horizontal":
            import math
            try:
                number = float(guide.value)
            except (ValueError, TypeError):
                raise ValueError("수평 기준선은 유한한 수치여야 합니다.") from None
            if not math.isfinite(number):
                raise ValueError("수평 기준선은 유한한 수치여야 합니다.")
