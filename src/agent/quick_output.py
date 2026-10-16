"""Conservative presentation defaults; statistical selections remain untouched."""
import re


def dual_axis_requested(text):
    """Recognize explicit axis intent without guessing from value magnitudes."""
    text=text or ''
    if re.search(r'(?:이중\s*축|보조\s*축|좌우\s*축)\s*(?:말고|없이|제외|사용하지)',text):
        return False
    return bool(re.search(r'이중\s*축|보조\s*축|좌우\s*(?:Y\s*)?축|(?:Y|세로)\s*축(?:을|이)?\s*(?:2|두)\s*개|(?:2|두)\s*개의?\s*(?:Y|세로)\s*축|왼쪽\s*(?:Y\s*)?축.*오른쪽\s*(?:Y\s*)?축|오른쪽\s*(?:Y\s*)?축.*왼쪽\s*(?:Y\s*)?축',text,re.I))


def dual_axis_defaults(series):
    units=list(dict.fromkeys(s['unit'].strip() for s in series))
    if len(series)<2 or len(units)>2 or len({s.get('frequency') for s in series})!=1:
        raise ValueError('이중축은 같은 주기의 지표 두 개 이상과 최대 두 종류의 단위로 구성해 주세요. 주기가 다른 자료는 분리 배치로 비교할 수 있습니다.')
    # Retain original units. A percentage group goes right regardless of order.
    right_unit=next((u for u in units if '%' in u or '％' in u),units[-1])
    right=[s['label'] for s in series if s['unit'].strip()==right_unit] if len(units)==2 else [series[-1]['label']]
    return dict(chart_type='line',series_chart_types={s['label']:'bar' if s['label'] in right else 'line' for s in series},secondary_axis_series=right,
                axes={'y':{'title_orientation':'horizontal','title_placement':'top'},'y2':{'title_orientation':'horizontal','title_placement':'top'}})

ALIASES = {
    'stacked_bar': r'누적\s*(?:막대|바)\s*(?:그래프|차트)?',
    'line': r'(?:선|라인)\s*(?:그래프|차트)',
    'bar': r'(?:막대|바)\s*(?:그래프|차트)',
    'area': r'영역\s*(?:그래프|차트)',
    'pie': r'(?:원|파이)\s*(?:그래프|차트)',
    'donut': r'도넛\s*(?:그래프|차트)',
    'treemap': r'트리맵', 'scatter': r'산점도', 'bubble': r'버블\s*(?:그래프|차트)',
    'histogram': r'히스토그램', 'box': r'상자\s*(?:그림|그래프)|박스\s*플롯',
    'heatmap': r'히트맵', 'waterfall': r'폭포\s*(?:그래프|차트)',
}


def requested_chart(text):
    remaining = text or ''
    found = []
    for kind, pattern in ALIASES.items():
        if re.search(pattern, remaining):
            found.append(kind)
            remaining = re.sub(pattern, '', remaining)
    if len(found) > 1:
        raise ValueError('복합 차트는 그래프 종류를 하나 선택한 뒤 계열별 고급 편집으로 지정해 주세요. 조회된 자료는 유지됩니다.')
    return found[0] if found else None
