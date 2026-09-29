from types import SimpleNamespace

from agent_runtime import StatBridgeAgent


def plan():
    return {
        "table_id": "DT_513Y001",
        "table_name": "경제심리지수",
        "item_id": "13103134473999",
        "classifications": {},
        "frequency": "M",
        "start_period": "202501",
        "end_period": "202502",
        "exact_params": {"startPrdDe": "202501", "endPrdDe": "202502"},
    }


def agent_with_response(response):
    class Service:
        def __init__(self):
            self.calls = []

        def get_statistics(self, **kwargs):
            self.calls.append(kwargs)
            return response

    agent = object.__new__(StatBridgeAgent)
    agent.service = Service()
    agent.ncp = SimpleNamespace(configured=False)
    return agent


def test_agent_uses_external_csv_when_no_kosis_key(monkeypatch):
    monkeypatch.delenv("KOSIS_API_KEY", raising=False)
    agent = agent_with_response({
        "status": "success", "source": "local_csv",
        "rows": [{"PRD_DE": "202501", "DT": "100.1"}],
    })

    result = agent.execute_resolution("경제심리지수", {"api_plan": plan()}, generate_answer=False)

    assert agent.service.calls[0]["prefer_local"] is True
    assert result["execution"]["status"] == "success"
    assert result["execution"]["sources"][0]["source"] == "local_csv"


def test_agent_does_not_report_failed_mcp_lookup_as_success(monkeypatch):
    monkeypatch.delenv("KOSIS_API_KEY", raising=False)
    agent = agent_with_response({
        "status": "failed", "source": "none", "rows": [],
        "errors": [{"error": "KOSIS_API_KEY가 설정되지 않았습니다."}],
    })

    result = agent.execute_resolution("경제심리지수", {"api_plan": plan()}, generate_answer=False)

    assert result["execution"]["status"] == "error"
    assert "KOSIS_API_KEY" in result["execution"]["error"]
