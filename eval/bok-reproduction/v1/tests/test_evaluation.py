import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))


def test_independent_calendar_calculation():
    from core import calculate
    assert calculate({'202401': '100', '202501': '110'}, 'yoy', 'M') == {'202401': None, '202501': '10.0'}
    assert calculate({'202401': '0', '202501': '110'}, 'yoy', 'M')['202501'] is None
    assert calculate({'202401': '1', '202403': '3'}, 'difference', 'M')['202403'] is None
    with pytest.raises(ValueError):
        calculate({'202401': 'NaN'}, 'level', 'M')


def test_provider_exact_identity_and_period():
    from core import FrozenProvider
    s = {'table_id': 'T', 'item_id': 'I', 'classifications': {'objL1': 'C'}, 'frequency': 'M', 'unit': '%', 'label': 'test',
         'points': [{'period': '202401', 'value': '1'}]}
    p = FrozenProvider([s])
    assert p.get_statistics('T', 'I', {'objL1': 'C'}, 'M', '202401', '202401')['row_count'] == 1
    with pytest.raises(ValueError):
        p.get_statistics('T', 'I', {'objL1': 'WRONG'}, 'M', '202401', '202401')
    with pytest.raises(ValueError):
        FrozenProvider([s, s])


def test_numeric_fail_closed():
    from core import compare_series
    s = {'table_id': 'T', 'item_id': 'I', 'classifications': {}, 'frequency': 'M', 'unit': '%',
         'points': [{'period': '202401', 'value': '1'}]}
    assert compare_series([s], [s])['passed']
    for wrong in [[], [s, s], [{**s, 'unit': '원'}], [{**s, 'points': []}],
                  [{**s, 'points': [{'period': '202401', 'value': '100'}]}],
                  [{**s, 'points': s['points'] * 2}]]:
        assert not compare_series([s], wrong)['passed']
    assert not compare_series([], [])['passed']


def test_review_binds_gold_and_observation():
    from core import digest_value, review_packet, review_valid
    c = {'id': 'C', 'input': {'query': 'q'}, 'expected': {'decision': 'resolved'}, 'group_id': 'G'}
    p = {'id': 'C', 'execution_status': 'observed', 'answer': 'a'}
    r = review_packet(c, p)
    assert not review_valid(c, p, r)
    r.update(reviewer='human', human_approved=True, scores={k: 2 for k in r['scores']},
             evidence_notes={k:'source evidence checked' for k in r['scores']},critical_error=False)
    assert review_valid(c, p, r)
    assert not review_valid({**c, 'expected': {'decision': 'clarify'}}, p, r)
    assert not review_valid(c, {**p, 'answer': 'changed'}, r)


def test_unexecuted_or_missing_never_passes():
    from core import score_case
    c = {'id': 'C', 'input': {'query': 'q'}, 'expected': {'decision': 'resolved', 'series': []}, 'review': {'human_approved': False}}
    assert score_case(c, None)['status'] == 'not_executed'
    assert score_case(c, {'execution_status': 'error'})['status'] == 'error'
    assert score_case(c, {'execution_status': 'observed', 'decision': 'resolved'})['status'] != 'passed'


def test_strict_json_and_year_quarter():
    from core import calculate, read_json_line, number, period
    for token in ('NaN','Infinity','-Infinity'):
        with pytest.raises(ValueError):
            read_json_line('{"value":'+token+'}')
    with pytest.raises(ValueError):
        number(True)
    with pytest.raises(ValueError):
        period('202413','M')
    assert calculate({'202304':'10','202401':'12'},'difference','Q')['2024Q1']=='2'


def test_blind_packets_and_duplicates():
    from evaluate import blind_packets, score
    c={'id':'C','input':{'query':'q'},'expected':{},'group_id':'G','required_facts':['f']}
    p={'id':'C','execution_status':'observed','profile':'sol','actual_models':['secret-model'],'trace':['private-model']}
    packets,mapping=blind_packets([c],[p])
    assert 'secret-model' not in str(packets)
    assert 'private-model' not in str(packets)
    assert mapping[0]['profile']=='sol'
    with pytest.raises(ValueError):
        score([c],[p,p],{},[])


def test_paid_execution_is_explicit_and_never_offline_fallback(tmp_path):
    from evaluate import run
    with pytest.raises(ValueError):
        run([],tmp_path/'missing.json','model_fixed')
    with pytest.raises(ValueError):
        run([],tmp_path/'missing.json','live')


def test_stale_oracle_rejected():
    from core import digest_value
    from evaluate import score
    c={'id':'C','category':'derived','group_id':'G','input':{'query':'q'},'expected':{'oracle_sha256':'old'}}
    p={'id':'C','execution_status':'observed','input_sha256':digest_value(c['input'])}
    with pytest.raises(ValueError):
        score([c],[p],{'C':[]},[])


def test_conflicting_second_review_is_pending_and_not_aggregated():
    from core import digest_value, review_packet, RUBRIC
    from evaluate import score
    c={'id':'C','category':'recovery','group_id':'G','input':{'query':'q'},
       'expected':{'decision':'recoverable_failure','requires_numeric':False,'observed_contract':{'input_preserved':True}}}
    c['review']={'human_approved':True,'reviewer':'gold','input_sha256':digest_value(c['input']),
                 'expected_sha256':digest_value(c['expected'])}
    p={'id':'C','execution_status':'observed','decision':'recoverable_failure','input_preserved':True,
       'input_sha256':digest_value(c['input'])}
    first=review_packet(c,p)
    first.update(reviewer='first',human_approved=True,scores={k:2 for k in RUBRIC},critical_error=False,
                 evidence_notes={k:'checked evidence' for k in RUBRIC})
    second={**first,'reviewer':'second','scores':{k:0 for k in RUBRIC},'critical_error':True}
    first['second_review']=second
    report=score([c],[p],{},[first])
    assert report['quantitative'][0]['status']=='pending_second_review'
    assert report['qualitative']['facts']['n']==0


def test_unexecuted_not_counted_as_observed():
    from core import summary
    report=summary([{'id':'C'}],[{'execution_status':'not_executed'}],
                   [{'status':'not_executed','quantitative_pass':False}])
    assert report['observed']==0


def test_rendered_values_not_only_internal_series():
    from core import figure_consistent
    s={'label':'test','frequency':'M','points':[{'period':'202401','value':'1'}]}
    p={'series':[s],'plotly_figure':{'data':[{'name':'test','type':'scatter','mode':'lines','x':['2024-01'],'y':[1]}]}}
    assert figure_consistent(p)
    p['plotly_figure']['data'][0]['y']=[100]
    assert not figure_consistent(p)


def test_calculated_values_require_real_source_and_units():
    from core import digest_value, score_case
    source={'table_id':'T','item_id':'I','classifications':{},'frequency':'M'}
    expected={'points':[{'period':'202501','value':'10'}],'unit':'%','frequency':'M','sources':[source]}
    c={'id':'C','input':{'query':'q'},'expected':{'decision':'resolved','requires_numeric':True}}
    p={'execution_status':'observed','decision':'resolved','input_sha256':digest_value(c['input']),
       'calculated_points':[{'period':'202501','value':10}],'output_unit':'%','output_frequency':'M',
       'statistics_requests':[source]}
    assert score_case(c,p,expected)['quantitative_pass']
    p['statistics_requests']=[]
    assert not score_case(c,p,expected)['quantitative_pass']


def test_compare_cannot_hide_regression_or_mix_source_versions():
    import copy
    from core import RUBRIC
    from evaluate import compare
    base={'case_contracts_sha256':'same','provider_sha256':['same'],
          'categories':{'source_subset':{'attempts':1,'quantitative_pass':1}},
          'quantitative':[{'id':'C','status':'passed','quantitative_pass':True,'critical_error':False}],
          'qualitative':{k:{'mean':2} for k in RUBRIC}}
    candidate=copy.deepcopy(base)
    assert compare(base,candidate)['adoption']=='eligible_for_human_decision'
    candidate['quantitative'][0]['quantitative_pass']=False
    assert compare(base,candidate)['regressions']==['C']
    candidate['provider_sha256']=['different']
    with pytest.raises(ValueError):
        compare(base,candidate)


def test_mock_model_adapter_gets_input_only_and_actual_model_checked(tmp_path,monkeypatch):
    import evaluate
    from core import digest_file, write
    write(tmp_path/'profiles.json',{'seed':42,'baseline':{'main_model':'main','text_model':'cheap'}})
    write(tmp_path/'provider.json',{'series':[]})
    write(tmp_path/'manifest.json',{'local_provider_sha256':digest_file(tmp_path/'provider.json')})
    monkeypatch.setattr(evaluate,'BASE',tmp_path)
    adapter=tmp_path/'adapter.py'
    adapter.write_text("def run_input(payload, provider, profile):\n    assert set(payload)=={'query'}\n    return {'execution_status':'observed','actual_models':[{'purpose':'summary','model':'cheap'}]}\n")
    case={'id':'C','input':{'query':'q'},'expected':{'private_gold':'not allowed'},'evidence':{'secret':'not allowed'}}
    result=evaluate.run([case],tmp_path/'provider.json','model_fixed',adapter,allow_paid=True)
    assert result[0]['execution_status']=='observed'
    adapter.write_text("def run_input(payload, provider, profile):\n    return {'execution_status':'observed','actual_models':[{'purpose':'summary','model':'WRONG'}]}\n")
    result=evaluate.run([case],tmp_path/'provider.json','model_fixed',adapter,allow_paid=True)
    assert result[0]['execution_status']=='unobserved'
