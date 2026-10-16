"""Explicit level + year-over-year requests, calculated from calendar-matched observations."""
import re
import math
from collections import defaultdict
from chart_data_transforms import previous_year_period
from report_summary import difference_unit

CALCULATION_NOTE='전년동기 비교는 서버에서 계산한 값입니다. 증가율은 (이번 값 ÷ 전년 값 − 1) × 100, 차이는 이번 값 − 전년 값이며 금리·비중의 차이 단위는 %p입니다. 전년 값이 없거나 증가율의 분모가 0인 시점은 계산하지 않습니다.'

YOY_PATTERN=r'전년\s*(?:동기\s*)?(?:대비)?\s*(?:증가율|증감률)'
DIFF_PATTERN=r'전년\s*(?:동기\s*)?(?:대비)?\s*(?:차이|변화폭|증감폭)'
LEVEL_PATTERN=r'(?:잔액|수준|원자료|원지수|지수|금액|규모|건수|인원|수량|총액)'

def measurement_mode(query):
    query=re.sub(YOY_PATTERN+r'\s*(?:말고|대신|아닌)', ' ',query)
    difference=bool(re.search(DIFF_PATTERN,query))
    pattern=DIFF_PATTERN if difference else YOY_PATTERN
    if not re.search(pattern,query):return 'raw'
    pair=(re.search(LEVEL_PATTERN+r'\s*(?:과|와|및|,|하고)\s*'+pattern,query)
          or re.search(pattern+r'\s*(?:과|와|및|,)\s*'+LEVEL_PATTERN,query))
    return ('level_and_difference' if pair else 'difference') if difference else ('level_and_yoy' if pair else 'yoy')

def wants_level_and_yoy(query):return measurement_mode(query)=='level_and_yoy'

def comparison_modes(query,plans,tables):
    from request_match_guard import catalog_mentions,scoped_metric_query
    mentions=catalog_mentions(query,tables);by_id={str(t['table_id']):t for t in tables}
    return {str(p['table_id']):measurement_mode(scoped_metric_query(query,by_id[str(p['table_id'])],mentions)) for p in plans}

def with_comparison_history(requests):
    return [{**r,'start_period':previous_year_period(r['start_period'],r['frequency'])} for r in requests]

def append_yoy(rows,plans,modes=None):
    from output_agent import OutputAgent
    windows={str(p['table_id']):(p['start_period'],p['end_period']) for p in plans}
    grouped=defaultdict(list)
    for row in rows:grouped[OutputAgent._series_key(row)].append(row)
    visible=[];derived=[];calculations=[];missing=[]
    for key,items in grouped.items():
        source,label,unit=key;start,end=windows[source]
        mode=(modes or {}).get(source,'level_and_yoy')
        if mode=='raw':
            visible.extend(row for row in items if start<=str(row['PRD_DE'])<=end);continue
        difference=mode in {'difference','level_and_difference'}
        if not difference and ('%' in unit or '％' in unit):raise ValueError('금리·비중·비율의 전년동기 비교는 증가율(%)과 차이(%p)가 다릅니다. 원래 수준을 볼지 전년동기 대비 차이를 볼지 지정해 주세요.')
        lookup={}
        for row in items:
            try:v=float(str(row.get('DT','')).replace(',',''))
            except (ValueError,TypeError):continue
            if not math.isfinite(v):continue
            period=str(row['PRD_DE'])
            if period in lookup and lookup[period]!=v:raise ValueError('같은 시점에 서로 다른 값이 있어 증가율을 계산할 수 없습니다.')
            lookup[period]=v
        target=label+(' · 전년동기 대비 차이' if difference else ' · 전년동기 대비 증가율')
        derived_unit=difference_unit(unit) if difference else '%'
        kind='year_over_year_difference' if difference else 'year_over_year'
        for row in items:
            period=str(row['PRD_DE'])
            if not start<=period<=end:continue
            if mode in {'level_and_yoy','level_and_difference'}:visible.append(row)
            prior=previous_year_period(period,row['_FREQUENCY']);base=lookup.get(prior)
            if base is None or (not difference and base==0) or period not in lookup:
                missing.append(period);continue
            value=lookup[period]-base if difference else (lookup[period]/base-1)*100
            derived.append({**row,'DT':str(value),'UNIT_NM':derived_unit,'_SERIES_LABEL':target,'_DERIVED_CALCULATION':kind})
            calculations.append({'label':target,'period':period,'value':value,'unit':derived_unit,'basePeriod':prior,'baseValue':base,'currentValue':lookup[period],'sourceId':source,'kind':kind,'formula':'current - previous_year' if difference else '(current / previous_year - 1) * 100'})
    if not derived:raise ValueError('전년 같은 시점의 값이 없거나 0이어서 증가율을 계산할 수 없습니다. 더 긴 기간을 제공하는 원자료 표를 선택해 주세요.')
    return visible+derived,calculations,sorted(set(missing))
