"""Fetch comparison observations for the confirmed plans without changing the view."""
from copy import deepcopy

from chart_data_transforms import previous_year_period


def ensure_comparison_history(result, service):
    execution = result.get('execution') or {}
    if execution.get('chartComparisonHistory') is not None and execution.get('chartAnnualIndices') is not None:
        return result
    rows = execution.get('rows') or []
    if any(r.get('_DERIVED_CALCULATION') or any(c in str(r.get('UNIT_NM', '')) for c in ('%', '％')) for r in rows):
        raise ValueError('이미 비율·증감률인 자료입니다. 원지수·금액 등 수준 자료에서 전년동기 대비를 선택해 주세요.')
    plans = result.get('api_plans') or [result.get('api_plan')]
    plans = [p for p in plans if p]
    if not plans:
        raise ValueError('전년도 비교값을 조회할 확정된 통계표가 없습니다.')
    import os
    requests = []
    for i, plan in enumerate(plans):
        start = plan['start_period']
        # Full calendar years also support explicitly labelled annual index growth.
        if plan['frequency'] == 'M':
            start = start[:4] + '01'
        requests.append(dict(request_id=str(i), table_id=plan['table_id'],
            item_id=plan['item_id'], classifications=plan['classifications'],
            frequency=plan['frequency'], start_period=previous_year_period(start, plan['frequency']),
            end_period=plan['end_period'], prefer_local=not bool(os.getenv('KOSIS_API_KEY', '').strip()),
            allow_fallback=False))
    try:
        outcomes = service.get_statistics_batch(requests)['results']
    except Exception as exc:
        raise ValueError('전년도 비교 자료를 조회하지 못했습니다. 잠시 후 다시 시도해 주세요.') from exc
    if len(outcomes) != len(plans):
        raise ValueError('전년도 비교 자료의 응답 개수가 조회 계획과 다릅니다.')
    history, sources = [], []
    for plan, req, outcome in zip(plans, requests, outcomes):
        data = outcome.get('data') or {}
        if outcome.get('status') != 'success' or data.get('status') != 'success':
            raise ValueError('전년도 비교 자료를 조회하지 못했습니다. 잠시 후 다시 시도해 주세요.')
        for row in data.get('rows') or []:
            if row.get('TBL_ID') and str(row['TBL_ID']) != str(plan['table_id']):
                raise ValueError('전년도 비교 자료의 출처가 선택한 통계표와 다릅니다.')
            history.append({**row, '_SERIES_LABEL': str(plan.get('series_label') or plan['table_name']),
                '_SOURCE_SERIES_ID': str(plan['table_id']), '_FREQUENCY': str(plan['frequency'])})
        sources.append({'tableId': plan['table_id'], 'start': req['start_period'],
                        'end': req['end_period'], 'source': data.get('source')})
    candidate = deepcopy(result)
    candidate['execution']['chartComparisonHistory'] = history
    candidate['execution']['chartComparisonSources'] = sources
    # Annual trade indices are published independently. Never substitute the
    # average of monthly indices when an annual observation is unavailable.
    annual_requests=[]
    annual_plans=[]
    for i,plan in enumerate(plans):
        matching=[r for r in rows if str(r.get('TBL_ID',plan['table_id']))==str(plan['table_id'])]
        if plan['frequency']!='M' or not matching or not all('=100' in str(r.get('UNIT_NM','')).replace(' ','').replace('＝','=') for r in matching):
            continue
        annual_plans.append(plan)
        annual_requests.append({**requests[i], 'request_id': 'annual-'+str(i), 'frequency':'Y',
            'start_period':str(int(plan['start_period'][:4])-1),'end_period':plan['end_period'][:4]})
    annual=[]
    if annual_requests:
        try:
            annual_outcomes=service.get_statistics_batch(annual_requests)['results']
            if len(annual_outcomes)!=len(annual_plans):raise ValueError('annual response count')
            for plan,req,outcome in zip(annual_plans,annual_requests,annual_outcomes):
                data=outcome.get('data') or {}
                if outcome.get('status')!='success' or data.get('status')!='success':continue
                for row in data.get('rows') or []:
                    if len(str(row.get('PRD_DE','')))!=4 or str(row.get('TBL_ID'))!=str(plan['table_id']):continue
                    if row.get('ITM_ID') and str(row['ITM_ID'])!=str(plan['item_id']):continue
                    annual.append({**row,'_SERIES_LABEL':str(plan.get('series_label') or plan['table_name']),
                        '_SOURCE_SERIES_ID':str(plan['table_id']),'_FREQUENCY':'Y'})
                sources.append({'tableId':plan['table_id'],'start':req['start_period'],'end':req['end_period'],
                    'frequency':'Y','source':data.get('source')})
        except Exception:
            # Monthly YoY remains available without an annual guide.
            pass
    candidate['execution']['chartAnnualIndices']=annual
    return candidate
