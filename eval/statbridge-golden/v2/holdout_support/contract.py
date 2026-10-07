"""Neutral holdout contracts; no private cases or answers are embedded."""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter

MODES = {"discovery": 6, "e2e": 8, "output": 3, "edit": 1}
CHECKS = ("question_clear", "original_locator_verified", "numbers_units_frequency_verified",
          "acceptable_answers_verified", "public_overlap_checked", "independent_recalculation")


def value_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def holdout_schema(public_schema):
    schema = copy.deepcopy(public_schema)
    schema["title"] = "StatBridge private holdout v2"
    schema["properties"]["id"]["pattern"] = r"^SBV2-H[0-9]{4}$"
    schema["properties"]["split"] = {"const": "holdout"}
    return schema


def series_key(series):
    return [series["provider"], series["table_id"], series["item_id"],
            sorted(series["classifications"].items()), series["frequency"], series["unit"]]


def exclusion_index(cases, load_fixture, shared_definitions=()):
    research, locators, periods = set(), set(), set()
    shared = {tuple(v) for v in shared_definitions}
    for case in cases:
        research.update(case["evidence"]["research_result_ids"])
        for source in case["evidence"]["sources"]:
            if not source["path"].endswith(".csv") and (source["sha256"], source["locator"]) not in shared:
                locators.add((source["sha256"], source["locator"]))
        data = case["expected"].get("data")
        if data:
            for series in load_fixture(data.get("source_fixture") or data["fixture"])["series"]:
                for point in series["points"]:
                    periods.add(value_hash([series_key(series), point["period"]]))
    return {"public_cases": len(cases), "research_result_ids": sorted(research),
            "source_locators": [list(v) for v in sorted(locators)],
            "shared_methodology_locators": [list(v) for v in sorted(shared)],
            "series_period_sha256": sorted(periods),
            "policy": "No shared research result/figure or series-period; table reuse alone is allowed."}


def check_candidates(cases, exclusions, load_fixture, complete=True):
    errors = []
    if complete and Counter(c.get("mode") for c in cases) != MODES:
        errors.append("holdout mode quotas: discovery 6/e2e 8/output 3/edit 1")
    if complete:
        ids = {c.get("id") for c in cases}
        if ids != {f"SBV2-H{i:04d}" for i in range(1, 19)}:
            errors.append("holdout IDs must be H0001..H0018")
        decisions = Counter(c.get("expected", {}).get("resolution", {}).get("decision")
                            for c in cases if c.get("mode") == "discovery")
        if decisions != {"resolved": 3, "clarify": 2, "unsupported": 1}:
            errors.append("holdout discovery quotas")
        kinds = Counter(t for c in cases if c.get("mode") == "e2e" for t in c.get("tags", []) if t in {"single", "multi"})
        if kinds != {"single": 6, "multi": 2}:
            errors.append("holdout e2e quotas")
        charts = [(c["input"].get("output_request", {}).get("chart_type"),
                   c["input"].get("output_request", {}).get("layout")) for c in cases if c.get("mode") == "output"]
        if sorted(charts, key=str) != sorted([("line", "combined"), ("bar", "combined"), ("line", "separate")], key=str):
            errors.append("holdout output quotas")
    known_research = set(exclusions["research_result_ids"])
    known_locators = {tuple(v) for v in exclusions["source_locators"]}
    known_periods = set(exclusions["series_period_sha256"])
    for case in cases:
        cid, payload, expected = case["id"], case["input"], case["expected"]
        if payload["prior_turns"] or "data_fixture" in payload or any(w in payload["query"] for w in ("첨부", "앞서")):
            errors.append(cid + ": upload/prior-dialogue assumption")
        if "ai-assisted" not in case["review"]["annotation_method"]:
            errors.append(cid + ": missing ai-assisted disclosure")
        evidence = case["evidence"]
        if known_research.intersection(evidence["research_result_ids"]):
            errors.append(cid + ": public research result overlap")
        if any((s["sha256"], s["locator"]) in known_locators for s in evidence["sources"]):
            errors.append(cid + ": public source locator overlap")
        if case["mode"] == "edit" and payload.get("offline_edit_command", {}).get("operation") != "set_title":
            errors.append(cid + ": holdout edit must change title")
        data = expected.get("data")
        if not data:
            continue
        try:
            raw = load_fixture(data.get("source_fixture") or data["fixture"])["series"]
            if any(value_hash([series_key(s), p["period"]]) in known_periods for s in raw for p in s["points"]):
                errors.append(cid + ": public series-period overlap")
            actions = [a for a in payload["actions"] if a["kind"] == "confirm_period"]
            if case["mode"] != "discovery":
                if len(actions) != 1:
                    errors.append(cid + ": exactly one absolute period required")
                else:
                    for s in raw:
                        first, last = actions[0]["start"].replace("-", ""), actions[0]["end"].replace("-", "")
                        if s["frequency"] == "M":
                            first, last = first[:6], last[:6]
                        elif s["frequency"] == "Q":
                            first, last = (v[:4] + "Q" + str((int(v[4:6])-1)//3+1) for v in (first, last))
                        elif s["frequency"] == "Y":
                            first, last = first[:4], last[:4]
                        if not s["points"] or (first, last) != (s["points"][0]["period"], s["points"][-1]["period"]):
                            errors.append(cid + ": period/source fixture mismatch")
                        if first[:4] not in payload["query"] or last[:4] not in payload["query"]:
                            errors.append(cid + ": query must state absolute years")
            if case["mode"] == "e2e":
                tag = "multi" if len(raw) > 1 else "single"
                if tag not in case["tags"]:
                    errors.append(cid + ": series count/subtype mismatch")
            if case["mode"] == "output" and payload.get("output_request", {}).get("layout") == "separate" and len(raw) < 2:
                errors.append(cid + ": separate output requires multiple series")
        except (OSError, KeyError, TypeError, ValueError):
            errors.append(cid + ": unavailable/invalid source fixture")
    return errors


def check_approvals(cases, approvals):
    by_id = {a["id"]: a for a in approvals}
    errors = []
    if len(by_id) != len(approvals) or set(by_id) != {c["id"] for c in cases}:
        errors.append("approval IDs duplicate/missing/unknown")
    for case in cases:
        row = by_id.get(case["id"], {})
        reviewer = row.get("reviewer")
        if not reviewer or not row.get("author") or reviewer == row.get("author"):
            errors.append(case["id"] + ": independent reviewer required")
        if row.get("case_sha256") != value_hash(case):
            errors.append(case["id"] + ": approval hash mismatch")
        if row.get("human_approved") is not True or any(row.get(k) is not True for k in CHECKS):
            errors.append(case["id"] + ": human checks pending")
        if case["review"]["human_approved"] is not True or case["review"]["reviewer"] != reviewer:
            errors.append(case["id"] + ": inconsistent case approval")
        if not isinstance(row.get("implementation_exposure"), bool):
            errors.append(case["id"] + ": implementation exposure declaration missing")
    return errors


def aggregate_report(scored, environment):
    return {"evaluation_family": "statbridge-golden/v2/holdout", "environment": environment,
            "official_approved_cases": scored["official_approved_cases"],
            "summary": scored["summary"], "automatic_summary": scored["automatic_summary"],
            "limitations": ["Offline command replay does not assess natural-language editing.",
                            "No live/browser validation; pending review is not success."]}
