# StatBridge 골든셋 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** `docs/superpowers/specs/2026-10-06-statbridge-golden-set-design.md`의 정의대로 StatBridge 골든셋(9계층·오답 함정·회귀)의 스키마·검증기(validator)·채점기(scorer)·시드 사례·생성 절차를 구현한다.

**Architecture:** 새 계열 `eval/statbridge-golden/v1/`에 stdlib 전용 Python으로 validator와 scorer를 만든다. 데이터는 JSONL 레코드 + fixture JSON. 스키마 검증·누수·층화·fixture 무결성은 validator가, 채점·오답 분류·회귀는 scorer가 담당한다. 생성 절차는 문서(SOP)로 두고, 이 계획은 도구 + 시드 2건까지 만든다(90건 전체 저작은 후속 콘텐츠 작업).

**Tech Stack:** Python 3.11+ 표준 라이브러리만(json, csv, hashlib, argparse, unittest). 기존 스타일은 `eval/table-discovery/v4.1/scripts/`, `tools/evaluate_golden_set.py` 참조.

**규칙(AGENTS.md):** `main` 직접 푸시 금지 → 기능 브랜치 + PR. 커밋은 Conventional Commits(`eval`, `feat`, `test`, `docs`). 검증은 `.venv/bin/python` 대신 이 환경에선 시스템 파이썬 사용.

---

## 사전 결정 사항

- 대상 경로: `eval/statbridge-golden/v1/` (새 계열, 기존 v1~v4.1·end-to-end와 분리)
- 레코드 `schema_version`: `"gs1"`
- 데이터: `cases/dev.jsonl`, `cases/test.jsonl`, `cases/holdout_queries.jsonl`(정답 없음), `fixtures/*.json`
- 실행 명령(로컬): `python3 -m pytest eval/statbridge-golden/v1/tests -q` (없으면 `pytest ...`)

**최종 구조**

```
eval/statbridge-golden/v1/
  README.md
  schema.json
  manifest.json
  cases/dev.jsonl
  cases/test.jsonl
  cases/holdout_queries.jsonl
  fixtures/esi-2025.json
  fixtures/trade_price_2025.json
  scripts/validate.py
  scripts/score.py
  tests/test_validate.py
  tests/test_score.py
```

---

### Task 0: 기능 브랜치 생성

**Files:** 없음(브랜치만)

**Step 1: 브랜치 생성**

```bash
git checkout -b feat/statbridge-golden-set
```

**Step 2: 확인**

Run: `git branch --show-current`
Expected: `feat/statbridge-golden-set`

---

### Task 1: 스캐폴드 + 스키마 + README

**Files:**
- Create: `eval/statbridge-golden/v1/README.md`
- Create: `eval/statbridge-golden/v1/schema.json`
- Create: `eval/statbridge-golden/v1/manifest.json`
- Create: `eval/statbridge-golden/v1/cases/dev.jsonl` (빈 파일)
- Create: `eval/statbridge-golden/v1/cases/test.jsonl` (빈 파일)
- Create: `eval/statbridge-golden/v1/cases/holdout_queries.jsonl` (빈 파일)
- Create: `eval/statbridge-golden/v1/fixtures/` (디렉터리)

**Step 1: 디렉터리 생성**

```bash
mkdir -p eval/statbridge-golden/v1/{cases,fixtures,scripts,tests}
touch eval/statbridge-golden/v1/cases/{dev.jsonl,test.jsonl,holdout_queries.jsonl}
```

**Step 2: `schema.json` 작성**

```json
{
  "schema_version": "gs1",
  "gold_layers": ["e2e_kpi", "slots", "concepts", "clarification", "plan", "discovery", "numeric", "graph", "interpretation"],
  "status": ["labeled", "not_labeled", "not_applicable"],
  "expected_status": ["select", "clarify", "no_match", "catalog_only"],
  "claim_types": ["direction", "level", "extreme", "comparison", "change", "turning_point", "subperiod", "pace", "volatility", "context"],
  "id_prefix": "GS2-"
}
```

**Step 3: `manifest.json` 작성**

```json
{
  "lineage": "statbridge-golden",
  "version": "v1",
  "schema_version": "gs1",
  "targets": { "dev": 30, "test": 42, "holdout": 18, "total": 90 },
  "type_matrix": {
    "single":       { "dev": 12, "test": 18, "holdout": 6 },
    "followup":     { "dev": 6,  "test": 8,  "holdout": 4 },
    "multi":        { "dev": 4,  "test": 6,  "holdout": 3 },
    "clarify":      { "dev": 4,  "test": 6,  "holdout": 3 },
    "no_match":     { "dev": 3,  "test": 3,  "holdout": 1 },
    "catalog_only": { "dev": 1,  "test": 1,  "holdout": 1 }
  },
  "snapshot_id": "statbridge-local-csv-frozen-2026-09-28",
  "review": { "human_approval_required": true }
}
```

**Step 4: `README.md` 작성**

```markdown
# StatBridge Golden Set (lineage: statbridge-golden, v1)

정의는 `docs/superpowers/specs/2026-10-06-statbridge-golden-set-design.md`를 따른다.
정답의 우주는 KOSIS 한국은행 349표(`data/kosis/hankook_tables.json`)다.

## 실행
- 검증: `python3 eval/statbridge-golden/v1/scripts/validate.py`
- 채점: `python3 eval/statbridge-golden/v1/scripts/score.py <gold.jsonl> <pred.jsonl>`
- 테스트: `python3 -m pytest eval/statbridge-golden/v1/tests -q`

## 구성
- `cases/dev.jsonl`, `cases/test.jsonl`: 정답 포함
- `cases/holdout_queries.jsonl`: 정답 미포함(공개), 정답은 비공개 저장소
- `fixtures/`: 그래프·수치 스냅샷(로컬 CSV 해시 포함)
```

**Step 5: 커밋**

```bash
git add eval/statbridge-golden/v1
git commit -m "eval: scaffold statbridge-golden v1 (schema, manifest, README)"
```

---

### Task 2: validator — 파일 로드와 기본 구조 검사 (TDD)

**Files:**
- Create: `eval/statbridge-golden/v1/scripts/validate.py`
- Test: `eval/statbridge-golden/v1/tests/test_validate.py`

**Step 1: 실패하는 테스트 작성**

```python
import json, subprocess, sys, unittest
from pathlib import Path
V1 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V1 / "scripts"))
import validate as V

GOOD = {
    "id": "GS2-0001", "schema_version": "gs1", "split": "dev",
    "source": {"publisher": "한국은행"},
    "input": {"prior_turns": [], "query": "질의"},
    "gold": {k: {"status": "not_labeled"} for k in
             ["e2e_kpi","slots","concepts","clarification","plan","discovery","numeric","graph","interpretation"]},
    "provenance": {}, "review": {"machine_reviewed": True, "human_approved": False},
}

class TestValidateStructure(unittest.TestCase):
    def test_good_record_has_no_errors(self):
        self.assertEqual(V.validate_record(GOOD), [])

    def test_missing_gold_layer_is_error(self):
        bad = json.loads(json.dumps(GOOD)); del bad["gold"]["graph"]
        self.assertTrue(any("gold missing" in e for e in V.validate_record(bad)))

    def test_bad_status_is_error(self):
        bad = json.loads(json.dumps(GOOD)); bad["gold"]["graph"]["status"] = "maybe"
        self.assertTrue(any("status invalid" in e for e in V.validate_record(bad)))
```

**Step 2: 실패 확인**

Run: `python3 -m pytest eval/statbridge-golden/v1/tests/test_validate.py -q`
Expected: FAIL (`No module named 'validate'`)

**Step 3: `validate.py` 최소 구현**

```python
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
    return errs
```

**Step 4: 통과 확인**

Run: `python3 -m pytest eval/statbridge-golden/v1/tests/test_validate.py -q`
Expected: PASS (3 passed)

**Step 5: 커밋**

```bash
git add eval/statbridge-golden/v1/scripts/validate.py eval/statbridge-golden/v1/tests/test_validate.py
git commit -m "test: validator structure checks for golden set"
```

---

### Task 3: validator — discovery·interpretation 정합성

**Files:**
- Modify: `eval/statbridge-golden/v1/scripts/validate.py`
- Modify: `eval/statbridge-golden/v1/tests/test_validate.py`

**Step 1: 실패하는 테스트 추가**

```python
    def test_forbidden_overlaps_acceptable_is_error(self):
        r = json.loads(json.dumps(GOOD))
        r["gold"]["discovery"] = {"status": "labeled", "expected_status": "select",
                                  "acceptable_table_ids": ["DT_A"], "required_set": ["DT_A"],
                                  "forbidden_table_ids": ["DT_A"]}
        self.assertTrue(any("forbidden overlaps" in e for e in V.validate_record(r)))

    def test_no_match_with_tables_is_error(self):
        r = json.loads(json.dumps(GOOD))
        r["gold"]["discovery"] = {"status": "labeled", "expected_status": "no_match",
                                  "acceptable_table_ids": ["DT_A"], "required_set": [],
                                  "forbidden_table_ids": []}
        self.assertTrue(any("no_match has tables" in e for e in V.validate_record(r)))

    def test_context_claim_requires_source(self):
        r = json.loads(json.dumps(GOOD))
        r["gold"]["interpretation"] = {"status": "labeled",
            "required_claims": [{"id": "c1", "type": "direction", "expected": "up"}],
            "context_claims": [{"id": "x1", "type": "context", "text": "맥락"}]}
        self.assertTrue(any("context claim without source" in e for e in V.validate_record(r)))
```

**Step 2: 실패 확인**

Run: `python3 -m pytest eval/statbridge-golden/v1/tests/test_validate.py -q`
Expected: FAIL (새 3개 실패)

**Step 3: `validate_record`에 규칙 추가**

`for k, v in gold.items(): ...` 아래에 추가:

```python
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
```

**Step 4: 통과 확인**

Run: `python3 -m pytest eval/statbridge-golden/v1/tests/test_validate.py -q`
Expected: PASS (6 passed)

**Step 5: 커밋**

```bash
git add eval/statbridge-golden/v1/scripts/validate.py eval/statbridge-golden/v1/tests/test_validate.py
git commit -m "test: validator discovery and interpretation consistency"
```

---

### Task 4: validator — fixture 무결성·누수·층화 + CLI

**Files:**
- Modify: `eval/statbridge-golden/v1/scripts/validate.py`
- Modify: `eval/statbridge-golden/v1/tests/test_validate.py`

**Step 1: 실패하는 테스트 추가**

```python
    def test_fixture_missing_is_error(self):
        r = json.loads(json.dumps(GOOD))
        r["gold"]["graph"] = {"status": "labeled", "fixture": "fixtures/none.json", "snapshot_id": "x"}
        errs = V.validate_fixtures(r, V1)
        self.assertTrue(any("fixture missing" in e for e in errs))

    def test_holdout_leakage_is_error(self):
        errs = V.validate_holdout([{"id": "H1", "query": "q", "prior_turns": [], "table_ids": ["DT_A"]}])
        self.assertTrue(any("holdout leakage" in e for e in errs))
```

**Step 2: 실패 확인**

Run: `python3 -m pytest eval/statbridge-golden/v1/tests/test_validate.py -q`
Expected: FAIL (`validate_fixtures`/`validate_holdout` 없음)

**Step 3: 함수 + CLI 추가**

`validate_record` 아래에 추가:

```python
def validate_fixtures(r, base):
    errs = []
    for layer in ("numeric", "graph"):
        node = r.get("gold", {}).get(layer, {})
        if node.get("status") != "labeled":
            continue
        f = node.get("fixture")
        if not f:
            errs.append(f"{r['id']}: {layer} labeled without fixture")
            continue
        fp = base / f
        if not fp.is_file():
            errs.append(f"{r['id']}: fixture missing {f}")
            continue
        if node.get("fixture_sha256") and sha256_file(fp) != node["fixture_sha256"]:
            errs.append(f"{r['id']}: fixture_sha256 mismatch")
        fx = json.loads(fp.read_text(encoding="utf-8"))
        series = fx.get("series", [])
        if not series:
            errs.append(f"{r['id']}: fixture has no series")
        if node.get("snapshot_id") and fx.get("snapshot_id") != node["snapshot_id"]:
            errs.append(f"{r['id']}: snapshot mismatch")
        for s in series:
            ps = [p["period"] for p in s.get("points", [])]
            if len(ps) != len(set(ps)):
                errs.append(f"{r['id']}: duplicate periods")
            if ps != sorted(ps):
                errs.append(f"{r['id']}: periods not ordered")
            sf, sha = s.get("source_file"), s.get("source_file_sha256")
            if sf and sha and (REPO / sf).is_file() and sha256_file(REPO / sf) != sha:
                errs.append(f"{r['id']}: source_file_sha256 mismatch {sf}")
    return errs


def validate_holdout(records):
    errs = []
    for r in records:
        leaked = set(r) - HOLDOUT_ALLOWED
        if leaked:
            errs.append(f"{r['id']}: holdout leakage {sorted(leaked)}")
    return errs


def validate_all():
    errs = []
    dev = load(V1 / "cases/dev.jsonl")
    test = load(V1 / "cases/test.jsonl")
    holdout = load(V1 / "cases/holdout_queries.jsonl")
    labeled = dev + test
    ids = [r["id"] for r in labeled] + [r["id"] for r in holdout]
    if len(ids) != len(set(ids)):
        errs.append("duplicate ids across splits")
    for r in labeled:
        errs += validate_record(r)
        errs += validate_fixtures(r, V1)
    errs += validate_holdout(holdout)
    return errs


def main():
    errs = validate_all()
    for e in errs:
        print(e)
    print(f"{len(errs)} errors")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 4: 통과 확인 (빈 데이터에서도 오류 0)**

Run: `python3 -m pytest eval/statbridge-golden/v1/tests/test_validate.py -q && python3 eval/statbridge-golden/v1/scripts/validate.py`
Expected: 테스트 PASS, validator `0 errors`

**Step 5: 커밋**

```bash
git add eval/statbridge-golden/v1/scripts/validate.py eval/statbridge-golden/v1/tests/test_validate.py
git commit -m "test: validator fixture integrity, holdout leakage, CLI"
```

---

### Task 5: scorer — discovery 채점 (P/R/F1 + forbidden_hit)

**Files:**
- Create: `eval/statbridge-golden/v1/scripts/score.py`
- Test: `eval/statbridge-golden/v1/tests/test_score.py`

**Step 1: 실패하는 테스트 작성**

```python
import sys, unittest
from pathlib import Path
V1 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V1 / "scripts"))
import score as S

DISC = {"status": "labeled", "expected_status": "select",
        "acceptable_table_ids": ["DT_A", "DT_B"], "required_set": ["DT_A", "DT_B"],
        "forbidden_table_ids": ["DT_X"]}

class TestDiscovery(unittest.TestCase):
    def test_exact_match(self):
        out = S.score_discovery(DISC, {"status": "select", "table_ids": ["DT_A", "DT_B"]})
        self.assertEqual(out["exact"], True); self.assertEqual(out["f1"], 1.0)

    def test_partial_recall(self):
        out = S.score_discovery(DISC, {"status": "select", "table_ids": ["DT_A"]})
        self.assertFalse(out["exact"]); self.assertAlmostEqual(out["recall"], 0.5)

    def test_forbidden_hit(self):
        out = S.score_discovery(DISC, {"status": "select", "table_ids": ["DT_A", "DT_B", "DT_X"]})
        self.assertTrue(out["forbidden_hit"])
```

**Step 2: 실패 확인**

Run: `python3 -m pytest eval/statbridge-golden/v1/tests/test_score.py -q`
Expected: FAIL (`No module named 'score'`)

**Step 3: `score.py` 최소 구현**

```python
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
```

**Step 4: 통과 확인**

Run: `python3 -m pytest eval/statbridge-golden/v1/tests/test_score.py -q`
Expected: PASS (3 passed)

**Step 5: 커밋**

```bash
git add eval/statbridge-golden/v1/scripts/score.py eval/statbridge-golden/v1/tests/test_score.py
git commit -m "test: scorer discovery metrics and forbidden hit"
```

---

### Task 6: scorer — numeric·graph 채점

**Files:**
- Modify: `eval/statbridge-golden/v1/scripts/score.py`
- Modify: `eval/statbridge-golden/v1/tests/test_score.py`

**Step 1: 실패하는 테스트 추가**

```python
class TestGraph(unittest.TestCase):
    FX = {"series": [{"table_id": "DT_A", "item_id": "1",
                      "points": [{"period": "202501", "value": 1.0}, {"period": "202502", "value": 2.0}]}]}
    G = {"status": "labeled", "chart_type": "line", "layout": "combined"}

    def test_graph_exact(self):
        pred = {"chart_type": "line", "layout": "combined",
                "series": [{"table_id": "DT_A", "item_id": "1",
                            "points": [{"period": "202501", "value": 1.0}, {"period": "202502", "value": 2.0}]}]}
        out = S.score_graph(self.G, self.FX, pred, tol=0.01)
        self.assertTrue(out["type_ok"] and out["layout_ok"] and out["series_ok"] and out["points_ok"])

    def test_graph_wrong_type(self):
        out = S.score_graph(self.G, self.FX, {"chart_type": "bar", "layout": "combined", "series": []}, tol=0.01)
        self.assertFalse(out["type_ok"]); self.assertFalse(out["series_ok"])
```

**Step 2: 실패 확인**

Run: `python3 -m pytest eval/statbridge-golden/v1/tests/test_score.py -q`
Expected: FAIL (`score_graph` 없음)

**Step 3: 함수 추가**

```python
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
```

**Step 4: 통과 확인**

Run: `python3 -m pytest eval/statbridge-golden/v1/tests/test_score.py -q`
Expected: PASS (5 passed)

**Step 5: 커밋**

```bash
git add eval/statbridge-golden/v1/scripts/score.py eval/statbridge-golden/v1/tests/test_score.py
git commit -m "test: scorer numeric and graph exact checks"
```

---

### Task 7: scorer — interpretation 채점 (recall·환각·일치)

**Files:**
- Modify: `eval/statbridge-golden/v1/scripts/score.py`
- Modify: `eval/statbridge-golden/v1/tests/test_score.py`

**Step 1: 실패하는 테스트 추가**

```python
class TestInterpretation(unittest.TestCase):
    G = {"status": "labeled",
         "required_claims": [{"id": "c1", "type": "direction", "series": "수출", "period": "2025-01~2025-06", "expected": "down"},
                             {"id": "c2", "type": "level", "period": "202512", "expected_value": 94.8, "tolerance": 0.5}],
         "forbidden_claims": [{"type": "hallucination", "text": "하락세였다"}]}

    def test_hit_all(self):
        claims = [{"type": "direction", "series": "수출", "period": "2025-01~2025-06", "expected": "down"},
                  {"type": "level", "period": "202512", "value": 94.9}]
        out = S.score_interpretation(self.G, {"claims": claims})
        self.assertAlmostEqual(out["claim_recall"], 1.0); self.assertFalse(out["forbidden_hit"])

    def test_forbidden(self):
        out = S.score_interpretation(self.G, {"claims": [{"type": "hallucination", "text": "하락세였다"}]})
        self.assertTrue(out["forbidden_hit"])

    def test_partial(self):
        out = S.score_interpretation(self.G, {"claims": []})
        self.assertAlmostEqual(out["claim_recall"], 0.0)
```

**Step 2: 실패 확인**

Run: `python3 -m pytest eval/statbridge-golden/v1/tests/test_score.py -q`
Expected: FAIL (`score_interpretation` 없음)

**Step 3: 함수 추가**

```python
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
```

**Step 4: 통과 확인**

Run: `python3 -m pytest eval/statbridge-golden/v1/tests/test_score.py -q`
Expected: PASS (8 passed)

**Step 5: 커밋**

```bash
git add eval/statbridge-golden/v1/scripts/score.py eval/statbridge-golden/v1/tests/test_score.py
git commit -m "test: scorer interpretation claims and hallucination"
```

---

### Task 8: scorer — 종합·오답 분류·failures.jsonl·CLI

**Files:**
- Modify: `eval/statbridge-golden/v1/scripts/score.py`
- Modify: `eval/statbridge-golden/v1/tests/test_score.py`

**Step 1: 실패하는 테스트 추가**

```python
class TestGrade(unittest.TestCase):
    def test_status_hierarchy(self):
        self.assertEqual(S.classify({"forbidden_hit": True, "exact": True}), "forbidden_hit")
        self.assertEqual(S.classify({"forbidden_hit": False, "exact": True}), "correct")
        self.assertEqual(S.classify({"forbidden_hit": False, "exact": False}), "mismatch")
```

**Step 2: 실패 확인**

Run: `python3 -m pytest eval/statbridge-golden/v1/tests/test_score.py -q`
Expected: FAIL (`classify` 없음)

**Step 3: 함수 + CLI 추가**

```python
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
```

**Step 4: 통과 확인**

Run: `python3 -m pytest eval/statbridge-golden/v1/tests/test_score.py -q`
Expected: PASS (9 passed)

**Step 5: 커밋**

```bash
git add eval/statbridge-golden/v1/scripts/score.py eval/statbridge-golden/v1/tests/test_score.py
git commit -m "feat: scorer aggregation, failure classification, CLI"
```

---

### Task 9: 시드 사례 GS2-0001 (단일 그래프 + 해석)

**Files:**
- Create: `eval/statbridge-golden/v1/fixtures/esi-2025.json`
- Create: `eval/statbridge-golden/v1/cases/dev.jsonl` (레코드 1줄 추가)

**Step 1: fixture 작성** (값은 실제 `data/tables/DT_513Y001__경제심리지수.csv` E2000 계열)

```json
{
  "snapshot_id": "statbridge-local-csv-frozen-2026-09-28",
  "series": [{
    "table_id": "DT_513Y001", "item_id": "13103134473999",
    "label": "경제심리지수 순환변동치", "frequency": "M", "unit": "",
    "classifications": { "objL1": "13102134473ACC_CD.E2000" },
    "source_file": "data/tables/DT_513Y001__경제심리지수.csv",
    "source_file_sha256": "f7a94317fdaad7175dd1473e727fbff86e7473ae7767a2e3f1edbbb2ec5efdaa",
    "source_last_changed_dates": ["2026-09-13"],
    "points": [
      { "period": "202501", "value": 89.8 }, { "period": "202502", "value": 89.6 },
      { "period": "202503", "value": 89.6 }, { "period": "202504", "value": 89.9 },
      { "period": "202505", "value": 90.5 }, { "period": "202506", "value": 91.1 },
      { "period": "202507", "value": 91.9 }, { "period": "202508", "value": 92.6 },
      { "period": "202509", "value": 93.2 }, { "period": "202510", "value": 93.8 },
      { "period": "202511", "value": 94.3 }, { "period": "202512", "value": 94.8 }
    ]
  }]
}
```

**Step 2: fixture 해시 계산 후 레코드의 `fixture_sha256`에 기입**

Run: `sha256sum eval/statbridge-golden/v1/fixtures/esi-2025.json`

**Step 3: dev.jsonl에 레코드 1줄 추가** (한 줄 JSON, `<HASH>`는 Step 2 값)

```json
{"id":"GS2-0001","schema_version":"gs1","split":"dev","source":{"publisher":"한국은행","publication":"통화신용정책보고서","doc_id":"2026-09-10_통화신용정책보고서(2026년 9월)","locator":"경제심리 및 성장 설명","url":"https://www.bok.or.kr/portal/bbs/B0000156/view.do?menuNo=200067&nttId=11064613"},"input":{"prior_turns":[],"query":"2025년 경제심리지수 순환변동치 월별 추이 보여주고 해석해줘"},"gold":{"e2e_kpi":{"status":"labeled","pass":true,"final_output":"그래프 + 해석"},"slots":{"status":"labeled","metric":"경제심리지수 순환변동치","target":"경제심리지수","period":{"type":"absolute","start":"2025-01","end":"2025-12"},"frequency":"M"},"concepts":{"status":"labeled","acceptable_concepts":["경제심리지수","경제심리지수 순환변동치","ESI"]},"clarification":{"status":"labeled","need_clarification":false},"plan":{"status":"labeled","acceptable_tool_sequences":[["search","metadata","resolve","output"]]},"discovery":{"status":"labeled","expected_status":"select","acceptable_table_ids":["DT_513Y001"],"required_set":["DT_513Y001"],"forbidden_table_ids":["DT_512Y013"]},"numeric":{"status":"labeled","frequency":"M","unit":"","fixture":"fixtures/esi-2025.json","fixture_sha256":"<HASH>","snapshot_id":"statbridge-local-csv-frozen-2026-09-28"},"graph":{"status":"labeled","chart_type":"line","layout":"separate","fixture":"fixtures/esi-2025.json","fixture_sha256":"<HASH>","snapshot_id":"statbridge-local-csv-frozen-2026-09-28","series":[{"table_id":"DT_513Y001","item_id":"13103134473999","label":"경제심리지수 순환변동치","unit":"","classifications":{"objL1":"13102134473ACC_CD.E2000"}}],"visual_checks":["축 지수 단위","범례 구분","보간 없음"]},"interpretation":{"status":"labeled","report_grade":true,"purpose":"경제심리지수로 경기 심리 흐름 점검","required_claims":[{"id":"c1","type":"direction","period":"2025-01~2025-12","expected":"up"},{"id":"c2","type":"change","period":"2025-01~2025-12","expected_delta":5.0,"tolerance":0.2},{"id":"c3","type":"extreme","subtype":"min","period":"202502","value":89.6},{"id":"c4","type":"extreme","subtype":"max","period":"202512","value":94.8},{"id":"c5","type":"turning_point","period":"202502"}],"acceptable_claims":[],"context_claims":[],"forbidden_claims":[{"type":"hallucination","text":"2025년에 하락세였다"},{"type":"forecast_as_fact","text":"2026년에도 상승할 것"}],"rubric":[{"id":"A","prompt":"요약"},{"id":"B","prompt":"추세"},{"id":"C","prompt":"국면"},{"id":"F","prompt":"시사점 절제"}],"reference_text":"2025년 경제심리지수 순환변동치는 1월 89.8에서 2월 89.6으로 저점을 기록한 뒤 12월 94.8까지 상승했다.","source_basis":{"catalog_ids":["DT_513Y001"],"fixture":"fixtures/esi-2025.json"}}},"provenance":{"annotation_method":"llm_draft+human_review","labeler":"PM/Evaluation"},"review":{"machine_reviewed":true,"human_approved":false}}
```

**Step 4: validator 통과 확인**

Run: `python3 eval/statbridge-golden/v1/scripts/validate.py`
Expected: `0 errors`

**Step 5: 커밋**

```bash
git add eval/statbridge-golden/v1/fixtures/esi-2025.json eval/statbridge-golden/v1/cases/dev.jsonl
git commit -m "eval: add seed case GS2-0001 (single graph + interpretation)"
```

---

### Task 10: 시드 사례 GS2-0042 (복수 표 비교 그래프)

**Files:**
- Create: `eval/statbridge-golden/v1/fixtures/trade_price_2025.json`
- Modify: `eval/statbridge-golden/v1/cases/dev.jsonl`

**Step 1: fixture 작성** (수출물가지수 DT_402Y014 / 수입물가지수 DT_401Y015, 원화기준, 2025 월별)

```json
{
  "snapshot_id": "statbridge-local-csv-frozen-2026-09-28",
  "series": [
    { "table_id": "DT_402Y014", "item_id": "13103134642999", "label": "수출물가지수(원화기준)",
      "frequency": "M", "unit": "2020=100",
      "classifications": { "objL1": "13102134642ACC_CD.*AA", "objL2": "13102134642CRR_CTRT_CD.W" },
      "source_file": "data/tables/DT_402Y014__수출물가지수(기본분류).csv",
      "source_file_sha256": "20de37771a42edcbb1f3b1c957ee1f9155d11a913d05635a142aedddad03df3d",
      "source_last_changed_dates": ["2026-09-13"],
      "points": [
        { "period": "202501", "value": 135.31 }, { "period": "202502", "value": 134.56 },
        { "period": "202503", "value": 135.11 }, { "period": "202504", "value": 133.05 },
        { "period": "202505", "value": 128.39 }, { "period": "202506", "value": 126.88 },
        { "period": "202507", "value": 127.86 }, { "period": "202508", "value": 128.69 },
        { "period": "202509", "value": 129.37 }, { "period": "202510", "value": 134.7 },
        { "period": "202511", "value": 139.42 }, { "period": "202512", "value": 140.28 }
      ] },
    { "table_id": "DT_401Y015", "item_id": "13103134643999", "label": "수입물가지수(원화기준)",
      "frequency": "M", "unit": "2020=100",
      "classifications": { "objL1": "13102134643ACC_CD.*AA", "objL2": "13102134643CRR_CTRT_CD.W" },
      "source_file": "data/tables/DT_401Y015__수입물가지수(기본분류).csv",
      "source_file_sha256": "5e6b6296b412da3233de11522477023f5d7e0c244dbf38516628605c10b5a5e8",
      "source_last_changed_dates": ["2026-09-13"],
      "points": [
        { "period": "202501", "value": 145.08 }, { "period": "202502", "value": 143.6 },
        { "period": "202503", "value": 143.04 }, { "period": "202504", "value": 139.82 },
        { "period": "202505", "value": 134.61 }, { "period": "202506", "value": 133.73 },
        { "period": "202507", "value": 134.84 }, { "period": "202508", "value": 135.21 },
        { "period": "202509", "value": 135.56 }, { "period": "202510", "value": 138.19 },
        { "period": "202511", "value": 141.47 }, { "period": "202512", "value": 142.68 }
      ] }
  ]
}
```

**Step 2: 해시 계산**

Run: `sha256sum eval/statbridge-golden/v1/fixtures/trade_price_2025.json`

**Step 3: dev.jsonl에 GS2-0042 1줄 추가** (한 줄 JSON, `<HASH>`는 Step 2 값). `required_claims`의 `extreme`은 `extremes` 묶음이 아니라 시점별로 split한다(validator가 `extremes` type을 거부).

```json
{"id":"GS2-0042","schema_version":"gs1","split":"dev","source":{"publisher":"한국은행","publication":"경제전망보고서","doc_id":"2026-08-27_경제전망보고서(2026년 8월)","locator":"물가 흐름 설명","url":"https://www.bok.or.kr/"},"input":{"prior_turns":[],"query":"2025년 수출물가지수와 수입물가지수 원화기준 흐름을 비교해서 보여주고 해석해줘"},"gold":{"e2e_kpi":{"status":"labeled","pass":true,"final_output":"두 계열 결합 꺾은선 + 비교 해석"},"slots":{"status":"labeled","metrics":["수출물가지수","수입물가지수"],"basis":"원화기준","period":{"type":"absolute","start":"2025-01","end":"2025-12"},"frequency":"M"},"concepts":{"status":"labeled","acceptable_concepts":["수출물가지수","수입물가지수","수출입물가지수"]},"clarification":{"status":"labeled","need_clarification":false},"plan":{"status":"labeled","acceptable_tool_sequences":[["search:수출물가지수","search:수입물가지수","metadata","resolve","output"]]},"discovery":{"status":"labeled","expected_status":"select","required_set":["DT_402Y014","DT_401Y015"],"acceptable_table_ids":["DT_402Y014","DT_401Y015"],"forbidden_table_ids":["DT_404Y014"]},"numeric":{"status":"labeled","frequency":"M","unit":"2020=100","fixture":"fixtures/trade_price_2025.json","fixture_sha256":"<HASH>","snapshot_id":"statbridge-local-csv-frozen-2026-09-28"},"graph":{"status":"labeled","chart_type":"line","layout":"combined","fixture":"fixtures/trade_price_2025.json","fixture_sha256":"<HASH>","snapshot_id":"statbridge-local-csv-frozen-2026-09-28","series":[{"table_id":"DT_402Y014","item_id":"13103134642999","label":"수출물가지수(원화기준)","unit":"2020=100","classifications":{"objL1":"13102134642ACC_CD.*AA","objL2":"13102134642CRR_CTRT_CD.W"}},{"table_id":"DT_401Y015","item_id":"13103134643999","label":"수입물가지수(원화기준)","unit":"2020=100","classifications":{"objL1":"13102134643ACC_CD.*AA","objL2":"13102134643CRR_CTRT_CD.W"}}],"visual_checks":["단위·기준시점 동일 축","범례로 수출/수입 구분","누락/중복 기간 보간 없음"]},"interpretation":{"status":"labeled","report_grade":true,"purpose":"수출입물가지수 비교로 수출입 가격차 흐름을 점검","required_claims":[{"id":"c1","type":"comparison","series":["수입물가지수","수출물가지수"],"expected":"A>B","period":"2025-01~2025-12"},{"id":"c2","type":"direction","series":"수출물가지수","period":"2025-01~2025-06","expected":"down"},{"id":"c3","type":"direction","series":"수출물가지수","period":"2025-06~2025-12","expected":"up"},{"id":"c4","type":"turning_point","series":"수출물가지수","period":"202506"},{"id":"c5","type":"extreme","series":"수출물가지수","subtype":"min","period":"202506","value":126.88},{"id":"c6","type":"extreme","series":"수출물가지수","subtype":"max","period":"202512","value":140.28},{"id":"c7","type":"extreme","series":"수입물가지수","subtype":"max","period":"202501","value":145.08},{"id":"c9","type":"extreme","series":"수입물가지수","subtype":"min","period":"202506","value":133.73},{"id":"c8","type":"comparison","metric":"gap","series":["수입물가지수","수출물가지수"],"periods":["202501","202512"],"expected_delta":-7.37,"tolerance":0.2}],"acceptable_claims":[{"id":"a1","type":"change","series":"수입물가지수","period":"2025-01~2025-12","expected_delta":-2.40,"tolerance":0.2}],"context_claims":[],"forbidden_claims":[{"type":"hallucination","text":"수출물가지수가 수입물가지수보다 높았다"},{"type":"forecast_as_fact","text":"하반기에도 상승세가 이어질 것"}],"rubric":[{"id":"A","prompt":"요약"},{"id":"B","prompt":"추세"},{"id":"C","prompt":"국면"},{"id":"D","prompt":"구간별 속도"},{"id":"E","prompt":"수준 맥락"},{"id":"F","prompt":"시사점 절제"}],"reference_text":"2025년 중 수출물가지수와 수입물가지수(원화기준, 2020=100)는 모두 상반기 하락 후 하반기 반등하는 U자 흐름을 보였다. 수출물가지수는 1월 135.31에서 6월 126.88로 저점을 기록한 뒤 12월 140.28까지 올랐다. 수입물가지수는 1월 145.08로 연중 최고를 나타낸 후 6월 133.73까지 내렸다가 12월 142.68로 반등했다. 두 지수 모두 6월을 저점으로 전환되었고, 전 기간에 걸쳐 수입물가지수가 수출물가지수를 상회했다. 다만 그 격차는 1월 9.77p에서 12월 2.40p로 크게 축소되어 수출입 가격차가 완화되는 모습을 보였다.","source_basis":{"catalog_ids":["DT_402Y014","DT_401Y015"],"fixture":"fixtures/trade_price_2025.json"}}},"provenance":{"annotation_method":"llm_draft+human_review","labeler":"PM/Evaluation","notes":"총지수(*AA)·원화기준(W)·2020=100 계열에서 도출"},"review":{"machine_reviewed":true,"human_approved":false}}
```

**Step 4: validator 통과 확인**

Run: `python3 eval/statbridge-golden/v1/scripts/validate.py`
Expected: `0 errors`

**Step 5: 커밋**

```bash
git add eval/statbridge-golden/v1/fixtures/trade_price_2025.json eval/statbridge-golden/v1/cases/dev.jsonl
git commit -m "eval: add seed case GS2-0042 (multi-table comparison graph)"
```

---

### Task 11: 생성 절차 SOP 문서

**Files:**
- Create: `eval/statbridge-golden/v1/GENERATION.md`

**Step 1: SOP 작성**

```markdown
# 생성 절차 (SOP)

정의: `docs/superpowers/specs/2026-10-06-statbridge-golden-set-design.md`

1. 씨앗 선정: `research/그림표-분석/그림표_마스터.csv`에서 5개 발간물에 고르게, `사용 데이터·출처`가 `한국은행` 포함인 행 우선.
2. 문장 생성(LLM 보조): 유형별 문장 후보 생성(공식/일상/조건/복수/모호/범위 밖/후속).
3. 정답 부여: 표 ID는 `data/kosis/hankook_tables.json`(349표)에서 매핑. 수치·그래프는 `data/tables/`의 로컬 CSV에서 fixture 생성(source_file_sha256 기록).
4. 오답 함정: `forbidden_table_ids`(sibling 오답), `forbidden_claims`(방향 반전·환각·전망 단정).
5. 사람 검수: 원문·카탈로그 대조 후 `review.human_approved=true`.
6. 누수: holdout은 `cases/holdout_queries.jsonl`에 `id/query/prior_turns`만. 정답은 비공개 저장소.
7. 검증·채점: `validate.py` 0 errors, `score.py`로 오답 분류 확인.

분할 목표는 `manifest.json` 참조(총 90: dev 30 / test 42 / holdout 18).
```

**Step 2: 커밋**

```bash
git add eval/statbridge-golden/v1/GENERATION.md
git commit -m "docs: golden set generation SOP"
```

---

### Task 12: 최종 검증 + README 연결

**Files:**
- Modify: `eval/README.md` (계열 표에 새 계열 행 추가)
- Modify: `eval/statbridge-golden/v1/README.md` (실행 결과 반영)

**Step 1: 전체 테스트 실행**

Run: `python3 -m pytest eval/statbridge-golden/v1/tests -q`
Expected: PASS (all)

**Step 2: validator 실행**

Run: `python3 eval/statbridge-golden/v1/scripts/validate.py`
Expected: `0 errors`

**Step 3: scorer 스모크 테스트** (dev 골드로 자기채점: 정답을 예측으로 넣으면 전부 correct)

간단한 예측 생성 후:

```bash
python3 - <<'PY'
import json
from pathlib import Path
V1=Path("eval/statbridge-golden/v1")
gold=[json.loads(l) for l in (V1/"cases/dev.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
preds=[]
for g in gold:
    G=g["gold"]; d=G["discovery"]
    fx=json.loads((V1/G["graph"]["fixture"]).read_text(encoding="utf-8")) if G.get("graph",{}).get("status")=="labeled" else {"series":[]}
    s=G.get("slots",{}); c=G.get("concepts",{}); cl=G.get("clarification",{}); pl=G.get("plan",{}); e=G.get("e2e_kpi",{})
    preds.append({
      "id":g["id"],"status":d.get("expected_status"),"table_ids":d.get("acceptable_table_ids",[]),
      "slots":{k:s[k] for k in ("metric","metrics","target","frequency","basis","period") if k in s},
      "concepts":{"concepts":c.get("acceptable_concepts",[])},
      "clarification":{"asked":cl.get("need_clarification",False),"options":cl.get("acceptable_options",[])},
      "plan":{"tool_sequences":pl.get("acceptable_tool_sequences",[])},
      "e2e":{"pass":e.get("pass")},
      "graph":{"chart_type":G.get("graph",{}).get("chart_type"),"layout":G.get("graph",{}).get("layout"),"series":fx["series"]},
      "numeric":{"series":fx["series"]},
      "interpretation":{"claims":G.get("interpretation",{}).get("required_claims",[])}
    })
Path("/tmp/pred.jsonl").write_text("".join(json.dumps(p,ensure_ascii=False)+"\n" for p in preds),encoding="utf-8")
PY
python3 eval/statbridge-golden/v1/scripts/score.py eval/statbridge-golden/v1/cases/dev.jsonl /tmp/pred.jsonl
```

Expected: `correct` = 전체 건수, `forbidden_hit` 0, `mismatch` 0

**Step 4: `eval/README.md`에 행 추가**

```markdown
| 표 탐색+해석 | [`statbridge-golden/v1`](statbridge-golden/v1/README.md) | 자체 설계 계열(9계층·오답 함정·해석). 초기 시드 진행 중, 사람 승인 전 |
```

**Step 5: 커밋**

```bash
git add eval/README.md eval/statbridge-golden/v1/README.md
git commit -m "docs: register statbridge-golden v1 lineage"
```

---

## 검증 요약 (계획 완료 기준)

- `python3 -m pytest eval/statbridge-golden/v1/tests -q` → all pass
- `python3 eval/statbridge-golden/v1/scripts/validate.py` → `0 errors`
- `score.py` 자기채점 → correct=전체, forbidden_hit=0
- 기존 계열 회귀: `python3 -m pytest -q eval/table-discovery/v4.1/tests` → 4 passed
- 시드 2건(GS2-0001, GS2-0042)이 spec §3.1·§3.2·§3.3 형태를 실제로 구현

## 범위 밖 (후속 계획)

- 90건 전체 저작(콘텐츠 작업, SOP에 따라 진행)
- holdout 비공개 정답·평가기(private 저장소)
- 사람 rubric 판정 UI/기록
- 5개 발간물 문체 커버리지 자동 리포트
