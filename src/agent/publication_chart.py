"""Compact publication view over computed year-over-year observations."""
from html import escape
import math


def publication_image_size(presentation):
    """Default canvas follows the compact economic-outlook reference (715:662)."""
    width = presentation.width or 715
    height = presentation.height or round(width * 662 / 715)
    return width, height


def finish_publication(fig, series, spec):
    yearly_bars=spec.presentation.publication_yoy
    if not yearly_bars and not spec.presentation.publication_axes:
        return
    if yearly_bars and (spec.transform != 'year_over_year' or spec.chart_type != 'bar' or len(series) != 1 or spec.report or spec.secondary_axis_series):
        raise ValueError('전년동기 막대그래프는 한 계열의 전년동기 대비 막대그래프에서 사용해 주세요.')
    if (spec.report and spec.report.kind not in {'forecast','events'}) or spec.secondary_axis_series or spec.layout!='combined' or len({s['unit'] for s in series})!=1 or len({s['frequency'] for s in series})!=1:
        raise ValueError('양쪽 동일 눈금은 같은 단위·주기의 지표를 한 그래프에 표시할 때 사용할 수 있습니다.')
    item = series[0]
    fig.layout.annotations = tuple(a for a in fig.layout.annotations or []
        if not str(a.name or '').startswith('statbridge-axis-title:'))
    periods = sorted({p['date'] for s in series for p in s['points']})
    values = [p['value'] for s in series for p in s['points']]
    extent = max(values + [0]) - min(values + [0])
    raw_step = max(extent / 6, .01)
    power = 10 ** math.floor(math.log10(raw_step))
    step = next(f * power for f in (1, 2, 5, 10) if f * power >= raw_step)
    lo = math.floor(min(values + [0]) / step) * step
    hi = math.ceil(max(values + [0]) / step) * step
    if lo == hi:
        hi = lo + step
    axis = spec.axes.get('y')
    if axis and axis.minimum is not None:
        lo, hi = axis.minimum, axis.maximum
    if axis and axis.tick_step:
        step = axis.tick_step
    if item.get('frequency') == 'M':
        interval=6 if yearly_bars else max(1,math.ceil(len(periods)/6))
        ticks = [i for i, p in enumerate(periods) if (int(p[-2:])-1)%interval==0]
        if not ticks or ticks[0] != 0:
            ticks.insert(0, 0)
        if not yearly_bars and len(periods)-1 not in ticks:
            ticks.append(len(periods)-1)
        labels = [f"{p[2:4]}.{int(p[-2:])}" if i == 0 or p[-2:] == '01' else str(int(p[-2:]))
                  for i, p in ((i, periods[i]) for i in ticks)]
    else:
        from snapshot_chart_style import date_label
        ticks = list(range(0, len(periods), max(1, math.ceil(len(periods)/7))))
        labels = [date_label(periods[i], item.get('frequency', '')) for i in ticks]
    dimensions = dict(zip(('width', 'height'), publication_image_size(spec.presentation))) if yearly_bars else {'height': spec.presentation.height or 520}
    fig.update_layout(showlegend=spec.show_legend and not yearly_bars, bargap=spec.presentation.bar_gap, **dimensions,
        meta={'publicationYoy': yearly_bars,'publicationAxes':True},
        margin=dict(l=65, r=65, t=105, b=113 if yearly_bars else 70), font=dict(family=spec.presentation.font_family, size=spec.presentation.font_size, color=spec.presentation.font_color),
        title=dict(text='<b>'+escape(spec.title)+'</b>', x=spec.presentation.title_x, y=.98 if spec.presentation.title_y is None else spec.presentation.title_y,
                   font=dict(size=spec.presentation.title_size, color=spec.presentation.font_color)),
        yaxis2=dict(overlaying='y', side='right', range=[lo, hi], dtick=step, tickmode='linear',
                    showgrid=False, zeroline=False, visible=True, ticks='inside', showline=True, linecolor='#222222'))
    if spec.show_legend and not yearly_bars and spec.legend_position=='top':
        fig.update_layout(legend=dict(y=1.15,yanchor='bottom'),margin=dict(t=150))
    fig.update_xaxes(title_text='', tickmode='array', tickvals=ticks, ticktext=labels,
                     range=[-.5, len(periods)-.5], autorange=False,
                     showgrid=False, showline=True, mirror=True, linecolor='#222222', ticks='inside')
    fig.layout.yaxis.update(title_text='', range=[lo, hi], autorange=False, dtick=step, tickmode='linear',
                     zeroline=True, zerolinecolor='#333333', zerolinewidth=1, gridcolor='#bbbbbb',
                     showline=True, linecolor='#222222', ticks='inside')
    # Plotly only displays an overlaid axis when a trace references it. Bind
    # an invisible copy of a real observation; this is still the same series.
    import plotly.graph_objects as go
    fig.add_trace(go.Scatter(x=[item['points'][0]['date']], y=[item['points'][0]['value']], yaxis='y2', mode='markers',
        marker=dict(opacity=0), hoverinfo='skip', showlegend=False,
        meta={'seriesLabel': item['label'], 'role': 'axis-mirror'}))
    unit='(전년동기 대비, %)' if spec.transform=='year_over_year' else '('+escape(item['unit'])+')'
    for x, anchor in ((0, 'left'), (1, 'right')):
        fig.add_annotation(name='publication-unit', x=x, y=1.04, xref='paper', yref='paper',
            text=unit, showarrow=False, xanchor=anchor, yanchor='bottom', font=dict(size=15, color='#111111'))
    for annual in item.get('annualGrowth', []) if yearly_bars else []:
        indices = [i for i, p in enumerate(periods) if p[:4] == str(annual['year'])]
        if len(indices) != 12:
            continue
        value = annual['value']
        fig.add_shape(type='line', x0=indices[0]-.5, x1=indices[-1]+.5, y0=value, y1=value,
                      line=dict(color='#808080', width=2, dash='dash'))
        fig.add_annotation(x=(indices[0]+indices[-1])/2, y=value, text=f"{str(annual['year'])[2:]}년: {value:.0f}%",
            showarrow=True, ax=0, ay=-40, arrowhead=2, arrowcolor='#808080', font=dict(size=13, color='#777777'),
            hovertext=f"공표 연간지수의 전년 대비 증가율: {value:.2f}%")
