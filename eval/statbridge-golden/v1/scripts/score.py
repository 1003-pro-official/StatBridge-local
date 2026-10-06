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


# Prediction record contract (nested by layer):
# {"id": str,
#  "status": "select|clarify|no_match|catalog_only", "table_ids": [str],
#  "slots": {"metric"|"metrics", "target", "frequency", "basis", "period": {"start","end"}},
#  "concepts": {"concepts": [str]},
#  "clarification": {"asked": bool, "options": [str]},
#  "plan": {"tool_sequences": [[str]]},
#  "e2e": {"pass": bool},
#  "numeric": {"series": [{"table_id","item_id","points":[{"period","value"}]}]},
#  "graph": {"chart_type", "layout", "series": [...]},
#  "interpretation": {"claims": [ ... ]}}

def classify(case_result):
    if case_result.get("forbidden_hit"):
        return "forbidden_hit"
    if case_result.get("exact"):
        return "correct"
    return "mismatch"


def _as_set(v):
    if v is None:
        return None
    return set(v) if isinstance(v, list) else {v}


def score_slots(gold, pred):
    p = pred.get("slots") or {}
    checks = hits = 0
    gm = _as_set(gold.get("metrics") or gold.get("metric"))
    pm = _as_set(p.get("metrics") or p.get("metric"))
    if gm is not None:
        checks += 1
        hits += int(gm == pm)
    for f in ("target", "frequency", "basis"):
        if gold.get(f) is not None:
            checks += 1
            hits += int(p.get(f) == gold.get(f))
    gp, pp = gold.get("period") or {}, p.get("period") or {}
    for k in ("start", "end"):
        if gp.get(k):
            checks += 1
            hits += int(pp.get(k) == gp.get(k))
    return {"hit": hits, "total": checks, "exact": checks == 0 or hits == checks}


def score_concepts(gold, pred):
    acc = set(gold.get("acceptable_concepts", []))
    got = set((pred.get("concepts") or {}).get("concepts", []))
    if not acc and not got:
        return {"recall": 1.0, "exact": True}
    recall = len(acc & got) / len(acc) if acc else 1.0
    return {"recall": recall, "exact": bool(acc & got)}


def score_clarification(gold, pred):
    need = bool(gold.get("need_clarification"))
    asked = bool((pred.get("clarification") or {}).get("asked", False))
    return {"need": need, "asked": asked, "exact": need == asked}


def score_plan(gold, pred):
    acc = gold.get("acceptable_tool_sequences", [])
    got = (pred.get("plan") or {}).get("tool_sequences", [])
    return {"exact": any(seq in acc for seq in got) if acc else True}


def score_e2e(gold, pred):
    want = bool(gold.get("pass"))
    got = bool((pred.get("e2e") or {}).get("pass", False))
    return {"exact": want == got}


def _fixture_path(gold, v1):
    node = gold.get("graph") or gold.get("numeric") or {}
    f = node.get("fixture")
    return (v1 / f) if f else None


_SCALAR = {"slots": score_slots, "concepts": score_concepts,
           "clarification": score_clarification, "plan": score_plan, "e2e_kpi": score_e2e}


def score(gold_path, pred_path, out_dir=None, tol=0.01):
    gold = {r["id"]: r for r in load(gold_path)}
    pred = {r["id"]: r for r in load(pred_path)}
    results, failures = [], []
    for gid, g in gold.items():
        p = pred.get(gid, {})
        case = {"id": gid, "forbidden_hit": False, "exact": True, "layers": {}}
        gmap = g["gold"]
        checks = []
        for layer, fn in _SCALAR.items():
            node = gmap.get(layer, {})
            if node.get("status") != "labeled":
                continue
            res = fn(node, p)
            case["layers"][layer] = res
            checks.append(res["exact"])
        dnode = gmap.get("discovery", {})
        if dnode.get("status") == "labeled":
            dr = score_discovery(dnode, p)
            case["layers"]["discovery"] = dr
            checks.append(dr["exact"])
            case["forbidden_hit"] |= dr["forbidden_hit"]
        for layer in ("numeric", "graph"):
            gnode = gmap.get(layer, {})
            if gnode.get("status") != "labeled":
                continue
            fp = _fixture_path({"graph": gnode}, V1)
            fixture = json.loads(Path(fp).read_text(encoding="utf-8")) if fp else {"series": []}
            res = score_graph(gnode, fixture, p.get("graph") or {}, tol) if layer == "graph" \
                else score_numeric(fixture, p.get("numeric") or {}, tol)
            case["layers"][layer] = res
            checks.append(res["exact"])
        inode = gmap.get("interpretation", {})
        if inode.get("status") == "labeled":
            ir = score_interpretation(inode, p.get("interpretation") or {})
            case["layers"]["interpretation"] = ir
            checks.append(ir["exact"])
            case["forbidden_hit"] |= ir["forbidden_hit"]
        case["exact"] = bool(checks and all(checks))
        case["grade"] = classify(case)
        results.append(case)
        if case["grade"] != "correct":
            failures.append({"id": gid, "grade": case["grade"],
                             "failed_layer": _first_failed(case), "reason": case["layers"]})
    summary = {"n": len(results),
               "correct": sum(r["grade"] == "correct" for r in results),
               "forbidden_hit": sum(r["grade"] == "forbidden_hit" for r in results),
               "mismatch": sum(r["grade"] == "mismatch" for r in results)}
    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "failures.jsonl").write_text(
            "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in failures), encoding="utf-8")
    return {"summary": summary, "cases": results}


def _first_failed(case):
    if case["forbidden_hit"]:
        return "forbidden"
    for layer, res in case["layers"].items():
        if isinstance(res, dict) and res.get("exact") is False:
            return layer
    return "e2e_kpi"


def main(argv):
    gold, pred = argv[0], argv[1]
    out_dir = argv[2] if len(argv) > 2 else None
    print(json.dumps(score(gold, pred, out_dir=out_dir)["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
