"""Synthetic data verifies the reference answer structure, never its figures."""
import json

from statistical_question import SYSTEM, answer_question
from test_statistical_question import item, text


def rates():
    return [item('신규취급액 · 대출평균', ('4.6', '4.5')) | {'tableName': '예금은행 대출금리(신규취급액 기준)'},
            item('신규취급액 · 저축성수신', ('3.3', '3.1')) | {'tableName': '예금은행 수신금리(신규취급액 기준)'}]


def test_reference_style_connects_levels_changes_and_rate_gap_without_model():
    answer = answer_question('대출금리와 수신금리의 하락 속도가 같은가?', rates())
    assert answer['status'] == 'answered'
    assert len(answer['paragraphs']) == 1
    assert '0.1 %p' in text(answer) and '0.2 %p' in text(answer)
    assert '1.3 %p에서 1.4 %p' in text(answer)
    assert '하락 속도에는 차이' in text(answer)
    assert any(f['formula'] == 'left_target - right_target' for f in answer['facts'])


def test_compound_question_answers_available_part_and_explains_missing_part():
    answer = answer_question('대출금리와 수신금리의 하락 속도가 같은가? 전체 증가를 어떤 항목이 주도했는가?', rates())
    assert answer['status'] == 'partially_answered'
    assert [s['status'] for s in answer['sections']] == ['answered', 'insufficient_data']
    assert '하락 속도에는 차이' in text(answer)
    assert answer['requiredData'] and '금리' in ' '.join(answer['sections'][1]['paragraphs'])
    keys = {f['id'] for f in answer['facts']}
    assert all(set(c['fact_ids']) <= keys for c in answer['claims'])


def test_missing_rate_names_specific_required_series():
    answer = answer_question('대출금리와 수신금리의 하락 속도가 같은가?', rates()[1:])
    assert answer['status'] == 'insufficient_data'
    assert '대출금리' in ' '.join(answer['requiredData'])
    assert not answer['facts']


def test_actual_source_annual_rate_unit_spellings_are_equivalent():
    data = rates()
    data[0]['unit'] = '연%'
    data[1]['unit'] = '연리%'
    answer = answer_question('대출금리와 수신금리의 하락 속도가 같은가?', data)
    assert answer['status'] == 'answered'
    assert '1.3 %p에서 1.4 %p' in text(answer)
    assert [s['unit'] for s in answer['scope']['series']] == ['연%', '연리%']
    data[1]['unit'] = '월%'
    assert answer_question('대출금리와 수신금리의 하락 속도가 같은가?', data)['status'] == 'insufficient_data'


def test_additive_components_support_concentration_sentence():
    data = [item('가계대출', ('120', '125'), '조원'), item('주택담보대출', ('90', '97'), '조원'),
            item('기타대출', ('30', '28'), '조원')]
    answer = answer_question('전체 증가를 어떤 항목이 주도했는가?', data)
    assert answer['status'] == 'answered'
    assert len(answer['paragraphs']) == 1
    assert '주택담보대출' in text(answer) and '집중' in text(answer)
    assert any(f['formula'] == 'sum(component_changes) == total_change' for f in answer['facts'])


def test_reference_figures_are_not_runtime_evidence_and_metadata_has_no_values():
    class InspectPlanner:
        configured = True
        def request(self, system, context, **kwargs):
            assert '예시' in system and 'speed' in system and 'forecast' in system
            series = json.loads(context)['series']
            assert series[0]['tableName'].startswith('예금은행 대출금리')
            assert not any('points' in s or 'value' in s for s in series)
            return json.dumps({'analysis': 'speed', 'series_ids': [0, 1]}), {}
    answer = answer_question('하락 속도가 같은가?', rates(), InspectPlanner())
    assert answer['status'] == 'answered'
    assert '4.40' not in text(answer) and '4.5' in text(answer)


def test_model_failure_retains_named_rate_comparison():
    class BrokenPlanner:
        configured = True
        def request(self, *args, **kwargs):
            raise RuntimeError('synthetic model outage')
    answer = answer_question('대출금리와 수신금리의 하락 속도가 같은가?', rates(), BrokenPlanner())
    assert answer['status'] == 'answered' and answer['method'] == 'rules'
    assert answer['limitations']


def test_reference_style_never_confirms_an_unmatched_total_or_a_spurious_sum():
    data = [item('전체 대출', ('120', '125'), '조원'), item('주택담보대출', ('90', '97'), '조원'),
            item('기타대출', ('20', '28'), '조원')]
    answer = answer_question('전체 증가를 어떤 항목이 주도했는가?', data)
    assert '집중되었습니다' not in text(answer)
    assert '합계 관계를 확인해야' in text(answer)
    assert not any(f['formula'].startswith('sum(') for f in answer['facts'])


def test_two_answered_questions_keep_distinct_fact_ids():
    answer = answer_question('대출금리와 수신금리의 하락 속도가 같은가? 대출금리와 수신금리의 차이는?', rates())
    assert answer['status'] == 'answered' and len(answer['sections']) == 2
    keys = [f['id'] for f in answer['facts']]
    assert len(keys) == len(set(keys))
    assert all(set(c['fact_ids']) <= set(keys) for c in answer['claims'])


def test_equal_component_changes_never_single_out_one_leader():
    data = [item('가계대출', ('100', '104'), '조원'), item('주택담보대출', ('70', '72'), '조원'),
            item('기타대출', ('30', '32'), '조원')]
    answer = answer_question('전체 증가를 어떤 항목이 주도했는가?', data)
    assert '집중되었습니다' not in text(answer)
    assert '어느 한 항목만 주도했다고 판단할 수 없습니다' in text(answer)


def test_model_cannot_replace_a_requested_rate_with_another_existing_series():
    from test_statistical_question import Planner
    data = rates() + [item('다른 금리', ('6.0', '5.5'))]
    answer = answer_question('대출금리와 수신금리의 하락 속도가 같은가?', data, Planner('speed', (0, 2)))
    assert answer['status'] == 'answered' and answer['method'] == 'rules'
    assert '다른 금리' not in text(answer)
    assert '1.3 %p에서 1.4 %p' in text(answer)


def test_partial_answer_endpoint_receives_table_metadata_and_keeps_snapshot(monkeypatch):
    import copy
    import bridge_api as api
    from authenticated_client import TestClient
    from output_schema import ChartSpec

    plans = [{'table_id': 'SYNTHETIC_LOAN', 'table_name': '예금은행 대출금리(신규취급액 기준)', 'frequency': 'M'},
             {'table_id': 'SYNTHETIC_DEPOSIT', 'table_name': '예금은행 수신금리(신규취급액 기준)', 'frequency': 'M'}]
    rows = [{'PRD_DE': p['date'], 'DT': p['value'], 'ITM_NM': s['label'], 'UNIT_NM': s['unit'],
             '_SOURCE_SERIES_ID': plan['table_id'], '_FREQUENCY': 'M'}
            for plan, s in zip(plans, rates()) for p in s['points']]
    session = {'result': {'api_plans': plans, 'execution': {'rows': rows}},
               'output': {'editVersion': 0, 'chartState': ChartSpec().model_dump(mode='json'), 'evidence': []}}
    monkeypatch.setitem(api.EDIT_SESSIONS, 'question-examples', session)
    monkeypatch.setattr(api.agent.output_agent, 'ncp_client', None)
    with TestClient(api.app) as client:
        before = copy.deepcopy(session)
        response = client.post('/api/report/question', json={
            'edit_session_id': 'question-examples', 'revision': 0,
            'question': '대출금리와 수신금리의 하락 속도가 같은가? 전체 증가를 어떤 항목이 주도했는가?'})
        assert response.status_code == 200, response.text
        answer = response.json()
        assert answer['status'] == 'partially_answered'
        assert len(answer['sections']) == 2 and answer['facts']
        assert '하락 속도에는 차이' in text(answer)
        assert session == before


def test_focused_speed_compares_signed_changes_before_ranking():
    from focused_question_answer import focused_answer
    answer={'status':'answered','question':'두 지표의 변화 속도가 같은가?', 'facts':[
        {'id':'a','formula':'target - baseline','result':'1','unit':'%p','observations':[{'label':'A'}]},
        {'id':'b','formula':'target - baseline','result':'-1','unit':'%p','observations':[{'label':'B'}]}], 'claims':[], 'limitations':[]}
    result=focused_answer(answer)
    assert '방향 또는 변화폭이 달라' in result['paragraphs'][0]
    assert '변화폭이 같아' not in ' '.join(result['paragraphs'])
    answer['facts'][0]['result']='-2'
    assert '하락 속도에는 차이' in focused_answer(answer)['paragraphs'][0]
