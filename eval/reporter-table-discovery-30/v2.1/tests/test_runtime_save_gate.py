import copy
import json
from pathlib import Path

import pytest

from importlib.util import module_from_spec, spec_from_file_location

DATASET = Path(__file__).resolve().parents[1]
ROOT = DATASET.parents[2]


def load(name, filename):
    spec = spec_from_file_location(name, DATASET / "scripts" / filename)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load("reporter200_runner", "evaluate_runtime.py")
GOLD = [json.loads(line) for line in (DATASET / "statbridge-reporter200.jsonl")
        .read_text(encoding="utf-8").splitlines() if line]
MANIFEST = json.loads((DATASET / "dataset_manifest.json").read_text(encoding="utf-8"))


def perfect_prediction(case: dict) -> dict:
    """Runtime response a fully correct run would return for this case."""
    workflow = case["workflow_gold"]
    status = workflow["resolution"]["agent_status"]
    plans = workflow["classification_and_plan"]["series"]
    body: dict = {"status": workflow["resolution"]["api_status"]}
    if status == "need_clarification":
        body["clarifications"] = [workflow["resolution"]["clarification"]]
    if status == "resolved":
        requires_period = workflow["post_discovery"]["period_selection_required"]
        body["periodSelection"] = {} if requires_period else {"source": "text"}
    return {"id": case["id"], "repeat_of": None, "query": case["query"], "http_status": 200,
            "agent_status": status, "api_status": workflow["resolution"]["api_status"],
            "selected_table_ids": sorted({plan["table_id"] for plan in plans}), "api_plans": plans,
            "boundary_response": body, "numeric_calls": 0, "output_calls": 0, "duration_s": 1.0, "error": None}


def score_all(predicate=None) -> list[dict]:
    scored = []
    for case in GOLD:
        prediction = perfect_prediction(case)
        if predicate:
            prediction = predicate(case, prediction)
        scored.append(runner.score_case(case, prediction))
    return scored


def test_gold_is_self_consistent_with_the_scoring_contract():
    """A perfectly correct runtime must score 200/200, so no gold case can demand a contradictory response."""
    scored = score_all()
    failed = [(row["id"], row["failed_checks"]) for row in scored if not row["passed"]]
    assert failed == []
    summary = runner.summarize(scored, [], GOLD, {"numeric_calls": 0, "output_calls": 0})
    assert summary["passed"] == 200 and summary["failed"] == 0
    assert summary["legacy"] == {"cases": 30, "passed": 30}
    assert summary["by_kind"]["resolved"] == {"cases": 140, "passed": 140}
    assert summary["by_kind"]["no_match"] == {"cases": 53, "passed": 53}
    assert summary["by_kind"]["need_clarification"] == {"cases": 7, "passed": 7}
    assert runner.decide(summary, []) == {"saved": True, "reasons": []}


def test_manifest_records_the_frozen_scoring_policy():
    assert MANIFEST["scoring_policy_sha256"] == runner.policy_sha256()
    assert runner.policy_sha256({"b": 1, "a": 2}) == runner.policy_sha256({"a": 2, "b": 1})


def test_repeat_sample_is_deterministic_and_uses_the_frozen_strata():
    plan = runner.POLICY["repeat_sample_plan"]
    sample = runner.stratified_sample(GOLD)
    assert [case["id"] for case in sample] == [case["id"] for case in runner.stratified_sample(GOLD)]
    assert len(sample) == sum(plan.values())
    for name, count in plan.items():
        status, _, composition = name.partition("|")
        picked = [case for case in sample if runner.status_of(case) == status
                  and (runner.composition_of(case) or "") == composition]
        assert len(picked) == count, name


def test_unknown_stratum_size_is_rejected():
    with pytest.raises(ValueError):
        runner.stratified_sample(GOLD, {"no_match|": 999})


def test_duplicate_series_identity_is_counted_not_collapsed():
    case = next(item for item in GOLD if len(item["workflow_gold"]["classification_and_plan"]["series"]) > 1)
    duplicated = copy.deepcopy(case)
    plans = duplicated["workflow_gold"]["classification_and_plan"]["series"]
    plans[1] = copy.deepcopy(plans[0])
    prediction = perfect_prediction(duplicated)
    prediction["api_plans"] = prediction["api_plans"][:1]
    scored = runner.score_case(duplicated, prediction)
    assert scored["checks"]["series_identity_set"] is False
    assert "series_identity" in scored["failures"]


def test_swapped_periods_between_duplicate_series_fail_the_param_check():
    case = next(item for item in GOLD
                if len(item["workflow_gold"]["classification_and_plan"]["series"]) == 2)
    duplicated = copy.deepcopy(case)
    plans = duplicated["workflow_gold"]["classification_and_plan"]["series"]
    plans[1] = copy.deepcopy(plans[0])
    plans[1]["period_start"] = "190001" if plans[0]["period_start"] != "190001" else "190002"
    plans[1]["exact_params"] = {**plans[0]["exact_params"], "startPrdDe": plans[1]["period_start"]}
    prediction = perfect_prediction(duplicated)
    prediction["api_plans"] = [copy.deepcopy(plans[0]), copy.deepcopy(plans[0])]
    scored = runner.score_case(duplicated, prediction)
    assert scored["checks"]["series_identity_set"] is True
    assert scored["checks"]["exact_api_params"] is False


def test_every_check_maps_to_a_failure_class():
    """A check without a class would silently become an unclassified failure."""
    observed = set()
    for case in GOLD:
        prediction = perfect_prediction(case)
        prediction["boundary_response"]["chart"] = {}
        observed |= set(runner.score_case(case, prediction)["checks"])
    assert observed == set(runner.FAILURE_CLASS)
    assert "unclassified" not in runner.FAILURE_CLASS.values()


def test_boundary_violation_is_classified_and_blocks_the_report():
    def violate(case, prediction):
        prediction["numeric_calls"] = 1
        return prediction

    scored = score_all(violate)
    summary = runner.summarize(scored, [], GOLD, {"numeric_calls": 1, "output_calls": 0})
    assert summary["boundary_violations"] == 1
    assert summary["failures"]["boundary_violation"] == 200
    assert runner.decide(summary, [])["saved"] is False


def test_gate_blocks_low_kind_rate_legacy_and_gold_suspect():
    summary = runner.summarize(score_all(), [], GOLD, {"numeric_calls": 0, "output_calls": 0})

    def broken(**overrides):
        modified = json.loads(json.dumps(summary))
        modified.update(overrides)
        return modified

    assert runner.decide(broken(by_kind={**summary["by_kind"],
                                        "resolved": {"cases": 119, "passed": 113}}), [])["saved"] is False
    assert runner.decide(broken(by_kind={**summary["by_kind"],
                                        "no_match": {"cases": 45, "passed": 40}}), [])["saved"] is False
    assert runner.decide(broken(legacy={"cases": 30, "passed": 29}), [])["saved"] is False
    assert runner.decide(summary, ["REPORTER30-V2.1-042"])["saved"] is False
    assert runner.decide(broken(unclassified_failures=1), [])["saved"] is False
    assert runner.decide(broken(http_failures=1), [])["saved"] is False


def test_report_is_written_only_when_the_gate_passes(tmp_path):
    summary = runner.summarize(score_all(), [], GOLD, {"numeric_calls": 0, "output_calls": 0})
    result = {"environment": {"dataset_sha256": "x"}, "summary": summary, "cases": [], "gold_suspect": []}
    blocked = runner.decide(summary, ["REPORTER30-V2.1-042"])
    runner.write_results(tmp_path, result, blocked)
    assert not (tmp_path / "REPORT.md").exists()
    assert (tmp_path / "diagnostic.md").exists() and (tmp_path / "scores.json").exists()
    assert json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8"))["policy_sha256"] \
        == runner.policy_sha256()
    runner.write_results(tmp_path, result, runner.decide(summary, []))
    assert (tmp_path / "REPORT.md").read_text(encoding="utf-8").startswith("# 기자 질의 골든셋 v2.1 평가 결과")


def test_threshold_rounding_accepts_the_documented_boundary():
    assert runner.decide(runner.summarize(
        score_all(), [], GOLD, {"numeric_calls": 0, "output_calls": 0}), [])["saved"] is True
    summary = runner.summarize(score_all(), [], GOLD, {"numeric_calls": 0, "output_calls": 0})
    summary["by_kind"]["resolved"] = {"cases": 119, "passed": 114}
    assert runner.decide(summary, [])["saved"] is True
    summary["by_kind"]["resolved"] = {"cases": 119, "passed": 113}
    assert runner.decide(summary, [])["saved"] is False
