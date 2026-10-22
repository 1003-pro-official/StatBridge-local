import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))


def test_validation_passes():
    from validate import main
    assert main(['--no-oracles']) == 0


def test_public_cases_carry_contract_not_values():
    from e2e_common import BASE, rows
    for case in rows(BASE / 'cases' / 'dev.jsonl') + rows(BASE / 'cases' / 'test.jsonl'):
        expected = case['expected']
        assert 'points' not in expected
        assert 'values' not in expected
        assert 'DT_' not in case['input']['query']
        assert '[' not in case['input']['query']


def test_holdout_has_no_answers():
    from e2e_common import BASE, rows
    holdout = rows(BASE / 'cases' / 'holdout_queries.jsonl')
    assert len(holdout) == 40
    assert all(set(item) == {'id', 'mode', 'output_kind', 'query', 'prior_turns', 'reference_date'} for item in holdout)


def test_tier_c_is_not_scored():
    from e2e_common import BASE, rows
    for case in rows(BASE / 'cases' / 'dev.jsonl') + rows(BASE / 'cases' / 'test.jsonl'):
        if case['tier'] == 'C':
            assert case['eligible_for_scoring'] is False
            assert case['expected']['decision'] == 'unresolved_probe'


def test_period_helpers():
    from build_cases import iso_periods, periods_between, rewrite_period
    assert periods_between('202301', '202303', 'M') == ['202301', '202302', '202303']
    assert periods_between('2023Q3', '2024Q1', 'Q') == ['2023Q3', '2023Q4', '2024Q1']
    assert periods_between('2022', '2024', 'A') == ['2022', '2023', '2024']
    assert iso_periods(['2023Q1', '2025Q4'], 'Q') == ('2023-01-01', '2025-12-31')
    assert rewrite_period('2023년 1월부터 2025년 12월까지 금리 추이', 'M', ['202501', '202512']).startswith('2025년 1월부터 2025년 12월까지')


def test_norm_periods():
    from score import norm
    assert norm('2023-01', 'M') == '202301'
    assert norm('2023Q1', 'Q') == '2023Q1'
    assert norm('2023', 'A') == '2023'


def _case_and_oracle():
    series = {'table_id': 'T', 'item_id': 'I', 'classifications': {'objL1': 'C'}, 'frequency': 'M'}
    oracle = {'series': [{**series, 'unit': '%', 'label': 'x',
                          'points': [{'period': '202301', 'value': '1.0'}, {'period': '202302', 'value': '2.0'}]}]}
    case = {'id': 'SBE-9999', 'mode': 'query_output', 'tier': 'A', 'group_id': 'X', 'eligible_for_scoring': True,
            'input': {'query': 'q'}, 'expected': {'decision': 'resolved', 'series': [series],
                                                  'periods': ['202301', '202302'], 'oracle_sha256': 'x'},
            'qualitative_applicable': ['facts']}
    prediction = {'id': 'SBE-9999', 'execution_status': 'observed', 'decision': 'resolved',
                  'series': [{**series, 'unit': '%', 'label': 'x',
                              'points': [{'period': '202301', 'value': 1.0}, {'period': '202302', 'value': 2.0}]}]}
    return case, oracle, prediction


def test_score_pass_waits_for_human_review():
    from score import score_case
    case, oracle, prediction = _case_and_oracle()
    result = score_case(case, prediction, oracle, None)
    assert result['status'] == 'pending_review'


def test_score_numeric_mismatch_fails():
    from score import score_case
    case, oracle, prediction = _case_and_oracle()
    prediction['series'][0]['points'][1]['value'] = 2.0001
    assert score_case(case, prediction, oracle, None)['status'] == 'failed'


def test_score_missing_series_fails():
    from score import score_case
    case, oracle, prediction = _case_and_oracle()
    prediction['series'] = []
    assert score_case(case, prediction, oracle, None)['status'] == 'failed'


def test_review_gate_requires_scores_and_notes():
    from e2e_common import review_packet, review_valid
    case, oracle, prediction = _case_and_oracle()
    packet = review_packet(case, prediction)
    assert not review_valid(case, prediction, packet)
    packet.update(human_approved=True, reviewer='r1',
                  scores={'facts': 2, 'completeness': None, 'clarity': None,
                          'source_limits': None, 'visual': None, 'conversation_recovery': None},
                  not_applicable=['completeness', 'clarity', 'source_limits', 'visual', 'conversation_recovery'],
                  evidence_notes={'facts': '계열·기간 일치 확인'}, critical_error=False)
    assert review_valid(case, prediction, packet)


def test_paid_path_stays_unapproved():
    from e2e_common import BASE, read
    profiles = read(BASE / 'profiles.json')
    assert profiles['selected_profile'] is None
    assert profiles['approval'] == {'approved_by': None, 'approved_at': None,
                                     'cost_cap_usd': None, 'repeats': None, 'modes': []}
    assert all(value is None for profile in profiles['profiles'].values()
               for value in profile['models'].values())


def test_paid_runner_refuses_without_approval():
    from e2e_common import BASE, read
    from run_model import require_approval
    profiles = read(BASE / 'profiles.json')
    problems = require_approval(profiles, 'single_model', ['derived'], 1)
    assert any('approved_by' in problem for problem in problems)
    assert any('models are not filled' in problem for problem in problems)


def test_edit_and_follow_up_scoring():
    from score import compare_edit, compare_follow_up
    case = {'expected': {'expected_state': {'title': 'x', 'legend': False, 'recent': 2},
                         'periods': ['202401', '202402'],
                         'series': [{'table_id': 'T', 'item_id': 'I',
                                     'classifications': {'objL1': 'C'}, 'frequency': 'M'}]}}
    good = {'chart_state': {'title': 'x', 'show_legend': False}, 'point_counts': [2, 2]}
    assert compare_edit(case, good) == []
    assert compare_edit(case, {'chart_state': {'title': 'y'}, 'point_counts': [12]}) != []
    follow = {'statistics_requests': [{'table_id': 'T', 'item_id': 'I',
                                       'classifications': {'objL1': 'C'}, 'frequency': 'M'}],
              'period': {'start': '2024-01-01', 'end': '2024-02-29'}}
    assert compare_follow_up(case, follow) == []
    follow['period'] = {'start': '2024-02-01', 'end': '2024-02-29'}
    assert compare_follow_up(case, follow) != []


def test_handoff_and_review_exist():
    from e2e_common import BASE
    assert (BASE / 'HANDOFF.md').is_file()
    assert (BASE / 'REVIEW.md').is_file()
