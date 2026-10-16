"""API regressions for merging main period provenance with PR follow-up context."""
import copy
import pytest


@pytest.mark.parametrize("execute", [False, True])
@pytest.mark.parametrize("expression,source,basis", [
    ("2021년부터 2024년까지", "text", None),
    ("최근 5년", "latest_observation", "최신 제공 관측 시점 기준"),
])
def test_explicit_period_keeps_source_and_basis_in_preview_and_execution(monkeypatch, execute, expression, source, basis):
    import bridge_api as api
    selected = api.agent.resolver.candidate_shell("DT_513Y001")
    plan = api.agent.build_api_plan("경제심리지수", selected).as_dict()
    resolution = {"status": "resolved", "api_plan": plan, "selected_table": selected, "state": {}}
    monkeypatch.setattr(api.agent, "run", lambda **_: copy.deepcopy(resolution))
    monkeypatch.setattr(api.agent, "validate_resolution", lambda query, result: result)
    monkeypatch.setattr(api, "_availability_from_plans", lambda _: {"min": "2000-01-01", "max": "2025-12-31"})
    monkeypatch.setattr(api.agent, "execute_resolution", lambda **kw: {**kw["resolution"], "execution": {"status": "planned_only"}})
    # An explicit request must win even when validated prior context is available.
    monkeypatch.setattr(api.agent, "_validated_followup_plans", lambda _: ({}, [{**plan, "start_period": "202101", "end_period": "202212"}]))
    result = api.query(api.QueryRequest(query=f"경제심리지수 {expression}", execute=execute))
    selection = result["periodSelection"]
    assert selection["source"] == source
    assert selection["basis"] == basis
    expected = {"start": "2021-01-01", "end": "2024-12-31"} if source == "text" else {"start": "2021-01-01", "end": "2025-12-31"}
    assert selection["requested"] == selection["applied"] == expected


@pytest.mark.parametrize("explicit_ui", [False, True])
def test_followup_context_is_used_only_without_a_new_ui_period(monkeypatch, explicit_ui):
    import bridge_api as api
    selected = api.agent.resolver.candidate_shell("DT_513Y001")
    plan = api.agent.build_api_plan("경제심리지수", selected).as_dict()
    resolution = {"status": "resolved", "api_plan": plan, "selected_table": selected, "state": {}}
    monkeypatch.setattr(api.agent, "run", lambda **_: copy.deepcopy(resolution))
    monkeypatch.setattr(api.agent, "validate_resolution", lambda query, result: result)
    monkeypatch.setattr(api, "_availability_from_plans", lambda _: {"min": "2000-01-01", "max": "2025-12-31"})
    monkeypatch.setattr(api.agent, "_validated_followup_plans", lambda _: ({}, [{**plan, "start_period": "202101", "end_period": "202212"}]))
    monkeypatch.setattr(api.agent, "execute_resolution", lambda **kw: {**kw["resolution"], "execution": {"status": "planned_only"}})
    dates = {"period_start": "2023-01-01", "period_end": "2024-12-31"} if explicit_ui else {}
    result = api.query(api.QueryRequest(query="경제심리지수도 추가해줘", execute=False, **dates))
    selection = result["periodSelection"]
    assert selection["source"] == ("ui" if explicit_ui else "context")
    assert selection["basis"] is None
    assert selection["requested"] == selection["applied"] == ({"start": "2023-01-01", "end": "2024-12-31"} if explicit_ui else {"start": "2021-01-01", "end": "2022-12-31"})
