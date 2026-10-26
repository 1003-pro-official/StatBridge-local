"""Explicit provider routing, synthetic IO, no external observation fixtures."""
import copy
import json
from types import SimpleNamespace as NS
import pytest

from derived_provider_scope import explicit_provider_check
from derived_support_policy import assessment_scope
from expression_tree_validator import DerivedValidationError

MIXED='2020년부터 2023년까지 한국은행의 한국 연간 명목 GDP를 세계은행의 한국 연간 인구로 나눠 1인당 명목 GDP를 계산하고 그래프로 보여줘. GDP는 원화 기준으로 계산해줘.'
EXTERNAL='2020년부터 2023년까지 세계은행의 한국 연간 이산화탄소 배출량을 세계은행의 한국 연간 인구로 나눠 1인당 이산화탄소 배출량을 계산하고 그래프로 보여줘.'


def req(name,provider):
    return {'name':name,'requested_provider':provider,'search_terms':['국내총생산'],
            'periods':[{'label':'조회','start':'2020','end':'2023','frequency':'Y'}],
            'unit':'명' if '인구' in name else '원','quotation':''}


def setup(external=False):
    inputs=[req('세계은행 한국 연간 이산화탄소 배출량','external') if external else req('한국은행 한국 연간 명목 GDP','bok_kosis'),
            req('세계은행 한국 연간 인구','external')]
    responses=[{'inputs':inputs,'questions':[],'calculation_guide':'명목 GDP(원) ÷ 인구(명)'}]
    if not external:responses.append({'table_id':'DT_SYNTH','item_id':'I','classifications':[],'reason':'일치'})
    calls=[]
    def ask(*a,**kw):calls.append('model');return json.dumps(responses.pop(0),ensure_ascii=False),{'model':'synthetic'}
    meta={'table_id':'DT_SYNTH','table_name':'연간 명목 국내총생산','items':[{'item_id':'I','item_name':'총계'}],
          'dimensions':[],'frequencies':['Y'],'periods':[{'frequency':'Y','start_period':'2000','end_period':'2025'}],
          'comments':[],'metadata_origin':'actual_KOSIS_metadata_API'}
    def metadata(tid):calls.append('metadata');return copy.deepcopy(meta)
    cat=NS(approved={'DT_SYNTH'},store=NS(get=lambda t:NS(canonical_dict=lambda:copy.deepcopy(meta))),
           get_table_metadata=metadata,search_approved_tables=lambda *a,**kw:[{'table_id':'DT_SYNTH'}],
           validate_source_selection=lambda s:meta)
    def fetch(**kw):calls.append('observations');assert kw['allow_fallback'] is False;return {'synthetic':True}
    def ensure():raise AssertionError('Must not start global inventory')
    r=NS(catalog=cat,planner=NS(client=NS(request=ask,supports_json_schema=True)),
         api_inventory=NS(ensure=ensure),gateway=NS(get_statistics=fetch),
         input_series=lambda s,r:NS(values={'2020':1,'2021':2,'2022':3,'2023':4},unit='원'))
    return r,calls,responses


def test_all_explicit_external_is_unsupported_without_inventory_or_api():
    r,calls,_=setup(True);out=explicit_provider_check(r,EXTERNAL)
    assert out['unsupported'] and out['recovery']['issue']=='unsupported'
    assert '지원하지 않는 범위' in out['summary'] and '다시 작성' in out['summary']
    assert not out.get('supplement') and calls==['model']


def test_mixed_preserves_requested_provider_and_verifies_only_api_candidate():
    r,calls,_=setup();out=explicit_provider_check(r,MIXED);a=out['availability']
    assert assessment_scope(a)=='mixed' and a['checkedTables']==1
    assert [s['status'] for s in a['sources']]==['available','not_found']
    assert 'SP.POP.TOTL' in str(a['sources'][1]['guidance'])
    assert a['sources'][1]['periods'][0]['frequency']=='Y' and a['sources'][1]['unit']=='명'
    assert calls==['model','metadata','model','observations']
    assert a['calculationExecuted'] is False


@pytest.mark.parametrize('kind',['source_api_error','source_metadata_incomplete'])
def test_failed_api_or_missing_unit_never_opens_upload(kind):
    r,_,_=setup()
    def fail(*a):raise DerivedValidationError('확인 실패',failure_kind=kind)
    r.input_series=fail
    a=explicit_provider_check(r,MIXED)['availability']
    assert assessment_scope(a)=='verification_pending' and not any(s['status']=='available' for s in a['sources'])


def test_ambiguous_provider_is_not_declared_external_only():
    r,calls,responses=setup(True);responses[0]['inputs'][0]['requested_provider']='unspecified'
    assert explicit_provider_check(r,EXTERNAL) is None and calls==['model']


def test_requirements_cache_never_reuses_observations():
    r,calls,responses=setup();explicit_provider_check(r,MIXED)
    responses.append({'table_id':'DT_SYNTH','item_id':'I','classifications':[],'reason':'일치'})
    explicit_provider_check(r,MIXED)
    assert calls.count('observations')==2 and calls.count('model')==3


def test_partial_candidate_rejection_is_not_global_absence():
    r,_,responses=setup();responses[-1].update(table_id='',item_id='')
    assert assessment_scope(explicit_provider_check(r,MIXED)['availability'])=='verification_pending'
