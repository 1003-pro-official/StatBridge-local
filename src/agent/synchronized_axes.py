"""One common linear scale from displayed observations or an explicit range."""
import math
from chart_availability import comparable_axis_units

def synchronized_scale(series,spec):
    right_labels=spec.secondary_axis_series or (spec.report.right_axis if spec.report and spec.report.kind=="dual_axis" else [])
    if not spec.presentation.sync_y_axes or not right_labels:return None
    if len(comparable_axis_units(series))!=1:raise ValueError('좌우 축 동기화는 단위가 같은 지표에서만 사용할 수 있습니다.')
    left=spec.axes.get('y');right=spec.axes.get('y2')
    if any(a and a.scale!='linear' for a in [left,right]):raise ValueError('좌우 축 동기화는 선형 눈금에서 사용해 주세요.')
    axis=left if left and left.minimum is not None else right if right and right.minimum is not None else None
    values=[p['value'] for s in series for p in s['points']]
    bars=[s for s in series if spec.series_chart_types.get(s['label'],spec.chart_type) in {'bar','stacked_bar'}]
    if bars:values.append(0)
    if spec.chart_type=='stacked_bar' or spec.presentation.bar_mode in {'stack','relative'}:
        totals={}
        for s in bars:
            for p in s['points']:
                k=(s['label'] in right_labels,p['date'],p['value']>=0)
                totals[k]=totals.get(k,0)+p['value']
        values.extend(totals.values())
    lo,hi=(axis.minimum,axis.maximum) if axis else (min(values),max(values))
    span=hi-lo or max(abs(hi)*.2,1)
    raw=span/5;power=10**math.floor(math.log10(raw));step=next(v*power for v in [1,2,2.5,5,10] if v*power>=raw)
    if not axis:lo=math.floor(lo/step)*step;hi=math.ceil(hi/step)*step
    if lo==hi:hi=lo+step
    return [lo,hi],(axis.tick_step if axis and axis.tick_step else left.tick_step if left and left.tick_step else step),bool(left and left.reverse)
