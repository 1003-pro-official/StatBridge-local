from __future__ import annotations

import json
import math
from typing import Any

import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from output_schema import ChartSpec


def render_plotly(series: list[dict[str, Any]], spec: ChartSpec) -> dict[str, Any]:
    """Render validated chart state and numeric data without executing model code."""
    if not series:
        return {"data": [], "layout": {"title": spec.title}}
    chart_type = spec.chart_type
    if chart_type == "auto":
        chart_type = "bar" if max(len(s["points"]) for s in series) <= 6 else "line"

    units = {s.get("unit") or "" for s in series}
    if len(units) > 1 and chart_type in {"stacked_bar", "pie", "donut", "heatmap", "treemap", "waterfall"}:
        raise ValueError("이 그래프 종류는 단위가 다른 계열을 함께 사용할 수 없습니다.")
    layout_mode = "separate" if len(units) > 1 and not spec.secondary_axis_series else spec.layout
    category_types = {"pie", "donut", "treemap", "histogram", "box", "waterfall"}
    if chart_type in category_types:
        layout_mode = "combined"

    dual_axis = layout_mode == "combined" and bool(spec.secondary_axis_series)
    if layout_mode == "separate" and len(series) > 1:
        fig = make_subplots(rows=len(series), cols=1, shared_xaxes=True,
                            subplot_titles=[s["label"] for s in series], vertical_spacing=0.08)
    elif dual_axis:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
    else:
        fig = go.Figure()

    def add(trace: Any, index: int = 0) -> None:
        if layout_mode == "separate" and len(series) > 1:
            fig.add_trace(trace, row=index + 1, col=1)
        elif dual_axis:
            fig.add_trace(trace, row=1, col=1, secondary_y=series[index]["label"] in spec.secondary_axis_series)
        else:
            fig.add_trace(trace)

    if chart_type in {"scatter", "bubble"}:
        needed = 3 if chart_type == "bubble" else 2
        if len(series) < needed:
            raise ValueError(f"{chart_type} 그래프에는 최소 {needed}개 계열이 필요합니다.")
        aligned = [
            (period, series[0]["label"], series[1]["label"], values[0], values[1], values[2] if needed == 3 else None)
            for period in sorted(set.intersection(*(set(p["date"] for p in s["points"]) for s in series[:needed])))
            if len(values := [next(p["value"] for p in s["points"] if p["date"] == period) for s in series[:needed]]) == needed
        ]
        if not aligned:
            raise ValueError("공통 시점이 없어 산점도를 만들 수 없습니다.")
        sizes = [max(8, min(40, abs(row[5]) ** 0.5)) for row in aligned] if needed == 3 else 8
        add(go.Scatter(x=[r[3] for r in aligned], y=[r[4] for r in aligned], mode="markers",
                       text=[r[0] for r in aligned], marker={"size": sizes}, name=" · ".join(s["label"] for s in series[:needed])))
    elif chart_type == "heatmap":
        if len(series) < 2:
            raise ValueError("히트맵에는 최소 2개 계열이 필요합니다.")
        periods = sorted({p["date"] for s in series for p in s["points"]})
        add(go.Heatmap(x=periods, y=[s["label"] for s in series],
                       z=[[next((p["value"] for p in s["points"] if p["date"] == period), None) for period in periods] for s in series]))
    elif chart_type in {"pie", "donut", "treemap"}:
        if len(series) < 2:
            raise ValueError(f"{chart_type} 그래프에는 최소 2개 범주가 필요합니다.")
        latest = [(s["label"], s["points"][-1]["value"]) for s in series if s["points"]]
        if any(value < 0 for _, value in latest):
            raise ValueError("음수 값은 비율 그래프에 사용할 수 없습니다.")
        labels, values = zip(*latest)
        if chart_type == "treemap":
            add(go.Treemap(labels=labels, parents=[""] * len(labels), values=values))
        else:
            add(go.Pie(labels=labels, values=values, hole=0.45 if chart_type == "donut" else 0))
    elif chart_type == "histogram":
        for index, s in enumerate(series):
            add(go.Histogram(x=[p["value"] for p in s["points"]], name=s["label"], marker_color=s["color"]), index)
    elif chart_type == "box":
        for index, s in enumerate(series):
            add(go.Box(y=[p["value"] for p in s["points"]], name=s["label"], marker_color=s["color"]), index)
    elif chart_type == "waterfall":
        if len(series) != 1:
            raise ValueError("워터폴은 현재 한 계열의 기여도 데이터만 지원합니다.")
        s = series[0]
        add(go.Waterfall(x=[p["date"] for p in s["points"]], y=[p["value"] for p in s["points"]],
                         measure=["relative"] * len(s["points"]), name=s["label"]))
    else:
        for index, s in enumerate(series):
            x = [p["date"] for p in s["points"]]
            y = [p["value"] for p in s["points"]]
            common = {"name": s["label"], "marker_color": s["color"]}
            series_type = spec.series_chart_types.get(s["label"], chart_type)
            if series_type in {"bar", "stacked_bar"}:
                add(go.Bar(x=x, y=y, **common), index)
            else:
                emphasized = not spec.highlighted_series or spec.highlighted_series == s["label"]
                add(go.Scatter(x=x, y=y, mode="lines+markers",
                               line={"width": spec.line_width * (1.5 if spec.highlighted_series and emphasized else 1), "color": s["color"]},
                               opacity=1 if emphasized else 0.3,
                               fill="tozeroy" if series_type == "area" else None, name=s["label"]), index)
    if chart_type == "stacked_bar":
        fig.update_layout(barmode="stack")
    fig.update_layout(
        title={"text": spec.title + (f"<br><sup>{spec.subtitle}</sup>" if spec.subtitle else "")},
        # The UI shows a wrapping legend above the chart; a second Plotly legend
        # consumes plotting space and can cover the upper part of long series.
        showlegend=False,
        template="plotly_white", height=max(420, len(series) * 300) if layout_mode == "separate" else 520,
        margin={"l": 76, "r": 76 if dual_axis else 35, "t": 88, "b": 72},
    )
    if chart_type not in {"pie", "donut", "treemap"}:
        periods = sorted({point["date"] for item in series for point in item["points"]})
        if periods:
            step = max(1, math.ceil((len(periods) - 1) / 5))
            ticks = periods[::step]
            if ticks[-1] != periods[-1]:
                ticks.append(periods[-1])
            frequency = str(series[0].get("frequency") or "")
            tick_labels = [f"{period[:4]}-{period[4:6]}" if frequency == "M" and len(period) == 6 else period for period in ticks]
            # KOSIS periods such as 202501 are identifiers, not Plotly dates.
            # Explicit categories keep every month at its own x position.
            if chart_type not in {"scatter", "bubble", "histogram", "box"}:
                fig.update_xaxes(type="category", categoryorder="array", categoryarray=periods)
            fig.update_xaxes(tickmode="array", tickvals=ticks, ticktext=tick_labels, tickangle=0, automargin=True)
        fig.update_xaxes(title_text=spec.x_axis_label)
        fig.update_yaxes(title_text="", automargin=True)
        left_label = spec.y_axis_label or (series[0].get("unit") or "")
        if left_label:
            fig.add_annotation(x=0, y=1.04, xref="paper", yref="paper", text=left_label,
                               showarrow=False, xanchor="left", yanchor="bottom")
        if dual_axis:
            right_units = {s.get("unit") or "" for s in series if s["label"] in spec.secondary_axis_series}
            fig.add_annotation(x=1, y=1.04, xref="paper", yref="paper", text=" / ".join(sorted(right_units)),
                               showarrow=False, xanchor="right", yanchor="bottom")
        if layout_mode == "combined" and chart_type in {"line", "bar", "stacked_bar", "area"}:
            def padded_range(items: list[dict[str, Any]]) -> list[float] | None:
                values = [point["value"] for item in items for point in item["points"]]
                if not values:
                    return None
                low, high = min(values), max(values)
                span = high - low or max(abs(high) * 0.1, 1.0)
                padding = span * 0.12
                return [min(0, low) - padding if chart_type in {"bar", "stacked_bar"} else low - padding, high + padding]

            left = [item for item in series if item["label"] not in spec.secondary_axis_series]
            right = [item for item in series if item["label"] in spec.secondary_axis_series]
            if left and (bounds := padded_range(left)):
                fig.update_yaxes(range=bounds, secondary_y=False if dual_axis else None)
            if right and (bounds := padded_range(right)):
                fig.update_yaxes(range=bounds, secondary_y=True)
    if chart_type in {"line", "bar", "stacked_bar", "area"}:
        for highlight in spec.highlights:
            fig.add_vrect(x0=highlight.start, x1=highlight.end, fillcolor="gold", opacity=0.15,
                          line_width=0, annotation_text=highlight.label)
        for value in spec.reference_lines:
            fig.add_hline(y=value, line_dash="dash", line_color="gray")
        for annotation in spec.annotations:
            fig.add_annotation(x=annotation.period, y=1, yref="paper", text=annotation.text, showarrow=False)
    return json.loads(pio.to_json(fig, validate=True))
