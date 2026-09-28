"""Score saved StatBridge resolution predictions against a v2 case file."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def score_resolution(predicted: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
    resolution = predicted.get("resolution", predicted)
    actual_ids = set(resolution.get("proposed_table_ids") or [])
    expected_ids = set(expected.get("table_ids") or [])
    scores = {
        "table_set_exact": float(actual_ids == expected_ids),
        "intent_exact": float(resolution.get("intent") == expected.get("intent")),
        "clarification_exact": float(
            resolution.get("clarification_kind") == expected.get("clarification_kind")
        ),
    }
    groups = expected.get("retrieval_groups") or []
    if groups:
        top_five = (predicted.get("ranked_table_ids") or [])[:5]
        scores["recall_at_5"] = sum(bool(set(group) & set(top_five)) for group in groups) / len(groups)
        ranked = predicted.get("ranked_table_ids") or []
        scores["top1"] = float(bool(ranked) and any(ranked[0] in group for group in groups))
    return scores


def score_cases(cases: list[dict[str, Any]], predictions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    grouped: dict[str, list[dict[str, float]]] = defaultdict(list)
    for case in cases:
        expected = case.get("expected", {}).get("resolution")
        if not expected:
            continue
        prediction = predictions.get(case["id"])
        metrics = score_resolution(prediction or {}, expected)
        grouped[case.get("category", "uncategorized")].append(metrics)
        rows.append({"id": case["id"], "scored": prediction is not None, **metrics})
    summary = {
        category: {key: round(sum(item[key] for item in items) / len(items), 4)
                   for key in items[0]} | {"cases": len(items)}
        for category, items in grouped.items()
    }
    return {"summary": summary, "cases": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path, help="JSON array of v2 cases")
    parser.add_argument("predictions", type=Path, help="JSON object keyed by case ID")
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
    print(json.dumps(score_cases(cases, predictions), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
