"""Unambiguous one-observation expansion of the current highlighted region."""
import re
from output_schema import ChartEditCommand


def expand_highlight(instruction,spec,series,history=()):
    if not re.search(r"(?:현재|기존).*강조.*한\s*칸.*앞",instruction):return None
    if re.search(r"제목|격자|범례|두께|삭제|뒤로",instruction):return None
    regions=[('highlight',h) for h in spec.highlights]+[('shape',s) for s in spec.paper_shapes if s.type in {'rect','circle'} and s.fill]
    for edit in reversed(history):
        operation=edit.get('operation')
        candidates=[]
        if operation in {'update_shape','update_highlight'}:
            candidates=[r for r in regions if r[1].id==edit.get('value')]
        elif operation=='add_shape' and spec.paper_shapes:
            candidates=[r for r in regions if r[0]=='shape' and r[1].id==spec.paper_shapes[-1].id]
        elif operation=='highlight_period':
            candidates=[r for r in regions if r[0]=='highlight' and r[1].start==edit.get('start') and r[1].end==edit.get('end')]
        if len(candidates)==1:
            regions=candidates;break
    if len(regions)!=1:
        raise ValueError('넓힐 강조 영역을 하나로 지정해 주세요. 기존 그래프는 유지됩니다.')
    kind,region=regions[0]
    periods=sorted({p['date'] for s in series for p in s['points']})
    colors=re.findall(r'#[0-9a-fA-F]{6}',instruction)
    color=colors[-1] if colors else None
    from chart_edit_intents import selected_style
    selected=selected_style(instruction,'update_shape' if kind=='shape' else 'update_highlight')
    if kind=='highlight':
        index=periods.index(region.start)
        if index==0:raise ValueError('강조 영역이 이미 첫 관측 시점부터 시작합니다.')
        params={'start':periods[index-1]}
        if color:params['color']=color
        if selected:params.update(selected)
        return ChartEditCommand(operation='update_highlight',kind='STYLE_EDIT',value=region.id,params=params)
    if region.data_anchor:
        anchor=region.data_anchor.model_dump()
        source=next(s for s in series if s['label']==anchor['label'])
        dates=[p['date'] for p in source['points']]
        index=dates.index(anchor['start'])
        if index==0:raise ValueError('강조 영역이 이미 첫 관측 시점부터 시작합니다.')
        anchor['start']=dates[index-1]
        params={'data_anchor':anchor}
    else:
        if region.x0==0:raise ValueError('강조 영역이 이미 그래프의 왼쪽 끝부터 시작합니다.')
        params={'x0':max(0,region.x0-1/max(1,len(periods)-1))}
    if color:params.update(fill=color,color=color)
    if selected:params.update(selected,fill=selected['color'])
    return ChartEditCommand(operation='update_shape',kind='STYLE_EDIT',value=region.id,params=params)
