"""The reference describes appearance, never replacement statistical evidence."""
import re
REFERENCE_STYLE_POLICY='''스냅샷과 같은 경제 통계 그래프는 set_presentation design_template=snapshot을 기반으로 지원되는 형식을 적용할 수 있다. 범례는 현재 실제 지표 이름이며 latest_values=true는 현재 조회값의 마지막 관측값만 표시한다. 선+막대 복합 그림은 존재하는 실제 계열에만 종류/좌우축을 연결한다. 없는 금리차·증가율 계열을 계산하거나 만들어 맞추지 않는다. 참고 파일이 있고 사용자가 '이렇게 그려줘', '이 그림처럼'이라고 하면 그래프 전체의 시각적 형식 적용을 명시적으로 위임한 요청이다. 어떤 요소를 골라 달라는 일반적인 역질문을 반복하지 마라. 현재 데이터로 지원되는 차트 종류, 선/막대, 계열 순서별 색상, 점 표시, 선 두께, 범례 위치, 흰 배경, 격자와 배치를 분석해 적용한다. 이미지의 제목, 지표 이름, 시점, 단위, 수치, 축 범위, 출처, 전망구간, 장기평균/기준선 수치를 현재 데이터로 복사하지 않는다. 현재 chartState의 제목·부제·축 이름·실제 seriesLabels를 유지한다. axis minimum/maximum은 그대로 두고 자동 범위를 사용한다. reference에 패널이 있으면 현재 계열을 패널로 나누는 set_layout value=horizontal/grid/separate와 set_presentation panel_columns를 사용할 수 있다. 참고의 패널별 곡선 수를 맞추려고 데이터 계열을 복제하거나 만들지 않는다. 누적 막대는 값의 단위와 의미가 합산에 적합한 현재 데이터에서만 사용한다. 자료 차원, 지원 종류 또는 판독 정보가 부족해 요청 자체를 충족할 수 없을 때만 부족한 조건 하나를 명시해 clarification을 반환한다. set_series_style은 color,width,markers,dash를 params에 함께 넣어 명령 수를 줄인다. 모든 명령의 params는 객체이며 불필요하면 {}이다. null이나 문자열로 반환하지 않는다. 검토 단계에서도 이 전체 형식 위임은 sources text에 연결된 실제 요청이다. 구조 오류와 임의의 숫자 추가를 확인하되 일반적인 요소 선택 질문으로 되돌리지 않는다.'''

def generic_reference_style(instruction):
    text=re.sub(r'\s+','',instruction).rstrip('.!?。')
    return bool(re.fullmatch(r'(?:이렇게|이(?:그림|그래프|이미지)(?:처럼|같이)|(?:첨부한?|참고)(?:파일|그림|그래프|이미지)(?:처럼|같이))(?:그려|만들어|바꿔|변경해)(?:줘|주세요)?',text))

def validate_reference_style(commands,instruction,current):
    if not generic_reference_style(instruction):return
    state=current.get('chartState') or {}
    names={'set_title':'title','set_subtitle':'subtitle','rename_series':'display_names'}
    for command in commands:
        if command.kind=='DATA_EDIT':raise ValueError('참고 그래프의 형식 적용 중 조회 수치·기간·데이터를 변경하려는 명령을 제외해야 합니다. 기존 그래프를 유지했습니다.')
        if command.operation in names:
            old=(state.get('display_names') or {}).get(command.label,command.label) if command.operation=='rename_series' else state.get(names[command.operation])
            if command.value!=old:raise ValueError('참고 이미지의 제목·지표 이름을 현재 통계에 복사하지 않습니다. 현재 이름을 유지해 형식을 다시 적용해 주세요.')
        if command.operation=='set_axis_labels' and any(value is not None and value!=state.get(key) for key,value in [('x_axis_label',command.x_axis_label),('y_axis_label',command.y_axis_label)]):
            raise ValueError('참고 이미지의 축 단위를 현재 통계에 복사하지 않습니다. 현재 축 이름을 유지해 주세요.')
        if command.operation in {'add_guide','add_reference_line','add_annotation','add_note'}:
            raise ValueError('참고 이미지의 기준값·주석을 현재 데이터의 근거로 추가하지 않습니다. 현재 자료에 적용할 값을 별도로 지정해 주세요.')
        if command.operation=='set_axis_style' and any(key in command.params for key in ('minimum','maximum')):
            raise ValueError('참고 이미지의 수치 범위를 복사하지 않습니다. 현재 데이터의 자동 축 범위를 유지해 주세요.')
        if command.operation=='set_report':
            patch=command.params.get('patch') or {}
            if any(patch.get(key) for key in ('forecast_start','intervals','events','source_note','footnotes')):
                raise ValueError('참고 이미지의 전망·기준값·출처를 현재 통계의 근거로 추가하지 않습니다. 시각적 형식만 적용해 주세요.')

REFERENCE_STRUCTURE_POLICY='''series_types와 secondary_axis_indices의 길이와 순서는 반드시 이미지의 실제 범례/곡선을 기준으로 읽는다. 현재 계열이 4개이고 이미지가 선 1개와 막대 1개면 series_types는 2개여야 한다. 현재 계열 수에 맞춰 이미지의 선/막대를 복제하거나 배열을 늘리지 않는다. 선·막대가 함께 있거나 좌우 축이 있는 참고에는 reference_style 안에 series_types:[그림의 범례 순서대로 line/bar/area], secondary_axis_indices:[실제 오른쪽 축에 연결된 계열의 0부터 시작하는 순서]도 반드시 반환한다. 여러 색의 선이 같은 축에 있는 경우 두 필드를 생략할 수 있다. 오른쪽 단위가 왼쪽과 다르고 막대가 해당 축에 연결된 그림이면 그 막대 순서를 secondary_axis_indices에 넣는다. 현재 데이터의 단위가 같더라도 그림의 실제 좌우축 구조 판독을 생략하지 않는다. 이 필드는 참고 수치나 단위를 복사하지 않고 현재 지표의 같은 순서에 형식만 연결하기 위한 구조다. 참고 파일 응답에는 commands와 함께 reference_style={chart_type:line/bar/stacked_bar/area/scatter/bubble/pie/donut/histogram/box/heatmap/treemap/waterfall, panel_count:양의 정수, columns:1~4}를 반드시 반환한다. 이 필드는 추론 과정이 아니라 그림에서 직접 확인한 시각 구조이다. 여러 색의 선이 같은 시간축에 겹쳐 있는 그림은 panel_count=1이다. 별도의 작은 그래프 또는 세로 구분선으로 나뉘어 시간축이 반복되는 비교 영역은 각각 한 패널로 세어라. 예를 들어 세 영역에 각각 같은 연도가 반복되면 panel_count=3,columns=3이다. 패널 수를 현재 데이터 계열 수로 추측하지 말고 참고 파일에서 읽어라. 현재 계열 수와 영역 수가 맞으면 각 실제 계열을 한 패널에 표시하고 해당 set_layout을 포함한다. 이 경우 현재 seriesLabels 순서대로 한 계열씩 배치하는 기준이 이미 정해졌으므로 패널 분류나 그룹 지정 clarification을 요청하지 않는다. 검토 단계에서도 후보의 이 배치를 유지한다. 현재 계열 수가 다르고 원본의 그룹별 여러 곡선을 복제해야 하는 경우 필요한 그룹 구분을 구체적으로 질문한다. 빈 value, start, end, label 등의 불필요한 필드는 생략하거나 JSON null로 반환한다.'''


def compact_reference_settings(commands):
    """Combine repeated patches within one delegated appearance request only."""
    result=[];slots={}
    for raw in commands:
        command=dict(raw);op=command.get('operation');params=command.get('params')
        if op in {'set_presentation','set_axis_style','set_series_style'} and isinstance(params,dict):
            key=(op,command.get('label'))
            # Multiple theme applications can have independent side effects.
            if params.get('design_template'):slots.pop(key,None)
            if key in slots:
                result[slots[key]]['params']={**result[slots[key]]['params'],**params}
                continue
            slots[key]=len(result)
        else:
            # Non-patch operations may alter the meaning of later settings.
            slots={}
        result.append(command)
    return result

def bind_reference_structure(proposal,context):
    """Bind observed geometry to supported operations; never synthesize series."""
    from pydantic import BaseModel,ConfigDict,Field,StrictInt
    from chart_availability import CHART_TYPES
    class Appearance(BaseModel):
        model_config=ConfigDict(extra='forbid')
        chart_type:str
        panel_count:int=Field(ge=1,le=50)
        columns:int=Field(ge=1,le=4)
        series_types:list[str]=Field(default_factory=list,max_length=50)
        secondary_axis_indices:list[StrictInt]=Field(default_factory=list,max_length=20)
    if proposal.get('clarification'):return proposal
    try:
        appearance=Appearance.model_validate(proposal.get('reference_style'))
    except ValueError as error:
        raise ValueError('참고 그래프의 종류·분할 구조를 판독하지 못했습니다. 더 선명한 파일 또는 원하는 그래프 종류를 알려 주세요.') from error
    if appearance.chart_type not in CHART_TYPES:raise ValueError('참고 그림의 종류를 현재 통계 데이터로 표현할 수 없습니다. 지원되는 그래프 형식을 지정해 주세요.')
    count=len(context.get('seriesLabels') or [])
    if any(t not in {'line','bar','area'} for t in appearance.series_types):raise ValueError('참고 그림의 복합 계열 종류를 지원하지 않습니다.')
    mixed=len(set(appearance.series_types))>1 or bool(appearance.secondary_axis_indices)
    if mixed and len(appearance.series_types)!=count:
        raise ValueError(f'참고 복합 그래프는 {len(appearance.series_types)}개 계열이며 현재는 {count}개입니다. 각 선·막대와 좌우 축에 연결할 현재 지표를 지정해 주세요.')
    if any(type(i) is not int or not 0<=i<count for i in appearance.secondary_axis_indices):raise ValueError('참고 그림의 보조축 계열 위치를 확인하지 못했습니다.')
    if appearance.secondary_axis_indices and len(set(appearance.secondary_axis_indices))>=count:
        raise ValueError("참고 이미지의 좌우 축 연결을 확인해 주세요. 왼쪽 축에도 계열이 필요합니다.")
    if mixed and appearance.panel_count!=1:raise ValueError('복합축의 여러 패널은 현재 지표별 축 연결을 먼저 지정해 주세요.')
    if appearance.panel_count>1 and appearance.panel_count!=count:
        raise ValueError(f'참고 그림은 {appearance.panel_count}개 비교 영역이며 현재 데이터는 {count}개 계열입니다. 각 영역에 넣을 지표의 그룹을 지정해 주세요. 데이터는 복제하지 않습니다.')
    commands=[]
    raw_commands=proposal.get('commands') or []
    if len(raw_commands)>36:raise ValueError('참고 형식의 설정이 너무 많습니다. 설정을 나누어 주세요.')
    for raw in compact_reference_settings(raw_commands):
        command=dict(raw)
        if isinstance(command.get('params'),dict):
            params=dict(command['params'])
            if command.get('operation')=='set_presentation':params.pop('number_decimals',None)
            if command.get('operation')=='set_axis_style':
                params.pop('decimals',None);params.pop('tick_step',None)
            command['params']=params
        commands.append(command)
    # Appearance is model-observed metadata, not a benchmark answer. Bind it
    # after theme commands so a theme cannot silently flatten its subplots.
    commands=[c for c in commands if c.get('operation') not in {'set_layout','set_chart_type'}]
    if mixed:
        commands=[c for c in commands if c.get('operation') not in {'set_series_chart_type','set_secondary_axis'}]
        base='line' if 'line' in appearance.series_types else 'bar'
        appearance.chart_type=base
        labels=context.get('seriesLabels') or []
        mapping=(context.get('chartState') or {}).get('series_chart_types') or {}
        for label,kind in zip(labels,appearance.series_types):
            if kind!=base or mapping.get(label,base)!=base:
                commands.append({'operation':'set_series_chart_type','label':label,'value':kind,'params':{}})
        desired_right={labels[i] for i in appearance.secondary_axis_indices}
        old_right=set((context.get('chartState') or {}).get('secondary_axis_series') or [])
        old_right.update(((context.get('chartState') or {}).get('report') or {}).get('right_axis') or [])
        commands=[c for c in commands if c.get('operation')!='remove_secondary_axis']
        for label in sorted(old_right-desired_right):
            if label in labels:commands.append({'operation':'remove_secondary_axis','value':label,'params':{}})
        for index in appearance.secondary_axis_indices:
            commands.append({'operation':'set_secondary_axis','value':labels[index],'params':{}})
        if (context.get('chartState') or {}).get('report'):
            commands.append({'operation':'set_report','params':{'patch':{'kind':'dual_axis' if appearance.secondary_axis_indices else 'forecast',
                'right_axis':[labels[i] for i in appearance.secondary_axis_indices]}}})
    current=context.get('chartState') or {}
    compact=[]
    for c in commands:
        if c.get('operation')=='set_legend' and c.get('value')==current.get('legend_position') and current.get('show_legend',True):continue
        if c.get('operation')=='set_axis_style' and isinstance(c.get('params'),dict):
            axis=(current.get('axes') or {}).get(c.get('label'))
            if isinstance(axis,dict) and all(axis.get(k)==v for k,v in c['params'].items()):continue
        compact.append(c)
    commands=compact
    commands=[c for c in commands if not(c.get('operation')=='set_series_chart_type' and c.get('value')==appearance.chart_type
        and current.get('chart_type')==appearance.chart_type and (current.get('series_chart_types') or {}).get(c.get('label'),appearance.chart_type)==appearance.chart_type)]
    if appearance.chart_type not in {'line','area'} or (context.get('chartState') or {}).get('chart_type')!=appearance.chart_type:
        commands.insert(0,{'operation':'set_chart_type','value':appearance.chart_type,'params':{}})
    layout='combined' if appearance.panel_count==1 else 'horizontal' if appearance.columns>=count else 'grid'
    commands.append({'operation':'set_layout','value':layout,'params':{}})
    if len(commands)>12:raise ValueError('참고 형식의 설정이 너무 많습니다. 데이터별 색상 설정을 줄이거나 변경을 나눠 주세요.')
    # The only current source is the user's single whole-format request. All
    # style commands belong to it; explicit multi-clause/sketch paths are unchanged.
    result={**proposal,'commands':commands,'reference_style':appearance.model_dump()}
    if 'candidateProposal' in context:
        instruction=context.get('instruction','')
        result['coverage']=[{'source_id':'text:0','text':instruction,'status':'covered','command_indices':list(range(len(commands)))}]
    return result
