"""Observation-bound typography and date/last-value layout for report charts."""
from html import escape
import math


def legend_name(item,series,spec):
    label=item['label']
    name=spec.display_names.get(label,label)
    parts=[s['label'].split(' · ',1) for s in series]
    if label not in spec.display_names and spec.presentation.design_template=='snapshot' and parts and all(len(p)==2 and p[0]==parts[0][0] for p in parts):
        name=label.split(' · ',1)[1]
    right=spec.secondary_axis_series or (spec.report.right_axis if spec.report and spec.report.kind=='dual_axis' else [])
    if right and spec.presentation.design_template=='snapshot' and '(좌축)' not in name and '(우축)' not in name:
        name+=' (우축)' if label in right else ' (좌축)'
    return name


def date_label(period, frequency):
    if len(period)==6 and period.isdigit():
        if frequency=='Q' and 1<=int(period[-2:])<=4:return f'{period[:4]} Q{int(period[-2:])}'
        if frequency=='M':return period[:4]+'-'+period[-2:]
    if len(period)==8 and period.isdigit():return period[:4]+'-'+period[4:6]+'-'+period[6:]
    return period


def spaced_offsets(entries, gap=19):
    """Return display offsets only; never move the underlying observations."""
    result={}
    previous=None
    for key, position in sorted(entries,key=lambda entry:entry[1]):
        target=position if previous is None else max(position,previous+gap)
        result[key]=target-position
        previous=target
    if result:
        center=(max(result.values())+min(result.values()))/2
        result={key:value-center for key,value in result.items()}
    return result


def finish_snapshot(fig,series,spec,panels=False,columns=1):
    """Apply the chosen design and optional latest labels to actual traces."""
    snapshot=spec.presentation.design_template=='snapshot'
    if snapshot:
        fig.update_xaxes(showline=True,linecolor='#d3d9df',linewidth=.7,ticks='outside',ticklen=3,tickcolor='#c5cdd5')
        fig.update_yaxes(showline=False,ticks='',gridwidth=.6)
        # Explicit custom axis options always win over defaults.
        for name,axis in spec.axes.items():
            fig.layout['xaxis' if name=='x' else 'yaxis2' if name=='y2' else 'yaxis'].showgrid=axis.show_grid
        if spec.chart_type in {'auto','line','bar','stacked_bar','area','waterfall','heatmap'} and spec.presentation.bar_orientation!='horizontal':
            for name in list(fig.layout):
                if not name.startswith('xaxis'):continue
                number=int(name[5:] or 1)-1
                if panels and number>=len(series):
                    fig.layout[name].visible=False
                    fig.layout['yaxis'+name[5:]].visible=False
                    continue
                selected=series[number:number+1] if panels else series
                periods=sorted({p['date'] for s in selected for p in s['points']})
                if not periods or spec.axes.get('x') and spec.axes['x'].tick_step is not None:continue
                limit=max(3,8//max(1,columns)) if panels else 8
                indices=list(range(0,len(periods),max(1,math.ceil((len(periods)-1)/max(1,limit-1)))))
                if len(periods)-1 not in indices:indices.append(len(periods)-1)
                fig.layout[name].update(tickmode='array',tickvals=indices,ticktext=[date_label(periods[i],selected[0].get('frequency','')) for i in indices])
    if not spec.presentation.latest_values or spec.presentation.bar_orientation=='horizontal' or spec.chart_type not in {'auto','line','bar','area'}:
        return
    entries=[];groups={};stack_tops={};stack_totals={}
    if spec.presentation.bar_mode in {'stack','relative'}:
        for bar in fig.data:
            if bar.type!='bar' or not isinstance(bar.meta,dict):continue
            for date,value in zip(bar.x,bar.y):
                xref,yref=bar.xaxis or 'x',bar.yaxis or 'y'
                key=(xref,yref,str(date),value>=0)
                top=stack_totals.get(key,0)+value;stack_totals[key]=top
                stack_tops[(bar.meta.get('seriesLabel'),str(date),xref,yref)]=top
    for item in series:
        traces=[t for t in fig.data if isinstance(t.meta,dict) and t.meta.get('seriesLabel')==item['label'] and t.type in {'scatter','bar'}]
        if not traces or not item['points']:continue
        if spec.series_styles.get(item['label']) and spec.series_styles[item['label']].show_values:continue
        trace=traces[0];xref=trace.xaxis or 'x';yref=trace.yaxis or 'y'
        axis=fig.layout['yaxis'+yref[1:]]
        key=tuple(axis.domain or (0,1))
        values=[p['value'] for s in series for p in s['points'] if any(isinstance(t.meta,dict) and t.meta.get('seriesLabel')==s['label'] and (t.yaxis or 'y')==yref for t in fig.data if t.type in {'scatter','bar'})]
        lo,hi=min(values),max(values)
        stacked_values=[v for (label,date,x,y),v in stack_tops.items() if x==xref and y==yref]
        if stacked_values:lo,hi=min(lo,min(stacked_values)),max(hi,max(stacked_values))
        if any(t.type=='bar' and (t.yaxis or 'y')==yref for t in fig.data):lo,hi=min(lo,0),max(hi,0)
        last=item['points'][-1]
        plot_height=max(160,(fig.layout.height or 580)-(fig.layout.margin.t or 0)-(fig.layout.margin.b or 0))
        anchor=stack_tops.get((item['label'],last['date'],xref,yref),last['value'])
        position=(anchor-lo)/max(1e-12,hi-lo)*plot_height*(key[1]-key[0])
        entries.append((item,last,trace,xref,yref,key,anchor));groups.setdefault(key,[]).append((item['label'],position))
    offsets={key:spaced_offsets(values,max(19,spec.presentation.font_size+6)) for key,values in groups.items()}
    for item,last,trace,xref,yref,key,anchor in entries:
        axis=fig.layout['xaxis'+xref[1:]]
        periods=list(axis.categoryarray or sorted({p['date'] for p in item['points']}))
        if last['date'] not in periods:continue
        color=trace.line.color if trace.type=='scatter' else item['color']
        fig.add_annotation(name='statbridge-latest:'+item['label'],x=periods.index(last['date']),y=anchor,xref=xref,yref=yref,
            text=escape(f"{last['value']:,.{spec.presentation.number_decimals}f}"),showarrow=False,xanchor='left',yanchor='middle',xshift=8,
            yshift=offsets[key][item['label']],font=dict(size=spec.presentation.font_size,color=color),bgcolor=spec.presentation.background,
            hovertext=escape(item['label']+' · '+date_label(last['date'],item.get('frequency',''))+' · '+item.get('unit','')))
    fig.update_layout(margin=dict(r=max(fig.layout.margin.r or 0,95)))
