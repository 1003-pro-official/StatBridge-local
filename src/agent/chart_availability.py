"""The selector uses the same renderer and validations as final output."""
from output_schema import ChartSpec

CHART_TYPES = ("line","bar","stacked_bar","area","scatter","bubble","pie","donut","histogram","box","heatmap","treemap","waterfall")


def combined_layout_reason(series):
    reasons=[]
    if len({s.get('unit') or '단위 미상' for s in series})>1:
        reasons.append('한 그래프의 같은 축에 표시하려면 단위가 같아야 합니다. 현재 '+', '.join(f"{s['label']} ({s.get('unit') or '단위 미상'})" for s in series)+'입니다. 계열별 그래프를 선택해 주세요. 보조축은 별도로 명시한 경우에만 사용합니다.')
    frequencies={s.get('frequency') for s in series if s.get('frequency')}
    if len(frequencies)>1:
        reasons.append('관측 주기가 '+', '.join(sorted(frequencies))+'로 다릅니다. 같은 주기로 조회하거나 계열별 그래프를 선택해 주세요.')
    return ' / '.join(reasons)


def data_requirements(series, kind):
    """Concrete observed blockers, shared by selection and final rendering."""
    errors=[]
    count=len(series)
    if not count or any(not s['points'] for s in series):
        errors.append('조회된 계열 중 수치 관측값이 없는 계열이 있습니다. 실제 숫자 데이터가 필요합니다.')
        return errors
    units={s.get('unit') or '단위 미상' for s in series}
    if kind in {'scatter','bubble'}:
        needed=3 if kind=='bubble' else 2
        if count!=needed:
            errors.append(f"{'버블 그래프' if needed==3 else '산점도'}에는 정확히 {needed}개 지표가 필요합니다. 현재 {count}개입니다. "+
                          (f'{needed-count}개 지표를 추가 조회해 주세요.' if count<needed else '사용할 지표를 줄여 다시 조회해 주세요. 나머지 지표를 임의로 버리지 않습니다.'))
        frequencies={s.get('frequency') for s in series if s.get('frequency')}
        if len(frequencies)>1:
            errors.append('관측 주기가 다릅니다: '+', '.join(sorted(frequencies))+'. 같은 주기의 지표가 필요합니다.')
        common=set.intersection(*(set(p['date'] for p in s['points']) for s in series))
        if not common:
            ranges='; '.join(f"{s['label']}: {s['points'][0]['date']}~{s['points'][-1]['date']}" for s in series)
            errors.append('같은 시점에 X·Y'+('·크기' if needed==3 else '')+' 값이 모두 존재하는 관측값이 0개입니다. '+ranges)
        if kind=='bubble' and count==3:
            values=[p['value'] for p in series[2]['points'] if p['date'] in common]
            if values and (min(values)<0 or max(values)<=0):
                errors.append(f"크기 지표 '{series[2]['label']}'에 음수가 있거나 양수 값이 없습니다. 버블 면적에 사용할 0 이상의 값과 최소 한 개의 양수가 필요합니다.")
    if kind in {'stacked_bar','pie','donut','heatmap','treemap','waterfall'} and len(units)>1:
        errors.append('같은 단위가 필요하지만 현재 '+', '.join(f"{s['label']} ({s.get('unit') or '단위 미상'})" for s in series)+'입니다. 다른 단위는 합산하거나 구성비로 비교할 수 없습니다.')
    if kind in {'pie','donut','treemap','heatmap'} and count<2:
        errors.append(f'최소 2개 비교 지표가 필요하지만 현재 {count}개입니다. 비교할 지표 1개를 추가 조회해 주세요.')
    if kind in {'pie','donut','treemap'}:
        latest=[s['points'][-1] for s in series]
        if len({p['date'] for p in latest})>1:
            errors.append('각 지표의 마지막 시점이 다릅니다: '+', '.join(f"{s['label']}={p['date']}" for s,p in zip(series,latest))+'. 같은 시점의 값이 필요합니다.')
        if any(p['value']<0 for p in latest):
            errors.append('구성비에 사용할 마지막 값에 음수가 있습니다. 모든 구성 값이 0 이상이어야 합니다.')
        if sum(p['value'] for p in latest)<=0:
            errors.append('마지막 시점 값의 합계가 0 이하입니다. 구성비를 계산하려면 합계가 0보다 커야 합니다.')
    if kind=='waterfall' and count!=1:
        errors.append(f'폭포 그래프는 현재 1개 지표의 증감만 지원합니다. 현재 {count}개 지표입니다. 지표 1개를 선택해 조회해 주세요.')
    return errors


def inspect_charts(series):
    from plotly_renderer import render_plotly
    from research_chart_editing import validate_research_spec
    allowed, unavailable = [], {}
    if not series or not any(s["points"] for s in series):
        return [], {kind:"조회된 수치 데이터가 없습니다." for kind in CHART_TYPES}
    mixed_frequency=len({s["frequency"] for s in series if s.get("frequency")})>1
    for kind in CHART_TYPES:
        spec=ChartSpec(chart_type=kind,layout="separate" if combined_layout_reason(series) and kind in {'line','bar','stacked_bar','area','histogram','box'} else "combined")
        try:
            blockers=data_requirements(series,kind)
            if blockers:
                raise ValueError(' / '.join(blockers))
            validate_research_spec(series,spec)
            render_plotly(series,spec)
            allowed.append(kind)
        except ValueError as exc:
            unavailable[kind]=str(exc)
    return allowed,unavailable
