"""Deterministic global display requests, independent of sketch selection."""
import re
from output_schema import ChartEditCommand


def selected_style(instruction,operation,mark=None):
    if '사용자가 고른 RGB 색상' not in instruction:return None
    tail=instruction.split('사용자가 고른 RGB 색상')[-1]
    choices={name:(color,float(opacity)) for name,color,opacity in re.findall(r'(화살표 기호|화살표 이후 차트|박스 강조|원 강조|강조 영역|차트)\s+(#[0-9a-fA-F]{6})\s+불투명도\s+([01](?:\.\d+)?)',tail)}
    target=('화살표 기호' if '화살표 기호' in choices else '화살표 이후 차트') if mark and mark.tool=='arrow' else '박스 강조' if mark and mark.tool=='rectangle' else '원 강조' if mark and mark.tool=='ellipse' else '강조 영역' if operation in {'highlight_period','update_highlight','add_shape','update_shape'} else '차트'
    chosen=choices.get(target)
    if not chosen and len(choices)==1 and target=='강조 영역':chosen=next(iter(choices.values()))
    if not chosen:return None
    color,opacity=chosen
    if not 0<=opacity<=1:raise ValueError('불투명도는 0부터 1 사이여야 합니다.')
    return {'color':color,'opacity':opacity}


def display_commands(instruction,spec,series):
    commands=[]
    if re.search(r'격자(?:무늬|\s*무늬)?.*(?:없애|없어|지워|지우|삭제|제거|투명)',instruction):
        for axis in ['x','y',*(['y2'] if spec.secondary_axis_series else [])]:
            commands.append(ChartEditCommand(operation='set_axis_style',kind='STYLE_EDIT',label=axis,params={'show_grid':False,'zero_line':False}))
    if re.search(r'(?:기간|날짜|눈금|시점).*(?:일관|일정|균일|규칙)',instruction):
        frequencies={s.get('frequency') for s in series}
        step=4 if frequencies=={'Q'} else 12 if frequencies=={'M'} else 1
        axis='y' if spec.chart_type in {'bar','stacked_bar'} and spec.presentation.bar_orientation=='horizontal' else 'x'
        commands.append(ChartEditCommand(operation='set_axis_style',kind='STYLE_EDIT',label=axis,params={'tick_step':step}))
    return commands


def arrow_note(instruction,mark):
    clause=re.search(r"화살표(?:(?!박스|사각형|격자).)*",instruction)
    if not clause or not re.search(r"그려|넣|추가",clause.group()) or re.search(r"차트|그래프|선 색|선의",clause.group()):return None
    choice=selected_style(instruction,'add_note',mark) or {}
    first,last=mark.points[0],mark.points[-1]
    color=choice.get('color') or re.search(r'#[0-9a-fA-F]{6}',instruction)
    if not isinstance(color,str):color=color.group() if color else '#ef4444'
    return ChartEditCommand(operation='add_note',kind='STYLE_EDIT',params={'text':'\u2009','label':mark.selection.label if mark.selection else None,'period':mark.selection.end or mark.selection.start if mark.selection else None,'x':last.x,'y':1-last.y,'arrow':True,'ax':max(-400,min(400,(first.x-last.x)*700)),'ay':max(-400,min(400,(first.y-last.y)*580)),'arrow_width':5,'arrow_size':2,'color':color,'opacity':choice.get('opacity',1)})


def symbol_note(instruction):
    symbol=next((s for s in ['→','↗','↘','↔','★','●','■','▲','✓','!','♥','◆'] if s in instruction),None)
    if not symbol or not re.search(r'기호|이모티콘',instruction) or not re.search(r'넣|추가',instruction):return None
    choice=selected_style(instruction,'add_note') or {}
    color=choice.get('color') or '#206b76'
    x=.15 if '왼쪽' in instruction else .85 if '오른쪽' in instruction and symbol not in ['→','↔'] else .5
    y=.85 if '위쪽' in instruction or '상단' in instruction else .15 if '아래쪽' in instruction or '하단' in instruction else .5
    return ChartEditCommand(operation='add_note',kind='STYLE_EDIT',params={'text':symbol,'x':x,'y':y,'font_size':30 if '크게' in instruction else 22,'color':color,'opacity':choice.get('opacity',1)})
