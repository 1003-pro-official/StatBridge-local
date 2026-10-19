"""Independent Decimal oracle and owner-scoped upload continuation contracts."""
import copy
from decimal import Decimal
from types import SimpleNamespace
import pytest
from expression_tree_schema import ExpressionPlan
from expression_tree_validator import validate_plan,DerivedValidationError
from dynamic_expression_executor import DynamicExpressionExecutor,Series
from derived_period_comparison import output_series,decorate_figure,validate_contract
from derived_supplement import DerivedSupplementService


def plan_data(count=12):
    periods=[{'label':'1기','start':'20180301','end':'20190930','basis':'monthly_mean'},
             {'label':'2기','start':'20241105','end':'20250224','basis':'exact'}]
    return {'plan_version':'1.0','indicator_name':'합성 자료 기간 비교 검증','economic_definition':'시험 원자료의 사용자 선언 방향에 따른 기간 변화율',
            'sources':[{'alias':f's{i}','table_id':f'USER_FILE:s{i}','item_id':'value','classifications':{},'frequency':'D','required_data':f'시험계열{i}'} for i in range(count)],
            'nodes':[{'id':f'n{i}','operator':'period_change','inputs':[f's{i}'],'periods':periods,'direction':'direct' if i==0 else 'inverse'} for i in range(count)],
            'outputs':[{'node':f'n{i}','label':f'계열{i}'} for i in range(count)],'start_period':'20180301','end_period':'20250224',
            'category_comparison':{'average_nodes':[f'n{i}' for i in range(1,count)] or ['n0']}}


def inputs(count=12):
    return {f's{i}':Series({'20180301':100+i,'20180302':104+i,'20190929':110+i,'20190930':114+i,
                           '20241105':120+i,'20250224':132+i},'지수' if i==0 else 'JPY/USD','D',[f's{i}']) for i in range(count)}


def test_twelve_period_reductions_decimal_and_categorical_output():
    plan=ExpressionPlan.model_validate(plan_data());validate_plan(plan,SimpleNamespace(validate_source_selection=lambda s:None))
    computed=DynamicExpressionExecutor().execute(plan,inputs())
    assert len(computed['rows'])==24
    for i in range(12):
        start=Decimal(102+i);end=Decimal(112+i)
        expected=(end/start-1)*100 if i==0 else (start/end-1)*100
        assert computed['series'][f'n{i}'].values['20190930']==pytest.approx(float(expected),abs=1e-12)
    result={'_derived':{'record':{'plan':plan.model_dump()},'series':{k:{'values':v.values} for k,v in computed['series'].items()}},
            'derivedEvidence':{'sourceSelections':[{'provenance':['Synthetic test only']}]} }
    series=output_series(result,[]);assert len(series)==2 and len(series[0]['points'])==12
    figure=decorate_figure(result,{'data':[],'layout':{}},series)
    assert figure['layout']['xaxis']['categoryarray']==[f'계열{i}' for i in range(12)]
    assert figure['layout']['xaxis']['ticktext']==[f'계열{i}' for i in range(12)]
    assert len(figure['layout']['shapes'])==2
    assert figure['layout']['shapes'][0]['y0']==pytest.approx(sum(p['value'] for p in series[0]['points'][1:])/11)


@pytest.mark.parametrize('mutation',['missing','zero','negative','overflow'])
def test_missing_and_nonpositive_prices_stop_without_filling(mutation):
    data=inputs(1)
    if mutation=='missing':del data['s0'].values['20241105']
    elif mutation=='overflow':data['s0'].values.update({'20241105':1e-308,'20250224':1e308})
    else:data['s0'].values['20241105']=0 if mutation=='zero' else -1
    with pytest.raises(DerivedValidationError):DynamicExpressionExecutor().execute(ExpressionPlan.model_validate(plan_data(1)),data)


@pytest.mark.parametrize('mutation',['outside','duplicate','mean_selection','frequency'])
def test_invalid_comparison_structure(mutation):
    d=plan_data(2)
    if mutation=='outside':d['nodes'][0]['periods'][0]['start']='20170101'
    elif mutation=='duplicate':d['nodes'][0]['periods'][1]['end']='20190930'
    elif mutation=='mean_selection':d['category_comparison']['average_nodes']=['injected']
    else:
        for s in d['sources']:s['frequency']='M'
    with pytest.raises(DerivedValidationError):validate_plan(ExpressionPlan.model_validate(d),SimpleNamespace(validate_source_selection=lambda s:None))


def assessment():
    return {'status':'checked','questions':['월평균?','평균 대상?'],'sources':[{'name':n,'status':'not_found','reason':'실제 API에서 주기 미지원',
             'periods':[{'label':'1기','start':'201803','end':'201909','frequency':'pending'},
                        {'label':'2기','start':'20241105','end':'20250224','frequency':'D'}]} for n in ['DXY 원지수','일본 JPY 환율']]}


def test_no_api_comparison_cannot_open_file_workspace(tmp_path):
    service=DerivedSupplementService(None,tmp_path)
    public=service.from_assessment(1,'일반 그래프 요청',assessment())
    assert public['unsupported'] and 'supplement' not in public
    assert not list(tmp_path.glob('user-*/*/workspace.json'))


def test_model_contract_cannot_override_user_formula_or_average():
    d=plan_data(2);settings={'periods':d['nodes'][0]['periods'],'series':[{'alias':f's{i}','label':f'계열{i}','direction':d['nodes'][i]['direction']} for i in range(2)],'average_aliases':['s1']}
    validate_contract(ExpressionPlan.model_validate(d),settings)
    for key in ['direction','label','average']:
        broken=copy.deepcopy(d)
        if key=='direction':broken['nodes'][1]['direction']='direct'
        elif key=='label':broken['outputs'].reverse()
        else:broken['category_comparison']['average_nodes']=['n0','n1']
        with pytest.raises(DerivedValidationError):validate_contract(ExpressionPlan.model_validate(broken),settings)


def test_existing_output_agent_renders_grouped_bars_table_and_means():
    from output_agent import OutputAgent
    p=ExpressionPlan.model_validate(plan_data());c=DynamicExpressionExecutor().execute(p,inputs())
    result={'query':'묶음 막대그래프','execution':{'rows':c['rows'],'calculations':list(c['calculations'].values())},
        'api_plans':[{'table_id':s.table_id,'table_name':s.required_data,'frequency':'D'} for s in p.sources],
        '_derived':{'record':{'plan':p.model_dump()},'series':{k:{'values':v.values,'unit':v.unit,'frequency':v.frequency} for k,v in c['series'].items()}},
        'derivedEvidence':{'sourceSelections':[{'origin':'user_file','provenance':['Synthetic test only']}]} }
    agent=OutputAgent();assert agent.inspect(result)['seriesCount']==2
    output=agent.prepare(result,{'chart_type':'bar','quick_output':True})
    assert output['plotlyFigure']['layout']['barmode']=='group'
    assert len(output['table']['rows'])==24
    assert len(output['plotlyFigure']['data'])==2
    assert output['tableDocument']['sections'][0]['periods']==[f'계열{i}' for i in range(12)]
    assert '평균하지 않았습니다' not in ' '.join(output['tableDocument']['notes'])


def test_legacy_file_only_cache_cannot_bypass_new_scope(tmp_path):
    service=DerivedSupplementService(None,tmp_path)
    workspace={'query':'과거 전체 파일 비교','comparison_required':True,'prefetched':{},
               'comparison_settings':{'old':True},'validated_comparison_plan':{'old':True}}
    assert service.advance(workspace)['unsupported']
    assert service.public({**workspace,'files':{'old':{}},'missing':[]})['unsupported']


def test_check_token_cannot_open_another_accounts_files(monkeypatch):
    import bridge_api as api
    from fastapi import HTTPException
    import time
    identifier='a'*32
    monkeypatch.setitem(api.DERIVED_SOURCE_CHECKS,identifier,{'owner':999,'created':time.time(),'assessment':assessment(),'query':'test'})
    token=api.account_auth.USER.set({'id':998})
    try:
        with pytest.raises(HTTPException) as error:api.supplement_from_check(api.SupplementCheckRequest(check_id=identifier))
        assert error.value.status_code==404
    finally:api.account_auth.USER.reset(token)
