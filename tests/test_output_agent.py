from __future__ import annotations

import sys
from pathlib import Path


AGENT_ROOT = Path(__file__).resolve().parents[1] / "src" / "agent"
sys.path.insert(0, str(AGENT_ROOT))

from output_agent import OutputAgent


def test_equal_display_names_do_not_merge_distinct_classification_codes():
    rows = [dict(TBL_ID='table', ITM_ID='item', C1=code,
                 C1_NM='동일 명칭', _SOURCE_SERIES_ID='table',
                 _SERIES_LABEL='지표', PRD_DE='202401', DT=value, UNIT_NM='%')
            for code, value in [('a', '10'), ('b', '20')]]
    series = OutputAgent()._series(rows)
    assert len(series) == 2
    assert len({s['label'] for s in series}) == 2
    assert [s['points'][0]['value'] for s in series] == [10, 20]
    assert [s['sourceIdentity']['classifications'] for s in series] == [{'objL1': 'a'}, {'objL1': 'b'}]


def test_conflicting_values_for_the_same_identity_still_fail_closed():
    import pytest
    row = dict(TBL_ID='table', ITM_ID='item', C1='a',
               _SOURCE_SERIES_ID='table', _SERIES_LABEL='지표',
               PRD_DE='202401', DT='10', UNIT_NM='%')
    with pytest.raises(ValueError, match='여러 개'):
        OutputAgent()._series([row, {**row, 'DT': '20'}])


def test_period_followup_accepts_natural_particle_without_replacing_metrics():
    from agent_runtime import StatBridgeAgent
    assert StatBridgeAgent._period_only_followup('방금 자료를 다른 기간으로 다시 보여줘: 2024년 1월부터 2025년 12월까지')
    assert not StatBridgeAgent._period_only_followup('기간으로 비교할 소비자물가지수를 2024년부터 2025년까지 보여줘')


def test_period_followup_revalidates_server_confirmed_output_window():
    import copy
    from agent_runtime import StatBridgeAgent
    agent = object.__new__(StatBridgeAgent)
    prior = {'table_id': 'table', 'item_id': 'item', 'classifications': {'objL1': 'a'},
             'frequency': 'M', 'start_period': '202301', 'end_period': '202512',
             'exact_params': {'startPrdDe': '202301', 'endPrdDe': '202512'}}
    observed = copy.deepcopy(prior)
    observed.update(start_period='202501')
    observed['exact_params']['startPrdDe'] = '202501'
    agent._catalog_candidates = lambda query: []
    agent._validated_followup_plans = lambda state: ('원래 요청', [prior])
    result = agent.validate_resolution(
        '다른 기간으로 보여줘: 2025년 1월부터 2025년 12월까지',
        {'status': 'resolved', 'state': {}, 'api_plans': [observed]},
        confirmed_periods={'table': ('202501', '202512')})
    assert result['request_validation']['valid'] is True
    assert result['api_plans'][0]['classifications'] == prior['classifications']
    assert prior['start_period'] == '202301'


def test_output_selection_and_editing():
    result = {
        "execution": {
            "status": "success",
            "rows": [
                {"PRD_DE": "202401", "DT": "100", "ITM_NM": "테스트", "UNIT_NM": "개"},
                {"PRD_DE": "202402", "DT": "110", "ITM_NM": "테스트", "UNIT_NM": "개"},
            ],
        }
    }
    output = OutputAgent().prepare(result, {
        "chart_type": "bar",
        "layout": "separate",
        "title": "편집 가능한 테스트 그래프",
        "show_legend": False,
    })

    assert output["status"] == "ready"
    assert output["visualization"]["chartType"] == "bar"
    assert output["visualization"]["layout"] == "separate"
    assert output["visualization"]["editable"] is True
    assert output["visualization"]["editOptions"]["title"] == "편집 가능한 테스트 그래프"
    assert len(output["visualization"]["series"][0]["points"]) == 2
    print("OUTPUT AGENT OK: chart selection, data shaping and edit specification")
