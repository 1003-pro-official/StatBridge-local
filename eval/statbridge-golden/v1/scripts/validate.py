#!/usr/bin/env python3
"""Validate the StatBridge golden set (structure, leakage, strata, fixtures)."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path

V1 = Path(__file__).resolve().parents[1]
REPO = V1.parents[2]
GOLD_KEYS = ["e2e_kpi","slots","concepts","clarification","plan","discovery","numeric","graph","interpretation"]
STATUS = {"labeled", "not_labeled", "not_applicable"}
HOLDOUT_ALLOWED = {"id", "query", "prior_turns"}
CLAIM_TYPES = {"direction","level","extreme","comparison","change","turning_point","subperiod","pace","volatility","context"}


def load(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_record(r):
    errs = []
    rid = r.get("id", "?")
    for k in ("id", "split", "input", "gold", "review"):
        if k not in r:
            errs.append(f"{rid}: missing {k}")
    if r.get("split") not in ("dev", "test", "holdout"):
        errs.append(f"{rid}: bad split")
    inp = r.get("input", {})
    if "query" not in inp:
        errs.append(f"{rid}: missing input.query")
    if "prior_turns" not in inp:
        errs.append(f"{rid}: missing input.prior_turns")
    gold = r.get("gold", {})
    for k in GOLD_KEYS:
        if k not in gold:
            errs.append(f"{rid}: gold missing {k}")
    for k, v in gold.items():
        if isinstance(v, dict) and v.get("status") not in STATUS:
            errs.append(f"{rid}: {k}.status invalid")
    d = gold.get("discovery", {})
    if d.get("status") == "labeled":
        st = d.get("expected_status")
        if st not in ("select", "clarify", "no_match", "catalog_only"):
            errs.append(f"{rid}: bad expected_status")
        acc = set(d.get("acceptable_table_ids", []))
        req = set(d.get("required_set", []))
        forb = set(d.get("forbidden_table_ids", []))
        if not req <= acc:
            errs.append(f"{rid}: required_set not subset of acceptable")
        if acc & forb:
            errs.append(f"{rid}: forbidden overlaps acceptable")
        if st == "no_match" and acc:
            errs.append(f"{rid}: no_match has tables")
        if st == "clarify" and acc:
            errs.append(f"{rid}: clarify has tables")
        if st == "select" and not acc:
            errs.append(f"{rid}: select without tables")
    interp = gold.get("interpretation", {})
    if interp.get("status") == "labeled":
        for c in interp.get("required_claims", []):
            if c.get("type") not in CLAIM_TYPES:
                errs.append(f"{rid}: bad claim type {c.get('type')}")
        for c in interp.get("context_claims", []):
            if not c.get("source"):
                errs.append(f"{rid}: context claim without source")
    return errs
