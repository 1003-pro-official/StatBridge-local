"""Synthetic contract regressions; no evaluation case or answer is imported."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('e2e_review_contract',Path(__file__).parents[1]/'eval/e2e-contract-review/review_contract.py')
review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)

@pytest.mark.parametrize('value,freq,wanted',[
    ('2025-12-31','Q','2025Q4'),('2025-03-31','Q','2025Q1'),
    ('2025-06-30','Q','2025Q2'),('2025-09-30','Q','2025Q3'),
    ('202504','Q','2025Q4'),('2025Q4','Q','2025Q4'),
    ('20251231','M','202512'),('2025','A','2025'),
    ('2025-12-31','Y','2025'),('2025-12-31','H','2025S2')])
def test_dates_and_api_periods(value,freq,wanted):
    assert review.period(value,freq)==wanted

@pytest.mark.parametrize('value,freq',[('202513','M'),('202505','Q'),('2025-02-30','Q'),('2025','M')])
def test_invalid_periods_fail_closed(value,freq):
    with pytest.raises(ValueError):review.period(value,freq)

def test_spread_is_between_two_sources_and_propagates_null():
    left=[{'period':'202501','value':'6.1'},{'period':'202502','value':None}]
    right=[{'period':'202501','value':'7.2'},{'period':'202502','value':'8'}]
    assert review.subtract_sources(left,right,'M')==[{'period':'202501','value':'-1.1'},{'period':'202502','value':None}]
    with pytest.raises(ValueError):review.subtract_sources(left,right[:1],'M')

def fixture():
    source={'alias':'input','table_id':'synthetic','item_id':'index','classifications':{},'frequency':'M'}
    expected={'operation':'growth','sources':[source],'periods':['202501','202502']}
    pred={'decision':'resolved','response':{'derivedEvidence':{
        'plan':{'sources':[source],'outputs':[{'node':'out'}],
                'nodes':[{'id':'out','operator':'pct_change','inputs':['input']}]},
        'issues':[{'node':'out','period':'202501','reason':'missing_input_or_history'}]}},
        'series':[{'unit':'%','points':[{'period':'202502','value':'2'}]}]}
    oracle={'points':[{'period':'202501','value':None},{'period':'202502','value':'2'}]}
    return pred,expected,oracle

def test_derived_schema_and_evidenced_missing_history():
    assert review.review_derived(*fixture())['status']=='pending_review'
    p,e,o=fixture();p['series'][0]['unit']='원'
    assert review.review_derived(p,e,o)['status']=='failed'

@pytest.mark.parametrize('mutation',['source','value','missing','extra','operation','nonfinite'])
def test_no_false_pass(mutation):
    p,e,o=fixture()
    if mutation=='source':p['response']['derivedEvidence']['plan']['sources'][0]={**e['sources'][0],'item_id':'other'}
    if mutation=='value':p['series'][0]['points'][0]['value']='3'
    if mutation=='missing':p['response']['derivedEvidence']['issues']=[]
    if mutation=='extra':p['series'][0]['points'].append({'period':'202503','value':'2'})
    if mutation=='operation':p['response']['derivedEvidence']['plan']['nodes'][0]['operator']='yoy_pct'
    if mutation=='nonfinite':p['series'][0]['points'][0]['value']='NaN'
    assert review.review_derived(p,e,o)['status']=='failed'
