from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


ChartType = Literal[
    "auto", "line", "bar", "stacked_bar", "area", "scatter", "bubble",
    "pie", "donut", "histogram", "box", "heatmap", "treemap", "waterfall",
]
Layout = Literal["combined", "separate"]


class Highlight(BaseModel):
    start: str
    end: str
    label: str = ""

    @model_validator(mode="after")
    def check_range(self) -> "Highlight":
        if not self.start or not self.end or self.start > self.end:
            raise ValueError("강조 기간의 시작은 종료보다 늦을 수 없습니다.")
        return self


class Annotation(BaseModel):
    period: str
    text: str = Field(min_length=1, max_length=200)


class ChartSpec(BaseModel):
    chart_type: ChartType = "auto"
    layout: Layout = "combined"
    title: str = Field(default="", max_length=150)
    subtitle: str = Field(default="", max_length=250)
    x_axis_label: str = Field(default="", max_length=80)
    y_axis_label: str = Field(default="", max_length=80)
    show_legend: bool = True
    legend_position: Literal["top", "bottom", "left", "right"] = "top"
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
    ]
    kind: Literal["STYLE_EDIT", "DATA_EDIT"]
    value: str | float | int | bool | None = None
    start: str | None = None
    end: str | None = None
    label: str | None = None
    x_axis_label: str | None = None
    y_axis_label: str | None = None

    @model_validator(mode="after")
    def check_kind(self) -> "ChartEditCommand":
        data_ops = {"hide_series", "filter_period", "set_top_n", "set_transform"}
        expected = "DATA_EDIT" if self.operation in data_ops else "STYLE_EDIT"
        if self.kind != expected:
            raise ValueError(f"{self.operation} 명령은 {expected}여야 합니다.")
        return self
