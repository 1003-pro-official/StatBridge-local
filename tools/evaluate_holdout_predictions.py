from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "agent"))

from stat_dictionary.stat_language_resolver import StatLanguageResolver  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate query-only holdout predictions and execution traces.")
    parser.add_argument("--queries", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--trace", required=True)
    args = parser.parse_args()

    dictionary = ROOT / "src" / "agent" / "stat_dictionary" / "stat_language_dictionary.json"
    resolver = StatLanguageResolver(dictionary)
    queries = [json.loads(line) for line in Path(args.queries).read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    status_map = {"resolved": "select", "need_clarification": "clarify", "no_match": "no_match", "catalog_only": "catalog_only"}
    predictions, traces = [], []

    for case in queries:
        started = time.perf_counter()
        prior = [turn.get("content", "") for turn in case.get("prior_turns", []) if turn.get("role") == "user"]
        current = case["query"]
        effective = resolver.merge_followup_query(prior[-1], current) if prior else current
        t1 = time.perf_counter()
        resolved = resolver.resolve(effective, top_k=12)
        t2 = time.perf_counter()
        raw = resolver.rank(effective, top_k=12)
        t3 = time.perf_counter()
        status = status_map.get(resolved.get("status", "no_match"), resolved.get("status", "no_match"))
        selected, path = [], "resolve"
        state_trace = {"previous_state": {}, "parsed_operations": [], "effective_query_state": {}, "effective_query": effective}

        if prior:
            candidates = resolver.rank_followup(prior[-1], current, top_k=12)
            state_trace = dict(resolver.last_followup_trace)
            selected = [item["table_id"] for item in candidates]
            if candidates:
                status = "select"
            path = "rank_followup"
        elif status == "catalog_only" and resolved.get("selected_table"):
            selected = [resolved["selected_table"]["table_id"]]
            path = "catalog_only"
        elif status == "select" and raw:
            selected = [item["table_id"] for item in resolver.rank_many(effective, top_k=12)]
            path = "rank_many"

        finished = time.perf_counter()
        predictions.append({"id": case["id"], "predicted_status": status, "predicted_table_ids": selected})
        current_state = resolver.parse_query_state(current)
        traces.append({
            "id": case["id"], "query": current,
            "previous_state": state_trace.get("previous_state", {}),
            "parsed_operations": state_trace.get("parsed_operations", []),
            "effective_query_state": state_trace.get("effective_query_state", {}),
            "raw_top5": [{"rank": index + 1, "table_id": item["table_id"], "table_name": item["table_name"], "reasons": item.get("reasons", [])} for index, item in enumerate(raw[:5])],
            "series_requests": current_state.series,
            "selected_series": selected,
            "predicted_status": status, "predicted_table_ids": selected,
            "failure_stage": None, "execution_path": path,
            "timings_ms": {"resolve": round((t2 - t1) * 1000, 3), "raw_rank": round((t3 - t2) * 1000, 3), "final_composition": round((finished - t3) * 1000, 3), "total": round((finished - started) * 1000, 3)},
        })

    Path(args.predictions).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in predictions), encoding="utf-8", newline="\n")
    Path(args.trace).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in traces), encoding="utf-8", newline="\n")
    print(json.dumps({"predictions": len(predictions), "traces": len(traces)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
