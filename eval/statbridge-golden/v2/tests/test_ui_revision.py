import copy
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
from common import read_json, read_jsonl, digest, identity
from run import execute_input, FrozenProvider, NoNetwork
from validate import validate_cases


def public_cases():
    return read_jsonl(BASE / "dev.jsonl") + read_jsonl(BASE / "test.jsonl")


def test_public_cases_have_no_file_upload_or_conversation_assumption():
    cases = public_cases()
    assert len(cases) == 72
    assert sum(c["mode"] == "output" for c in cases) == 12
    assert sum(c["mode"] == "edit" for c in cases) == 6
    for case in cases:
        assert not case["input"]["prior_turns"]
        assert "data_fixture" not in case["input"]
        assert "첨부" not in case["input"]["query"]
        assert "앞서" not in case["input"]["query"]
    assert validate_cases(cases, verify_sources=True)["errors"] == []


def test_archived_attachments_are_separate_and_hash_bound():
    cases = read_jsonl(BASE / "internal/components/cases.jsonl")
    assert len(cases) == 18
    for case in cases:
        assert case["input"]["data_fixture"].startswith("internal/components/")
        assert digest(BASE / case["input"]["data_fixture"]) == case["input"]["data_fixture_sha256"]
        assert digest(BASE / case["expected"]["data"]["fixture"]) == case["expected"]["data"]["fixture_sha256"]


def test_year_on_year_edit_has_real_previous_year_source_coverage():
    case = next(c for c in public_cases() if c["id"] == "SBV2-0072")
    source = read_json(BASE / case["expected"]["data"]["source_fixture"])["series"][0]
    expected = read_json(BASE / case["expected"]["data"]["fixture"])["series"][0]
    assert len(source["points"]) == 24
    assert len(expected["points"]) == 12
    assert source["points"][0]["period"] == "202301"
    assert expected["points"][0]["period"] == "202401"
    provider = FrozenProvider(NoNetwork(), BASE / "fixtures/provider.json")
    matching = [s for s in provider.series if identity(s) == identity(source)]
    assert len(matching) == 1
    assert matching[0]["points"] == source["points"]


def test_prepared_output_session_does_not_trigger_a_second_query():
    from output_agent import OutputAgent
    from run import fixture_rows
    provider = FrozenProvider(NoNetwork(), BASE / "fixtures/provider.json")
    series = provider.series[0]
    provider.calls = [{k: series[k] for k in ("provider", "table_id", "item_id", "classifications", "frequency")}]
    output = OutputAgent().prepare({"execution": {"rows": fixture_rows([series])}}, {"chart_type": "line"})
    calls = []
    class Response:
        status_code = 200
        def __init__(self, payload): self.payload = payload
        def json(self): return self.payload
        def raise_for_status(self): pass
    class Client:
        def post(self, path, json):
            calls.append((path, json))
            if path == "/api/query":
                assert json == {"query": "query", "execute": True}
                return Response({"status": "need_output_config", "outputSessionId": "issued",
                                 "tables": [{"tableId": series["table_id"]}]})
            assert json["session_ids"] == ["issued"]
            return Response({"status": "resolved", "outputSpec": output})
    payload = {"query": "query", "prior_turns": [], "actions": [
        {"kind": "confirm_period", "start": "2003-01-01", "end": "2003-12-31"},
        {"kind": "configure_output", "chart_type": "line", "layout": "combined"}]}
    actual, trace = execute_input("output", payload, Client(), provider)
    assert [path for path, _ in calls] == ["/api/query", "/api/output"]
    assert len(trace) == 2
    assert identity(actual["series"][0]) == identity(series)


def test_public_validator_blocks_reintroduced_attachment():
    cases = copy.deepcopy(public_cases())
    case = next(c for c in cases if c["mode"] == "output")
    case["input"]["query"] = "첨부한 파일로 그래프를 그려 주세요."
    assert any("public UI scenario" in e for e in validate_cases(cases)["errors"])
def test_pipeline_error_does_not_claim_unobserved_edit_corruption():
    from score import score_case
    from run import observation_hash
    import hashlib
    import json
    case = next(c for c in read_jsonl(BASE / "dev.jsonl") if c["id"] == "SBV2-0067")
    prediction = {"id": case["id"], "execution_status": "error", "error": "query failed",
                  "input_sha256": hashlib.sha256(json.dumps(case["input"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()}
    prediction["observation_sha256"] = observation_hash(prediction)
    result = score_case(case, prediction)
    assert result["status"] == "failed"
    assert "execution_error" in result["failures"]
    assert "edit_changed_source_data" not in result["failures"]
    assert "edit_requeried_data" not in result["failures"]
    assert result["unobserved_checks"] == ["data", "output", "edit"]

