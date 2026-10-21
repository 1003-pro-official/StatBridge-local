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
    assert report['quantitative'][0]['response_review_approved'] is False
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
          'execution_context':{'environment':'model_fixed','implementation_sha256':{'app.py':'same'},'evaluation_code_sha256':{'core.py':'same'}},
          'categories':{'source_subset':{'attempts':1,'quantitative_pass':1}},
          'quantitative':[{'id':'C','status':'passed','quantitative_pass':True,'critical_error':False,
                           'gold_approved':True,'response_review_approved':True}],
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
    assert result[0]['implementation_sha256']['src/agent/report_summary.py']
    assert result[0]['evaluation_code_sha256']['runtime_adapter']==digest_file(adapter)
    adapter.write_text("def run_input(payload, provider, profile):\n    return {'execution_status':'observed','actual_models':[{'purpose':'summary','model':'WRONG'}]}\n")
    result=evaluate.run([case],tmp_path/'provider.json','model_fixed',adapter,allow_paid=True)
    assert result[0]['execution_status']=='unobserved'


def test_adapter_failure_preserves_other_cases(tmp_path, monkeypatch):
    import evaluate
    from core import digest_file, write
    write(tmp_path/'profiles.json', {'seed':42,'baseline':{'main_model':'main','text_model':'cheap'}})
    write(tmp_path/'provider.json', {'series':[]})
    write(tmp_path/'manifest.json', {'local_provider_sha256':digest_file(tmp_path/'provider.json')})
    monkeypatch.setattr(evaluate, 'BASE', tmp_path)
    adapter=tmp_path/'adapter.py'
    adapter.write_text("def run_input(payload, provider, profile):\n    if payload['query']=='bad': raise TimeoutError('request timed out')\n    return {'execution_status':'observed','actual_models':[{'purpose':'summary','model':'cheap'}]}\n")
    cases=[{'id':q,'input':{'query':q}} for q in ('bad','good')]
    result=evaluate.run(cases,tmp_path/'provider.json','model_fixed',adapter,allow_paid=True)
    by_id={p['id']:p for p in result}
    assert by_id['bad']['execution_status']=='error'
    assert by_id['bad']['error_type']=='TimeoutError'
    assert by_id['good']['execution_status']=='observed'


def test_preflight_rejects_changed_or_escaped_attachment(tmp_path, monkeypatch):
    import evaluate
    from core import digest_file
    monkeypatch.setattr(evaluate, 'ROOT', tmp_path)
    attachment=tmp_path/'.venv/cache/reference.png'
    attachment.parent.mkdir(parents=True)
    attachment.write_bytes(b'fixture')
    payload={'setup':{'source_snapshot_sha256':'snapshot','attachment':{
        'path':'.venv/cache/reference.png','sha256':digest_file(attachment)}}}
    evaluate.preflight_input(payload,'snapshot')
    attachment.write_bytes(b'changed')
    with pytest.raises(ValueError,match='attachment'):
        evaluate.preflight_input(payload,'snapshot')
    payload['setup']['attachment']['path']='../../outside.png'
    with pytest.raises(ValueError,match='attachment'):
        evaluate.preflight_input(payload,'snapshot')


def test_component_executes_product_calculator_without_model():
    from component_adapter import run_input
    payload={'query':'전기비', 'setup':{'component_boundary':'synthetic calculator boundary, not standalone supported product analysis',
        'user_rows':[{'period':'202401','value':0},{'period':'202402','value':10},
                     {'period':'202403','value':None},{'period':'202405','value':20},{'period':'202406','value':30}]}}
    result=run_input(payload, None, {})
    assert result['execution_status']=='observed'
    assert result['model_called'] is False
    assert result['controlled_execution_evidence']['implementation_sha256']
    assert result['calculated_points']==[{'period':p,'value':v} for p,v in
        [('202401',None),('202402',None),('202403',None),('202405',None),('202406',50.0)]]
    assert result['statistics_requests']==[]
    assert run_input({'query':'unsupported'},None,{})['execution_status']=='not_executed'


def test_component_injects_invalid_fact_ids_into_product_summary():
    from component_adapter import run_input
    from core import FrozenProvider
    source={'table_id':'T','item_id':'I','classifications':{},'frequency':'M','unit':'연%',
            'label':'금리','points':[{'period':'202607','value':'3'},{'period':'202608','value':'2.5'}]}
    provider=FrozenProvider([source])
    payload={'query':'현재 자료의 관측 사실을 요약해줘.', 'setup':{
        'fault':{'boundary':'report_summary.model_response','kind':'invalid_fact_ids','response':{'fact_ids':['unknown']}},
        'summary_sources':[{'table_id':'T','item_id':'I','classifications':{},'frequency':'M',
                            'start_period':'202607','end_period':'202608'}]}}
    result=run_input(payload,provider,{})
    assert result['execution_status']=='observed'
    assert result['observed_contract']=={'facts_supported':True,'request_satisfied':True}
    assert result['controlled_execution_evidence']['injection_calls']==1
    assert result['controlled_execution_evidence']['summary']['source']=='rules'
    assert '0.5 %p' in result['explanation']
    assert len(result['statistics_requests'])==1


def test_supplemental_contexts_include_requested_comparisons():
    from core import BASE, rows
    cases={c['id']:c for c in rows(BASE/'supplemental.jsonl')}
    assert '중소기업' in cases['SUP-followup-02']['input']['setup']['initial_query']
    for case_id in ('SUP-followup-03','SUP-summary_style-02'):
        query=cases[case_id]['input']['setup']['initial_query']
        assert '대기업' in query and '중소기업' in query
    assert '전년동월' in cases['SUP-report-02']['input']['setup']['initial_query']


def test_nested_adapter_contract_is_scored_and_false_is_not_overridden():
    from core import score_case, digest_value
    case={'id':'C','input':{'query':'q'},'expected':{'decision':'resolved','requires_numeric':False,
        'observed_contract':{'facts_supported':True}}}
    prediction={'execution_status':'observed','decision':'resolved','input_sha256':digest_value(case['input']),
                'observed_contract':{'facts_supported':True}}
    assert score_case(case,prediction)['quantitative_pass']
    prediction.update(facts_supported=True,observed_contract={'facts_supported':False})
    assert not score_case(case,prediction)['quantitative_pass']


def test_not_executed_cases_do_not_inflate_attempt_count():
    from core import summary
    report=summary([{'id':'A'},{'id':'B'}],
        [{'execution_status':'observed'},{'execution_status':'not_executed'}],
        [{'status':'pending_review','quantitative_pass':True},{'status':'not_executed','quantitative_pass':False}])
    assert report['attempted']==1


def test_failed_case_still_requires_gold_approval_for_comparison():
    import copy
    from core import digest_value, review_packet, RUBRIC
    from evaluate import score, compare
    case={'id':'C','group_id':'G','category':'recovery','input':{'query':'q'},
          'expected':{'decision':'recoverable_failure','requires_numeric':False,'observed_contract':{'input_preserved':True}},
          'review':{'human_approved':False}}
    prediction={'id':'C','execution_status':'observed','decision':'recoverable_failure',
                'input_sha256':digest_value(case['input']),'observed_contract':{'input_preserved':False},
                'environment':'model_fixed','profile':'baseline','implementation_sha256':{'app.py':'same'},
                'evaluation_code_sha256':{'core.py':'same'},'provider_sha256':'same'}
    review=review_packet(case,prediction)
    review.update(reviewer='first',human_approved=True,scores={k:1 for k in RUBRIC},critical_error=False,
                  evidence_notes={k:'checked' for k in RUBRIC})
    review['second_review']={**review,'reviewer':'second','second_review':None}
    report=score([case],[prediction],{},[review])
    assert report['quantitative'][0]['status']=='failed'
    assert compare(report,copy.deepcopy(report))['adoption']=='pending_review_or_execution'
    case['review']={'human_approved':True,'reviewer':'gold','input_sha256':digest_value(case['input']),
                    'expected_sha256':digest_value(case['expected'])}
    approved=score([case],[prediction],{},[review])
    assert approved['quantitative'][0]['gold_approved'] is True
    assert compare(approved,copy.deepcopy(approved))['adoption']=='eligible_for_human_decision'
    approved['quantitative'][0].pop('gold_approved')
    assert compare(approved,copy.deepcopy(approved))['adoption']=='pending_review_or_execution'
    case['input']['query']='changed'
    stale=score([case],[prediction],{},[review])
    assert stale['quantitative'][0]['gold_approved'] is False


@pytest.mark.parametrize('change', ['environment','implementation_sha256','evaluation_code_sha256','missing'])
def test_comparison_rejects_different_or_missing_execution_context(change):
    import copy
    from core import RUBRIC
    from evaluate import compare
    report={'case_contracts_sha256':'same','provider_sha256':['same'],
            'execution_context':{'environment':'model_fixed','implementation_sha256':{'app.py':'same'},
                                 'evaluation_code_sha256':{'core.py':'same'}},
            'categories':{'derived':{'attempts':1,'quantitative_pass':1}},
            'quantitative':[{'id':'C','status':'passed','quantitative_pass':True,'critical_error':False,
                             'gold_approved':True,'response_review_approved':True}],
            'qualitative':{k:{'mean':2} for k in RUBRIC}}
    candidate=copy.deepcopy(report)
    if change=='missing':
        report.pop('execution_context');candidate.pop('execution_context')
    else:
        candidate['execution_context'][change]='changed'
    with pytest.raises(ValueError,match='execution context'):
        compare(report,candidate)


def test_numeric_review_packet_includes_values_and_safe_calculation_evidence():
    from evaluate import blind_packets
    case={'id':'C','group_id':'G','input':{'query':'q'},'expected':{}}
    prediction={'id':'C','execution_status':'observed','calculated_points':[{'period':'202606','value':50}],
                'output_unit':'%','output_frequency':'M','statistics_requests':[{'table_id':'T'}],
                'controlled_execution_evidence':{'issues':[{'period':'202605','reason':'missing'}],
                    'calendar_grid':{'202605':None,'202606':50},'actual_models':['hidden-model']}}
    packet=blind_packets([case],[prediction])[0][0]
    assert packet['response']['calculated_points']==prediction['calculated_points']
    assert packet['response']['output_unit']=='%'
    assert packet['response']['calculation_evidence']['issues']==prediction['controlled_execution_evidence']['issues']
    assert 'hidden-model' not in str(packet)


def test_review_mapping_collision_preserves_existing_file(tmp_path,monkeypatch):
    import evaluate
    from core import write_rows
    monkeypatch.setattr(evaluate,'ROOT',tmp_path)
    cache=tmp_path/'.venv/cache'
    cache.mkdir(parents=True)
    output=cache/'packet.jsonl'
    mapping=output.with_suffix('.mapping.json')
    mapping.write_text('existing reviewer mapping')
    cases=tmp_path/'cases.jsonl';predictions=tmp_path/'predictions.jsonl'
    write_rows(cases,[]);write_rows(predictions,[])
    monkeypatch.setattr(sys,'argv',['evaluate.py','review','--cases',str(cases),'--observations',str(predictions),'--output',str(output)])
    with pytest.raises(ValueError,match='overwrite'):
        evaluate.main()
    assert mapping.read_text()=='existing reviewer mapping'
    assert not output.exists()


def test_scoring_rejects_mixed_product_versions():
    from evaluate import score
    case={'id':'C','group_id':'G','category':'derived','input':{'query':'q'},'expected':{}}
    predictions=[{'id':'C','repeat':i,'execution_status':'not_executed','environment':'model_fixed','profile':'sol',
                  'implementation_sha256':{'app.py':str(i)},'evaluation_code_sha256':{'core.py':'same'}} for i in (0,1)]
    with pytest.raises(ValueError,match='execution context'):
        score([case],predictions,{},[])
