"""Deterministic, user-facing descriptions of validated chart edits."""
CHARTS={'auto':'자동 그래프','line':'선 그래프','bar':'막대 그래프','stacked_bar':'누적 막대 그래프','area':'영역 그래프','scatter':'산점도','bubble':'버블 그래프','pie':'원 그래프','donut':'도넛 그래프','histogram':'히스토그램','box':'상자 그림','heatmap':'히트맵','treemap':'트리맵','waterfall':'폭포 그래프'}
ENUMS={**CHARTS,'solid':'실선','dot':'점선','dash':'파선','longdash':'긴 파선','dashdot':'파선과 점선','circle':'원','square':'사각형','diamond':'마름모','cross':'십자','triangle-up':'위쪽 삼각형','triangle-down':'아래쪽 삼각형','linear':'직선','spline':'부드러운 곡선','hv':'가로 우선 계단선','vh':'세로 우선 계단선','hvh':'가로·세로 계단선','vhv':'세로·가로 계단선','top-left':'왼쪽 위','top-right':'오른쪽 위','bottom-left':'왼쪽 아래','bottom-right':'오른쪽 아래','top':'위쪽','bottom':'아래쪽','left':'왼쪽','right':'오른쪽','combined':'한 그래프에 함께','separate':'계열별로 나누어','horizontal':'가로 방향','vertical':'세로 방향','grid':'격자 배치','group':'나란히','stack':'누적','relative':'양수·음수를 나누어 누적','log':'로그 눈금','report':'경제보고서형','stability':'금융안정 분석형','outlook':'경제전망 분석형','slides':'발표자료형','academic':'논문·학술형','explore':'데이터 탐색형','snapshot':'스냅샷 보고서형'}
FIELDS={'tick_step':'눈금 간격','tick_angle':'눈금 글자 각도','color':'색상','dash':'선 모양','width':'선 두께','marker_size':'관측점 크기','marker_symbol':'관측점 모양','minimum':'축 최솟값','maximum':'축 최댓값','title':'축 제목','latest_values':'마지막 값 표시','font_size':'글자 크기','title_size':'제목 크기','font_family':'글꼴','font_color':'글자 색상','background':'배경 색상','grid_color':'격자 색상','legend_size':'범례 글자 크기','height':'그래프 높이','panel_columns':'패널 열 수','bar_mode':'막대 배치','bar_orientation':'막대 방향','bar_gap':'막대 간격','line_shape':'선 연결 방식','opacity':'불투명도','number_decimals':'수치 소수점 자리','color_scale':'색상 단계','decimals':'소수점 자리','scale':'축 눈금 방식','position':'위치','design_template':'디자인 테마','title_x':'제목 가로 위치','title_y':'제목 세로 위치','margin_left':'왼쪽 여백','margin_right':'오른쪽 여백','margin_top':'위쪽 여백','margin_bottom':'아래쪽 여백'}
BOOLS={'latest_values':'마지막 값 표시','markers':'관측점 표시','show_values':'수치 표시','show_grid':'격자 표시','zero_line':'0 기준선 표시','visible':'표시','reverse':'축 방향 반전','show_legend':'범례 표시','shared_y':'세로축 범위 통일','reverse_colors':'색상 순서 반전','show_colorbar':'색상 기준표 표시','arrow':'화살표 표시'}
NAMES={'set_axis_labels':'가로·세로축 이름','set_axis_style':'축 표시','set_presentation':'글꼴·배치','set_segment_style':'선택 구간 표시','set_point_style':'선택 관측점 표시','set_series_style':'데이터 표시','highlight_period':'기간 강조','filter_period':'표시 기간','rename_series':'데이터 표시 이름','highlight_series':'데이터 강조','reorder_series':'데이터 표시 순서','set_top_n':'표시할 데이터 수','set_secondary_axis':'보조 세로축','remove_secondary_axis':'보조 세로축','add_note':'설명 메모','update_note':'설명 메모','remove_note':'설명 메모','add_annotation':'주석','remove_annotation':'주석','add_guide':'기준선','update_guide':'기준선','remove_guide':'기준선','add_reference_line':'기준선','update_highlight':'강조 구간','remove_highlight':'강조 구간','clear_highlight':'기간 강조','add_shape':'강조 도형','update_shape':'강조 도형','remove_shape':'강조 도형','remove_range_style':'부분 표시 설정','clear_range_styles':'부분 표시 설정','set_transform':'수치 표시 방식','reset_styles':'그래프 표시 설정'}

def describe_edit(c):
    op=c.operation;p=c.params
    if op=='set_series_chart_types':
        return '지표별 차트 모양을 변경했습니다. ' + ' · '.join(f'{label}: {CHARTS.get(kind,kind)}' for label,kind in p.get('types',{}).items())
    label={'x':'가로축','y':'세로축','y2':'보조 세로축'}.get(c.label,c.label) if op=='set_axis_style' else c.label
    prefix=f'{label} · ' if label and not op.startswith(('remove_','update_')) else ''
    if c.start:prefix+=f'{c.start} ~ {c.end or c.start} · '
    if op=='set_table':
        names={'BOK-T01':'기본 3선형 통계표','BOK-T02':'다단 머리글 표','BOK-T03':'시계열 비교표','BOK-T04':'부록 대형 데이터표','BOK-T05':'항목 · 소계 강조표','BOK-T06':'주석 · 출처 결합표','default':'기본 화면형'}
        template=p.get('patch',{}).get('template')
        return (f'표 양식을 {names[template]}로 변경했습니다. ' if template in names else '표의 배치·표시 설정을 변경했습니다. ')+'조회 수치는 유지했습니다.'
    if op=='set_report':
        if p.get('clear'):return '일반 그래프 설정으로 돌아갔습니다.'
        from advanced_chart_spec import TEMPLATES
        name=TEMPLATES.get(p.get('patch',{}).get('template'),{}).get('name','보고서')
        return f'{name} 형식으로 변경했습니다. 조회 수치는 유지했습니다.'
    if op=='set_stickers':return f'이모티콘 {len(p.get("items",[]))}개의 위치·크기·회전을 적용했습니다.'
    if op in {'hide_series','show_series'}:return f'{c.value} 데이터를 '+('숨겼습니다.' if op=='hide_series' else '다시 표시했습니다.')
    if op in {'set_chart_type','set_series_chart_type'}:return prefix+f'{CHARTS.get(c.value,"선택한 그래프")} 형식으로 변경했습니다.'
    if op=='set_layout':return f'그래프를 {ENUMS.get(c.value,"선택한 배치")} 표시하도록 변경했습니다.'
    if op in {'set_title','set_subtitle'}:return f'{"제목" if op=="set_title" else "부제목"}을 “{c.value or ""}”로 변경했습니다.'
    parts=[]
    for k,v in p.items():
        if k in BOOLS and isinstance(v,bool):parts.append(f'{BOOLS[k]}를 '+('켰습니다.' if v else '껐습니다.'))
        elif k in FIELDS and isinstance(v,(str,int,float)) and not isinstance(v,bool):
            display=ENUMS.get(v,v) if isinstance(v,str) else v
            if k=='opacity':display=f'{float(v)*100:g}%'
            field='그래프 너비' if op=='set_presentation' and k=='width' else FIELDS[k]
            if k in {'color','font_color','background','grid_color'} and isinstance(v,str) and v.startswith('#'):display=f'선택한 색상 ({v})'
            parts.append(f'{field}: {display}.')
        elif k=='text' and isinstance(v,str):parts.append(f'내용: “{v}”.')
        elif k in {'x','y','ax','ay','x0','x1','y0','y1','data_anchor'} and not any('위치' in x for x in parts):parts.append('위치를 조정했습니다.')
    if not p and op in {'set_series_color','set_series_dash','set_line_width','set_legend'}:
        field={'set_series_color':'색상','set_series_dash':'선 모양','set_line_width':'선 두께','set_legend':'범례 위치'}[op]
        v=c.value
        if isinstance(v,bool):parts.append('범례를 '+('표시했습니다.' if v else '숨겼습니다.'))
        elif isinstance(v,(str,int,float)):parts.append(f'{field}: {ENUMS.get(v,v)}.')
    if op=='set_axis_labels':parts=[f'가로축 이름: {c.x_axis_label}.' if c.x_axis_label is not None else '',f'세로축 이름: {c.y_axis_label}.' if c.y_axis_label is not None else '']
    if parts:return prefix+' '.join(x for x in parts if x)
    name=NAMES.get(op,'그래프 설정')
    verb='지웠습니다.' if op.startswith(('remove_','clear_')) else '추가했습니다.' if op.startswith('add_') else '초기화했습니다.' if op=='reset_styles' else '변경했습니다.'
    return prefix+f'{name} 설정을 {verb}'
