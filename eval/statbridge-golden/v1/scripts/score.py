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
