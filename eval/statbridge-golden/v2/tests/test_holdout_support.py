import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BASE / "holdout_support"), str(BASE / "scripts")]
from contract import CHECKS, aggregate_report, check_approvals, check_candidates, exclusion_index, holdout_schema, value_hash
from common import read_json
from prepare_holdout import build_kit
import adapter


def synthetic_case(mode="e2e"):
    series = {"provider": "kosis", "table_id": "SYNTH_TABLE", "item_id": "SYNTH_ITEM",
              "classifications": {"objL1": "SYNTH_CLASS"}, "frequency": "M", "unit": "synthetic",
              "points": [{"period": "209901", "value": 1}, {"period": "209902", "value": 2}]}
    case = {"id": "SBV2-H0001", "split": "holdout", "mode": mode, "tags": ["single"],
            "input": {"query": "2099년 1월부터 2월까지 합성 지표", "prior_turns": [],
                      "actions": [{"kind": "confirm_period", "start": "2099-01-01", "end": "2099-02-28"}]},
            "expected": {"data": {"fixture": "fixtures/synthetic.json"}},
            "evidence": {"research_result_ids": ["SYNTH_RESULT"],
                         "sources": [{"path": "synthetic.xlsx", "sha256": "a" * 64, "locator": "sheet!A1:B3"}]},
            "review": {"annotation_method": "ai-assisted", "human_approved": False}}
    return case, {"series": [series]}


def empty_exclusions():
    return {"research_result_ids": [], "source_locators": [], "series_period_sha256": []}


def test_schema_adaptation_changes_only_holdout_identity():
    source = read_json(BASE / "schema.json")
    adapted = holdout_schema(source)
    assert source["properties"]["split"]["enum"] == ["dev", "test"]
    assert adapted["properties"]["split"] == {"const": "holdout"}
    assert adapted["properties"]["id"]["pattern"] == r"^SBV2-H[0-9]{4}$"
    assert adapted["properties"]["input"] == source["properties"]["input"]


@pytest.mark.parametrize("overlap", ["research", "locator", "period"])
def test_public_overlap_is_rejected_without_exporting_questions(overlap):
    case, fixture = synthetic_case()
    exclusion = exclusion_index([case], lambda p: fixture)
    serialized = json.dumps(exclusion, ensure_ascii=False)
    assert case["input"]["query"] not in serialized
    assert "expected" not in exclusion
    if overlap != "research":
        case["evidence"]["research_result_ids"] = ["OTHER"]
    if overlap == "period":
        case["evidence"]["sources"][0]["locator"] = "other!A1:B3"
    errors = check_candidates([case], exclusion, lambda p: fixture, complete=False)
    assert any(overlap in error for error in errors)


def test_same_table_different_period_and_source_is_allowed():
    public, fixture = synthetic_case()
    exclusion = exclusion_index([public], lambda p: fixture)
    private = copy.deepcopy(public)
    private["evidence"]["research_result_ids"] = ["OTHER"]
    private["evidence"]["sources"][0]["locator"] = "other!A1:B3"
    private["input"]["query"] = "2100년 1월부터 2월까지 새로운 분석 과제"
    private["input"]["actions"][0].update(start="2100-01-01", end="2100-02-28")
    newer = copy.deepcopy(fixture)
    for point in newer["series"][0]["points"]:
        point["period"] = point["period"].replace("2099", "2100")
    assert check_candidates([private], exclusion, lambda p: newer, complete=False) == []


def test_shared_methodology_is_not_a_reused_research_figure():
    case, fixture = synthetic_case()
    source = case["evidence"]["sources"][0]
    index = exclusion_index([case], lambda p: fixture, [(source["sha256"], source["locator"])])
    assert index["source_locators"] == []
    assert index["research_result_ids"] == ["SYNTH_RESULT"]


def test_provider_coverage_is_verified_without_running_candidate(monkeypatch, tmp_path):
    case, fixture = synthetic_case()
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures/synthetic.json").write_text(json.dumps(fixture), encoding="utf-8")
    provider = copy.deepcopy(fixture)
    provider["series"][0]["points"][0]["value"] = 999
    (tmp_path / "fixtures/provider.json").write_text(json.dumps(provider), encoding="utf-8")
    class Validator:
        def validate_cases(self, *args, **kwargs):
            return {"errors": [], "warnings": [], "count": 1, "human_approved": 0}
        def validate_fixture(self, *args): return []
        def catalog_contract(self): return None
    monkeypatch.setattr(adapter, "read", lambda path: empty_exclusions() if Path(path).name == "public-exclusions.json" else json.loads(Path(path).read_text(encoding="utf-8")))
    result = adapter.validate_holdout([case], tmp_path, Validator(), partial=True)
    assert any("coverage/value mismatch" in e for e in result["errors"])


def test_release_change_invalidates_execution(monkeypatch, tmp_path):
    source = tmp_path / "cases.jsonl"
    source.write_text("synthetic only", encoding="ascii")
    release = {"bundle_sha256": "bundle", "product_commit": "commit", "product_files": {},
               "files": {"cases.jsonl": adapter.sha(source)}}
    (tmp_path / "release.json").write_text(json.dumps(release), encoding="utf-8")
    monkeypatch.setattr(adapter, "verify_kit", lambda: "bundle")
    monkeypatch.setattr(adapter, "product_version", lambda *args: "commit")
    class Run:
        def implementation_hashes(self): return {}
    assert adapter.verify_release(tmp_path, tmp_path, Run()) == release
    source.write_text("changed synthetic only", encoding="ascii")
    with pytest.raises(ValueError, match="dataset changed"):
        adapter.verify_release(tmp_path, tmp_path, Run())


@pytest.mark.parametrize("mutation", ["attachment", "prior", "period", "edit", "separate"])
def test_unsupported_scenario_and_missing_comparison_blocked(mutation):
    case, fixture = synthetic_case()
    if mutation == "attachment":
        case["input"]["data_fixture"] = "fixtures/synthetic.json"
    elif mutation == "prior":
        case["input"]["prior_turns"] = [{"role": "user", "text": "old"}]
    elif mutation == "period":
        case["input"]["actions"][0]["end"] = "2099-03-31"
    elif mutation == "edit":
        case["mode"] = "edit"
        case["input"]["offline_edit_command"] = {"operation": "set_transform"}
    else:
        case["mode"] = "output"
        case["input"]["output_request"] = {"chart_type": "line", "layout": "separate"}
    assert check_candidates([case], empty_exclusions(), lambda p: fixture, complete=False)


def approved_example():
    case, _ = synthetic_case()
    case["review"].update(human_approved=True, reviewer="synthetic reviewer")
    row = {"id": case["id"], "case_sha256": value_hash(case), "author": "synthetic author",
           "reviewer": "synthetic reviewer", "human_approved": True, "implementation_exposure": True,
           **{check: True for check in CHECKS}}
    return case, row


@pytest.mark.parametrize("mutation", ["pending", "same_author", "case_changed", "missing_check", "missing_exposure"])
def test_approval_gate_rejects_incomplete_or_changed_cases(mutation):
    case, row = approved_example()
    assert check_approvals([case], [row]) == []
    if mutation == "pending":
        row["human_approved"] = False
    elif mutation == "same_author":
        row["author"] = row["reviewer"]
    elif mutation == "case_changed":
        case["input"]["query"] += " changed"
    elif mutation == "missing_check":
        row[CHECKS[0]] = None
    else:
        row.pop("implementation_exposure")
    assert check_approvals([case], [row])


def test_empty_holdout_is_not_production_complete():
    errors = check_candidates([], empty_exclusions(), lambda p: {}, complete=True)
    assert any("mode quotas" in e for e in errors)
    assert any("IDs" in e for e in errors)


def test_private_guard_rejects_public_checkout_before_any_case_read(monkeypatch, tmp_path):
    def fake_git(root, *args):
        if args == ("rev-parse", "--show-toplevel"):
            return str(tmp_path)
        return "https://github.com/example/public.git"
    monkeypatch.setattr(adapter, "git", fake_git)
    with pytest.raises(ValueError, match="no cases were read"):
        adapter.private_base(tmp_path)


def test_export_contains_only_allowlisted_public_tools_and_exclusion_metadata():
    (BASE / "results").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=BASE / "results", prefix="kit-test-") as directory:
        path = Path(directory) / "kit"
        result = build_kit(str(path.relative_to(BASE)))
        assert result["private_cases_created"] == 0
        manifest = read_json(path / "bundle-manifest.json")
        assert not any("cases.jsonl" in name or "dev.jsonl" in name or "test.jsonl" in name
                       or "predictions" in name or "provider.json" in name for name in manifest["files"])
        assert read_json(path / "public-exclusions.json")["public_cases"] == 72
        with pytest.raises(ValueError, match="overwrite"):
            build_kit(str(path.relative_to(BASE)))
        original_kit = adapter.KIT
        try:
            adapter.KIT = path
            adapter.verify_kit()
            (path / "contract.py").write_text("changed", encoding="ascii")
            with pytest.raises(ValueError, match="hash mismatch"):
                adapter.verify_kit()
        finally:
            adapter.KIT = original_kit


def test_export_rejects_outside_results():
    with pytest.raises(ValueError, match="results"):
        build_kit("holdout-kit")


def test_aggregate_report_never_contains_case_level_details():
    scored = {"official_approved_cases": 18, "summary": {"edit": {"pending_review": 1}},
              "automatic_summary": {}, "cases": [{"id": "secret", "failures": ["secret reason"]}]}
    report = aggregate_report(scored, "offline_fixed_provider")
    assert "secret" not in json.dumps(report)
    assert report["summary"]["edit"]["pending_review"] == 1


def test_synthetic_four_mode_execution_and_scoring():
    product = BASE.parents[2]
    result = subprocess.run([sys.executable, str(BASE / "holdout_support/synthetic_smoke.py"),
                             "--product-root", str(product), "--tool-dir", str(BASE / "scripts")],
                            capture_output=True, text=True, encoding="utf-8", check=True)
    value = json.loads(result.stdout)
    assert value["private_cases_created"] == 0
    assert [r["mode"] for r in value["modes"]] == ["discovery", "e2e", "output", "edit"]
    assert all(r["automatic_pass"] for r in value["modes"])
