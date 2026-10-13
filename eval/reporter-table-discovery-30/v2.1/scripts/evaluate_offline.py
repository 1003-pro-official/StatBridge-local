"""Offline rule-layer evaluation of the v2.1 gold: resolver candidates vs gold, no LLM and no HTTP.

Reads only the query and scores against gold afterwards. Useful before a full runtime run:
it finds gold/lexicon mismatches in seconds without keys.

shortcut: calls the resolver's internal _clarification for diagnostics; swap to a public API if one appears.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATASET = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "src/agent/stat_dictionary/stat_language_dictionary.json"
GOLD = DATASET / "statbridge-reporter200.jsonl"


def load_resolver():
    sys.path[:0] = [str(ROOT / "src/agent")]
    from stat_dictionary.stat_language_resolver import StatLanguageResolver
    return StatLanguageResolver(CATALOG)


def expected(case: dict) -> dict:
    workflow = case["workflow_gold"]
    status = workflow["resolution"]["agent_status"]
    return {
        "status": status,
        "tables": workflow["table_discovery"]["expected_table_ids"],
        "frequency": workflow["query_interpretation"]["frequency"],
        "clarification": workflow["resolution"].get("clarification") or {},
    }


def observe(resolver, case: dict, top_k: int) -> dict:
    query = case["query"]
    ranked = [item["table_id"] for item in resolver.rank(query, top_k=top_k)]
    clarification = resolver._clarification(query, resolver.rank(query, top_k=12)) or {}
    state = resolver.parse_query_state(query)
    return {"id": case["id"], "query": query, "ranked": ranked,
            "clarification_id": clarification.get("clarification_id"),
            "clarification_options": [option["value"] for option in clarification.get("options", [])],
            "frequency": state.frequency}


def score(observation: dict, gold: dict) -> dict:
    ranked = observation["ranked"]
    ranks = [ranked.index(table) + 1 for table in gold["tables"] if table in ranked]
    return {
        "id": observation["id"],
        "status": gold["status"],
        "top1_hit": bool(ranked) and ranked[0] in set(gold["tables"]),
        "best_rank": min(ranks) if ranks else None,
        "all_tables_found": bool(gold["tables"]) and len(ranks) == len(set(gold["tables"])),
        "frequency_match": observation["frequency"] == gold["frequency"] if gold["frequency"] else None,
        "clarification_expected": gold["clarification"].get("id"),
        "clarification_observed": observation["clarification_id"],
        "clarification_group_match": (observation["clarification_id"]
                                      == gold["clarification"].get("id")) if gold["clarification"] else None,
        "options_subset": (set(observation["clarification_options"])
                           <= {option["value"] for option in gold["clarification"].get("options", [])}
                           ) if gold["clarification"] else None,
        "missing_options": sorted({option["value"] for option in gold["clarification"].get("options", [])}
                                  - set(observation["clarification_options"])) if gold["clarification"] else [],
        "candidate_count": len(ranked),
        "top1_table": ranked[0] if ranked else None,
        "missing_tables": sorted(set(gold["tables"]) - set(ranked)),
    }


def rate(rows: list[dict], key: str) -> float | None:
    values = [row[key] for row in rows if row[key] is not None]
    return (sum(value is True for value in values) / len(values)) if values else None


def summarize(results: list[dict], resolved_rows: list[dict]) -> dict:
    ranks = [row["best_rank"] for row in resolved_rows if row["best_rank"]]
    return {
        "cases": len(results),
        "resolved_cases": len(resolved_rows),
        "table_top1_accuracy": rate(resolved_rows, "top1_hit"),
        "recall_at_1": rate(resolved_rows, "recall1"),
        "recall_at_3": rate(resolved_rows, "recall3"),
        "recall_at_5": rate(resolved_rows, "recall5"),
        "all_tables_found": rate(resolved_rows, "all_tables_found"),
        "mean_best_rank_of_found": round(statistics.fmean(ranks), 2) if ranks else None,
        "mrr": round(sum(1 / (row["best_rank"] or 0) if row["best_rank"] else 0 for row in resolved_rows)
                     / len(resolved_rows), 4) if resolved_rows else None,
        "mrr_of_found": round(statistics.fmean(1 / rank for rank in ranks), 4) if ranks else None,
        "any_gold_table_found": len(ranks) / len(resolved_rows) if resolved_rows else None,
        "frequency_accuracy": rate(results, "frequency_match"),
        "clarification_group_accuracy": rate(results, "clarification_group_match"),
        "clarification_options_subset": rate(results, "options_subset"),
        "no_match_with_candidates": sum(1 for row in results
                                        if row["status"] == "no_match" and row["candidate_count"] > 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=GOLD)
    parser.add_argument("--top-k", type=int, default=40)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    cases = [json.loads(line) for line in args.gold.read_text(encoding="utf-8").splitlines() if line]
    resolver = load_resolver()
    results, resolved_rows = [], []
    for case in cases:
        gold = expected(case)
        row = score(observe(resolver, case, args.top_k), gold)
        rank = row["best_rank"]
        row["recall1"] = rank is not None and rank <= 1
        row["recall3"] = rank is not None and rank <= 3
        row["recall5"] = rank is not None and rank <= 5
        results.append(row)
        if gold["status"] == "resolved":
            resolved_rows.append(row)
    summary = summarize(results, resolved_rows)
    summary["failed_clarification_group"] = [row["id"] for row in results
                                             if row["clarification_group_match"] is False]
    summary["missing_options_cases"] = {row["id"]: row["missing_options"] for row in results if row["missing_options"]}
    summary["missed_tables"] = {row["id"]: row["missing_tables"] for row in resolved_rows if row["missing_tables"]}
    summary["low_recall_cases"] = [row["id"] for row in resolved_rows if not row["recall5"]]
    summary["legacy_vs_new"] = {
        group: {"cases": len(rows), "recall_at_1": rate(rows, "recall1"), "any_found":
                (len([row for row in rows if row["best_rank"]]) / len(rows)) if rows else None}
        for group, rows in (("legacy_v2_30", [row for row in resolved_rows if row["id"].startswith("REPORTER30-V2-")]),
                            ("augmented_110", [row for row in resolved_rows
                                               if row["id"].startswith("REPORTER30-V2.1-")]))
    }
    summary["no_match_with_candidate_ids"] = [row["id"] for row in results
                                              if row["status"] == "no_match" and row["candidate_count"] > 0]
    summary["frequency_mismatch_ids"] = [row["id"] for row in results if row["frequency_match"] is False]
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "gold": str(args.gold),
               "resolver": "StatLanguageResolver (rule layer, no LLM, no HTTP)", "top_k": args.top_k,
               "summary": summary, "cases": results}
    output = args.output or ROOT / "evaluation_runs" / (
        "reporter200_v2.1_offline_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
    output.mkdir(parents=True, exist_ok=True)
    (output / "offline_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                                encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("보고서:", output / "offline_report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
