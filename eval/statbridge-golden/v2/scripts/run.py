"""Execute public inputs through the real app, with explicit offline/live boundaries."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import time
from types import SimpleNamespace
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from common import BASE, ROOT, digest, identity, local_path, read_json, read_jsonl, write_json, write_jsonl

sys.path[:0] = [str(ROOT / "src/backend"), str(ROOT / "src/agent")]


class NoNetwork:
    configured = False
    settings = SimpleNamespace(classifier_model="disabled_offline")

    def __getattr__(self, name):
        def blocked(*args, **kwargs):
            raise RuntimeError("offline external call blocked: " + name)
        return blocked


class ReplayCommand:
    """Replay a USER-SUPPLIED operation, not an expected answer or NLP judgment."""
    configured = True

    def __init__(self, command):
        self.command = copy.deepcopy(command)

    def chat_main(self, system, user, **kwargs):
        if "instruction" not in json.loads(user):
            raise RuntimeError("command replay cannot generate explanations")
        return json.dumps(self.command), {}

    @staticmethod
    def _json_object(text):
        return json.loads(text)


def fixture_rows(series):
    rows = []
    for s in series:
        source_id = s["series_id"] if s["provider"] == "attachment" else s["table_id"]
        for p in s["points"]:
            rows.append({"_SOURCE_SERIES_ID": source_id, "_SERIES_LABEL": s["label"],
                         "_FREQUENCY": s["frequency"], "UNIT_NM": s["unit"],
                         "PRD_DE": p["period"], "DT": p["value"],
                         "ITM_ID": s.get("item_id", ""), "TBL_ID": s.get("table_id", ""),
                         "C1": s.get("classifications", {}).get("objL1", ""), "C1_NM": s["label"]})
    return rows


class FrozenProvider:
    """Global registry lookup by actual service parameters; never receives cases/gold."""
    def __init__(self, metadata, fixture):
        self.metadata, self.calls, self.plans, self.metadata_cache = metadata, [], [], {}
        self.series = read_json(fixture)["series"]

    def __getattr__(self, name):
        return getattr(self.metadata, name)

    def get_table_metadata(self, *args, **kwargs):
        key = json.dumps([args, kwargs], sort_keys=True)
        if key not in self.metadata_cache:
            self.metadata_cache[key] = self.metadata.get_table_metadata(*args, **kwargs)
        return copy.deepcopy(self.metadata_cache[key])

    def get_statistics(self, table_id, item_id="ALL", classifications=None, frequency=None,
                       start_period=None, end_period=None, **kwargs):
        call = {"provider": "kosis", "table_id": table_id, "item_id": item_id,
                "classifications": classifications or {}, "frequency": frequency,
                "start_period": start_period, "end_period": end_period}
        self.calls.append(call)
        candidates = [s for s in self.series if
                      s["table_id"] == table_id and s["item_id"] == item_id and
                      s["classifications"] == call["classifications"] and s["frequency"] == frequency]
        if not candidates:
            raise ValueError("unregistered offline request; no answer substitution")
        def normalize(p):
            if frequency == "Q" and "Q" not in p:
                return p[:4] + "Q" + str(int(p[-2:]))
            return p
        start, end = normalize(start_period or ""), normalize(end_period or "99999999")
        points = {p["period"]: p for s in candidates for p in s["points"] if start <= p["period"] <= end}
        if not points:
            raise ValueError("requested period is not available in frozen provider")
        selected = {**candidates[0], "points": [points[p] for p in sorted(points)]}
        return {"status": "success", "source": "offline_fixture", "rows": fixture_rows([selected]),
                "row_count": len(points), "used_params": call}


class LiveProvider(FrozenProvider):
    def __init__(self, metadata):
        self.metadata, self.calls, self.plans, self.metadata_cache = metadata, [], [], {}
        self.series = read_json(BASE / "series_registry.json")

    def get_statistics(self, **kwargs):
        self.calls.append({"provider": "kosis", **{k: kwargs.get(k) for k in
            ("table_id", "item_id", "classifications", "frequency", "start_period", "end_period")}})
        return self.metadata.get_statistics(**kwargs)


class Unobserved(ValueError):
    pass


def observed_output(output, requested_identities):
    vis = output.get("visualization", {})
    result = {"series": [], "chart_type": vis.get("chartType"), "layout": vis.get("layout"),
              "plotly_figure": output.get("plotlyFigure"), "chart_state": output.get("chartState"),
              "explanation": output.get("explanation"), "evidence": output.get("evidence")}
    for item in vis.get("series", []):
        matches = [s for s in requested_identities if (s.get("series_id") or s.get("table_id")) == item.get("sourceId")]
        # Ambiguous observation is an error, never resolved using expected labels.
        if len(matches) != 1:
            raise ValueError("output lineage cannot be uniquely joined to observed request")
        source = matches[0]
        fields = ["provider", "series_id"] if source["provider"] == "attachment" else ["provider", "table_id", "item_id", "classifications"]
        series = {k: source[k] for k in fields}
        series.update(label=item["label"], unit=item["unit"], frequency=item["frequency"],
                      points=[{"period": p["date"], "value": p["value"]} for p in item["points"]])
        result["series"].append(series)
    return result


def observed_resolution(response):
    status = response.get("status")
    decision = "clarify" if status == "need_clarification" else "unsupported" if status in {"no_match", "catalog_only"} else "resolved"
    groups = response.get("clarifications") or ([response["clarification"]] if response.get("clarification") else [])
    return {"decision": decision, "table_ids": [t["tableId"] for t in response.get("tables", [])] if decision == "resolved" else [],
            "clarification": {"asked": decision == "clarify",
                "question": " ".join(g.get("question", "") for g in groups),
                "options": [str(o.get("label", "")) for g in groups for o in g.get("options", [])]}}


def selected_series(provider):
    result = []
    for plan in provider.plans:
        matches = [s for s in provider.series if s["table_id"] == plan["table_id"] and
                   s["item_id"] == plan["item_id"] and s["classifications"] == plan["classifications"] and
                   s["frequency"] == plan["frequency"]]
        units = {s["unit"] for s in matches}
        result.append({"provider": "kosis", "table_id": plan["table_id"], "item_id": plan["item_id"],
                       "classifications": plan["classifications"], "frequency": plan["frequency"],
                       "unit": next(iter(units)) if len(units) == 1 else "<unobserved>"})
    return result


def execute_input(mode, payload, client=None, provider=None, live=False, trace=None):
    """The only SUT entry point. No expected/evidence/review argument exists."""
    from output_agent import OutputAgent
    trace, result = trace if trace is not None else [], {}
    if "data_fixture" in payload:
        attached = read_json(local_path(BASE, payload["data_fixture"]))["series"]
        raw = {"execution": {"status": "success", "rows": fixture_rows(attached),
                             "sources": [{"source": "attachment", "series_id": s["series_id"]} for s in attached]}}
        if live:
            from ncp_clova_client import NcpClovaClient
            out_agent = OutputAgent(NcpClovaClient())
        else:
            out_agent = OutputAgent(None)
        before = copy.deepcopy(raw)
        output = out_agent.prepare(raw, payload.get("output_request"))
        trace.append({"stage": "OutputAgent.prepare", "response": copy.deepcopy(output)})
        for action in payload["actions"]:
            if action["kind"] == "edit":
                if not live:
                    out_agent.ncp_client = ReplayCommand(payload["offline_edit_command"])
                output = out_agent.edit(raw, output, action["instruction"])
                trace.append({"stage": "OutputAgent.edit", "response": copy.deepcopy(output)})
        result.update(observed_output(output, attached), source_data_preserved=raw == before,
                      statistics_calls_during_edit=0, edit_parser="live_ncp" if live else "input_command_replay")
    else:
        state = None
        session_ids = []
        def post(path, body):
            started = time.perf_counter()
            response = client.post(path, json=body)
            value = response.json()
            trace.append({"stage": path, "http_status": response.status_code,
                          "elapsed_ms": round((time.perf_counter()-started)*1000, 3), "response": value})
            response.raise_for_status()
            return value
        # Prior user turns actually traverse the app. Assistant prose is recorded, not
        # forged into an app state. State comes only from returned responses.
        for turn in payload["prior_turns"]:
            if turn["role"] == "user":
                response = post("/api/query", {"query": turn["text"], "state": state, "execute": False})
                state = response.get("state", state)
        response = post("/api/query", {"query": payload["query"], "execute": True})
        state = response.get("state", state)
        if response.get("outputSessionId"):
            session_ids.append(response["outputSessionId"])
        result["resolution"] = observed_resolution(response)
        if provider and result["resolution"]["decision"] == "resolved":
            result["resolution"]["series_selection"] = selected_series(provider)
        if mode == "discovery":
            return result, trace
        for action in payload["actions"]:
            if action["kind"] == "clarify":
                groups = response.get("clarifications") or [response.get("clarification", {})]
                group = next((g for g in groups if any(o.get("value") == action["value"] for o in g.get("options", []))), None)
                if not group:
                    raise ValueError("requested user option not offered by app")
                response = post("/api/query", {"query": payload["query"], "state": state, "execute": False,
                    "clarification": {"clarification_id": group["id"], "value": action["value"]}})
                state = response.get("state", state)
                result["resolution"] = observed_resolution(response)
                if provider and result["resolution"]["decision"] == "resolved":
                    result["resolution"]["series_selection"] = selected_series(provider)
            elif action["kind"] == "confirm_period":
                # The UI shows a period form only when the server requests it.
                if response.get("status") != "need_period":
                    if session_ids:
                        continue
                    raise ValueError("UI cannot confirm period at status: " + str(response.get("status")))
                response = post("/api/query", {"query": payload["query"], "state": state, "execute": True,
                    "period_start": action["start"], "period_end": action["end"]})
                state = response.get("state", state)
                result["resolution"] = observed_resolution(response)
                if provider and result["resolution"]["decision"] == "resolved":
                    result["resolution"]["series_selection"] = selected_series(provider)
                if not response.get("outputSessionId"):
                    raise ValueError("no actual output session: " + str(response.get("status")))
                session_ids.append(response["outputSessionId"])
            elif action["kind"] == "configure_output":
                response = post("/api/output", {"session_ids": session_ids, "chart_type": action["chart_type"],
                                               "chart_mode": action["layout"]})
            elif action["kind"] == "edit":
                edit_id = response["editSessionId"]
                if provider:
                    import bridge_api
                    raw_before = copy.deepcopy(bridge_api.EDIT_SESSIONS[edit_id]["result"])
                    calls_before = len(provider.calls)
                if not live:
                    if not provider:
                        raise ValueError("offline edit replay requires the local app")
                    with patch.object(bridge_api.agent.output_agent, "ncp_client", ReplayCommand(payload["offline_edit_command"])):
                        response = post("/api/output/edit", {"edit_session_id": edit_id, "instruction": action["instruction"]})
                else:
                    response = post("/api/output/edit", {"edit_session_id": edit_id, "instruction": action["instruction"]})
                if provider:
                    result.update(source_data_preserved=raw_before == bridge_api.EDIT_SESSIONS[edit_id]["result"],
                                  statistics_calls_during_edit=len(provider.calls)-calls_before,
                                  edit_parser="live_ncp" if live else "input_command_replay")
        if provider:
            identities = []
            for call in provider.calls:
                observed = {k: call[k] for k in ("provider", "table_id", "item_id", "classifications", "frequency")}
                if observed not in identities:
                    identities.append(observed)
        else:
            # Live public responses do not expose full classification/item lineage.
            # Save observations but fail rather than reconstruct identity from gold.
            raise Unobserved("remote API does not expose full series identities; numeric score remains unobserved")
        result.update(observed_output(response.get("outputSpec", {}), identities))
    return result, trace


def observation_hash(value):
    clean = {k: v for k, v in value.items() if k != "observation_sha256"}
    return hashlib.sha256(json.dumps(clean, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def implementation_hashes():
    import os
    files = []
    for directory in ("src/agent", "src/backend"):
        for root, dirs, names in os.walk(ROOT / directory):
            dirs[:] = [d for d in dirs if d not in {"frontend", "node_modules", "__pycache__", ".git"}]
            files.extend(Path(root) / n for n in names if n.endswith(".py"))
    files.extend((ROOT / "src/agent/stat_dictionary").glob("*.json"))
    files.extend((ROOT / "data/processed").glob("*.csv"))
    return {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p) for p in sorted(files)}


def run_cases(cases, live=False, base_url=None):
    import httpx
    stack = ExitStack()
    with stack:
        provider = None
        if live and base_url:
            client = stack.enter_context(httpx.Client(base_url=base_url, timeout=180))
        else:
            def blocked(*args, **kwargs):
                raise RuntimeError("offline network access is forbidden")
            if not live:
                stack.enter_context(patch("requests.sessions.Session.request", blocked))
                stack.enter_context(patch("httpx.HTTPTransport.handle_request", blocked))
                stack.enter_context(patch("urllib.request.urlopen", blocked))
            import bridge_api
            from agent_runtime import StatBridgeAgent
            from fastapi.testclient import TestClient
            from mcp_gateway import McpToolGateway
            from statbridge_mcp.statistics_service import StatisticsService
            if live:
                import os
                if not os.getenv("KOSIS_API_KEY") or not bridge_api.agent.ncp.configured:
                    raise ValueError("live requires configured KOSIS and NCP credentials; no fallback to offline")
                provider = LiveProvider(bridge_api.service)
            else:
                provider = FrozenProvider(StatisticsService(client=NoNetwork()), BASE / "fixtures/provider.json")
            gateway = McpToolGateway(provider)
            stack.enter_context(patch.object(bridge_api, "service", provider))
            from ncp_clova_client import NcpClovaClient, NcpSettings
            real_agent = StatBridgeAgent(gateway) if live else StatBridgeAgent(
                gateway, ncp_client=NcpClovaClient(NcpSettings(api_key="")))
            original_run = real_agent.run
            def record_plan(*args, **kwargs):
                response = original_run(*args, **kwargs)
                provider.plans = copy.deepcopy(response.get("api_plans") or ([response["api_plan"]] if response.get("api_plan") else []))
                return response
            stack.enter_context(patch.object(real_agent, "run", record_plan))
            stack.enter_context(patch.object(bridge_api, "agent", real_agent))
            stack.enter_context(patch.object(bridge_api, "OUTPUT_SESSIONS", {}))
            stack.enter_context(patch.object(bridge_api, "EDIT_SESSIONS", {}))
            client = stack.enter_context(TestClient(bridge_api.app))
        predictions = []
        for c in cases:
            started = time.perf_counter()
            if provider:
                provider.calls.clear()
                provider.plans.clear()
            print("Executing " + c["id"] + " (" + c["mode"] + ")", flush=True)
            prediction = {"id": c["id"], "environment": "live" if live else "offline_fixed_provider",
                          "execution_status": "observed",
                          "input_sha256": hashlib.sha256(json.dumps(c["input"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()}
            trace = []
            try:
                observed, trace = execute_input(c["mode"], copy.deepcopy(c["input"]), client, provider, live, trace)
                prediction.update(observed)
            except Exception as exc:
                prediction.update(execution_status="unobserved" if isinstance(exc, Unobserved) else "error",
                                  error_type=type(exc).__name__, error=str(exc))
            prediction["trace"] = trace
            prediction["elapsed_ms"] = round((time.perf_counter()-started)*1000, 3)
            prediction["statistics_requests"] = copy.deepcopy(provider.calls) if provider else []
            prediction["observation_sha256"] = observation_hash(prediction)
            predictions.append(prediction)
        return predictions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--base-url")
    parser.add_argument("--output", required=True, help="Ignored local results directory")
    args = parser.parse_args()
    cases = read_jsonl(args.cases)
    cases_hash = digest(args.cases)
    output = local_path(BASE, args.output)
    if not output.is_relative_to(BASE / "results"):
        raise ValueError("execution artifacts must be under ignored v2/results/")
    write_jsonl(output, run_cases(cases, args.live, args.base_url))
    write_json(output.with_suffix(".manifest.json"), {
        "ai_assisted": True, "environment": "live" if args.live else "offline_fixed_provider",
        "cases_sha256": cases_hash, "provider_sha256": digest(BASE / "fixtures/provider.json"),
        "implementation": implementation_hashes(),
        "limitations": ["Offline edit parser is input command replay; no NCP language-model validation.",
                        "Live API lacks complete classification lineage; identity is not filled from gold."]})
    print("Saved actual observations: " + str(output))


if __name__ == "__main__":
    main()
