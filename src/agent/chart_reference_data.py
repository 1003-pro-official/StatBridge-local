"""Resolve image legend entries against a related, server-owned catalog.

Reference files supply names and appearance, never observations or API IDs.
Only an aggregate selection can expand to the named members of its own family.
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import calendar
import re
from pydantic import BaseModel, ConfigDict, Field, model_validator
from output_schema import ChartSpec, SeriesStyle


class ReferenceSeries(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str = Field(min_length=1, max_length=100)
    table: str = Field(min_length=1, max_length=150)
    category: str = Field(min_length=1, max_length=150)
    style: SeriesStyle = Field(default_factory=SeriesStyle)


class ReferencePeriod(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start: str = Field(pattern=r'^\d{6}$')
    end: str = Field(pattern=r'^\d{6}$')

    @model_validator(mode='after')
    def valid_months(self):
        if self.start>self.end or any(not 1<=int(p[4:])<=12 for p in (self.start,self.end)):
            raise ValueError('참고 그림의 월별 기간을 확인하지 못했습니다.')
        return self


def reference_catalog(result, agent):
    """Expose exact category names only for siblings of the aggregate source."""
    from semantic_catalog_planner import catalog_paths
    plans = result.get('api_plans') or [result.get('api_plan')]
    plans = [p for p in plans if p]
    paths = catalog_paths()
    parents = set()
    for plan in plans:
        table = agent.tables_by_id.get(str(plan['table_id'])) or {}
        selected = set((plan.get('classifications') or {}).values())
        aggregate = any(v['value_id'] in selected and v['value_name'] in {'총지수','전체','합계','총계'}
                        for d in table.get('dimensions', []) for v in d.get('values', []))
        path = paths.get(str(plan['table_id']), '').split(' > ')
        if aggregate and len(path) >= 4:
            parents.add(tuple(path[:-1]))
    frequencies = {p['frequency'] for p in plans}
    def measure(name):
        # Export/import are directions of the same measure; volume, value and
        # price remain distinct even though the catalog parent is shared.
        return re.sub(r'^(?:수출|수입)', '', re.sub(r'\s+','',name))
    measures={measure(p['table_name']) for p in plans}
    return [{'table':t['table_name'], 'categories':[v['value_name'] for v in t['dimensions'][0]['values']],
             'start':str(t.get('period_start_observed') or ''),'end':str(t.get('period_end_observed') or '')}
            for t in agent.resolver.tables
            if tuple(paths.get(str(t['table_id']), '').split(' > ')[:-1]) in parents
            and measure(t['table_name']) in measures
            and t.get('prd_se')=='M' and 'M' in frequencies and len(t.get('dimensions') or []) == 1]


def prepare_reference_data(result, current, appearance, catalog, agent):
    """Return a complete new snapshot, or fail without mutating the old one."""
    requested = [ReferenceSeries.model_validate(s) for s in appearance.get('data_series') or []]
    if not requested:
        return None
    if not 1 <= len(requested) <= 6:
        raise ValueError('참고 그림에서 조회할 지표는 한 번에 6개까지입니다.')
    allowed = {c['table']:set(c['categories']) for c in catalog}
    if len({(s.table,s.category) for s in requested}) != len(requested):
        raise ValueError('참고 그림의 동일 지표를 여러 곡선으로 복제하지 않습니다.')
    old_series = agent.output_agent._series(result.get('execution',{}).get('rows',[]))
    periods = sorted({p['date'] for s in old_series for p in s['points']})
    if not periods:
        raise ValueError('기존 그래프의 실제 조회 기간을 확인하지 못했습니다.')
    start,end = periods[0],periods[-1]
    if appearance.get('display_period'):
        period = ReferencePeriod.model_validate(appearance['display_period'])
        # Re-query older available months too, but never fabricate future dates.
        bounds=[c for c in catalog if c['table'] in {s.table for s in requested}]
        available=bool(bounds) and all(len(c.get('start',''))==6 and len(c.get('end',''))==6 for c in bounds)
        lower=max(c['start'] for c in bounds) if available else start
        upper=min(c['end'] for c in bounds) if available else end
        if not lower <= period.start <= period.end <= upper:
            raise ValueError('참고 그림의 기간에 제공되는 통계가 없습니다. 기존 그래프는 유지됩니다.')
        start,end = period.start,period.end
    prepared=[]
    for item in requested:
        if item.table not in allowed or item.category not in allowed[item.table]:
            raise ValueError(f'참고 범례 “{item.label}”에 대응하는 정본 분류를 확인하지 못했습니다. 총지수로 대체하지 않았습니다.')
        query = item.table+' '+item.category
        resolved = agent.resolve(query)
        plans = resolved.get('api_plans') or []
        if resolved.get('status') != 'resolved' or len(plans) != 1:
            raise ValueError(f'“{query}”의 통계표·분류를 유일하게 선택하지 못했습니다.')
        plan = plans[0]
        table = agent.tables_by_id[str(plan['table_id'])]
        categories = {v['value_id']:v['value_name'] for d in table['dimensions'] for v in d['values']}
        chosen = [categories.get(v) for v in plan['classifications'].values()]
        if table['table_name'] != item.table or chosen != [item.category]:
            raise ValueError(f'“{query}”의 조회 계획이 요청한 분류와 다릅니다. 총지수로 대체하지 않았습니다.')
        prepared.append((item,query,resolved))
    def fetch(entry):
        item,query,resolved=entry
        fetched=agent.execute_resolution(query=query,resolution=deepcopy(resolved),execute=True,
            start_period=start,end_period=end,generate_answer=False)
        execution=fetched.get('execution') or {}
        if execution.get('status')!='success' or not execution.get('rows'):
            raise ValueError(f'“{query}”의 실제 관측값을 조회하지 못했습니다. 기존 그래프는 유지됩니다.')
        plan=fetched['api_plan']
        if any(str(row.get('C1',plan['classifications']['objL1']))!=str(plan['classifications']['objL1'])
               or str(row.get('ITM_ID',plan['item_id']))!=str(plan['item_id']) for row in execution['rows']):
            raise ValueError(f'“{query}”의 응답 항목·분류 ID가 요청과 다릅니다.')
        shown=agent.output_agent._series(execution['rows'])
        if len(shown)!=1 or not all(item.category in s['label'] for s in shown):
            raise ValueError(f'“{query}”의 응답 분류가 요청과 다릅니다.')
        return fetched,shown[0]['label']
    with ThreadPoolExecutor(max_workers=3) as pool:
        fetched=[future.result() for future in [pool.submit(copy_context().run,fetch,entry) for entry in prepared]]
    merged=deepcopy(fetched[0][0])
    plans=[p for r,_ in fetched for p in r['api_plans']]
    rows=[row for r,_ in fetched for row in r['execution']['rows']]
    bindings=[{'reference':s.label,'label':label,'table':s.table,'category':s.category}
              for (s,_,_),(r,label) in zip(prepared,fetched)]
    merged.update(api_plans=plans,request_validation={'valid':True,'table_ids':[p['table_id'] for p in plans]})
    merged['execution']={'status':'success','rows':rows,'row_count':len(rows),
        'sources':[source for r,_ in fetched for source in r['execution'].get('sources',[])],
        'referenceDataBinding':bindings}
    spec=ChartSpec.model_validate(current['chartState'])
    reset={'title':' · '.join(dict.fromkeys(s.table for s in requested))+' 추이','subtitle':'',
        'transform':'raw','report':None,'layout':'combined','y_axis_label':'','x_axis_label':'',
        'series_colors':{},'series_styles':{},'series_dashes':{},'display_names':{},'series_chart_types':{},
        'hidden_series':[],'series_order':[],'secondary_axis_series':[],'range_styles':[],
        'highlights':[],'annotations':[],'guides':[],'notes':[],'paper_shapes':[],
        'period_start':None,'period_end':None,'top_n':None,'axes':{}}
    reset['presentation']=spec.presentation.model_copy(update={'publication_yoy':False,'publication_axes':False})
    baseline={**agent.output_agent._build(merged,spec.model_copy(update=reset),generate_explanation=False),
              'editHistory':current.get('editHistory',[]),'editConversation':current.get('editConversation',[])}
    sessions=[{'query':query,'result':r,'table_name':item.table,'frequency':r['api_plan']['frequency'],
               'period':{'start':start[:4]+'-'+start[4:]+'-01',
                         'end':end[:4]+'-'+end[4:]+'-'+str(calendar.monthrange(int(end[:4]),int(end[4:]))[1])}}
              for (item,query,_),(r,_) in zip(prepared,fetched)]
    return merged,baseline,sessions
