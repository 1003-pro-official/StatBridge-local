#!/usr/bin/env python3
"""Score predictions against the StatBridge golden set."""
from __future__ import annotations
import json, sys
from pathlib import Path

V1 = Path(__file__).resolve().parents[1]


def load(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def _prf(gold, pred):
    tp = len(gold & pred); fp = len(pred - gold); fn = len(gold - pred)
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1


def score_discovery(gold, pred):
    st_g = gold.get("expected_status")
    st_p = pred.get("status")
    status_ok = st_g == st_p
    A = set(gold.get("acceptable_table_ids", []))
    R = set(gold.get("required_set", []))
    B = set(pred.get("table_ids", []))
    forbidden = set(gold.get("forbidden_table_ids", []))
    if not R:
        R = A
    p, r, f1 = _prf(R, B) if (R or B) else (1.0, 1.0, 1.0)
    return {
        "status_ok": status_ok,
        "exact": bool(status_ok and A == B),
        "precision": p, "recall": r, "f1": f1,
        "forbidden_hit": bool(forbidden & B),
    }


def _points_ok(expected, actual, tol):
    if len(expected) != len(actual):
        return False
    exp = {p["period"]: p["value"] for p in expected}
    act = {p["period"]: p["value"] for p in actual}
    if set(exp) != set(act):
        return False
    return all(abs(exp[k] - act[k]) <= tol for k in exp)


def score_graph(gold, fixture, pred, tol=0.01):
    exp_series = fixture.get("series", [])
    act_series = pred.get("series", [])

    def key(s):
        return (s.get("table_id"), s.get("item_id"))

    exp_keys = {key(s) for s in exp_series}
    act_keys = {key(s) for s in act_series}
    series_ok = exp_keys == act_keys
    points_ok = series_ok and all(
        _points_ok(e.get("points", []), next(
            (a.get("points", []) for a in act_series if key(a) == key(e)), []), tol)
        for e in exp_series)
    return {
        "type_ok": gold.get("chart_type") == pred.get("chart_type"),
        "layout_ok": gold.get("layout") == pred.get("layout"),
        "series_ok": series_ok,
        "points_ok": bool(points_ok),
        "exact": bool(gold.get("chart_type") == pred.get("chart_type")
                      and gold.get("layout") == pred.get("layout")
                      and series_ok and points_ok),
    }


def score_numeric(fixture, pred, tol=0.01):
    exp_series = fixture.get("series", [])
    act_series = pred.get("series", [])

    def key(s):
        return (s.get("table_id"), s.get("item_id"))

    exp_keys = {key(s) for s in exp_series}
    act_keys = {key(s) for s in act_series}
    ok = exp_keys == act_keys and all(
        _points_ok(e.get("points", []), next(
            (a.get("points", []) for a in act_series if key(a) == key(e)), []), tol)
        for e in exp_series)
    return {"series_ok": exp_keys == act_keys, "points_ok": bool(ok),
            "exact": bool(exp_keys == act_keys and ok)}


def _claim_match(gc, pc):
    if gc.get("type") != pc.get("type"):
        return False
    for field in ("series", "period", "subtype", "metric"):
        if gc.get(field) is not None and pc.get(field) != gc.get(field):
            return False
    if "expected" in gc and pc.get("expected") != gc["expected"]:
        return False
    if "expected_value" in gc:
        if "value" not in pc:
            return False
        if abs(pc["value"] - gc["expected_value"]) > gc.get("tolerance", 0.0):
            return False
    if "value" in gc and abs(pc.get("value", 0) - gc["value"]) > gc.get("tolerance", 0.0):
        return False
    return True


def score_interpretation(gold, pred):
    req = gold.get("required_claims", [])
    pcs = pred.get("claims", [])
    hit = sum(1 for gc in req if any(_claim_match(gc, pc) for pc in pcs))
    forbidden = gold.get("forbidden_claims", [])
    fhit = any(fc.get("type") == pc.get("type") and fc.get("text") == pc.get("text")
               for fc in forbidden for pc in pcs)
    return {
        "claim_recall": hit / len(req) if req else 1.0,
        "required_hit": hit, "required_total": len(req),
        "forbidden_hit": fhit,
        "exact": bool(not fhit and hit == len(req)),
    }
