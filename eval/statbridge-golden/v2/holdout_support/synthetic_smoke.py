"""Four-mode smoke using fabricated data and fake API transport, never holdout cases."""
from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def smoke(product_root, tool_dir):
    sys.path[:0] = [str(tool_dir), str(product_root / "src/agent"), str(product_root / "src/backend")]
    from run import execute_input, fixture_rows, observation_hash
    from score import score_case
    from output_agent import OutputAgent
    from contract import value_hash
    series = {"provider": "kosis", "table_id": "SYNTHETIC_TABLE", "item_id": "SYNTHETIC_ITEM",
              "classifications": {"objL1": "SYNTHETIC_CLASS"}, "frequency": "M", "unit": "synthetic units",
              "label": "Synthetic series", "points": [{"period": "209901", "value": 10}, {"period": "209902", "value": 12}]}
    plan = {k: series[k] for k in ("table_id", "item_id", "classifications", "frequency")}
    provider = SimpleNamespace(plans=[plan], calls=[], series=[series])
    agent = OutputAgent(None)
    bridge = SimpleNamespace(agent=SimpleNamespace(output_agent=agent), EDIT_SESSIONS={})
    raw = {"execution": {"rows": fixture_rows([series]), "sources": [{"source": "synthetic"}]}}
    calls = []

    class Response:
        status_code = 200
        def __init__(self, data): self.data = data
        def json(self): return self.data
        def raise_for_status(self): pass

    class Client:
        def post(self, path, json):
            calls.append((path, copy.deepcopy(json)))
            if path == "/api/query":
                assert json["execute"] is True
                if "period_start" not in json:
                    assert "state" not in json
                    return Response({"status": "need_period", "state": {"synthetic_runtime": True},
                                     "tables": [{"tableId": series["table_id"]}]})
                assert json["state"] == {"synthetic_runtime": True}
                provider.calls.append({"provider": "kosis", **plan})
                return Response({"status": "need_output_config", "outputSessionId": "synthetic-issued-output",
                                 "tables": [{"tableId": series["table_id"]}]})
            if path == "/api/output":
                assert json["session_ids"] == ["synthetic-issued-output"]
                output = agent.prepare(raw, {"chart_type": json["chart_type"], "layout": json["chart_mode"]})
                bridge.EDIT_SESSIONS["synthetic-issued-edit"] = {"result": copy.deepcopy(raw), "output": output}
                return Response({"outputSpec": output, "editSessionId": "synthetic-issued-edit"})
            assert path == "/api/output/edit"
            assert json["edit_session_id"] == "synthetic-issued-edit"
            session = bridge.EDIT_SESSIONS[json["edit_session_id"]]
            session["output"] = agent.edit(session["result"], session["output"], json["instruction"])
            return Response({"outputSpec": session["output"], "editSessionId": "synthetic-issued-edit"})

    results = []
    with tempfile.TemporaryDirectory(prefix="statbridge-synthetic-") as directory:
        base = Path(directory)
        (base / "fixtures").mkdir()
        (base / "fixtures/synthetic.json").write_text(json.dumps({"series": [series]}), encoding="utf-8")
        for mode in ("discovery", "e2e", "output", "edit"):
            provider.calls.clear()
            calls.clear()
            payload = {"query": "2099년 1월부터 2월까지 synthetic series", "prior_turns": [], "actions": []}
            expected = {"resolution": {"decision": "resolved", "acceptable_table_sets": [[series["table_id"]]],
                                        "series_selection": [{"provider": "kosis", **plan, "unit": series["unit"]}],
                                        "clarification": {"required": False}}}
            if mode != "discovery":
                payload["actions"] = [{"kind": "confirm_period", "start": "2099-01-01", "end": "2099-02-28"},
                                      {"kind": "configure_output", "chart_type": "line", "layout": "combined"}]
                expected["data"] = {"fixture": "fixtures/synthetic.json", "absolute_tolerance": 0.000001}
                expected["output"] = {"acceptable_chart_types": ["line"], "layout": "combined"}
            if mode == "edit":
                payload["actions"].append({"kind": "edit", "instruction": "제목을 'Synthetic title'로 변경해 주세요."})
                payload["offline_edit_command"] = {"operation": "set_title", "kind": "STYLE_EDIT", "value": "Synthetic title"}
                expected["output"].update(state={"title": "Synthetic title"}, preserve_data=True)
            with patch.dict(sys.modules, {"bridge_api": bridge}):
                observed, trace = execute_input(mode, payload, Client(), provider)
            prediction = {"id": "SYNTHETIC-" + mode, "execution_status": "observed", **observed,
                          "input_sha256": value_hash(payload)}
            prediction["observation_sha256"] = observation_hash(prediction)
            case = {"id": prediction["id"], "mode": mode, "input": payload, "expected": expected,
                    "review": {"human_approved": False}}
            scored = score_case(case, prediction, base=base)
            assert scored["automatic_pass"], scored
            assert scored["status"] == ("passed" if mode == "discovery" else "pending_review")
            if mode == "edit":
                assert observed["source_data_preserved"] is True
                assert observed["statistics_calls_during_edit"] == 0
            results.append({"mode": mode, "automatic_pass": True, "status": scored["status"],
                            "stages": [t["stage"] for t in trace]})
    return {"scope": "synthetic data + fake API transport; NOT product accuracy or holdout evaluation",
            "private_cases_created": 0, "modes": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-root", type=Path, required=True)
    parser.add_argument("--tool-dir", type=Path, default=Path(__file__).resolve().parent / "pinned/scripts")
    args = parser.parse_args()
    print(json.dumps(smoke(args.product_root.resolve(), args.tool_dir.resolve()), ensure_ascii=False))


if __name__ == "__main__":
    main()
