"""Output-only transplant regressions; provider responses are deterministic mocks."""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src/agent"), str(ROOT / "src/backend")]
os.environ.setdefault("STATBRIDGE_DATA_DIR", str(ROOT / "data/processed"))
os.environ["STATBRIDGE_HYBRID_RETRIEVAL"] = "0"

from output_agent import OutputAgent
from output_schema import ChartSpec, ChartEditCommand


class FakeModel:
    configured = True
    settings = SimpleNamespace(main_model="mock-output-model")

    def __init__(self, command=None):
        self.command = command

    def chat_main(self, system, user, **kwargs):
        if "명령 분류기" in system:
            return json.dumps(self.command, ensure_ascii=False), {}
        if "명세 생성기" in system:
            return '{"chart_type":"line","title":"모의 추천"}', {}
        return "제공된 숫자에 근거한 모의 설명입니다.", {}

    @staticmethod
    def _json_object(text):
        return json.loads(text)


def fixture_result(count=3):
    return {
        "api_plan": {"table_id": "DT_TEST", "table_name": "테스트 표", "org_id": "301",
                     "item_id": "ITEM", "frequency": "M", "start_period": "202401", "end_period": "202403"},
        "execution": {"status": "success", "rows": [
            {"PRD_DE": period, "DT": str(value + index), "ITM_NM": f"계열{index}", "UNIT_NM": "개",
             "_SOURCE_SERIES_ID": "DT_TEST", "_FREQUENCY": "M"}
            for index in range(count) for period, value in [("202401", 10), ("202402", 20), ("202403", 30)]
        ], "sources": [{"table_id": "DT_TEST", "source": "mock", "row_count": count * 3}]},
    }


@pytest.mark.parametrize('chart_type',['auto','line','bar','stacked_bar','area','scatter','bubble','pie','donut','histogram','box','heatmap','treemap','waterfall'])
def test_model_invented_series_names_cannot_block_user_selected_chart(chart_type):
    class WrongLabelsModel(FakeModel):
        def chat_main(self,system,user,**kwargs):
            if '명세 생성기' in system:
                return json.dumps({'chart_type':'line','series_chart_types':{'주택담보대출':'line','신용대출':'bar'},'secondary_axis_series':['신용대출']}),{}
            return '모의 설명',{}
    data=fixture_result(1 if chart_type=='waterfall' else 3 if chart_type=='bubble' else 2)
    original=copy.deepcopy(data)
    out=OutputAgent(WrongLabelsModel()).prepare(data,{'chart_type':chart_type,'title':'사용자 제목'})
    assert out['status']=='ready' and out['plotlyFigure']['data']
    if chart_type!='auto':assert out['chartState']['chart_type']==chart_type
    assert out['chartState']['title']=='사용자 제목'
    assert not out['chartState']['series_chart_types'] and not out['chartState']['secondary_axis_series']
    assert out['warnings'] and data==original


def test_explicit_invalid_edit_series_still_rejected():
    output=OutputAgent();data=fixture_result(2)
    with pytest.raises(ValueError,match='조회되지 않은 계열'):
        output._build(data,ChartSpec(chart_type='line',series_chart_types={'없는 지표':'line'}))


def test_valid_model_auxiliary_axis_does_not_override_pie_selection(monkeypatch):
    output=OutputAgent();data=fixture_result(2)
    labels=[s['label'] for s in output._series(data['execution']['rows'])]
    monkeypatch.setattr(output,'_propose_spec',lambda series,raw:{'secondary_axis_series':[labels[1]],'series_chart_types':{labels[0]:'bar'}})
    out=output.prepare(data,{'chart_type':'pie'})
    assert out['chartState']['chart_type']=='pie' and not out['chartState']['secondary_axis_series']


@pytest.mark.parametrize("chart_type", [
    "line", "bar", "stacked_bar", "area", "scatter", "bubble", "pie", "donut",
    "histogram", "box", "heatmap", "treemap", "waterfall",
])
def test_graph_types_and_original_values(chart_type):
    result = fixture_result(1 if chart_type == "waterfall" else 2 if chart_type=='scatter' else 3)
    original = copy.deepcopy(result)
    output = OutputAgent().prepare(result, {"chart_type": chart_type})
    assert output["status"] == "ready"
    assert output["plotlyFigure"]["data"]
    assert output["visualization"]["chartType"] == chart_type
    assert output["table"]["rows"][0]["value"] == 10
    assert output["evidence"][0]["source"] == "mock"
    assert result == original
    json.dumps(output, allow_nan=False)


@pytest.mark.parametrize("command,field,value", [
    ({"operation": "set_title", "value": "수정 제목"}, "title", "수정 제목"),
    ({"operation": "set_line_width", "value": 5}, "line_width", 5),
    ({"operation": "set_transform", "value": "cumulative"}, "transform", "cumulative"),
])
def test_natural_language_edit_with_mock_model(command, field, value):
    agent = OutputAgent(FakeModel(command))
    result = fixture_result()
    initial = agent.prepare(result, {"chart_type": "line"})
    edited = agent.edit(result, initial, "모의 수정 요청")
    assert edited["chartState"][field] == value
    assert len(edited["editHistory"]) == 1
    assert edited["explanation"]["source"] == "mock-output-model"


def test_mixed_units_separate_and_validation():
    result = fixture_result()
    result["execution"]["rows"][-1]["UNIT_NM"] = "%"
    with pytest.raises(ValueError,match='단위'):
        OutputAgent().prepare(result, {"chart_type": "line", "layout":"combined"})
    output = OutputAgent().prepare(result, {"chart_type": "line", "layout":"separate"})
    assert output["visualization"]["layout"] == "separate"
    with pytest.raises(ValueError):
        OutputAgent().prepare(fixture_result(1), {"chart_type": "scatter"})
    with pytest.raises(ValueError):
        ChartSpec(line_width=100)
    with pytest.raises(ValueError):
        ChartEditCommand(operation="set_title", kind="DATA_EDIT")


def test_http_query_output_edit_does_not_refetch(monkeypatch):
    monkeypatch.setenv("KOSIS_API_KEY", "offline-test-key")
    from fastapi.testclient import TestClient
    import bridge_api as api

    model = FakeModel({"operation": "set_title", "value": "수정 제목"})
    monkeypatch.setattr(api.agent.output_agent, "ncp_client", model)
    class EditModel:
        model_name = "mock-edit-model"
        supports_images = False
        def interpret(self, system, context):
            return model.command
    monkeypatch.setattr(api.edit_agent, "model", EditModel())
    calls = []

    def get_data(**kwargs):
        calls.append(kwargs)
        return {"status": "success", "source": "mock", "row_count": 2, "rows": [
            {"PRD_DE": "202401", "DT": "10", "ITM_NM": "경제심리지수", "UNIT_NM": ""},
            {"PRD_DE": "202402", "DT": "11", "ITM_NM": "경제심리지수", "UNIT_NM": ""},
        ]}

    monkeypatch.setattr(api.service, "get_statistics", get_data)
    client = TestClient(api.app)
    discovered = client.post("/api/query", json={"query": "DT_513Y001"}).json()
    assert discovered["status"] == "need_period"
    prepared_response = client.post("/api/query", json={
        "query": "DT_513Y001", "state": discovered["state"],
        "period_start": "2024-01-01", "period_end": "2024-02-29",
    })
    assert prepared_response.status_code == 200, prepared_response.text
    prepared = prepared_response.json()
    assert prepared["status"] == "need_output_config"
    assert prepared["chart"] == []
    session_id = prepared["outputSessionId"]
    invalid = client.post("/api/output", json={"session_ids": [session_id], "chart_type": "scatter"})
    assert invalid.status_code == 422
    rendered_response = client.post("/api/output", json={"session_ids": [session_id], "chart_type": "bar"})
    assert rendered_response.status_code == 200, rendered_response.text
    rendered = rendered_response.json()
    assert rendered["outputSpec"]["plotlyFigure"]["data"][0]["type"] == "bar"
    edited_response = client.post("/api/output/edit", json={
        "edit_session_id": rendered["editSessionId"], "instruction": "제목 변경",
    })
    assert edited_response.status_code == 200, edited_response.text
    edited = edited_response.json()
    assert edited["outputSpec"]["chartState"]["title"] == "수정 제목"
    assert edited["chart"] == rendered["chart"]
    assert len(calls) == 1
    assert calls[0]["prefer_local"] is False
    assert client.post("/api/output/edit", json={"edit_session_id": "missing", "instruction": "수정"}).status_code == 404
    api.EDIT_SESSIONS.pop(rendered["editSessionId"], None)


def test_target_runtime_contract_is_not_replaced():
    import bridge_api as api

    assert api.ROOT == ROOT
    assert api.MCP_ROOT == ROOT / "src/backend"
    assert api.DATA_DIR == ROOT / "data/processed"
    frontend = ROOT / "src/agent/frontend/src"
    client = (frontend / "api/client.ts").read_text(encoding="utf-8")
    app = (frontend / "App.tsx").read_text(encoding="utf-8")
    assert '?? "http://127.0.0.1:8000/api"' in client
    assert "isLoanRateComparison" not in app
    assert "submitQuery(initialQueryRequest(query))" in app
    assert "outputSpec?.visualization?.editOptions" in app
    assert "$1[redacted]" in app
