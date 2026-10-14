"""Conservative presentation defaults; statistical selections remain untouched."""
import re

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
