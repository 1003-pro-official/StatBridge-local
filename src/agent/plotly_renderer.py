from __future__ import annotations

import json
from typing import Any

import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from output_schema import ChartSpec
from research_plotly_styles import cartesian_traces, decorate, style_for, rgba
from html import escape
import math
import textwrap
from chart_availability import data_requirements, combined_layout_reason


def wrapped(text, width=24):
    return '<br>'.join(escape(line) for line in textwrap.wrap(str(text),width=width,break_long_words=True,break_on_hyphens=False))


def render_plotly(series: list[dict[str, Any]], spec: ChartSpec) -> dict[str, Any]:
    """Render validated chart state and numeric data without executing model code."""
    if not series:
        return {"data": [], "layout": {"title": spec.title}}
    chart_type = spec.chart_type
    if chart_type == "auto":
        chart_type = "bar" if max(len(s["points"]) for s in series) <= 6 else "line"
    blockers=data_requirements(series,chart_type)
    if blockers:
        raise ValueError(' / '.join(blockers))

    units = {s.get("unit") or "" for s in series}
    if len(units) > 1 and chart_type in {"stacked_bar", "pie", "donut", "heatmap", "treemap", "waterfall"}:
        raise ValueError("이 그래프 종류는 단위가 다른 계열을 함께 사용할 수 없습니다.")
    layout_mode = spec.layout
    if layout_mode=='combined' and chart_type in {'line','bar','stacked_bar','area','histogram','box'}:
        reason=combined_layout_reason(series)
        if reason and (not spec.secondary_axis_series or len({s.get('frequency') for s in series if s.get('frequency')})>1):
            raise ValueError(reason)
    category_types = {"pie", "donut", "treemap", "waterfall"}
    if chart_type in category_types:
        layout_mode = "combined"

    dual_axis = layout_mode == "combined" and bool(spec.secondary_axis_series)
    panels = layout_mode in {"separate", "horizontal", "grid"} and len(series) > 1 and chart_type not in {'scatter','bubble','heatmap'}
    columns = len(series) if layout_mode == "horizontal" else (2 if layout_mode == "grid" else 1)
    if panels:
        fig = make_subplots(rows=math.ceil(len(series)/columns), cols=columns, shared_xaxes=layout_mode == "separate" and chart_type not in {'histogram','box'},
                            shared_yaxes=spec.presentation.shared_y,
                            subplot_titles=[wrapped(spec.display_names.get(s["label"], s["label"]),26) for s in series],
                            vertical_spacing=min(.18, .8/max(1, math.ceil(len(series)/columns))))
    elif dual_axis:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
    else:
        fig = go.Figure()

    def add(trace: Any, index: int = 0) -> None:
        if panels:
            fig.add_trace(trace, row=index // columns + 1, col=index % columns + 1)
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
        styles = [style_for(spec, series[0], period=r[0]) for r in aligned]
        add(go.Scatter(x=[r[3] for r in aligned], y=[r[4] for r in aligned], mode="markers+text" if any(s["show_values"] for s in styles) else "markers",
                       text=[r[0] if s["show_values"] else "" for r,s in zip(aligned,styles)],
                       customdata=[[series[0]["label"], r[0],r[3],r[4],r[5]] for r in aligned], meta={"seriesLabel": series[0]["label"]},
                       hovertemplate='시점: %{customdata[1]}<br>'+escape(series[0]['label'])+': %{x:,.2f} '+escape(series[0]['unit'])+'<br>'+escape(series[1]['label'])+': %{y:,.2f} '+escape(series[1]['unit'])+ ('<br>'+escape(series[2]['label'])+': %{customdata[4]:,.2f} '+escape(series[2]['unit']) if needed==3 else '')+'<extra></extra>',
                       marker={"size": [s["marker_size"] if any(rule.label == series[0]["label"] and rule.start <= r[0] <= rule.end and rule.style.marker_size is not None for rule in spec.range_styles) or series[0]["label"] in spec.series_styles else (sizes[i] if isinstance(sizes,list) else sizes) for i,(r,s) in enumerate(zip(aligned,styles))],
                               "color": [rgba(s["color"],s["opacity"]) for s in styles], "symbol": [s["marker_symbol"] for s in styles]}, name='동일 시점의 지표 관계',showlegend=False))
    elif chart_type == "heatmap":
        if len(series) < 2:
            raise ValueError("히트맵에는 최소 2개 계열이 필요합니다.")
        periods = sorted({p["date"] for s in series for p in s["points"]})
        add(go.Heatmap(x=periods, y=[s["label"] for s in series],
                       colorscale=spec.presentation.color_scale, reversescale=spec.presentation.reverse_colors, showscale=spec.presentation.show_colorbar,
                       z=[[next((p["value"] for p in s["points"] if p["date"] == period), None) for period in periods] for s in series]))
    elif chart_type in {"pie", "donut", "treemap"}:
        if len(series) < 2:
            raise ValueError(f"{chart_type} 그래프에는 최소 2개 범주가 필요합니다.")
        latest = [(s["label"], s["points"][-1]["value"]) for s in series if s["points"]]
        if len({s["points"][-1]["date"] for s in series if s["points"]}) != 1:
            raise ValueError("구성비 그래프는 같은 시점의 값을 비교해야 합니다. 계열의 마지막 시점이 서로 다릅니다.")
        if not latest or sum(value for _,value in latest) <= 0:
            raise ValueError("구성비 그래프에는 합계가 0보다 큰 값이 필요합니다.")
        if any(value < 0 for _, value in latest):
            raise ValueError("음수 값은 비율 그래프에 사용할 수 없습니다.")
        labels, values = zip(*latest)
        colors = [rgba(style_for(spec,s)["color"],style_for(spec,s)["opacity"]) for s in series if s["points"]]
        display_labels = [wrapped(spec.display_names.get(label) or label,24) for label in labels]
        if chart_type == "treemap":
            add(go.Treemap(labels=display_labels, parents=[""] * len(labels), values=values, marker_colors=colors))
        else:
            add(go.Pie(labels=display_labels, values=values, marker_colors=colors, hole=0.45 if chart_type == "donut" else 0))
    elif chart_type == "histogram":
        for index, s in enumerate(series):
            style=style_for(spec,s)
            add(go.Histogram(x=[p["value"] for p in s["points"]], name=escape(spec.display_names.get(s["label"]) or s["label"]), marker_color=style["color"], opacity=style["opacity"],
                hovertemplate=escape(s['label'])+'<br>값 구간: %{x} '+escape(s['unit'])+'<br>관측 수: %{y}<extra></extra>'), index)
    elif chart_type == "box":
        for index, s in enumerate(series):
            style=style_for(spec,s)
            add(go.Box(y=[p["value"] for p in s["points"]], name=escape(spec.display_names.get(s["label"]) or s["label"]), marker_color=style["color"], opacity=style["opacity"],
                hovertemplate=escape(s['label'])+'<br>분포 값: %{y:,.2f} '+escape(s['unit'])+'<extra></extra>'), index)
    elif chart_type == "waterfall":
        if len(series) != 1:
            raise ValueError("워터폴은 현재 한 계열의 기여도 데이터만 지원합니다.")
        s = series[0]
        style=style_for(spec,s)
        values = [p['value'] for p in s['points']]
        # Levels are not contributions: accumulate changes, not every observed level.
        changes = [values[0]] + [current-previous for previous,current in zip(values,values[1:])]
        add(go.Waterfall(x=[p["date"] for p in s["points"]], y=changes,
                         measure=['absolute'] + ['relative'] * (len(values)-1),
                         customdata=[[s['label'],p['date'],p['value']] for p in s['points']],
                         hovertemplate=escape(s['label'])+'<br>시점: %{customdata[1]}<br>관측값: %{customdata[2]:,.2f} '+escape(s['unit'])+'<br>시작값 / 직전 시점 대비 변화: %{y:,.2f}<extra></extra>',
                         name=escape(spec.display_names.get(s["label"],s["label"])),
                         increasing={"marker":{"color":style["color"]}}, decreasing={"marker":{"color":style["color"]}}, opacity=style["opacity"]))
    else:
        for index, s in enumerate(series):
            x = [p["date"] for p in s["points"]]
            y = [p["value"] for p in s["points"]]
            series_type = spec.series_chart_types.get(s["label"], chart_type)
            for trace in cartesian_traces(s, spec, series_type):
                add(trace, index)
    if chart_type == "stacked_bar":
        fig.update_layout(barmode="stack")
    fig.update_layout(
        title={"text": wrapped(spec.title) + (f"<br><sup>{wrapped(spec.subtitle,32)}</sup>" if spec.subtitle else ""),"y":.96,"yanchor":"top","yref":"container"},
        showlegend=spec.show_legend,
        legend={"orientation": "h" if spec.legend_position in {"top", "bottom"} else "v",
                "x": -.2 if spec.legend_position == "left" else (1.02 if spec.legend_position == "right" else 0), "y": -0.25 if spec.legend_position == "bottom" else 1.08,
                "yanchor":"top" if spec.legend_position=='bottom' else 'bottom'},
        template="plotly_white", height=max(560, math.ceil(len(series)/columns)*360+160) if panels else 580,
    )
    if spec.legend_position in {"top-left","top-right","bottom-left","bottom-right"}:
        right=spec.legend_position.endswith("right")
        top=spec.legend_position.startswith("top")
        fig.update_layout(legend=dict(orientation="v",x=1 if right else 0,y=1 if top else 0,
            xanchor="right" if right else "left",yanchor="top" if top else "bottom"))
    if chart_type not in {"pie", "donut", "treemap"}:
        fig.update_xaxes(title_text=wrapped(spec.x_axis_label or ('시점' if chart_type not in {'scatter','bubble','histogram','box'} else '관측값')),automargin=True,nticks=10)
        fig.update_yaxes(title_text=wrapped(spec.y_axis_label or ('관측 수' if chart_type=='histogram' else ' / '.join(sorted(units)))),automargin=True)
        if panels:
            for index,item in enumerate(series):
                fig.update_yaxes(title_text=wrapped(spec.y_axis_label or ('관측 수' if chart_type=='histogram' else item.get('unit') or '값')),row=index//columns+1,col=index%columns+1)
                if chart_type=='histogram':
                    fig.update_xaxes(title_text=wrapped(spec.x_axis_label or '관측값 ('+(item.get('unit') or '단위 미상')+')'),row=index//columns+1,col=index%columns+1)
        if chart_type in {'scatter','bubble'}:
            fig.update_xaxes(title_text=wrapped(spec.x_axis_label or spec.display_names.get(series[0]['label'],series[0]['label'])+' ('+series[0]['unit']+')'))
            fig.update_yaxes(title_text=wrapped(spec.y_axis_label or spec.display_names.get(series[1]['label'],series[1]['label'])+' ('+series[1]['unit']+')'))
        elif chart_type=='box':
            fig.update_xaxes(title_text=spec.x_axis_label or '지표')
        elif chart_type in {'bar','stacked_bar'} and spec.presentation.bar_orientation=='horizontal':
            fig.update_xaxes(title_text=spec.x_axis_label or ' / '.join(sorted(units)))
            fig.update_yaxes(title_text=spec.y_axis_label or '시점')
        if dual_axis:
            right_units = {s.get("unit") or "" for s in series if s["label"] in spec.secondary_axis_series}
            fig.update_yaxes(title_text=" / ".join(sorted(right_units)), secondary_y=True)
    if chart_type in {"line", "bar", "stacked_bar", "area"}:
        for highlight in spec.highlights:
            fig.add_vrect(x0=highlight.start, x1=highlight.end, fillcolor=highlight.color, opacity=highlight.opacity,
                          line_width=0, annotation_text=escape(highlight.label))
        for value in spec.reference_lines:
            fig.add_hline(y=value, line_dash="dash", line_color="gray")
        for annotation in spec.annotations:
            fig.add_annotation(x=annotation.period, y=1, yref="paper", text=escape(annotation.text), showarrow=False)
    decorate(fig, series, spec, dual_axis)
    # Keep legend labels short, with full source labels retained in hover/meta.
    for trace in fig.data:
        meta=trace.meta if isinstance(trace.meta,dict) else {}
        item=next((s for s in series if s['label']==meta.get('seriesLabel')),None)
        if item and not trace.hovertemplate and trace.hoverinfo!='skip':
            label=escape(spec.display_names.get(item['label'],item['label']))
            unit=escape(item.get('unit') or '')
            if trace.type in {'scatter','bar','waterfall'}:
                value='%{x:,.2f}' if spec.presentation.bar_orientation=='horizontal' and trace.type=='bar' else '%{y:,.2f}'
                trace.hovertemplate=label+'<br>시점: %{customdata[1]}<br>값: '+value+' '+unit+'<extra></extra>' if trace.customdata is not None else label+'<br>'+value+' '+unit+'<extra></extra>'
        if trace.name and len(trace.name)>32:
            trace.name=trace.name[:29]+'…'
    if chart_type=='heatmap':
        fig.update_yaxes(title_text=spec.y_axis_label or '지표',tickmode='array',tickvals=[s['label'] for s in series],ticktext=[wrapped(spec.display_names.get(s['label'],s['label']),20) for s in series])
        fig.data[0].hovertemplate='시점: %{x}<br>지표: %{y}<br>값: %{z:,.2f} '+escape(next(iter(units)))+'<extra></extra>'
    if chart_type in {'pie','donut','treemap'}:
        fig.data[0].customdata=[s['label'] for s in series]
        period=series[0]['points'][-1]['date']
        unit=escape(next(iter(units)))
        fig.data[0].hovertemplate='%{customdata}<br>기준 시점: '+escape(period)+'<br>값: %{value:,.2f} '+unit+('<br>구성비: %{percent}' if chart_type!='treemap' else '')+'<extra></extra>'
        if chart_type!='treemap':
            fig.data[0].textinfo='percent'
        else:
            fig.data[0].texttemplate='%{label}<br>%{value:,.2f} '+unit
        # A visible value key remains informative without hover, even when the
        # model hides the legend or supplies an empty display name.
        total=sum(s['points'][-1]['value'] for s in series)
        info=['기준 시점: '+escape(period)+' · 마지막 공통 시점의 구성비']
        for index,s in enumerate(series,1):
            value=s['points'][-1]['value']
            info.append(wrapped(f"{index}. {spec.display_names.get(s['label']) or s['label']}",36))
            share=value/total*100
            percent='<0.01%' if 0<share<.01 else f'{share:.2f}%'
            info.append(f"값: {value:,.{spec.presentation.number_decimals}f} {unit} · 구성비: {escape(percent)}")
        category_info='<br>'.join(info)
        fig.add_annotation(x=0,y=-.4 if spec.show_legend and spec.legend_position=='bottom' else -.08,xref='paper',yref='paper',xanchor='left',yanchor='top',
            text=category_info,showarrow=False,align='left',font=dict(color=spec.presentation.font_color,size=12))
    for axis_name in ('x','y'):
        axis_spec=spec.axes.get(axis_name)
        if (not axis_spec or axis_spec.tick_step is None) and not (chart_type=='heatmap' and axis_name=='y'):
            updater=fig.update_xaxes if axis_name=='x' else fig.update_yaxes
            updater(tickmode='auto',nticks=10)
    title_lines=fig.layout.title.text.count('<br>')+1 if fig.layout.title.text else 0
    legend_space=65 if spec.show_legend and spec.legend_position=='top' and chart_type not in {'scatter','bubble'} else 0
    fig.update_layout(margin=dict(t=max(100,spec.presentation.margin_top, title_lines*spec.presentation.title_size+legend_space+90),
        b=max(spec.presentation.margin_bottom,150 if spec.legend_position=='bottom' else 110)),hoverlabel=dict(namelength=-1),
        hovermode='closest' if chart_type in {'scatter','bubble','pie','donut','treemap','heatmap','box','histogram'} else 'x unified')
    if chart_type in {'pie','donut','treemap'}:
        bottom=max(fig.layout.margin.b, (category_info.count('<br>')+1)*18+(160 if spec.show_legend and spec.legend_position=='bottom' else 60))
        fig.update_layout(margin=dict(b=bottom),height=max(fig.layout.height,400+fig.layout.margin.t+bottom),
            legend=dict(font=dict(color=spec.presentation.font_color)))
    _apply_monthly_coordinates(fig, series, spec, chart_type)
    return json.loads(pio.to_json(fig, validate=True))


def _apply_monthly_coordinates(fig: Any, series: list[dict[str, Any]], spec: ChartSpec, chart_type: str) -> None:
    """Use ISO dates for monthly coordinates, retaining original IDs in customdata.

    Run after style decoration so period ticks, partial segments, notes and guides
    agree with the displayed axis. Numeric scatter axes must never be converted.
    """
    if chart_type not in {"line", "bar", "stacked_bar", "area", "waterfall", "heatmap"}:
        return
    if any(item.get("frequency") and item["frequency"] != "M" for item in series):
        return
    periods = sorted({str(point["date"]) for item in series for point in item["points"]})
    if not periods or not all(len(p) == 6 and p.isdigit() and 1 <= int(p[4:]) <= 12 for p in periods):
        return
    def coordinate(value: Any) -> Any:
        value = str(value)
        return f"{value[:4]}-{value[4:]}-01" if value in periods else value
    horizontal = spec.presentation.bar_orientation == "horizontal" and chart_type in {"bar", "stacked_bar"}
    axis = "y" if horizontal else "x"
    for trace in fig.data:
        values = getattr(trace, axis, None)
        if values is not None:
            setattr(trace, axis, [coordinate(value) for value in values])
    axis_spec = spec.axes.get("y" if horizontal else "x")
    step = (max(1, int(axis_spec.tick_step)) if axis_spec and axis_spec.tick_step else
            max(1, math.ceil((len(periods)-1)/5)))
    ticks = periods[::step]
    if ticks[-1] != periods[-1]:
        ticks.append(periods[-1])
    updater = fig.update_yaxes if horizontal else fig.update_xaxes
    updater(type="date", tickmode="array", tickvals=[coordinate(p) for p in ticks],
            ticktext=[f"{p[:4]}-{p[4:]}" for p in ticks],
            categoryarray=None, automargin=True)
    # Paper coordinates are normalized positions, not observation periods.
    for annotation in fig.layout.annotations or ():
        ref = getattr(annotation, f"{axis}ref", None) or axis
        if ref != "paper" and "domain" not in ref:
            value = getattr(annotation, axis, None)
            if str(value) in periods:
                setattr(annotation, axis, coordinate(value))
    for shape in fig.layout.shapes or ():
        ref = getattr(shape, f"{axis}ref", None) or axis
        if ref != "paper" and "domain" not in ref:
            for endpoint in (f"{axis}0", f"{axis}1"):
                value = getattr(shape, endpoint, None)
                if str(value) in periods:
                    setattr(shape, endpoint, coordinate(value))
