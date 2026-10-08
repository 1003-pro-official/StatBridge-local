"""Deterministic presentation renderer; segment boundaries never alter observations."""
from __future__ import annotations

from html import escape
import math
from typing import Any

import plotly.graph_objects as go

from output_schema import ChartSpec


def style_for(spec: ChartSpec, item: dict, period: str | None = None, edge: tuple[str, str] | None = None) -> dict:
    label = item["label"]
    style = dict(color=item["color"], dash=spec.series_dashes.get(label, "solid"), width=spec.line_width,
                 opacity=1 if not spec.highlighted_series or spec.highlighted_series == label else .3,
                 marker_size=8, marker_symbol="circle", markers=True, show_values=False, line_shape="linear")
    style.update(spec.series_styles.get(label).model_dump(exclude_none=True) if label in spec.series_styles else {})
    if spec.highlighted_series == label:
        style["width"] = min(12, style["width"] * 1.5)
    for rule in spec.range_styles:
        if rule.label != label:
            continue
        matches = (edge is not None and rule.scope == "segment" and rule.start <= edge[0] and edge[1] <= rule.end) or (period is not None and rule.start <= period <= rule.end)
        if matches:
            style.update(rule.style.model_dump(exclude_none=True))
    return style


def rgba(color: str, opacity: float) -> str:
    return f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},{opacity})"


def arrange_top_captions(fig: Any, period_count: int) -> None:
    """Deduplicate automatic captions and place nearby captions in separate lanes.

    Explicit notes/arrows retain their requested coordinates and pixel offsets.
    """
    kept, seen, lanes = [], set(), []
    for annotation in fig.layout.annotations or []:
        automatic = (annotation.yref == "paper" or str(annotation.yref or "").endswith(" domain")) and annotation.y == 1 and not annotation.showarrow and not annotation.name
        if not automatic:
            kept.append(annotation)
            continue
        top = 1
        if str(annotation.yref or "").endswith(" domain"):
            axis_name = str(annotation.yref).split()[0].replace("y", "yaxis", 1)
            axis = getattr(fig.layout, axis_name, None)
            domain = getattr(axis, "domain", None)
            top = domain[1] if domain else 1
        coordinate_frame = (annotation.xref or "x", top)
        key = (coordinate_frame, annotation.x, annotation.text)
        if key in seen:
            continue
        seen.add(key)
        if isinstance(annotation.x, (int, float)) and (annotation.xref or "x").startswith("x"):
            # Approximate text extents in category units; lanes prevent start/min
            # and end/max captions at neighboring observations from overlapping.
            half_width = max(1, len(str(annotation.text or ""))) * .012 * max(1, period_count - 1)
            lane = 0
            while lane < len(lanes) and any(ref == coordinate_frame and abs(x-annotation.x) < width+half_width for ref,x,width in lanes[lane]):
                lane += 1
            if lane == len(lanes): lanes.append([])
            lanes[lane].append((coordinate_frame, annotation.x, half_width))
            annotation.yshift = (annotation.yshift or 0) + lane * 22
            annotation.yanchor = "bottom"
        kept.append(annotation)
    fig.layout.annotations = kept
    if len(lanes) > 1:
        fig.update_layout(margin_t=max(fig.layout.margin.t or 0, 80+(len(lanes)-1)*22))
    # A top legend occupies the same margin as caption lanes. Reserve a
    # separate row above the highest caption instead of moving captions into it.
    legend = fig.layout.legend
    if lanes and legend.y is not None and legend.y > 1:
        fig.update_layout(margin_t=max(fig.layout.margin.t or 0, 120+(len(lanes)-1)*22))
        plot_height=max(100,(fig.layout.height or 580)-(fig.layout.margin.t or 0)-(fig.layout.margin.b or 0))
        legend.y=max(legend.y,1+(len(lanes)*22+18)/plot_height)
        legend.yanchor="bottom"


def cartesian_traces(item: dict, spec: ChartSpec, kind: str) -> list[Any]:
    label, points = item["label"], item["points"]
    x, y = [p["date"] for p in points], [p["value"] for p in points]
    base = style_for(spec, item)
    local = [style_for(spec, item, period=p) for p in x]
    name = escape(spec.display_names.get(label) or label)
    common = dict(name=name, legendgroup=label, meta={"seriesLabel": label}, customdata=[[label, p] for p in x])
    marker = dict(color=[rgba(s["color"], s["opacity"]) for s in local],
                  size=[s["marker_size"] if s["markers"] else 0 for s in local], symbol=[s["marker_symbol"] for s in local])
    text = [f"{v:.{spec.presentation.number_decimals}f}" if s["show_values"] else "" for v, s in zip(y, local)]
    if kind in {"bar", "stacked_bar"}:
        horizontal = spec.presentation.bar_orientation == "horizontal"
        return [go.Bar(x=y if horizontal else x, y=x if horizontal else y, orientation="h" if horizontal else "v",
            marker=dict(color=marker["color"], line=dict(color=[s["color"] for s in local], width=[s["width"] if (label in spec.series_styles and spec.series_styles[label].width is not None) or any(r.label == label and r.start <= period <= r.end and r.style.width is not None for r in spec.range_styles) else 0 for period,s in zip(x,local)])),
            text=text, textposition="auto", **common)]
    segmented = any(r.label == label for r in spec.range_styles)
    if not segmented:
        return [go.Scatter(x=x, y=y, mode="lines+markers+text" if any(text) else "lines+markers", text=text,
            textposition="top center", marker=marker, line=dict(color=base["color"], dash=base["dash"], width=base["width"],shape=base["line_shape"]),
            opacity=base["opacity"], fill="tozeroy" if kind == "area" else None, **common)]
    traces = []
    # Filled area is a separate transparent boundary, not a solid line under dashes.
    if kind == "area":
        traces.append(go.Scatter(x=x, y=y, mode="lines", line=dict(width=0), fill="tozeroy",
            fillcolor=rgba(base["color"], .15), showlegend=False, hoverinfo="skip", **common))
    groups: list[tuple[int, int, dict]] = []
    for i in range(len(x)-1):
        current = style_for(spec, item, edge=(x[i], x[i+1]))
        edge_style = {k: current[k] for k in ("color", "dash", "width", "opacity", "line_shape")}
        if groups and groups[-1][2] == edge_style:
            start, _, previous = groups[-1]
            groups[-1] = start, i+1, previous
        else:
            groups.append((i, i+1, edge_style))
    for i, (start, end, s) in enumerate(groups):
        traces.append(go.Scatter(x=x[start:end+1], y=y[start:end+1], mode="lines", name=name, legendgroup=label,
            meta={"seriesLabel": label}, customdata=[[label, p] for p in x[start:end+1]], showlegend=i == 0,
            line=dict(color=s["color"], dash=s["dash"], width=s["width"],shape=s["line_shape"]), opacity=s["opacity"]))
    traces.append(go.Scatter(x=x, y=y, mode="markers+text" if any(text) else "markers", marker=marker,
        text=text, textposition="top center", showlegend=not groups, **common))
    return traces


def decorate(fig: Any, series: list[dict], spec: ChartSpec, dual_axis: bool) -> None:
    p = spec.presentation
    fig.update_layout(font=dict(family=p.font_family, size=p.font_size, color=p.font_color),
        title=dict(font=dict(size=p.title_size), x=p.title_x, xref="container", xanchor="center" if 0 < p.title_x < 1 else ("left" if p.title_x == 0 else "right")), legend=dict(font=dict(size=p.legend_size)),
        paper_bgcolor=p.background, plot_bgcolor=p.background,
        margin=dict(l=p.margin_left, r=p.margin_right, t=p.margin_top, b=p.margin_bottom), bargap=p.bar_gap)
    if p.width:
        fig.update_layout(width=p.width)
    if p.title_y is not None:
        fig.update_layout(title=dict(y=p.title_y,yref="container",xref="container",xanchor="center",yanchor="middle"))
    if p.height:
        fig.update_layout(height=p.height)
    if p.bar_mode:
        fig.update_layout(barmode=p.bar_mode)
    fig.update_xaxes(gridcolor=p.grid_color)
    fig.update_yaxes(gridcolor=p.grid_color)
    for name, axis in spec.axes.items():
        period_axis = (name == "y" if p.bar_orientation == "horizontal" else name == "x") and spec.chart_type not in {"scatter", "bubble", "histogram"}
        settings = dict(type="category" if period_axis else axis.scale,
            showgrid=axis.show_grid, zeroline=axis.zero_line, tickangle=axis.tick_angle,
            autorange="reversed" if axis.reverse else True)
        if axis.title is not None:
            settings["title_text"] = escape(axis.title)
        if axis.decimals is not None:
            settings["tickformat"] = f".{axis.decimals}f"
        if axis.tick_step is not None:
            settings["dtick"] = axis.tick_step
            if period_axis:
                dates=sorted({p["date"] for s in series for p in s["points"]})
                step=max(1,int(axis.tick_step))
                tick_dates=dates[::step]
                frequency=next((s.get("frequency") for s in series if s.get("frequency")),"")
                def tick_label(date):
                    if len(date)==6 and date.isdigit():
                        if frequency=="Q":return date[:4]+"년" if step%4==0 else date[:4]+"년 "+str(int(date[4:]))+"분기"
                        if frequency=="M":return date[:4]+"년" if step%12==0 else date[:4]+"년 "+str(int(date[4:]))+"월"
                    return date
                settings.update(tickmode="array",tickvals=tick_dates,ticktext=[tick_label(d) for d in tick_dates])
        if axis.minimum is not None:
            bounds = [axis.minimum, axis.maximum]
            if axis.scale == "log":
                bounds = [math.log10(v) for v in bounds]
            settings.update(range=list(reversed(bounds)) if axis.reverse else bounds, autorange=False)
        if name == "x":
            fig.update_xaxes(**settings)
        elif dual_axis:
            fig.update_yaxes(secondary_y=name == "y2", **settings)
        else:
            fig.update_yaxes(**settings)
    by_label = {s["label"]: s for s in series}
    def refs(label: str | None) -> tuple[str, str]:
        for trace in fig.data:
            if isinstance(trace.meta, dict) and trace.meta.get("seriesLabel") == label:
                return trace.xaxis or "x", trace.yaxis or "y"
        return "x", "y"
    for note in spec.notes:
        if note.label:
            if note.label not in by_label:
                continue
            point = next(p for p in by_label[note.label]["points"] if p["date"] == note.period)
            x, y, (xref, yref) = note.period, point["value"], refs(note.label)
        else:
            x, y, xref, yref = note.x, note.y, "paper", "paper"
        fig.add_annotation(name=note.id, x=x, y=y, xref=xref, yref=yref, text=escape(note.text),
            showarrow=note.arrow, ax=note.ax, ay=note.ay, arrowhead=2, arrowcolor=note.color, arrowwidth=note.arrow_width, arrowsize=note.arrow_size, opacity=note.opacity,
            font=dict(size=note.font_size, color=note.color))
    for guide in spec.guides:
        if guide.label in spec.hidden_series:
            continue
        xref, yref = refs(guide.label)
        horizontal = guide.orientation == "horizontal"
        v = float(guide.value) if horizontal else str(guide.value)
        fig.add_shape(name=guide.id, type="line", xref=f"{xref} domain" if horizontal else xref,
            yref=yref if horizontal else f"{yref} domain", x0=0 if horizontal else v, x1=1 if horizontal else v,
            y0=v if horizontal else 0, y1=v if horizontal else 1,
            line=dict(color=guide.color, dash=guide.dash, width=guide.width))
        if guide.text:
            fig.add_annotation(x=1 if horizontal else v, y=v if horizontal else 1,
                xref=f"{xref} domain" if horizontal else xref, yref=yref if horizontal else f"{yref} domain",
                text=escape(guide.text), showarrow=False, font=dict(color=guide.color))
    for shape in spec.paper_shapes:
        anchor=shape.data_anchor
        if anchor:
            item=by_label.get(anchor.label)
            if not item: continue
            periods=sorted({p["date"] for s in series for p in s["points"]})
            if anchor.start not in periods or anchor.end not in periods: continue
            xref,yref=refs(anchor.label)
            fig.add_shape(name=shape.id,type=shape.type,xref=xref,yref=yref,
                x0=periods.index(anchor.start)+anchor.start_offset,x1=periods.index(anchor.end)+anchor.end_offset,
                y0=anchor.y0,y1=anchor.y1,fillcolor=shape.fill,opacity=shape.opacity,
                line=dict(color=shape.color,width=shape.width,dash=shape.dash))
            continue
        fig.add_shape(name=shape.id, type=shape.type, xref="paper", yref="paper", x0=shape.x0, x1=shape.x1,
            y0=shape.y0, y1=shape.y1, fillcolor=shape.fill, opacity=shape.opacity,
            line=dict(color=shape.color, width=shape.width, dash=shape.dash))
    if p.notes:
        fig.add_annotation(x=0, y=-.2, xref="paper", yref="paper", text=escape(p.notes), showarrow=False, xanchor="left")
