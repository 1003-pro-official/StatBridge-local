from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


ChartType = Literal[
    "auto", "line", "bar", "stacked_bar", "area", "scatter", "bubble",
    "pie", "donut", "histogram", "box", "heatmap", "treemap", "waterfall",
]
Layout = Literal["combined", "separate", "horizontal", "grid"]
Color = str


class StrictStyle(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SeriesStyle(StrictStyle):
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    dash: Literal["solid", "dot", "dash", "longdash", "dashdot"] | None = None
    width: float | None = Field(default=None, ge=1, le=12)
    opacity: float | None = Field(default=None, ge=0.05, le=1)
    marker_size: float | None = Field(default=None, ge=2, le=24)
    marker_symbol: Literal["circle", "square", "diamond", "cross", "triangle-up", "triangle-down"] | None = None
    markers: bool | None = None
    show_values: bool | None = None
    line_shape: Literal["linear", "spline", "hv", "vh", "hvh", "vhv"] | None = None


class RangeStyle(StrictStyle):
    id: str = Field(default_factory=lambda: uuid4().hex)
    label: str
    start: str
    end: str
    scope: Literal["segment", "point"] = "segment"
    style: SeriesStyle

    @model_validator(mode="after")
    def valid_range(self) -> "RangeStyle":
        if not self.start or self.start > self.end or (self.scope == "point" and self.start != self.end):
            raise ValueError("부분 편집의 시점·구간이 올바르지 않습니다.")
        if not self.style.model_dump(exclude_none=True):
            raise ValueError("부분 편집 스타일을 지정해 주세요.")
        return self


class AxisStyle(StrictStyle):
    minimum: float | None = None
    maximum: float | None = None
    scale: Literal["linear", "log"] = "linear"
    reverse: bool = False
    show_grid: bool = True
    zero_line: bool = True
    tick_angle: float = Field(default=0, ge=-90, le=90)
    tick_step: float | None = Field(default=None, gt=0)
    decimals: int | None = Field(default=None, ge=0, le=6)
    title: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def valid_range(self) -> "AxisStyle":
        if (self.minimum is None) != (self.maximum is None):
            raise ValueError("축의 최솟값·최댓값을 함께 지정해 주세요.")
        if self.minimum is not None and self.minimum >= self.maximum:
            raise ValueError("축의 최솟값은 최댓값보다 작아야 합니다.")
        if self.scale == "log" and self.minimum is not None and self.minimum <= 0:
            raise ValueError("로그축 범위는 양수여야 합니다.")
        return self


class PresentationStyle(StrictStyle):
    font_family: str = Field(default="Arial, sans-serif", max_length=100)
    font_size: int = Field(default=12, ge=8, le=32)
    title_size: int = Field(default=18, ge=10, le=42)
    legend_size: int = Field(default=12, ge=8, le=30)
    font_color: str = Field(default="#263247", pattern=r"^#[0-9a-fA-F]{6}$")
    background: str = Field(default="#ffffff", pattern=r"^#[0-9a-fA-F]{6}$")
    grid_color: str = Field(default="#e5e7eb", pattern=r"^#[0-9a-fA-F]{6}$")
    height: int | None = Field(default=None, ge=280, le=2400)
    width: int | None = Field(default=None, ge=400, le=2000)
    title_x: float = Field(default=0, ge=0, le=1)
    title_y: float | None = Field(default=None, ge=0, le=1)
    margin_left: int = Field(default=65, ge=20, le=220)
    margin_right: int = Field(default=65, ge=20, le=220)
    margin_top: int = Field(default=80, ge=30, le=220)
    margin_bottom: int = Field(default=85, ge=30, le=240)
    bar_mode: Literal["group", "stack", "relative"] | None = None
    bar_gap: float = Field(default=0.2, ge=0, le=0.8)
    bar_orientation: Literal["vertical", "horizontal"] = "vertical"
    number_decimals: int = Field(default=1, ge=0, le=6)
    shared_y: bool = False
    notes: str = Field(default="", max_length=500)
    color_scale: Literal["Viridis", "Blues", "Reds", "RdBu", "YlOrRd", "Greens"] = "Viridis"
    reverse_colors: bool = False
    show_colorbar: bool = True


class PositionedNote(StrictStyle):
    id: str = Field(default_factory=lambda: uuid4().hex)
    text: str = Field(min_length=1, max_length=300)
    label: str | None = None
    period: str | None = None
    x: float = Field(default=0.5, ge=0, le=1)
    y: float = Field(default=0.9, ge=0, le=1)
    ax: float = Field(default=0, ge=-400, le=400)
    ay: float = Field(default=-45, ge=-400, le=400)
    arrow: bool = False
    color: str = Field(default="#263247", pattern=r"^#[0-9a-fA-F]{6}$")
    font_size: int = Field(default=12, ge=8, le=30)


class Guide(StrictStyle):
    id: str = Field(default_factory=lambda: uuid4().hex)
    orientation: Literal["horizontal", "vertical"] = "horizontal"
    value: float | str
    label: str | None = None
    text: str = Field(default="", max_length=100)
    color: str = Field(default="#6b7280", pattern=r"^#[0-9a-fA-F]{6}$")
    dash: Literal["solid", "dot", "dash", "longdash", "dashdot"] = "dash"
    width: float = Field(default=1, ge=1, le=8)


class PaperShape(StrictStyle):
    id: str = Field(default_factory=lambda: uuid4().hex)
    type: Literal["rect", "circle", "line"] = "rect"
    x0: float = Field(ge=0, le=1)
    x1: float = Field(ge=0, le=1)
    y0: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)
    color: str = Field(default="#ef4444", pattern=r"^#[0-9a-fA-F]{6}$")
    fill: str = Field(default="#ffffff", pattern=r"^#[0-9a-fA-F]{6}$")
    opacity: float = Field(default=0.25, ge=0.05, le=1)
    width: float = Field(default=2, ge=1, le=8)
    dash: Literal["solid", "dot", "dash", "longdash", "dashdot"] = "solid"


class Highlight(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    start: str
    end: str
    label: str = ""
    color: str = Field(default="#ffd700", pattern=r"^#[0-9a-fA-F]{6}$")
    opacity: float = Field(default=0.15, ge=0.05, le=1)

    @model_validator(mode="after")
    def check_range(self) -> "Highlight":
        if not self.start or not self.end or self.start > self.end:
            raise ValueError("강조 기간의 시작은 종료보다 늦을 수 없습니다.")
        return self


class Annotation(BaseModel):
    period: str
    text: str = Field(min_length=1, max_length=200)


class ChartSpec(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    chart_type: ChartType = "auto"
    layout: Layout = "combined"
    title: str = Field(default="", max_length=150)
    subtitle: str = Field(default="", max_length=250)
    x_axis_label: str = Field(default="", max_length=80)
    y_axis_label: str = Field(default="", max_length=80)
    show_legend: bool = True
    legend_position: Literal["top", "bottom", "left", "right", "top-left", "top-right", "bottom-left", "bottom-right"] = "top"
    line_width: float = Field(default=3, ge=1, le=12)
    highlighted_series: str | None = None
    highlights: list[Highlight] = Field(default_factory=list, max_length=20)
    annotations: list[Annotation] = Field(default_factory=list, max_length=30)
    reference_lines: list[float] = Field(default_factory=list, max_length=10)
    hidden_series: list[str] = Field(default_factory=list)
    period_start: str | None = None
    period_end: str | None = None
    top_n: int | None = Field(default=None, ge=1, le=100)
    transform: Literal["raw", "growth_rate", "year_over_year", "average", "cumulative"] = "raw"
    series_chart_types: dict[str, Literal["line", "bar", "area"]] = Field(default_factory=dict)
    secondary_axis_series: list[str] = Field(default_factory=list)
    series_colors: dict[str, str] = Field(default_factory=dict)
    series_dashes: dict[str, Literal["solid", "dot", "dash", "longdash", "dashdot"]] = Field(default_factory=dict)
    series_styles: dict[str, SeriesStyle] = Field(default_factory=dict)
    range_styles: list[RangeStyle] = Field(default_factory=list, max_length=80)
    display_names: dict[str, str] = Field(default_factory=dict)
    series_order: list[str] = Field(default_factory=list, max_length=100)
    axes: dict[Literal["x", "y", "y2"], AxisStyle] = Field(default_factory=dict)
    presentation: PresentationStyle = Field(default_factory=PresentationStyle)
    notes: list[PositionedNote] = Field(default_factory=list, max_length=40)
    guides: list[Guide] = Field(default_factory=list, max_length=30)
    paper_shapes: list[PaperShape] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def check_period(self) -> "ChartSpec":
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError("조회 시작 시점은 종료 시점보다 늦을 수 없습니다.")
        return self


class ChartEditCommand(BaseModel):
    operation: Literal[
        "set_title", "set_subtitle", "set_axis_labels", "set_chart_type", "set_layout",
        "set_legend", "set_line_width", "highlight_period", "highlight_series",
        "add_annotation", "add_reference_line", "hide_series", "filter_period",
        "set_top_n", "set_transform", "set_series_chart_type", "set_secondary_axis",
        "set_series_color", "set_series_dash",
        "set_segment_style", "set_point_style", "remove_range_style", "clear_range_styles",
        "set_series_style", "rename_series", "reorder_series", "show_series", "clear_highlight",
        "set_axis_style", "set_presentation", "remove_secondary_axis",
        "add_note", "update_note", "remove_note", "add_guide", "update_guide", "remove_guide",
        "update_highlight", "remove_highlight", "add_shape", "update_shape", "remove_shape", "reset_styles",
    ]
    kind: Literal["STYLE_EDIT", "DATA_EDIT"]
    value: str | float | int | bool | dict | list[str] | None = None
    start: str | None = None
    end: str | None = None
    label: str | None = None
    x_axis_label: str | None = None
    y_axis_label: str | None = None
    params: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_kind(self) -> "ChartEditCommand":
        data_ops = {"hide_series", "filter_period", "set_top_n", "set_transform"}
        expected = "DATA_EDIT" if self.operation in data_ops else "STYLE_EDIT"
        if self.kind != expected:
            raise ValueError(f"{self.operation} 명령은 {expected}여야 합니다.")
        return self


class SketchPoint(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class SketchMark(BaseModel):
    """Normalized viewport coordinates, not fabricated statistical observations."""
    id: str = Field(min_length=1, max_length=80)
    tool: Literal["pen", "arrow", "rectangle", "text"]
    points: list[SketchPoint] = Field(min_length=1, max_length=300)
    text: str = Field(default="", max_length=300)
    target: str = Field(default="", max_length=300)
    selection: "EditSelection | None" = None


class EditSelection(StrictStyle):
    label: str = Field(min_length=1, max_length=300)
    scope: Literal["series", "segment", "point"]
    start: str | None = Field(default=None, max_length=30)
    end: str | None = Field(default=None, max_length=30)

    @model_validator(mode="after")
    def check_selection(self) -> "EditSelection":
        if self.scope != "series" and (not self.start or not self.end or self.start > self.end):
            raise ValueError("부분 선택의 시작·종료 시점이 필요합니다.")
        if self.scope == "point" and self.start != self.end:
            raise ValueError("점 편집은 하나의 시점을 선택해야 합니다.")
        return self


class VisualEditContext(BaseModel):
    marks: list[SketchMark] = Field(default_factory=list, max_length=40)
    selected_target: str = Field(default="", max_length=300)
    selection: EditSelection | None = None
    # Optional snapshots are reserved for a future image-capable adapter.
    graph_image: str | None = Field(default=None, max_length=2_000_000, pattern=r"^data:image/png;base64,[A-Za-z0-9+/=]+$")
    marked_image: str | None = Field(default=None, max_length=2_000_000, pattern=r"^data:image/png;base64,[A-Za-z0-9+/=]+$")
