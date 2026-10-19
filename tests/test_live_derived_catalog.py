"""Metadata adapter contracts use synthetic HTTP fixtures; not live API results."""
from types import SimpleNamespace
import pytest
from statbridge_mcp.metadata_store import MetadataStore
from derived_catalog_tools import DerivedCatalogTools
from live_derived_catalog import LiveDerivedCatalog
from derived_indicator_planner import DerivedIndicatorPlanner
from expression_tree_validator import DerivedValidationError
from test_dynamic_derived_indicators import plan,Model

def test_actual_response_mapping_cache_and_allowlist():
    store=MetadataStore();m=store.get('DT_513Y001').canonical_dict();calls=[]
    rows=[{'ORG_ID':'301','TBL_ID':m['table_id'],'OBJ_ID':'ITEM','ITM_ID':i['item_id'],'ITM_NM':i['item_name']} for i in m['items']]
    for d in m['dimensions']:
        rows.extend({'ORG_ID':'301','TBL_ID':m['table_id'],'OBJ_ID':d['obj_id'],'OBJ_ID_SN':str(d['dimension_index']),
                     'OBJ_NM':d['obj_name'],'ITM_ID':v['class_id'],'ITM_NM':v['class_name']} for v in d['values'])
    def get(url,params):
        calls.append(params['type']);return {'TBL':[{'TBL_NM':m['table_name']}],'ITM':rows,'PRD':[{'PRD_SE':'월','STRT_PRD_DE':'2020.01','END_PRD_DE':'2024.12'}]}[params['type']]
    catalog=LiveDerivedCatalog(store,SimpleNamespace(api_key='fixture',_get=get));p=plan(DerivedCatalogTools(store),'inverse')
    meta=catalog.validate_source_selection(p.sources[0]);assert meta['metadata_origin']=='actual_KOSIS_metadata_API'
    assert meta['periods'][0]['start_period']=='202001'
    catalog.get_table_metadata(m['table_id']);assert calls==['TBL','ITM','PRD']
    with pytest.raises(DerivedValidationError):catalog.get_table_metadata('DT_OUTSIDE_349')
    assert len(calls)==3

def test_api_metadata_failure_does_not_fall_back_to_local_truth():
    calls=[]
    def fail(*a):calls.append(1);raise TimeoutError()
    c=LiveDerivedCatalog(MetadataStore(),SimpleNamespace(api_key='fixture',_get=fail))
    with pytest.raises(DerivedValidationError) as exc:c.get_table_metadata('DT_513Y001')
    assert exc.value.failure_kind=='source_api_error' and len(calls)==1

def test_obj_id_keys_require_corrected_model_plan_not_silent_server_rewrite():
    c=DerivedCatalogTools(MetadataStore());p=plan(c,'lag',lag=1).model_dump();wrong=__import__('copy').deepcopy(p)
    m=c.get_table_metadata(p['sources'][0]['table_id']);wrong['sources'][0]['classifications']={d['obj_id']:p['sources'][0]['classifications'][d['mcp_param']] for d in m['dimensions'] if d['values']}
    client=Model([{'action':'metadata','table_id':m['table_id']},{'action':'plan','plan':wrong},{'action':'plan','plan':p},{'approved':True,'reason':'synthetic fixture'}])
    result=DerivedIndicatorPlanner(client,c).plan('2020년 1월부터 2020년 4월까지 경제심리지수 원계열의 직전 1시점 값')
    assert result['status']=='planned' and len(result['usage'])==4
    assert result['plan'].sources[0].classifications==p['sources'][0]['classifications']

def test_exhausted_credit_is_not_reported_as_source_data_absence():
    from openai_chart_client import OpenAIChartClient,OpenAIChartError
    response=SimpleNamespace(ok=False,status_code=429,json=lambda:{'error':{'code':'credit_balance_exhausted','type':'insufficient_quota'}})
    c=OpenAIChartClient(api_key='fixture',session=SimpleNamespace(post=lambda *a,**kw:response))
    with pytest.raises(OpenAIChartError,match='크레딧') as exc:c.request('system','input')
    assert exc.value.failure_kind=='model_provider_error'
