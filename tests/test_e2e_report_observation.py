"""Synthetic observations only; no case contracts or gold labels."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('e2e_observations',Path(__file__).parents[1]/'eval/e2e-contract-review/observations.py')
observe=importlib.util.module_from_spec(spec);spec.loader.exec_module(observe)

def series():
    return [{'sourceIdentity':{'table_id':'actual','item_id':'observed',
                              'classifications':{'objL1':'a'},'frequency':'M'},
             'unit':'%','points':[{'date':'202501','value':1}]}]

def test_paragraph_response_and_actual_identity():
    result=observe.report_observation(series(),{'paragraphs':['첫 문단이다.','둘째 문단이다.'],'claims':[{'value':1}]})
    assert result['report']['text']=='첫 문단이다.\n\n둘째 문단이다.'
    assert result['series'][0]['table_id']=='actual'
    assert result['series'][0]['points']==[{'period':'202501','value':1}]

@pytest.mark.parametrize('key',['answer','markdown','text'])
def test_existing_text_responses(key):
    assert observe.report_observation(series(),{key:'설명이다.'})['report']['text']=='설명이다.'

def test_missing_provenance_cannot_be_replaced_with_expected():
    data=series();data[0].pop('sourceIdentity');data[0]['sourceId']='table'
    with pytest.raises(ValueError,match='sourceIdentity'):observe.report_observation(data,{'answer':'설명이다.'})

@pytest.mark.parametrize('response',[{}, {'paragraphs':[]},{'paragraphs':[{'text':'unsupported'}]},{'answer':' '}])
def test_missing_report_text_is_not_success(response):
    with pytest.raises(ValueError):observe.report_observation(series(),response)
