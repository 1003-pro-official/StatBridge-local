"""Score observed responses; free-text interpretation needs a signed human review."""
from __future__ import annotations

import argparse
import json
import hashlib
import re
from collections import Counter

from common import BASE, MODES, finite_number, identity, read_json, read_jsonl, write_json


def compare_series(expected, actual, tolerance):
    failures = []
    try:
        exp_keys, act_keys = [identity(s) for s in expected], [identity(s) for s in actual]
    except (KeyError, TypeError, ValueError):
        return ["missing_series_identity"]
    if len(act_keys) != len(set(act_keys)):
        failures.append("duplicate_series")
    if Counter(exp_keys) != Counter(act_keys):
        return failures + ["series_identity_or_count"]
    actual_by_key = {identity(s): s for s in actual}
    for exp in expected:
        act = actual_by_key[identity(exp)]
        ep, ap = exp["points"], act.get("points", [])
        periods = [p.get("period") for p in ap]
        if len(periods) != len(set(periods)):
            failures.append("duplicate_periods")
        if periods != [p["period"] for p in ep]:
            failures.append("periods_or_order")
            continue
        for e, a in zip(ep, ap):
            if "value" not in a:
                failures.append("missing_point_value")
            ev, av = e["value"], a.get("value")
            if ev is None:
                if av is not None:
                    failures.append("missing_value_imputed")
            elif not finite_number(av) or abs(ev - av) > tolerance:
                failures.append("numeric_value")
    return sorted(set(failures))


def check_plotly(series, figure, chart_type, layout="combined"):
    traces = figure.get("data", []) if isinstance(figure, dict) else []
    if chart_type not in {"line", "bar", "area", "stacked_bar"}:
        return ["plotly_check_not_implemented"]
    if len(traces) != len(series):
        return ["plotly_trace_count"]
    failures = []
    for s, trace in zip(series, traces):
        if not isinstance(trace.get("x"), list) or not isinstance(trace.get("y"), list):
            failures.append("plotly_arrays_not_observable")
            continue
        wanted = "bar" if chart_type in {"bar", "stacked_bar"} else "scatter"
        if trace.get("type") != wanted:
            failures.append("plotly_trace_type")
        if chart_type in {"line", "area"}:
            # Plotly's omitted scatter mode is lines+markers below 20 points,
            # lines otherwise (no stackgroup here); both contain a line.
            mode = trace.get("mode", "lines")
            if not isinstance(mode, str) or "lines" not in mode.split("+"):
                failures.append("plotly_line_mode")
            if trace.get("visible") in (False, "legendonly") or trace.get("opacity", 1) == 0 or trace.get("line", {}).get("width", 1) == 0:
                failures.append("plotly_hidden_line")
        if trace.get("name") != s["label"]:
            failures.append("plotly_series_label")
        if trace["x"] != [p["period"] for p in s["points"]] or trace["y"] != [p["value"] for p in s["points"]]:
            failures.append("plotly_values")
        if chart_type == "area" and trace.get("fill") != "tozeroy":
            failures.append("plotly_area_fill")
    if chart_type == "stacked_bar" and figure.get("layout", {}).get("barmode") != "stack":
        failures.append("plotly_stack")
    axes = [t.get("yaxis", "y") for t in traces]
    if len(series) > 1 and layout == "separate" and len(set(axes)) != len(series):
        failures.append("plotly_subplot_layout")
    if layout == "combined" and len(set(axes)) > 1:
        failures.append("plotly_unrequested_axes")
    return sorted(set(failures))


def check_resolution(gold, prediction):
    failures = []
    if prediction.get("decision") != gold["decision"]:
        failures.append("resolution_decision")
    got = prediction.get("table_ids", [])
    if len(got) != len(set(got)):
        failures.append("duplicate_table")
    if gold["decision"] == "resolved":
        if set(got) not in [set(option) for option in gold["acceptable_table_sets"]]:
            failures.append("selected_tables")
        if gold.get("series_selection"):
            try:
                if Counter(identity(s) for s in gold["series_selection"]) != Counter(identity(s) for s in prediction.get("series_selection", [])):
                    failures.append("selected_series_identity")
            except (KeyError, TypeError, ValueError):
                failures.append("selected_series_identity")
    elif got:
        failures.append("unresolved_has_selected_tables")
    clarification = gold["clarification"]
    if clarification["required"]:
        observed = prediction.get("clarification", {})
        if not observed.get("asked"):
            failures.append("clarification_not_asked")
        options = observed.get("options", [])
        normalize = lambda text: re.sub(r"\s+", "", text)
        allowed = [term for group in clarification["option_groups"] for term in group]
        exact = {normalize(term): term for term in allowed}
        confirmed, uncertain = set(), set()
        for option in options:
            if not isinstance(option, str):
                failures.append("clarification_extra_options")
                continue
            key = normalize(option)
            if key in exact:
                confirmed.add(exact[key])
            else:
                mentioned = {term for term in allowed if normalize(term) in key}
                if mentioned:
                    uncertain.update(mentioned)
                    failures.append("clarification_semantics_unreviewed")
                else:
                    failures.append("clarification_extra_options")
        if len(options) != len(set(options)):
            failures.append("duplicate_clarification_options")
        for group in clarification["option_groups"]:
            if not set(group).issubset(confirmed | uncertain):
                failures.append("clarification_options")
        question = observed.get("question", "") + " ".join(observed.get("options", []))
        if not all(d in question for d in clarification["dimensions"]):
            failures.append("clarification_dimensions")
    elif prediction.get("clarification", {}).get("asked"):
        failures.append("unnecessary_clarification")
    return sorted(set(failures))


def score_case(case, prediction, review=None, base=BASE):
    if not prediction or prediction.get("execution_status") == "not_executed":
        return {"id": case["id"], "mode": case["mode"], "status": "not_executed", "failures": []}
    if prediction.get("execution_status") == "unobserved":
        return {"id": case["id"], "mode": case["mode"], "status": "unobserved", "failures": []}
    failures = []
    if not prediction.get("input_sha256"):
        failures.append("input_hash_missing")
    elif prediction["input_sha256"] != hashlib.sha256(
            json.dumps(case["input"], sort_keys=True, ensure_ascii=False).encode()).hexdigest():
        failures.append("input_hash_mismatch")
    if prediction.get("execution_status") != "observed":
        failures.append("execution_error")
    expected = case["expected"]
    if "resolution" in expected:
        failures += check_resolution(expected["resolution"], prediction.get("resolution", {}))
    if prediction.get("execution_status") != "observed":
        return {"id": case["id"], "mode": case["mode"], "status": "failed", "automatic_pass": False,
                "failures": sorted(set(failures)), "gold_approved": case["review"]["human_approved"],
                "interpretation_reviewed": False,
                "unobserved_checks": [name for name in ("data", "output", "edit")
                                      if name in expected or (name == "edit" and case["mode"] == "edit")]}
    if "data" in expected:
        fx = read_json(base / expected["data"]["fixture"])
        failures += compare_series(fx["series"], prediction.get("series", []), expected["data"]["absolute_tolerance"])
    if "output" in expected:
        out = expected["output"]
        chart_type = prediction.get("chart_type")
        if chart_type not in out["acceptable_chart_types"]:
            failures.append("chart_type")
        if prediction.get("layout") != out["layout"]:
            failures.append("chart_layout")
        failures += check_plotly(prediction.get("series", []), prediction.get("plotly_figure", {}), chart_type, out["layout"])
        for key, value in out.get("state", {}).items():
            if prediction.get("chart_state", {}).get(key) != value:
                failures.append("chart_state:" + key)
            fig_layout = (prediction.get("plotly_figure") or {}).get("layout", {})
            if key == "title" and fig_layout.get("title", {}).get("text") != value:
                failures.append("plotly_title")
            if key == "show_legend" and fig_layout.get("showlegend") != value:
                failures.append("plotly_legend")
        if out.get("preserve_data"):
            failures += ["edit_changed_source_data"] if prediction.get("source_data_preserved") is not True else []
        if case["mode"] == "edit" and prediction.get("statistics_calls_during_edit") != 0:
            failures.append("edit_requeried_data")
    from run import observation_hash
    bound_hash = observation_hash(prediction)
    review_valid = bool(review and review.get("prediction_sha256") == bound_hash == prediction.get("observation_sha256")
                        and review.get("reviewer") and review.get("human_approved") is True)
    semantic_review_required = "clarification_semantics_unreviewed" in failures
    if semantic_review_required and review_valid:
        if review.get("clarification_options_correct") is True:
            failures.remove("clarification_semantics_unreviewed")
        elif review.get("clarification_options_correct") is False:
            failures.append("clarification_review")
    if "output" in expected and review_valid:
        if not all(review.get(k) is True for k in ("facts_correct", "no_contradiction", "no_unsupported_claim", "claims_covered")):
            failures.append("interpretation_review")
    semantics_pending = "clarification_semantics_unreviewed" in failures
    hard_failures = [f for f in failures if f != "clarification_semantics_unreviewed"]
    status = "failed" if hard_failures else "pending_review" if semantics_pending or ("output" in expected and not review_valid) else "passed"
    return {"id": case["id"], "mode": case["mode"], "status": status,
            "automatic_pass": not failures and not semantic_review_required, "failures": sorted(set(failures)),
            "clarification_semantics_reviewed": semantic_review_required and review_valid and review.get("clarification_options_correct") in (True, False),
            "gold_approved": case["review"]["human_approved"], "interpretation_reviewed": review_valid}


def unique_rows(rows, label):
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate " + label + " IDs")
    return {r["id"]: r for r in rows}


def score(cases, predictions, reviews=(), base=BASE):
    case_map, pred_map, review_map = unique_rows(cases, "case"), unique_rows(predictions, "prediction"), unique_rows(reviews, "review")
    if set(pred_map) - set(case_map) or set(review_map) - set(case_map):
        raise ValueError("unknown prediction/review IDs")
    results = []
    for c in cases:
        try:
            results.append(score_case(c, pred_map.get(c["id"]), review_map.get(c["id"]), base))
        except (KeyError, TypeError, ValueError) as exc:
            results.append({"id": c["id"], "mode": c["mode"], "status": "failed", "automatic_pass": False,
                            "gold_approved": c["review"]["human_approved"], "interpretation_reviewed": False,
                            "failures": ["invalid_observation:" + type(exc).__name__]})
    summary = {mode: dict(Counter(r["status"] for r in results if r["mode"] == mode)) for mode in MODES}
    return {"summary": summary, "cases": results,
            "approved_summary": {mode: dict(Counter(r["status"] for r in results if r["mode"] == mode and r.get("gold_approved"))) for mode in MODES},
            "draft_summary": {mode: dict(Counter(r["status"] for r in results if r["mode"] == mode and not r.get("gold_approved"))) for mode in MODES},
            "automatic_summary": {mode: {"pass": sum(r.get("automatic_pass", False) for r in results if r["mode"] == mode),
                "fail": sum(r["status"] == "failed" for r in results if r["mode"] == mode),
                "unobserved": sum(r["status"] == "unobserved" for r in results if r["mode"] == mode),
                "not_executed": sum(r["status"] == "not_executed" for r in results if r["mode"] == mode)} for mode in MODES},
            "official_approved_cases": sum(c["review"]["human_approved"] for c in cases),
            "note": "Draft diagnostics; pending human interpretation is never a pass."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases")
    parser.add_argument("predictions")
    parser.add_argument("--reviews")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = score(read_jsonl(args.cases), read_jsonl(args.predictions), read_jsonl(args.reviews) if args.reviews else [])
    write_json(args.output, result)
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
