"""Offline contracts for text/sketch -> edit agent -> output agent."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/agent"))
from chart_edit_agent import ChartEditAgent, Hcx007EditModel
from ncp_clova_client import NcpClovaClient, NcpSettings
from output_agent import OutputAgent
from output_schema import VisualEditContext
from test_output_agent_migration import fixture_result


class FakeEditModel:
    model_name = "mock-edit-model"
    supports_images = False
    def __init__(self, proposal):
        self.proposal = proposal
        self.context = None
    def interpret(self, system, context):
        self.context = copy.deepcopy(context)
        return self.proposal


def mark(text="빨간 점선", target="계열0"):
    return {"id": "m1", "tool": "arrow", "points": [{"x": .2, "y": .3}, {"x": .4, "y": .5}],
            "text": text, "target": target}


def test_batch_sketch_to_output_preserves_raw_data():
    source = fixture_result()
    original = copy.deepcopy(source)
    output_agent = OutputAgent()
    initial = output_agent.prepare(source, {"chart_type": "line"})
    before = copy.deepcopy(initial)
    model = FakeEditModel({"commands": [
        {"operation": "set_series_color", "label": "계열0", "value": "#ff0000"},
        {"operation": "set_series_dash", "label": "계열0", "value": "dash"},
        {"operation": "set_legend", "value": "bottom"},
        {"operation": "set_title", "value": "새 제목"},
    ]})
    editor = ChartEditAgent(model, output_agent)
    result = editor.edit(source, initial, "표시한 계열을 바꾸고 범례는 아래로", {"marks": [{**mark(),"selection":{"label":"계열0","scope":"series"}}]})
    assert result["plotlyFigure"]["data"][0]["line"]["color"] == "#ff0000"
    assert result["plotlyFigure"]["data"][0]["line"]["dash"] == "dash"
    assert result["chartState"]["legend_position"] == "bottom"
    assert len(result["editHistory"]) == 4
    assert result["table"] == initial["table"]
    assert result["editAgent"]["path"] == ["interpret_edit", "render_output"]
    assert model.context["visual"]["marks"][0]["points"][0]["x"] == .2
    assert source == original and initial == before


@pytest.mark.parametrize("command", [
    {"operation": "set_line_width", "value": 99},
    {"operation": "set_series_color", "label": "계열0", "value": "javascript:bad"},
    {"operation": "set_series_color", "label": "없는 계열", "value": "#ffffff"},
    {"operation": "set_series_dash", "label": "계열0", "value": "invalid"},
    {"operation": "execute_code", "value": "bad"},
])
def test_invalid_batch_is_atomic(command):
    output = OutputAgent()
    source = fixture_result()
    initial = output.prepare(source, {"chart_type": "line"})
    before = copy.deepcopy(initial)
    editor = ChartEditAgent(FakeEditModel({"commands": [{"operation": "set_title", "value": "부분 적용 금지"}, command]}), output)
    with pytest.raises(ValueError):
        editor.edit(source, initial, "잘못된 수정")
    assert initial == before


def test_no_handwriting_guess_and_clarification():
    output = OutputAgent()
    source = fixture_result()
    initial = output.prepare(source, {"chart_type": "line"})
    editor = ChartEditAgent(FakeEditModel({"clarification": "어느 계열인가요?", "commands": []}), output)
    with pytest.raises(ValueError, match="손글씨"):
        editor.edit(source, initial, "", {"marks": [mark(text="")]})
    with pytest.raises(ValueError, match="어느 계열"):
        editor.edit(source, initial, "이 선 수정")
    with pytest.raises(ValueError):
        editor.edit(source, initial, "수정", {"selected_target": "없는 계열"})
    with pytest.raises(ValueError):
        VisualEditContext(marks=[{**mark(), "points": [{"x": 2, "y": 0}]}])


def test_hcx007_is_independent_and_never_receives_images():
    client = NcpClovaClient(NcpSettings(api_key="mock-not-a-key", main_model="other-model", main_url="https://invalid.example"))
    adapter = Hcx007EditModel(client)
    assert adapter.client.settings.main_model == "HCX-007"
    assert adapter.client.settings.main_api_version == "v3"
    assert adapter.client.settings.main_url == ""
    assert client.settings.main_model == "other-model"
    captured = {}
    def chat(system, user, **kwargs):
        captured.update(json.loads(user))
        return '{"commands":[{"operation":"set_title","value":"제목"}]}', {}
    adapter.client.chat_main = chat
    adapter.interpret("test", {"visual": {"marks": [mark()], "graph_image": "private image", "marked_image": "private image"}})
    assert "graph_image" not in captured["visual"]
    assert "marked_image" not in captured["visual"]


def test_image_adapter_can_be_replaced_without_orchestration_changes():
    output = OutputAgent()
    source = fixture_result()
    initial = output.prepare(source, {"chart_type": "line"})
    model = FakeEditModel({"commands": [{"operation": "set_title", "value": "VLM 어댑터 모의 테스트"}]})
    model.supports_images = True
    model.model_name = "mock-vlm"
    snapshot = "data:image/png;base64,aGVsbG8="
    result = ChartEditAgent(model, output).edit(source, initial, "", {"marks": [mark(text="")], "marked_image": snapshot})
    assert model.context["visual"]["marked_image"] == snapshot
    assert result["editCapabilities"] == {"model": "mock-vlm", "supportsImages": True}
    assert snapshot not in json.dumps(result)


def test_http_sketch_request_and_failed_session_rollback(monkeypatch):
    from fastapi.testclient import TestClient
    import bridge_api as api
    source = fixture_result()
    output_agent = OutputAgent()
    initial = output_agent.prepare(source, {"chart_type": "line"})
    model = FakeEditModel({"commands": [{"operation": "set_title", "value": "표시 수정"}]})
    monkeypatch.setattr(api, "edit_agent", ChartEditAgent(model, output_agent))
    monkeypatch.setattr(api, "_table_card", lambda table_id: {"tableId": table_id})
    record = {"result": source, "output": initial, "sessions": [{"query": "테스트", "table_name": "테스트",
               "period": {"start": "202401", "end": "202403"}, "frequency": "M"}]}
    monkeypatch.setitem(api.EDIT_SESSIONS, "sketch-test", record)
    client = TestClient(api.app)
    response = client.post("/api/output/edit", json={"edit_session_id": "sketch-test", "visual": {"marks": [mark(text="제목을 표시 수정으로", target="title")]}})
    assert response.status_code == 200, response.text
    assert response.json()["outputSpec"]["chartState"]["title"] == "표시 수정"
    assert response.json()["warnings"] == []
    assert "제목" in response.json()["outputSpec"]["editChanges"][0]
    assert "edit" in [s["id"] for s in response.json()["lineage"]]
    before = copy.deepcopy(record["output"])
    model.proposal = {"commands": [{"operation": "set_line_width", "value": 100}]}
    response = client.post("/api/output/edit", json={"edit_session_id": "sketch-test", "instruction": "너무 굵게"})
    assert response.status_code == 422
    assert record["output"] == before
    response = client.post("/api/output/edit", json={"edit_session_id": "sketch-test", "instruction": "수정", "visual": {"graph_image": "https://example.com"}})
    assert response.status_code == 422
