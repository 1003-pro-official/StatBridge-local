"""Reject range captions as headers without accepting misplaced numeric cells."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('bok_v2_xlsx_evaluator',Path(__file__).parents[1]/'scripts/evaluate.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_range_caption_is_not_a_period_header():
    assert not module._period_matches('월별 · 2022-01 ~ 2022-12','202201','M')
    assert not module._period_matches('2022Q1 ~ 2022Q4','2022Q1','Q')
    assert not module._period_matches('2022년부터 2024년까지','2022','Y')
    assert module._period_matches('2022-01','202201','M')
    assert module._period_matches('1999-12','199912','M')
    assert module._period_matches('2022년 1분기','2022Q1','Q')


def test_export_caption_does_not_make_valid_headers_ambiguous():
    expected=[{'frequency':'M','points':[{'period':'202201','value':'7'},{'period':'202202','value':'9'}]}]
    cells={'A1':{'text':'월별 · 2022-01 ~ 2022-02'},'B2':{'text':'2022-01'},
           'C2':{'text':'2022-02'},'B3':{'value':'7'},'C3':{'value':'9'}}
    module._check_xlsx_cells(expected,cells)
    cells['B2'],cells['C2']=cells['C2'],cells['B2']
    with pytest.raises(ValueError,match='numeric values'):
        module._check_xlsx_cells(expected,cells)


def test_missing_header_stays_a_failure():
    expected=[{'frequency':'Y','points':[{'period':'2022','value':'7'}]}]
    with pytest.raises(ValueError,match='headers'):
        module._check_xlsx_cells(expected,{'A1':{'text':'2022~2024'},'B2':{'value':'7'}})


def test_stacked_series_sections_use_each_numeric_cell_once():
    expected=[{'frequency':'M','points':[{'period':'202201','value':'7'},{'period':'202202','value':'9'}]},
              {'frequency':'M','points':[{'period':'202201','value':'3'},{'period':'202202','value':'4'}]}]
    cells={'B2':{'text':'2022-01'},'C2':{'text':'2022-02'},
           'B3':{'value':'7'},'C3':{'value':'9'},
           'B5':{'text':'2022-01'},'C5':{'text':'2022-02'},
           'B6':{'value':'3'},'C6':{'value':'4'}}
    module._check_xlsx_cells(expected,cells)
    cells['B6']={'value':'30'}
    with pytest.raises(ValueError,match='numeric values'):
        module._check_xlsx_cells(expected,cells)


def test_duplicate_observations_cannot_be_hidden_by_dictionary_indexing():
    s={'table_id':'T','item_id':'I','classifications':{},'frequency':'M','unit':'건',
       'points':[{'period':'202201','value':'7'}]}
    assert module.compare([s],[s])['passed']
    assert not module.compare([s],[s,s])['passed']
    assert not module.compare([s],[{**s,'points':s['points']*2}])['passed']
