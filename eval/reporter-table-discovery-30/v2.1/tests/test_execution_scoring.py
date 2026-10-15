"""조회 계층 채점기·값 채점기의 오프라인 회귀 (런타임 스택 불필요)."""
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


execution = load("reporter200_execution", "evaluate_execution.py")
values = load("reporter200_values", "score_execution_values.py")
GOLD = [json.loads(line) for line in (DATASET / "statbridge-reporter200.jsonl")
        .read_text(encoding="utf-8").splitlines() if line]
SNAPSHOT = DATASET / "kosis_snapshot.json"


def test_period_conversion_matches_the_ui_format():
    assert execution.to_iso("202201", "M") == "2022-01-01"
    assert execution.to_iso("202512", "M", end=True) == "2025-12-31"
    assert execution.to_iso("202201", "Q") == "2022-01-01"
    assert execution.to_iso("202504", "Q", end=True) == "2025-12-31"
    assert execution.to_iso("2020", "A") == "2020-01-01"
    assert execution.to_iso("2024", "A", end=True) == "2024-12-31"


def test_value_comparison_uses_the_snapshot_precision_and_keeps_missing_as_missing():
    assert values.values_equal("101.96", "101.96")
    assert values.values_equal("101.96", "101.964")          # 소수 2자리 → ±0.005
    assert not values.values_equal("101.96", "102.10")
    assert not values.values_equal("", "0")                  # 결측을 0으로 대체하면 불일치
    assert values.values_equal("", "")
    assert values.values_equal("-", "-")


def test_row_signature_maps_response_columns_to_gold_params():
    row = {"TBL_ID": "DT_404Y014", "C1": "abc", "C1_NM": "총지수", "PRD_DE": "202101", "DT": "101.96"}
    assert values.row_signature(row) == ("DT_404Y014", (("objL1", "abc"),))


def session_for(case: dict, tables: list[str], rows: list[dict]) -> dict:
    return {"result": {"api_plans": [{"table_id": table, "item_id": "x", "classifications": {}}
                                     for table in tables],
                       "execution": {"rows": rows, "sources": ["kosis"]}}}


def evidence_for(case: dict, *, wrong_item: bool = False, wrong_class: bool = False):
    plans, rows, snap = [], [], {"series": {}}
    for plan in case["workflow_gold"]["classification_and_plan"]["series"]:
        plans.append({key: plan.get(key) for key in ("table_id", "item_id", "classifications", "frequency")})
        plans[-1].update(start_period=plan["period_start"], end_period=plan["period_end"])
        classifications = dict(plan.get("classifications") or {})
        row = {"TBL_ID": plan["table_id"], "ITM_ID": plan["item_id"], "PRD_DE": plan["period_start"],
               "DT": "1", "_FREQUENCY": plan["frequency"], "_SOURCE_SERIES_ID": plan["table_id"]}
        for index, (key, value) in enumerate(sorted(classifications.items()), 1):
            row[f"C{index}"] = "WRONG" if wrong_class and index == 1 else value
        if wrong_item and not rows:
            row["ITM_ID"] = "WRONG"
        rows.append(row)
        identity = (case["id"], str(plan["table_id"]), str(plan["item_id"]), tuple(sorted(classifications.items())))
        snap["series"][identity] = {"points": {plan["period_start"]: "1"}, "rows": 1}
    return plans, rows, snap


def test_resolved_case_passes_when_tables_period_and_rows_match():
    case = next(item for item in GOLD
                if item["workflow_gold"]["resolution"]["agent_status"] == "resolved"
                and item["workflow_gold"]["query_interpretation"]["period"])
    plan = case["workflow_gold"]["classification_and_plan"]["series"][0]
    body = {"status": execution.EXECUTED_STATUS,
            "period": {"start": execution.to_iso(plan["period_start"], plan["frequency"]),
                       "end": execution.to_iso(plan["period_end"], plan["frequency"], end=True)}}
    runtime_plans, rows, snapshot_entry = evidence_for(case)
    row = execution.score_case(case, http_status=200, body=body,
                               session={"result": {"api_plans": runtime_plans,
                                                   "execution": {"rows": rows, "sources": ["kosis"]}}},
                               snapshot_entry=snapshot_entry)
    assert row["passed"], row["failed_checks"]


def test_resolved_case_fails_when_a_different_table_is_fetched():
    case = next(item for item in GOLD
                if item["workflow_gold"]["resolution"]["agent_status"] == "resolved"
                and item["workflow_gold"]["query_interpretation"]["period"])
    plan = case["workflow_gold"]["classification_and_plan"]["series"][0]
    body = {"status": execution.EXECUTED_STATUS,
            "period": {"start": execution.to_iso(plan["period_start"], plan["frequency"]),
                       "end": execution.to_iso(plan["period_end"], plan["frequency"], end=True)}}
    runtime_plans, rows, snapshot_entry = evidence_for(case)
    runtime_plans[0]["table_id"] = "DT_101Y001"
    row = execution.score_case(case, http_status=200, body=body,
                               session={"result": {"api_plans": runtime_plans,
                                                   "execution": {"rows": rows, "sources": ["kosis"]}}},
                               snapshot_entry=snapshot_entry)
    assert row["checks"]["plans_match"] is False and not row["passed"]


def test_must_not_fetch_case_fails_when_the_runtime_executes():
    case = next(item for item in GOLD if item["workflow_gold"]["resolution"]["agent_status"] == "no_match")
    executed = execution.score_case(case, http_status=200,
                                   body={"status": execution.EXECUTED_STATUS}, session={"result": {}}, snapshot_entry=None)
    assert executed["passed"] is False and executed["checks"]["not_executed"] is False
    quiet = execution.score_case(case, http_status=200,
                                 body={"status": "no_match"}, session=None, snapshot_entry=None)
    assert quiet["passed"] is True


def test_injected_period_must_match_gold_and_requires_initial_need_period():
    case = next(item for item in GOLD
                if item["workflow_gold"]["resolution"]["agent_status"] == "resolved"
                and item["workflow_gold"]["query_interpretation"]["period"] is None)
    plan = case["workflow_gold"]["classification_and_plan"]["series"][0]
    runtime_plans, rows, snapshot_entry = evidence_for(case)
    body = {"status": execution.EXECUTED_STATUS,
            "period": {"start": execution.to_iso(plan["period_start"], plan["frequency"]),
                       "end": execution.to_iso(plan["period_end"], plan["frequency"], end=True)}}
    session = {"result": {"api_plans": runtime_plans, "execution": {"rows": rows, "sources": ["kosis"]}}}
    row = execution.score_case(case, http_status=200, body=body, session=session,
                               snapshot_entry=snapshot_entry, injected_period=True,
                               injected_interval=body["period"], first_body={"status": "need_period"})
    assert row["checks"]["period_match"] is True and row["checks"]["period_followup_passed"] is True
    wrong = dict(body, period={"start": "2025-07-01", "end": "2026-06-30"})
    row = execution.score_case(case, http_status=200, body=wrong, session=session,
                               snapshot_entry=snapshot_entry, injected_period=True,
                               injected_interval=wrong["period"], first_body={"status": "no_match"})
    assert row["checks"]["period_match"] is False and row["checks"]["period_followup_passed"] is False


def test_snapshot_lookup_uses_nested_series_map_and_full_identity():
    indexed = execution.load_snapshot_index(SNAPSHOT)
    case = next(case for case in GOLD if case["workflow_gold"]["resolution"]["agent_status"] == "resolved")
    plan = case["workflow_gold"]["classification_and_plan"]["series"][0]
    key = (case["id"], plan["table_id"], plan["item_id"], tuple(sorted(plan["classifications"].items())))
    assert indexed["series"][key]["case_id"] == case["id"]


@pytest.mark.parametrize("field", ["gold_sha256", "catalog_sha256"])
def test_snapshot_hash_mismatch_is_rejected(tmp_path, field):
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8")); snapshot[field] = "0" * 64
    path = tmp_path / "snapshot.json"; path.write_text(json.dumps(snapshot), encoding="utf-8")
    with pytest.raises(ValueError, match=field):
        execution.load_snapshot_index(path)


def test_snapshot_missing_or_duplicate_series_is_rejected(tmp_path):
    original = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    missing = copy.deepcopy(original); missing["series"].pop(next(iter(missing["series"])))
    path = tmp_path / "missing.json"; path.write_text(json.dumps(missing), encoding="utf-8")
    with pytest.raises(ValueError, match="identity mismatch"):
        execution.load_snapshot_index(path)
    duplicate = copy.deepcopy(original); duplicate["series"]["duplicate"] = copy.deepcopy(next(iter(duplicate["series"].values())))
    path.write_text(json.dumps(duplicate), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        execution.load_snapshot_index(path)


def test_same_table_wrong_item_or_classification_fails():
    case = next(case for case in GOLD if case["workflow_gold"]["resolution"]["agent_status"] == "resolved")
    plans, rows, snapshot_entry = evidence_for(case, wrong_item=True)
    result = execution.score_case(case, http_status=200, body={"status": execution.EXECUTED_STATUS},
                                  session={"result": {"api_plans": plans, "execution": {"rows": rows}}},
                                  snapshot_entry=snapshot_entry)
    assert not result["passed"] and result["series"][0]["fetched_rows"] == 0
    plans, rows, snapshot_entry = evidence_for(case, wrong_class=True)
    result = execution.score_case(case, http_status=200, body={"status": execution.EXECUTED_STATUS},
                                  session={"result": {"api_plans": plans, "execution": {"rows": rows}}},
                                  snapshot_entry=snapshot_entry)
    assert not result["passed"] and result["series"][0]["fetched_rows"] == 0


def test_multiple_series_are_scored_independently():
    case = next(case for case in GOLD if case["workflow_gold"]["resolution"]["agent_status"] == "resolved"
                and len(case["workflow_gold"]["classification_and_plan"]["series"]) > 1)
    plans, rows, snapshot_entry = evidence_for(case)
    result = execution.score_case(case, http_status=200, body={"status": execution.EXECUTED_STATUS},
                                  session={"result": {"api_plans": plans, "execution": {"rows": rows}}},
                                  snapshot_entry=snapshot_entry)
    assert all(item["passed"] for item in result["series"])
    result = execution.score_case(case, http_status=200, body={"status": execution.EXECUTED_STATUS},
                                  session={"result": {"api_plans": plans, "execution": {"rows": rows[:1]}}},
                                  snapshot_entry=snapshot_entry)
    assert sum(item["passed"] for item in result["series"]) == 1 and not result["passed"]


def test_snapshot_period_keys_are_checked_per_series():
    case = next(case for case in GOLD if case["workflow_gold"]["resolution"]["agent_status"] == "resolved")
    plan = case["workflow_gold"]["classification_and_plan"]["series"][0]
    runtime = {key: plan.get(key) for key in ("table_id", "item_id", "classifications", "frequency")}
    runtime.update(start_period=plan["period_start"], end_period=plan["period_end"])
    row = {"TBL_ID": plan["table_id"], "ITM_ID": plan["item_id"], "PRD_DE": plan["period_start"],
           "_SOURCE_SERIES_ID": plan["table_id"], "_FREQUENCY": plan["frequency"]}
    for index, (_key, value) in enumerate(sorted((plan.get("classifications") or {}).items()), 1):
        row[f"C{index}"] = value
    result = execution.score_series(case["id"], plan, [runtime], [row],
                                    {"points": {plan["period_start"]: "1", "209901": "2"}})
    assert result["missing_periods"] == ["209901"] and not result["passed"]


def test_unexpected_runtime_series_fails():
    case = next(case for case in GOLD if case["workflow_gold"]["resolution"]["agent_status"] == "resolved")
    plans, rows, snapshot_entry = evidence_for(case)
    plans.append({"table_id": "EXTRA", "item_id": "EXTRA", "classifications": {}, "frequency": "M",
                  "period_start": "202001", "period_end": "202001"})
    result = execution.score_case(case, http_status=200, body={"status": execution.EXECUTED_STATUS},
                                  session={"result": {"api_plans": plans, "execution": {"rows": rows}}},
                                  snapshot_entry=snapshot_entry)
    assert result["checks"]["unexpected_plans"] is False and not result["passed"]


def test_short_snapshot_range_is_reported_as_limited_coverage():
    case = next(case for case in GOLD if case["workflow_gold"]["resolution"]["agent_status"] == "resolved")
    plans, rows, snapshot_entry = evidence_for(case)
    plan = case["workflow_gold"]["classification_and_plan"]["series"][0]
    body = {"status": execution.EXECUTED_STATUS,
            "period": {"start": execution.to_iso(plan["period_start"], plan["frequency"]),
                       "end": execution.to_iso(plan["period_end"], plan["frequency"], end=True)}}
    result = execution.score_case(case, http_status=200, body=body,
                                  session={"result": {"api_plans": plans,
                                                      "execution": {"rows": rows, "sources": ["kosis"]}}},
                                  snapshot_entry=snapshot_entry)
    assert result["snapshot_coverage_limited"] is True


def test_missing_cases_remain_in_the_denominator():
    missing = GOLD[0]
    kept = execution.keep_missing_cases(GOLD[:2], [{"id": GOLD[1]["id"], "passed": True}])
    assert len(kept) == 2
    row = next(row for row in kept if row["id"] == missing["id"])
    assert row["failed_checks"] == ["case_record_present"]
    assert len(row["series"]) == len(missing["workflow_gold"]["classification_and_plan"]["series"])
    assert all(item["fetched_rows"] == 0 for item in row["series"])


def test_unreached_resolved_case_keeps_every_expected_series():
    case = next(item for item in GOLD if item["workflow_gold"]["resolution"]["agent_status"] == "resolved")
    result = execution.score_case(case, http_status=500, body={"status": "http_error"}, session=None,
                                  snapshot_entry={"series": {}})
    expected = case["workflow_gold"]["resolution"]["series_count"]
    assert len(result["series"]) == expected
    assert all(item["fetched_rows"] == 0 for item in result["series"])


def test_limited_run_cannot_be_a_full_pass():
    summary = {"cases": 200, "complete": True, "contract_failures": 0,
               "output_guard_installed": True, "output_calls": 0}
    assert execution.evaluation_exit_code(summary, 200, partial_run=True) != 0


def test_missing_output_guard_target_fails_loudly():
    assert not execution.install_output_guard(object(), {"output": 0})


def test_output_generation_call_blocks_pass():
    class Output:
        def prepare(self):
            pass
    class Agent:
        output_agent = Output()
    class API:
        agent = Agent()
    calls = {"output": 0}
    assert execution.install_output_guard(API(), calls)
    with pytest.raises(RuntimeError, match="forbidden"):
        API.agent.output_agent.prepare()
    summary = {"cases": 1, "complete": True, "contract_failures": 0,
               "output_guard_installed": True, "output_calls": calls["output"]}
    assert execution.evaluation_exit_code(summary, 1, partial_run=False) != 0


def test_failed_contract_returns_nonzero():
    summary = {"cases": 1, "complete": True, "contract_failures": 1,
               "output_guard_installed": True, "output_calls": 0}
    assert execution.evaluation_exit_code(summary, 1, partial_run=False) != 0


def test_snapshot_matches_the_gold_and_carries_a_reference_date():
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert snapshot["reference_date"] and snapshot["series_count"] == len(snapshot["series"])
    keys = {(entry["case_id"], entry["table_id"], tuple(sorted(entry["classifications"].items())))
            for entry in snapshot["series"].values()}
    expected = {(case["id"], plan["table_id"], tuple(sorted((plan["classifications"] or {}).items())))
                for case in GOLD
                for plan in case["workflow_gold"]["classification_and_plan"]["series"]}
    assert expected == keys, "스냅샷과 골드 계열이 어긋남"
