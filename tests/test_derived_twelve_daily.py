"""Synthetic daily files and real catalog boundaries; no live-provider claims."""
import copy,json,io,csv,base64
from decimal import Decimal
from types import SimpleNamespace
import pytest
from expression_tree_schema import ExpressionPlan
from expression_tree_validator import (DerivedValidationError,period_index,shift_period,
    canonical_bound,prior_year_period,validate_plan)
from dynamic_expression_executor import DynamicExpressionExecutor,Series
from derived_catalog_tools import DerivedCatalogTools
from derived_supplement import DerivedSupplementService,SupplementalCatalog
from derived_supplement_schema import PartialInputs
from derived_indicator_runtime import DerivedIndicatorRuntime
from statbridge_mcp.metadata_store import MetadataStore
from test_dynamic_derived_indicators import Model


def daily_plan(count=12,operator='pct_change',**parameters):
    if operator=='pct_change':parameters={'lag':1,**parameters}
    return {'plan_version':'1.0','indicator_name':'독립 합성 일별 12개 비교',
        'economic_definition':'사용자 제공 합성 계열의 달력일 기준 변환 비교',
        'sources':[{'alias':f'x{i}','table_id':f'USER_FILE:x{i}','item_id':'value','classifications':{},
                    'frequency':'D','required_data':f'합성 지수 {i}'} for i in range(count)],
        'nodes':[{'id':f'n{i}','operator':operator,'inputs':[f'x{i}'],**parameters} for i in range(count)],
        'outputs':[{'node':f'n{i}','label':f'지수 {i} 변화율'} for i in range(count)],
        'start_period':'20240228','end_period':'20240301'}


@pytest.mark.parametrize('period',['20230229','20241301','20240431','20240001','20240100','18991231','22010101','2024-02-29','202402'])
def test_invalid_daily_dates_are_blocked(period):
    with pytest.raises(DerivedValidationError):period_index(period,'D')


@pytest.mark.parametrize('period,offset,expected', [('20240228',1,'20240229'),('20240229',1,'20240301'),('20240301',-1,'20240229'),('20231231',1,'20240101')])
def test_calendar_shift_handles_leap_and_year_boundaries(period,offset,expected):
    assert shift_period(period,'D',offset)==expected
    assert canonical_bound(expected[:4]+'-'+expected[4:6]+'-'+expected[6:],'D')==expected


@pytest.mark.parametrize('count',[13,20])
def test_thirteenth_input_and_output_are_blocked(count):
    with pytest.raises(ValueError):ExpressionPlan.model_validate(daily_plan(count))


def test_combined_partial_limit_is_twelve_not_twelve_plus_twelve():
    p=daily_plan(12)
    missing=[{'alias':f'm{i}','required_data':f'합성 {i}','reason':'시험용','frequency':'D','unit':'지수'} for i in range(12)]
    PartialInputs.model_validate({'action':'request_inputs','available_sources':[], 'missing':missing,'start_period':'20240228','end_period':'20240301'})
    with pytest.raises(ValueError):
        PartialInputs.model_validate({'action':'request_inputs','available_sources':p['sources'][:1], 'missing':missing,'start_period':'20240228','end_period':'20240301'})


@pytest.mark.parametrize('chart_type',['line','bar'])
def test_twelve_daily_file_only_requests_rejected_but_engine_math_preserved(tmp_path,chart_type):
    from output_agent import OutputAgent
    from output_schema import ChartSpec
    p=daily_plan();slots=[{'alias':s['alias'],'required_data':s['required_data'],'reason':'사용자 합성 시험 원자료',
                          'frequency':'D','unit':'지수','lookback':1} for s in p['sources']]
    model=Model([{'action':'request_inputs','available_sources':[],'missing':slots,
                  'start_period':'20240228','end_period':'20240301'}, {'action':'plan','plan':p},
                 {'approved':True,'reason':'합성 파일의 달력일 기준 변화율'}])
    catalog=DerivedCatalogTools(MetadataStore())
    def forbidden(**kw):raise AssertionError('User files must never invoke an external API')
    runtime=DerivedIndicatorRuntime(SimpleNamespace(service=SimpleNamespace(store=catalog.store),get_statistics=forbidden),model,tmp_path/'evidence')
    service=DerivedSupplementService(runtime,tmp_path/'files')
    initial=service.start(1,'2024년 2월 28일부터 2024년 3월 1일까지 제공할 합성 지수 12개의 일별 전일 대비 변화율을 각각 계산해 주세요.')
    assert initial['unsupported'] and 'supplement' not in initial
    assert not list((tmp_path/'files').glob('user-*/*/workspace.json'))
    # The arithmetic engine remains generic; public request policy is stricter.
    series={f'x{i}':Series({t:float(v+i) for t,v in [('20240227',90),('20240228',100),('20240229',110),('20240301',121)]},'지수','D',[f'x{i}']) for i in range(12)}
    computed=DynamicExpressionExecutor().execute(ExpressionPlan.model_validate(p),series)
    result={'execution':{'rows':computed['rows']}}
    assert len(result['execution']['rows'])==36
    for row in result['execution']['rows']:
        i=int(row['_SOURCE_SERIES_ID'][1:]);v,prior={'20240228':(100,90),'20240229':(110,100),'20240301':(121,110)}[row['PRD_DE']]
        expected=(Decimal(v+i)/Decimal(prior+i)-1)*100
        assert abs(Decimal(str(row['DT']))-expected)<Decimal('1e-10')
    mutated=ExpressionPlan.model_validate(p);mutated.sources.append(mutated.sources[0])
    with pytest.raises(DerivedValidationError,match='최대 12'):
        validate_plan(mutated,SimpleNamespace(validate_source_selection=lambda s:None))


def test_daily_yoy_uses_same_date_not_365_day_offset():
    p=ExpressionPlan.model_validate(daily_plan(1,'yoy_pct'));p.start_period=p.end_period='20250301'
    values={'20240301':100.,'20240229':999.,'20250301':110.}
    result=DynamicExpressionExecutor().execute(p,{'x0':Series(values,'지수','D',['x0'])})
    assert result['rows'][0]['DT']==pytest.approx(10.)
    assert prior_year_period('20240229','D') is None
    assert prior_year_period('20250301','D')=='20240301'


def test_daily_yoy_does_not_substitute_february_28_for_leap_day():
    p=ExpressionPlan.model_validate(daily_plan(1,'yoy_pct'))
    p.start_period='20240228';p.end_period='20240229'
    result=DynamicExpressionExecutor().execute(p,{'x0':Series({'20230228':100.,'20240228':110.,'20240229':120.},'지수','D',['x0'])})
    assert [r['PRD_DE'] for r in result['rows']]==['20240228']
    assert any(i['period']=='20240229' for i in result['issues'])


def test_daily_gap_never_becomes_previous_business_day():
    p=ExpressionPlan.model_validate(daily_plan(1));p.start_period='20240308';p.end_period='20240312'
    result=DynamicExpressionExecutor().execute(p,{'x0':Series({'20240307':100.,'20240308':110.,'20240311':121.,'20240312':133.1},'지수','D',['x0'])})
    assert [r['PRD_DE'] for r in result['rows']]==['20240308','20240312']
    assert any(i['period']=='20240311' for i in result['issues'])


def test_daily_revision_recomputes_only_changed_branch():
    p=ExpressionPlan.model_validate(daily_plan());engine=DynamicExpressionExecutor()
    raw={f'x{i}':Series({'20240227':90.+i,'20240228':100.+i,'20240229':110.+i,'20240301':121.+i},'지수','D',[f'x{i}']) for i in range(12)}
    before=engine.execute(p,raw);raw['x0']=Series({'20240227':90.,'20240228':100.,'20240229':120.,'20240301':144.},'지수','D',['x0'])
    after=engine.execute(p,raw,cached=before['series'],changed=['x0'])
    assert after['series']['n0'].values['20240229']==pytest.approx(20.)
    for i in range(1,12):assert after['series'][f'n{i}'] is before['series'][f'n{i}']
    assert before['series']['n0'].values['20240229']==pytest.approx(10.)


def test_daily_still_blocks_work_and_memory_exhaustion():
    class Catalog:
        def validate_source_selection(self,source):pass
    p=ExpressionPlan.model_validate(daily_plan());p.start_period='20000101';p.end_period='20500101'
    p.nodes.extend([n.model_copy(update={'id':f'extra{i}','inputs':[n.id]}) for i,n in enumerate(p.nodes[:])])
    with pytest.raises(DerivedValidationError,match='메모리'):validate_plan(p,Catalog())
    p=ExpressionPlan.model_validate(daily_plan(12,'rolling_mean',window=120));p.start_period='20000101';p.end_period='20100101'
    with pytest.raises(DerivedValidationError,match='작업량'):validate_plan(p,Catalog())


def test_approved_monthly_table_cannot_be_mislabeled_daily():
    from expression_tree_schema import SourceSelection
    catalog=DerivedCatalogTools(MetadataStore());m=catalog.get_table_metadata('DT_404Y014')
    s=SourceSelection(alias='x',table_id=m['table_id'],item_id=m['items'][0]['item_id'],frequency='D',required_data='생산자물가',
        classifications={d['mcp_param']:d['values'][0]['class_id'] for d in m['dimensions']})
    with pytest.raises(DerivedValidationError,match='주기'):catalog.validate_source_selection(s)


def test_daily_ui_boundaries_preserve_exact_day():
    from bridge_api import _ui_period
    assert _ui_period('20241105','D')=='2024-11-05'
    assert _ui_period('20250224','D',end=True)=='2025-02-24'
    with pytest.raises(DerivedValidationError):_ui_period('20230229','D')

@pytest.mark.parametrize('operator,parameters,expected',[
 ('add',{},242.),('subtract',{},0.),('multiply',{},14641.),('divide',{},1.),
 ('pct_change',{'lag':1},10.),('yoy_pct',{},10.),('difference',{'lag':1},11.),
 ('rolling_mean',{'window':2},115.5),('cumulative_sum',{},331.),
 ('rebase_100',{'base_period':'20240228'},121.),('lag',{'lag':1},110.),
 ('inverse',{},1/121),('log',{},__import__('math').log(121)),('power',{'exponent':2},14641.)])
def test_all_fourteen_operators_on_daily_calendar(operator,parameters,expected):
    p=ExpressionPlan.model_validate(daily_plan(2,'inverse'))
    binary=operator in {'add','subtract','multiply','divide'}
    p.nodes=p.nodes[:1];p.outputs=p.outputs[:1]
    from expression_tree_schema import ExpressionNode
    p.nodes[0]=ExpressionNode(id='n0',operator=operator,inputs=['x0','x1'] if binary else ['x0'],**parameters)
    values={'20230301':110.,'20240227':90.,'20240228':100.,'20240229':110.,'20240301':121.}
    result=DynamicExpressionExecutor().execute(p,{f'x{i}':Series(dict(values),'지수','D',[f'x{i}']) for i in range(2)})
    assert next(r['DT'] for r in result['rows'] if r['PRD_DE']=='20240301')==pytest.approx(expected,abs=1e-10)
