"""Collect the manual V2 smoke script and guard the output review fixes."""

import runpy
from pathlib import Path

import pytest

from output_agent import OutputAgent


ROOT = Path(__file__).resolve().parents[1]


def test_manual_v2_script():
    runpy.run_path(str(ROOT / "tests" / "TEST_OUTPUT_AGENT_V2.py"), run_name="__main__")


def sample_result():
    return {"execution": {"status": "success", "rows": [
        {"_SERIES_LABEL": "금리", "PRD_DE": "202401", "DT": "4.2", "UNIT_NM": "%"},
        {"_SERIES_LABEL": "금리", "PRD_DE": "202402", "DT": "4.3", "UNIT_NM": "%"},
    ]}}


def test_auto_fallback_explains_only_successful_render(monkeypatch):
    agent = OutputAgent()
    monkeypatch.setattr(agent, "_propose_spec", lambda *_: {"chart_type": "scatter"})
    explanations = []

    def explain(series, spec, summary):
        explanations.append(spec.chart_type)
        return {"text": summary, "source": "test"}

    monkeypatch.setattr(agent, "_explain", explain)
    output = agent.prepare(sample_result(), {"chart_type": "auto"})
    assert output["chartState"]["chart_type"] == "bar"
    assert explanations == ["bar"]


def test_invalid_explicit_chart_does_not_request_explanation(monkeypatch):
    agent = OutputAgent()
    monkeypatch.setattr(agent, "_propose_spec", lambda *_: {})
    monkeypatch.setattr(agent, "_explain", lambda *_: pytest.fail("Invalid rendering must not call the model"))
    with pytest.raises(ValueError):
        agent.prepare(sample_result(), {"chart_type": "scatter"})


def test_model_series_names_are_limited_to_queried_series():
    import json

    class FakeClient:
        configured = True

        def chat_main(self, *_args, **_kwargs):
            return json.dumps({
                "chart_type": "line",
                "series_chart_types": {"조회하지 않은 계열": "bar", "예금금리": "line"},
                "secondary_axis_series": ["조회하지 않은 계열"],
            }), {}

        @staticmethod
        def _json_object(text):
            return json.loads(text)

    agent = OutputAgent(FakeClient())
    series = [{"label": "예금금리", "unit": "%", "points": [{"date": "202401", "value": 3.0}]}]
    proposed = agent._propose_spec(series, {})
    assert proposed["series_chart_types"] == {"예금금리": "line"}
    assert proposed["secondary_axis_series"] == []


def test_combined_series_with_two_units_uses_secondary_axis():
    result = {"execution": {"status": "success", "rows": [
        {"_SOURCE_SERIES_ID": "deposit", "_SERIES_LABEL": "예금금리", "PRD_DE": "202401", "DT": "3.0", "UNIT_NM": "%", "_FREQUENCY": "M"},
        {"_SOURCE_SERIES_ID": "loan", "_SERIES_LABEL": "대출금리", "PRD_DE": "202401", "DT": "4.0", "UNIT_NM": "연리%", "_FREQUENCY": "M"},
    ]}}
    output = OutputAgent().prepare(result, {"chart_type": "line", "layout": "combined"})
    assert output["visualization"]["layout"] == "combined"
    assert output["chartState"]["secondary_axis_series"] == ["대출금리"]
    assert len(output["visualization"]["series"]) == 2
    layout = output["plotlyFigure"]["layout"]
    assert layout["xaxis"]["tickangle"] == 0
    assert layout["yaxis"]["range"][1] > 3.0
    assert layout["yaxis2"]["range"][1] > 4.0
    assert {annotation["text"] for annotation in layout["annotations"]} >= {"%", "연리%"}


def test_edit_sessions_evict_oldest_after_successful_render(monkeypatch):
    import bridge_api

    monkeypatch.setattr(bridge_api, "EDIT_SESSIONS", {str(i): {} for i in range(100)})
    session = {"result": sample_result(), "period": {"start": "202401", "end": "202402"},
               "frequency": "M", "query": "금리", "table_name": "금리"}
    monkeypatch.setattr(bridge_api, "OUTPUT_SESSIONS", {"input": session})
    monkeypatch.setattr(bridge_api.agent, "render_output", lambda result, request: {
        **result, "output": OutputAgent().prepare(result, request),
    })
    response = bridge_api.render_output(bridge_api.OutputRenderRequest(session_ids=["input"], chart_type="line"))
    assert len(bridge_api.EDIT_SESSIONS) == 100
    assert "0" not in bridge_api.EDIT_SESSIONS
    assert "1" in bridge_api.EDIT_SESSIONS
    assert response["editSessionId"] in bridge_api.EDIT_SESSIONS
    assert not bridge_api.OUTPUT_SESSIONS


def test_invalid_output_keeps_input_session_and_returns_detail(monkeypatch):
    import bridge_api
    from fastapi import HTTPException

    monkeypatch.setattr(bridge_api, "OUTPUT_SESSIONS", {"input": {
        "result": sample_result(), "query": "금리",
    }})
    monkeypatch.setattr(bridge_api, "EDIT_SESSIONS", {})

    def fail(*_):
        raise ValueError("산점도에는 두 계열이 필요합니다.")

    monkeypatch.setattr(bridge_api.agent, "render_output", fail)
    with pytest.raises(HTTPException) as exc:
        bridge_api.render_output(bridge_api.OutputRenderRequest(session_ids=["input"], chart_type="scatter"))
    assert exc.value.status_code == 422
    assert exc.value.detail == "산점도에는 두 계열이 필요합니다."
    assert "input" in bridge_api.OUTPUT_SESSIONS
    assert not bridge_api.EDIT_SESSIONS


def test_edit_reuses_cached_rows_without_query(monkeypatch):
    import bridge_api

    result = sample_result()
    output = OutputAgent().prepare(result, {"chart_type": "line"})
    monkeypatch.setattr(bridge_api, "EDIT_SESSIONS", {"edit": {
        "result": result, "output": output, "sessions": [{
            "period": {"start": "202401", "end": "202402"},
            "frequency": "M", "query": "금리", "table_name": "금리",
        }],
    }})
    monkeypatch.setattr(bridge_api.agent, "run", lambda **_: pytest.fail("No new query on edit"))
    monkeypatch.setattr(bridge_api.agent, "execute_resolution", lambda **_: pytest.fail("No new data fetch on edit"))
    monkeypatch.setattr(bridge_api.agent.output_agent, "edit", lambda saved, current, instruction: {
        **current, "summary": "수정 완료",
    })
    response = bridge_api.edit_output(bridge_api.OutputEditRequest(edit_session_id="edit", instruction="제목 변경"))
    assert response["summary"] == "수정 완료"
    assert response["chart"] == output["visualization"]["series"]


def test_launcher_checks_new_output_dependencies():
    launcher = (ROOT / "scripts/windows/START_STATBRIDGE.cmd").read_text(encoding="utf-8")
    assert "langgraph,plotly" in launcher
    assert "require.resolve('plotly.js-dist-min')" in launcher
    assert "if defined FRONT_INSTALL" in launcher
