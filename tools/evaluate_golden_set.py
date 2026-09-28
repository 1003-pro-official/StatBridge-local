"""Validate the BOK golden set and score the current catalog search locally."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "eval" / "golden-set"


def load_cases(corpus_dir: Path = DEFAULT_CORPUS) -> list[dict[str, Any]]:
    cases = []
    for path in sorted((corpus_dir / "cases").glob("*.json")):
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise ValueError(f"case file must contain an array: {path}")
        cases.extend(loaded)
    return cases


def validate_cases(
    cases: list[dict[str, Any]],
    supported_ids: set[str],
    corpus_dir: Path = DEFAULT_CORPUS,
) -> list[str]:
    errors: list[str] = []
    manifest = json.loads((corpus_dir / "manifest.json").read_text(encoding="utf-8"))
    reports = {item["id"]: item for item in manifest.get("reports", [])}
    report_ids = set(reports)
    seen: set[str] = set()
    split_ids: dict[str, set[str]] = {"development": set(), "holdout": set()}

    for case in cases:
        case_id = str(case.get("id") or "<missing-id>")
        if case_id in seen:
            errors.append(f"{case_id}: duplicate id")
        seen.add(case_id)
        split = case.get("split")
        if split not in split_ids:
            errors.append(f"{case_id}: invalid split")
        if not str(case.get("query") or "").strip():
            errors.append(f"{case_id}: query is empty")
        source = case.get("source") or {}
        if source.get("report_id") not in report_ids:
            errors.append(f"{case_id}: unknown source report {source.get('report_id')!r}")
        if not source.get("locator"):
            errors.append(f"{case_id}: source locator is missing")
        if not str(source.get("url") or "").startswith("https://www.bok.or.kr/"):
            errors.append(f"{case_id}: source must link to an official BOK page")
        if source.get("report_id") in reports:
            report = reports[source["report_id"]]
            if source.get("url") != report["url"]:
                errors.append(f"{case_id}: source URL differs from manifest")
            if case_id.startswith("expanded-") and report.get("primary_pdf_url"):
                if source.get("pdf_url") != report["primary_pdf_url"] or source.get("pdf_sha256") != report["primary_pdf_sha256"]:
                    errors.append(f"{case_id}: PDF provenance differs from manifest")
        expected = case.get("expected") or {}
        if expected.get("status") not in {"candidate_found", "need_clarification", "no_match"}:
            errors.append(f"{case_id}: invalid expected status")
        groups = expected.get("retrieval_groups", [])
        if case.get("evaluation", {}).get("current_check") == "retrieval" and not groups:
            errors.append(f"{case_id}: retrieval case has no expected table group")
        for index, group in enumerate(groups):
            if not group:
                errors.append(f"{case_id}: retrieval group {index} is empty")
            for table_id in group:
                if table_id not in supported_ids:
                    errors.append(f"{case_id}: unsupported table id {table_id}")
                elif split in split_ids:
                    split_ids[split].add(table_id)
        for chart_series in (expected.get("chart") or {}).get("series", []):
            table_id = chart_series.get("table_id")
            if table_id not in supported_ids:
                errors.append(f"{case_id}: unsupported chart table id {table_id}")
        chart = expected.get("chart")
        if "chart" in case.get("tags", []):
            if not chart:
                errors.append(f"{case_id}: chart tag has no chart expectation")
            else:
                fixture_path = corpus_dir / str(chart.get("fixture") or "")
                if not fixture_path.is_file():
                    errors.append(f"{case_id}: chart fixture is missing: {fixture_path}")
                else:
                    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
                    if fixture.get("snapshot_id") != manifest.get("value_snapshot_id"):
                        errors.append(f"{case_id}: chart fixture uses a different value snapshot")
                    if not fixture.get("series"):
                        errors.append(f"{case_id}: chart fixture has no series")
                    expected_series = {
                        (item.get("table_id"), item.get("label"), item.get("unit"))
                        for item in chart.get("series", [])
                    }
                    fixture_series = {
                        (item.get("table_id"), item.get("label"), item.get("unit"))
                        for item in fixture.get("series", [])
                    }
                    if expected_series != fixture_series:
                        errors.append(f"{case_id}: chart expectation differs from fixture series")
                    for series in fixture.get("series", []):
                        if not series.get("points"):
                            errors.append(f"{case_id}: chart fixture series has no points")
                        if series.get("table_id") not in supported_ids:
                            errors.append(f"{case_id}: fixture has unsupported table id {series.get('table_id')}")
                        source_file = ROOT / str(series.get("source_file") or "")
                        if not source_file.is_file():
                            errors.append(f"{case_id}: fixture source file is missing: {source_file}")
                        elif hashlib.sha256(source_file.read_bytes()).hexdigest() != series.get("source_file_sha256"):
                            errors.append(f"{case_id}: fixture source file checksum changed: {source_file}")
                        periods = [str(point.get("period") or "") for point in series.get("points", [])]
                        if periods != sorted(set(periods)):
                            errors.append(f"{case_id}: fixture periods must be unique and ordered")
        current_check = case.get("evaluation", {}).get("current_check")
        if current_check == "clarification":
            options = expected.get("clarification_options") or []
            if len(options) < 2 or any(table_id not in supported_ids for table_id in options):
                errors.append(f"{case_id}: clarification needs at least two supported options")
        if current_check not in {"retrieval", "empty_result", "clarification", "deferred"}:
            errors.append(f"{case_id}: invalid current_check")
    counts = manifest.get("counts", {})
    if len(cases) != counts.get("cases"):
        errors.append(f"case count {len(cases)} differs from manifest")
    if sum("chart" in case.get("tags", []) for case in cases) != counts.get("chart_cases"):
        errors.append("chart case count differs from manifest")
    for split, target in counts.get("splits", {}).items():
        if sum(case.get("split") == split for case in cases) != target:
            errors.append(f"{split} count differs from manifest")
    if split_ids["development"] & split_ids["holdout"]:
        errors.append("development and holdout target table IDs overlap")
    if len(split_ids["development"] | split_ids["holdout"]) < counts.get("minimum_distinct_target_tables", 0):
        errors.append("too few distinct target table IDs")
    for family, target in counts.get("family_targets", {}).items():
        if family == "범위 밖":
            actual = sum(case.get("category") == "out_of_scope" for case in cases)
        else:
            actual = sum(case.get("category") != "out_of_scope"
                         and reports.get(case.get("source", {}).get("report_id"), {}).get("family") == family
                         for case in cases)
        if actual != target:
            errors.append(f"{family}: {actual} cases differ from target {target}")
    return errors


def score_retrieval(
    expected_groups: list[list[str]], ranked_ids: list[str], k: int = 5
) -> dict[str, float]:
    if not expected_groups:
        raise ValueError("at least one required series group is needed")
    top_k = ranked_ids[:k]
    hits = sum(bool(set(group).intersection(top_k)) for group in expected_groups)
    first_relevant_rank = next(
        (rank for rank, table_id in enumerate(ranked_ids, start=1)
         if any(table_id in group for group in expected_groups)),
        None,
    )
    return {
        "recall_at_k": hits / len(expected_groups),
        "mrr": 1 / first_relevant_rank if first_relevant_rank else 0.0,
        "top1": float(bool(ranked_ids) and any(ranked_ids[0] in group for group in expected_groups)),
    }


def evaluate(cases: list[dict[str, Any]], searcher: Any, analysis: Any = None) -> dict[str, Any]:
    scores = defaultdict(list)
    rows = []
    for case in cases:
        check = case["evaluation"]["current_check"]
        if check == "deferred":
            rows.append({"id": case["id"], "status": "deferred"})
            continue
        if check == "clarification":
            if analysis is None:
                rows.append({"id": case["id"], "status": "deferred"})
                continue
            result = analysis.analyze({"query": case["query"]})
            offered = {item["table_id"] for item in result.get("candidates", [])}
            expected = set(case["expected"]["clarification_options"])
            passed = result["status"] == "need_clarification" and expected <= offered
            scores[case["category"]].append({"pass_rate": float(passed)})
            rows.append({"id": case["id"], "status": "scored", "offered_ids": sorted(offered),
                         "pass_rate": float(passed)})
            continue
        candidates = searcher.search(case["query"], top_k=5)
        ranked_ids = [item["table_id"] for item in candidates]
        if check == "retrieval":
            metric = score_retrieval(case["expected"]["retrieval_groups"], ranked_ids)
            scores[case["category"]].append(metric)
            rows.append({"id": case["id"], "status": "scored", "ranked_ids": ranked_ids, **metric})
        else:
            empty_match = not ranked_ids
            scores[case["category"]].append({"empty_result": float(empty_match)})
            rows.append({"id": case["id"], "status": "scored", "ranked_ids": ranked_ids,
                         "empty_result": float(empty_match)})

    summary = {}
    for category, metrics in scores.items():
        keys = metrics[0]
        summary[category] = {
            key: round(sum(item[key] for item in metrics) / len(metrics), 4)
            for key in keys
        }
        summary[category]["cases"] = len(metrics)
    case_map = {case["id"]: case for case in cases}
    by_split = {}
    for split in ("development", "holdout"):
        subset = [row for row in rows if case_map[row["id"]].get("split") == split and row["status"] == "scored"]
        metrics = defaultdict(list)
        for row in subset:
            category = case_map[row["id"]]["category"]
            for key in ("recall_at_k", "mrr", "top1", "pass_rate", "empty_result"):
                if key in row:
                    metrics[category, key].append(row[key])
        by_split[split] = {category: {key: round(sum(values) / len(values), 4)
                                      for (cat, key), values in metrics.items() if cat == category}
                           for category in {cat for cat, _ in metrics}}
    return {"summary": summary, "by_split": by_split, "cases": rows}


def evaluate_charts(cases: list[dict[str, Any]], corpus_dir: Path, analysis: Any) -> dict[str, Any]:
    """Compare the real chart API path with fixed CSV observations, offline."""
    rows = []
    for case in cases:
        chart = case.get("expected", {}).get("chart")
        if not chart:
            continue
        fixture = json.loads((corpus_dir / chart["fixture"]).read_text(encoding="utf-8"))
        selections = [{"table_id": item["table_id"], "item_id": item["item_id"],
                       "classifications": item["classifications"], "frequency": item["frequency"],
                       "start_period": item["points"][0]["period"],
                       "end_period": item["points"][-1]["period"]}
                      for item in fixture["series"]]
        result = analysis.analyze({"query": case["query"], "series": selections, "source": "local"})
        actual = result.get("chart") or []
        checks = []
        for expected, observed in zip(fixture["series"], actual):
            checks.append(expected["table_id"] == observed["table_id"]
                          and expected["unit"] == observed["unit"]
                          and expected["frequency"] == observed["frequency"]
                          and expected["points"] == observed["points"])
        passed = result["status"] == "resolved" and len(actual) == len(fixture["series"]) and all(checks)
        rows.append({"id": case["id"], "split": case.get("split"), "passed": passed, "status": result["status"]})
    return {"passed": sum(row["passed"] for row in rows), "total": len(rows), "cases": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT / "src" / "backend"))
    from statbridge_mcp.metadata_store import MetadataStore
    from statbridge_mcp.search_engine import SearchEngine
    from statbridge_mcp.statistics_service import StatisticsService
    from analysis_service import AnalysisService

    sys.path.insert(0, str(ROOT / "src" / "backend"))

    cases = load_cases(args.corpus)
    store = MetadataStore()
    errors = validate_cases(cases, set(store.table_ids()), args.corpus)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    analysis = AnalysisService(StatisticsService(store=store))
    result = evaluate(cases, SearchEngine(store), analysis)
    result["chart"] = evaluate_charts(cases, args.corpus, analysis)
    gates = json.loads((args.corpus / "manifest.json").read_text(encoding="utf-8"))["evaluation"]["release_gates"]
    holdout = result["by_split"]["holdout"]
    retrieval = [row["recall_at_k"] for row in result["cases"]
                 if next(case for case in cases if case["id"] == row["id"])["split"] == "holdout"
                 and "recall_at_k" in row]
    result["retrospective_gate_checks"] = {
        "overall_recall": round(sum(retrieval) / len(retrieval), 4) >= gates["holdout_recall_at_5"],
        "category_recall": all(values.get("recall_at_k", 1) >= gates["holdout_category_recall_at_5"]
                               for values in holdout.values()),
        "clarification": holdout["clarification"]["pass_rate"] >= gates["holdout_clarification_pass_rate"],
        "no_match": holdout["out_of_scope"]["empty_result"] >= gates["holdout_no_match_rate"],
        "chart_exact": result["chart"]["passed"] / result["chart"]["total"] >= gates["chart_exact_pass_rate"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
