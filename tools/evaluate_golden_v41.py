from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "src" / "agent"
sys.path.insert(0, str(AGENT))

from stat_dictionary.stat_language_resolver import StatLanguageResolver  # noqa: E402


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def status_name(raw: str) -> str:
    return {"resolved": "select", "need_clarification": "clarify", "no_match": "no_match", "catalog_only": "catalog_only"}.get(raw, raw)


def safe_div(a, b):
    return a / b if b else 0.0


def round_metrics(value):
    if isinstance(value, float):
        return round(value, 6)
    return value


def context_query(case):
    current=case["query"]
    prior=[x.get("content","") for x in case.get("prior_turns",[]) if x.get("role")=="user"]
    return StatLanguageResolver.merge_followup_query(prior[-1],current) if prior else current


def evaluate_case(case, resolver, top_k=12):
    query = context_query(case)
    resolved = resolver.resolve(query, top_k=top_k)
    ranked = resolver.rank(query, top_k=top_k)
    ranked_ids = [item["table_id"] for item in ranked]
    predicted_status = status_name(resolved.get("status", "no_match"))
    predicted = []
    if case.get("prior_turns"):
        prior=[x.get("content","") for x in case["prior_turns"] if x.get("role")=="user"]
        followup_ranked=resolver.rank_followup(prior[-1],case["query"],top_k=top_k) if prior else []
        if followup_ranked:
            predicted_status="select"
            predicted=[x["table_id"] for x in followup_ranked]
    elif predicted_status == "catalog_only" and resolved.get("selected_table"):
        predicted=[resolved["selected_table"]["table_id"]]
    elif predicted_status == "select" and ranked_ids:
        predicted = [x["table_id"] for x in resolver.rank_many(query, top_k=top_k)]
    gold = list(case.get("table_ids") or [])
    gold_set, pred_set = set(gold), set(predicted)
    if predicted_status == "catalog_only":
        ranked_ids=predicted+ranked_ids
    hits = [ranked_ids.index(table_id) + 1 for table_id in gold if table_id in ranked_ids]
    best_rank = min(hits) if hits else None
    set_precision = safe_div(len(gold_set & pred_set), len(pred_set)) if gold_set else float(predicted_status == case["expected_status"])
    set_recall = safe_div(len(gold_set & pred_set), len(gold_set)) if gold_set else float(predicted_status == case["expected_status"])
    set_f1 = safe_div(2 * set_precision * set_recall, set_precision + set_recall)
    if case["expected_status"] != predicted_status:
        if case["expected_status"] == "clarify": failure = "E: 질문해야 하는데 임의 선택 또는 무결과"
        elif case["expected_status"] == "no_match": failure = "F: 지원하지 않는 질문에 후보 반환"
        elif case["type"] == "followup": failure = "H: followup context 손실"
        else: failure = "A: query understanding/status 오류"
    elif case["type"] == "multi" and pred_set != gold_set:
        failure = "G: multi-table 일부 표만 찾음" if pred_set <= gold_set else "G: multi-table 불필요한 표 추가"
    elif gold and not hits:
        failure = "C: 정답이 Recall@5 밖"
    elif gold and ranked_ids and ranked_ids[0] not in gold_set:
        failure = "D: 정답 후보 존재하나 Top-1 실패" if hits else "C: retrieval miss"
    else:
        failure = None
    return {
        "id": case["id"], "split": case["split"], "type": case["type"],
        "difficulty": case["difficulty"], "language_style": case["language_style"],
        "query": case["query"], "gold_table_ids": gold, "predicted_table_ids": predicted,
        "search_top_k": [{
            "table_id": item["table_id"], "table_name": item["table_name"],
            "rule_score": float(item.get("score") or 0), "vector_score": None,
            "reranker_score": None, "final_score": float(item.get("score") or 0),
        } for item in ranked[:top_k]],
        "expected_status": case["expected_status"], "predicted_status": predicted_status,
        "best_gold_rank": best_rank, "recall_at_1": bool(best_rank and best_rank <= 1),
        "recall_at_3": bool(best_rank and best_rank <= 3), "recall_at_5": bool(best_rank and best_rank <= 5),
        "reciprocal_rank": safe_div(1, best_rank) if best_rank else 0.0,
        "top1_correct": bool(gold and ranked_ids and ranked_ids[0] in gold_set),
        "exact_set_match": pred_set == gold_set,
        "set_precision": set_precision, "set_recall": set_recall, "set_f1": set_f1,
        "decision_correct": predicted_status == case["expected_status"],
        "failure_category": failure,
    }


def aggregate(rows):
    table_rows = [x for x in rows if x["gold_table_ids"]]
    multi = [x for x in rows if x["type"] == "multi"]
    def avg(key, subset): return safe_div(sum(float(x[key]) for x in subset), len(subset))
    metrics = {
        "total": len(rows), "type_counts": dict(Counter(x["type"] for x in rows)),
        "recall_at_1": avg("recall_at_1", table_rows), "recall_at_3": avg("recall_at_3", table_rows),
        "recall_at_5": avg("recall_at_5", table_rows), "mrr": avg("reciprocal_rank", table_rows),
        "top1_accuracy": avg("top1_correct", table_rows),
        "multi_exact_set_match": avg("exact_set_match", multi),
        "multi_set_precision": avg("set_precision", multi), "multi_set_recall": avg("set_recall", multi),
        "multi_set_f1": avg("set_f1", multi),
    }
    for kind, name in (("clarify", "clarify_decision_accuracy"), ("no_match", "no_match_decision_accuracy"),
                       ("catalog_only", "catalog_only_decision_accuracy"), ("followup", "followup_accuracy")):
        subset = [x for x in rows if x["type"] == kind]
        key = "decision_correct" if kind in {"clarify", "no_match", "catalog_only"} else "exact_set_match"
        metrics[name] = avg(key, subset)
    for group_key in ("difficulty", "language_style", "type", "split"):
        grouped = {}
        for value in sorted({x[group_key] for x in rows}):
            subset = [x for x in rows if x[group_key] == value]
            grouped[value] = {"count": len(subset), "decision_accuracy": avg("decision_correct", subset),
                              "exact_set_accuracy": avg("exact_set_match", subset)}
        metrics[f"by_{group_key}"] = grouped
    metrics["failure_counts"] = dict(Counter(x["failure_category"] for x in rows if x["failure_category"]))
    return json.loads(json.dumps(metrics, default=round_metrics))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    resolver = StatLanguageResolver(AGENT / "stat_dictionary" / "stat_language_dictionary.json")
    cases = read_jsonl(args.dataset)
    rows = [evaluate_case(case, resolver) for case in cases]
    payload = {"mode": "rule_only_current_runtime", "dataset": str(args.dataset), "metrics": aggregate(rows), "cases": rows}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["metrics"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
