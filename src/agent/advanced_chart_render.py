"""Deterministic report renderers; the three engines consume the same observations."""
from __future__ import annotations

import copy
from html import escape
import math
import numpy as np
import plotly.graph_objects as go
from advanced_chart_spec import PALETTE, validate_report
from research_plotly_styles import rgba


def period_text(period,frequency,format='period'):
    if format=='year':return period[:4]
    if len(period)==6 and period.isdigit():
        if frequency=='Q' and 1<=int(period[-2:])<=4:return f'{period[:4]}Q{int(period[-2:])}'
        if frequency=='M':return period[:4]+'-'+period[-2:]
    return period


def report_warnings(series,spec):
    warnings=[]
    right=spec.report.right_axis if spec.report else spec.secondary_axis_series
    kind=spec.report.kind if spec.report else spec.chart_type
    for key in ['y','y2']:
        axis=spec.axes.get(key)
        if axis and axis.minimum is not None:
            affected=[s for s in series if (s['label'] in right)==(key=='y2')]
            clipped=sum(p['value']<axis.minimum or p['value']>axis.maximum for s in affected for p in s['points'])
            if clipped:warnings.append(f'{key}축 사용자 범위 밖에 관측값 {clipped}개가 있습니다. 원자료는 유지되지만 그래프에서는 잘립니다.')
            if axis.minimum>0 and (kind in {'contribution','waterfall','bar','stacked_bar'} or kind=='dual_axis' and key=='y2'):
                warnings.append('막대 축의 0 기준이 잘려 크기 비교가 과장될 수 있습니다.')
    if kind=='dual_axis' or right:warnings.append('왼쪽과 오른쪽 축은 독립된 단위·범위입니다. 선의 높이와 막대 높이를 직접 비교하지 마세요.')
    if kind=='regression':warnings.append('OLS는 제공된 동일 시점 관측값의 선형 관계 요약이며 인과관계 검증이 아닙니다.')
    return warnings


def aligned(series):
    lookups=[{p['date']:p['value'] for p in s['points']} for s in series]
    periods=sorted(set.intersection(*(set(values) for values in lookups)))
    return periods, [[values[d] for d in periods] for values in lookups]


def regression(series):
    periods,values=aligned(series)
    x,y=map(np.asarray,values)
    if len(x)<3 or len(set(x))<2: raise ValueError('회귀에는 같은 시점의 관측 쌍 3개 이상과 서로 다른 X 값이 필요합니다.')
    slope,intercept=np.linalg.lstsq(np.column_stack((x,np.ones(len(x)))),y,rcond=None)[0]
    fitted=slope*x+intercept
    total=float(np.sum((y-y.mean())**2))
    return {'method':'OLS with intercept','n':len(x),'slope':float(slope),'intercept':float(intercept),
            'r_squared':None if total==0 else float(1-np.sum((y-fitted)**2)/total),
            'x':[float(x.min()),float(x.max())],'y':[float(slope*x.min()+intercept),float(slope*x.max()+intercept)]}


def report_style(spec):
    kind=spec.report.kind
    kinds={'forecast':'line','dual_axis':'line','contribution':'stacked_bar','panels':'line','events':'line',
        'fan':'line','waterfall':'waterfall','regression':'scatter','heatmap':'heatmap','violin':'box',
        'stacked_area':'area','scenario':'line','bubble':'bubble'}
    presentation=spec.presentation.model_copy(update={'background':'#ffffff',
        'margin_top':spec.presentation.margin_top if spec.presentation.design_template else 100,'margin_bottom':min(240,(spec.presentation.margin_bottom if spec.presentation.design_template else 100)+len(spec.report.footnotes)*16),
        'height':spec.report.height,'width':None,'panel_columns':spec.report.columns,'bar_mode':'relative' if kind=='contribution' else 'group'})
    return spec.model_copy(update={'chart_type':kinds[kind], 'presentation':presentation,
        'layout':'grid' if kind=='panels' else 'combined',
        'secondary_axis_series':spec.report.right_axis if kind=='dual_axis' else [],
        'series_chart_types':{s:'bar' for s in spec.report.right_axis} if kind=='dual_axis' else {},
        'series_colors':spec.series_colors,'legend_position':spec.legend_position})


def source_caption(result, options):
    plans=result.get('api_plans') or ([result['api_plan']] if result.get('api_plan') else [])
    ids=list(dict.fromkeys(str(p['table_id']) for p in plans))
    origins=list(dict.fromkeys(str(s.get('source') or '출처 확인 필요') for s in (result.get('execution') or {}).get('sources',[])))
    caption='자료: '+(' / '.join(origins) or '제공된 데이터')+(' · '+', '.join(ids) if ids else '')
    return caption + (' | 사용자 표기: '+options.source_note if options.source_note else '')


def plotly_report(series, spec, result):
    from plotly_renderer import render_plotly
    options=spec.report
    periods=validate_report(series,options)
    base=report_style(spec)
    colored=[{**s,'color':spec.series_colors.get(s['label'],s.get('color') or PALETTE[i%len(PALETTE)])} for i,s in enumerate(series)]
    if options.kind=='violin':
        fig=go.Figure(render_plotly(colored,base))
        fig.data=()
        for s in colored: fig.add_trace(go.Violin(y=[p['value'] for p in s['points']],name=spec.display_names.get(s['label'],s['label']),box_visible=True,meanline_visible=True,line_color=s['color'],points=False))
    else:
        fig=go.Figure(render_plotly(colored,base))
    if options.kind not in {'regression','bubble','violin'}:
        for i,s in enumerate(series if options.kind=='panels' else series[:1]):
            dates=[p['date'] for p in s['points']] if options.kind=='panels' else periods
            step=max(1,math.ceil(len(dates)/8));ticks=dates[::step]
            if dates[-1] not in ticks:ticks.append(dates[-1])
            axis='xaxis' if i==0 else f'xaxis{i+1}'
            # Numeric period strings are ambiguous to Plotly.js category ticks.
            # Axis tick positions are ordinal indexes; observation x values stay raw.
            fig.update_layout({axis:{'tickmode':'array','tickvals':[dates.index(d) for d in ticks],'ticktext':[period_text(d,s.get('frequency'),options.date_format) for d in ticks]}})
    if options.kind=='stacked_area':
        # Use one trace per complete series, rather than individual line segments.
        fig.data=()
        for s in colored: fig.add_trace(go.Scatter(x=[p['date'] for p in s['points']],y=[p['value'] for p in s['points']],name=spec.display_names.get(s['label'],s['label']),stackgroup='composition',mode='lines',line={'color':s['color']}))
    if options.kind=='regression':
        fit=regression(series)
        fig.add_trace(go.Scatter(x=fit['x'],y=fit['y'],mode='lines',name=f"OLS (n={fit['n']})",line={'color':'#555555','dash':'dash'}))
    if options.intervals:
        for band in sorted(options.intervals,key=lambda b:-b.level):
            color=colored[next(i for i,s in enumerate(series) if s['label']==band.label)]['color']
            fig.add_trace(go.Scatter(x=band.periods,y=band.lower,mode='lines',line={'width':0},showlegend=False,hoverinfo='skip'))
            fig.add_trace(go.Scatter(x=band.periods,y=band.upper,mode='lines',line={'width':0},fill='tonexty',fillcolor=rgba(color,.15),name=f'{band.label} {band.level:.0%} ({band.method})'))
        # Bands behind the center lines. Preserve paired lower/upper ordering.
        n=len(options.intervals)*2
        fig.data=fig.data[-n:]+fig.data[:-n]
    if options.forecast_start:
        # Explicit user-marked display region; no prediction values are fabricated.
        start=periods.index(options.forecast_start)-.5
        fig.add_shape(type='rect',xref='x',yref='paper',x0=start,x1=len(periods)-.5,y0=0,y1=1,fillcolor='#dde4ec',opacity=.35,line_width=0,layer='below')
        fig.add_annotation(x=options.forecast_start,y=1,xref='x',yref='paper',text=escape(options.forecast_description),showarrow=False,yshift=12,font={'size':11,'color':'#6b7280'})
    for event in options.events:
        fig.add_shape(type='line',xref='x',yref='paper',x0=event.period,x1=event.period,y0=0,y1=1,line={'color':'#777777','dash':'dot','width':1})
        fig.add_annotation(x=event.period,y=1,xref='x',yref='paper',text=escape(event.text),showarrow=False,yshift=28,font={'size':11})
    footer=[source_caption(result,options),*options.footnotes]
    if options.intervals: footer.extend(f'{b.level:.0%} 구간: {b.method}; {b.source}' for b in options.intervals)
    fig.add_annotation(x=0,y=0,xref='paper',yref='paper',xanchor='left',yanchor='top',yshift=-64,
        text='<br>'.join(escape(t) for t in footer),showarrow=False,align='left',font={'size':10,'color':'#4b5563'})
    if options.kind not in {'regression','bubble','violin'}:
        # Plotly.js can match numeric category strings to the first tick even
        # when Python serializes distinct ticktext. Non-numeric rendering keys
        # remove that ambiguity; document/data periods remain unchanged.
        for axis_name in list(fig.layout):
            if not axis_name.startswith('xaxis'):continue
            axis=fig.layout[axis_name]
            categories=list(axis.categoryarray or periods)
            keys={d:'period:'+str(d) for d in categories}
            axis.categoryarray=[keys[d] for d in categories]
            if axis.tickvals is not None:
                axis.tickvals=[keys[categories[int(v)]] if isinstance(v,(int,float)) else keys.get(v,v) for v in axis.tickvals]
            ref='x'+axis_name[5:]
            for trace in fig.data:
                if (trace.xaxis or 'x')==ref and trace.x is not None:
                    original=list(trace.x)
                    if trace.type=='heatmap':
                        trace.customdata=[original for _ in trace.y]
                        trace.hovertemplate=(trace.hovertemplate or '').replace('%{x}','%{customdata}')
                    elif trace.customdata is None and trace.hoverinfo!='skip':
                        trace.customdata=[[trace.name,v] for v in original]
                        trace.hovertemplate='시점: %{customdata[1]}<br>값: %{y}<extra>%{fullData.name}</extra>'
                    trace.x=[keys.get(v,v) for v in original]
            for shape in fig.layout.shapes or ():
                if shape.xref==ref:shape.x0=keys.get(shape.x0,shape.x0);shape.x1=keys.get(shape.x1,shape.x1)
            for annotation in fig.layout.annotations or ():
                if annotation.xref==ref:annotation.x=keys.get(annotation.x,annotation.x)
    from plotly.io import to_json
    import json
    return json.loads(to_json(fig))


def echarts_report(series,spec,result):
    o=spec.report;periods=validate_report(series,o)
    period_index={d:i for i,d in enumerate(periods)}
    # ECharts lacks native violin traces and saved image/paper decorations here.
    if o.kind=='violin' or spec.stickers or spec.paper_shapes or spec.notes or spec.range_styles or spec.guides or spec.highlights or spec.annotations or spec.reference_lines:
        raise ValueError('ECharts 미리보기는 바이올린·저장 이미지·도형·위치 주석·구간별 스타일을 지원하지 않습니다. Plotly와 인쇄 출력은 별도로 확인하세요.')
    panels=o.kind=='panels';count=len(series) if panels else 1
    grids=[];xs=[];ys=[]
    for i in range(count):
        row,col=divmod(i,o.columns if panels else 1)
        columns=min(o.columns,count) if panels else 1
        rows=math.ceil(count/columns)
        grids.append({'left':f'{8+col*90/columns}%','top':f'{20+row*62/rows}%','width':f'{78/columns}%','height':f'{48/rows}%','containLabel':True})
        xs.append({'type':'category','data':[p['date'] for p in series[i]['points']] if panels else periods,'gridIndex':i,'axisLabel':{'hideOverlap':True}})
        ys.append({'type':'value','gridIndex':i,'name':series[i]['unit'] if panels else series[0]['unit'],'splitLine':{'lineStyle':{'color':'#e3e7ed'}}})
    for i,axis in enumerate(xs):
        axis['reportPeriodLabels']={d:period_text(d,series[i if panels else 0].get('frequency'),o.date_format) for d in axis.get('data',[])}
    for name,axes in [('x',xs),('y',ys)]:
        style=spec.axes.get(name)
        if style:
            for axis in axes:
                axis['splitLine']={'show':style.show_grid,'lineStyle':{'color':spec.presentation.grid_color}}
                axis['inverse']=style.reverse
                if style.minimum is not None:axis.update(min=style.minimum,max=style.maximum)
                if name=='y' and style.scale=='log':axis['type']='log'
    if o.kind=='dual_axis':
        ys[0]['name']=next(s['unit'] for s in series if s['label'] not in o.right_axis)
        ys.append({'type':'value','gridIndex':0,'position':'right','name':next(s['unit'] for s in series if s['label'] in o.right_axis),'splitLine':{'show':False}})
    traces=[]
    for i,s in enumerate(series):
        x=[p['date'] for p in s['points']];values={p['date']:p['value'] for p in s['points']}
        data=[values.get(d) for d in (x if panels else periods)]
        trace={'name':spec.display_names.get(s['label'],s['label']),'type':'bar' if o.kind=='contribution' or s['label'] in o.right_axis else 'line',
            'data':data,'xAxisIndex':i if panels else 0,'yAxisIndex':i if panels else int(s['label'] in o.right_axis),
            'itemStyle':{'color':spec.series_colors.get(s['label'],s.get('color') or PALETTE[i%len(PALETTE)])},'connectNulls':False}
        if o.kind in {'contribution','stacked_area'}: trace['stack']='sum'
        if o.kind=='stacked_area': trace['areaStyle']={}
        style=spec.series_styles.get(s['label'])
        trace['lineStyle']={'width':style.width if style and style.width else spec.line_width,'type':spec.series_dashes.get(s['label'],style.dash if style and style.dash else 'solid')}
        trace['showSymbol']=bool(style and style.markers)
        if style and style.opacity is not None:trace['itemStyle']['opacity']=style.opacity
        if style and style.color:trace['itemStyle']['color']=style.color
        traces.append(trace)
    if o.kind in {'regression','bubble'}:
        dates,values=aligned(series)
        if o.kind=='bubble' and (min(values[2])<0 or max(values[2])<=0): raise ValueError('버블 크기는 0 이상이며 양수가 하나 이상 있어야 합니다.')
        xs=[{'type':'value','name':series[0]['unit']}];ys=[{'type':'value','name':series[1]['unit']}]
        traces=[{'type':'scatter','name':'동일 시점 관계','data':list(map(list,zip(*values))),'symbolSize':8,'reportCustom':'bubble' if o.kind=='bubble' else None}]
        if o.kind=='regression':
            fit=regression(series);traces.append({'type':'line','name':f"OLS n={fit['n']}",'data':list(map(list,zip(fit['x'],fit['y']))),'showSymbol':False,'lineStyle':{'type':'dashed'}})
    if o.kind=='heatmap':
        ys=[{'type':'category','data':[s['label'] for s in series]}]
        traces=[{'type':'heatmap','data':[[j,i,p['value']] for i,s in enumerate(series) for p in s['points'] for j,d in enumerate(periods) if d==p['date']]}]
    if o.kind=='waterfall':
        if len(series)!=1: raise ValueError('워터폴은 하나의 관측 계열이 필요합니다.')
        vals=[p['value'] for p in series[0]['points']];previous=[0,*vals[:-1]]
        traces=[{'type':'custom','reportCustom':'waterfall','name':series[0]['label'],
            'encode':{'x':0,'y':[1,2]},
            'data':[[i,min(a,b),max(a,b),b-a,b] for i,(a,b) in enumerate(zip(previous,vals))]}]
    for band in o.intervals:
        cells=[[period_index[d],lo,hi,period_index[d2],lo2,hi2] for d,lo,hi,d2,lo2,hi2 in zip(band.periods,band.lower,band.upper,band.periods[1:],band.lower[1:],band.upper[1:])]
        traces.insert(0,{'type':'custom','reportCustom':'band','name':f'{band.label} {band.level:.0%}','encode':{'x':[0,3],'y':[1,2,4,5]},'data':cells,'itemStyle':{'color':'rgba(34,85,164,.15)'}})
    if o.forecast_start and traces:
        traces[-1]['markArea']={'silent':True,'itemStyle':{'color':'rgba(160,170,180,.15)'},'data':[[{'xAxis':o.forecast_start,'name':o.forecast_description},{'xAxis':periods[-1]}]]}
    if o.events and traces: traces[-1]['markLine']={'symbol':['none','none'],'data':[{'xAxis':e.period,'name':e.text,'label':{'formatter':e.text}} for e in o.events]}
    footer=[source_caption(result,o),*o.footnotes,*[f'{b.level:.0%}: {b.method}; {b.source}' for b in o.intervals]]
    option={'backgroundColor':'#ffffff','animation':False,'title':[{'text':spec.title,'subtext':spec.subtitle,'left':'center','top':12},
        {'text':'\n'.join(footer),'textStyle':{'fontSize':10,'fontWeight':'normal'},'left':10,'bottom':5}],
        'textStyle':{'fontFamily':'Malgun Gothic, Noto Sans CJK KR, sans-serif'},'tooltip':{'trigger':'item'},'legend':{'top':75,'type':'scroll'},'grid':grids,'xAxis':xs,'yAxis':ys,'series':traces}
    option['legend']['show']=spec.show_legend
    if spec.legend_position=='bottom':option['legend'].update(top='auto',bottom=60)
    option['textStyle']['fontSize']=spec.presentation.font_size
    if o.kind=='heatmap':
        values=[p['value'] for s in series for p in s['points']]
        option['visualMap']={'min':min(values),'max':max(values),'calculable':True,'orient':'horizontal','bottom':45,'left':'center'}
    return option
