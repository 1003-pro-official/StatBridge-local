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


def test_resolved_case_passes_when_tables_period_and_rows_match():
    case = next(item for item in GOLD
                if item["workflow_gold"]["resolution"]["agent_status"] == "resolved"
                and item["workflow_gold"]["query_interpretation"]["period"])
    plan = case["workflow_gold"]["classification_and_plan"]["series"][0]
    body = {"status": execution.EXECUTED_STATUS,
            "period": {"start": execution.to_iso(plan["period_start"], plan["frequency"]),
                       "end": execution.to_iso(plan["period_end"], plan["frequency"], end=True)}}
    all_tables = [item["table_id"] for item in case["workflow_gold"]["classification_and_plan"]["series"]]
    row = execution.score_case(case, http_status=200, body=body,
                               session=session_for(case, all_tables, [{"PRD_DE": plan["period_start"], "DT": "1"}]),
                               snapshot_entry={"rows": 1})
    assert row["passed"], row["failed_checks"]


def test_resolved_case_fails_when_a_different_table_is_fetched():
    case = next(item for item in GOLD
                if item["workflow_gold"]["resolution"]["agent_status"] == "resolved"
                and item["workflow_gold"]["query_interpretation"]["period"])
    plan = case["workflow_gold"]["classification_and_plan"]["series"][0]
    body = {"status": execution.EXECUTED_STATUS,
            "period": {"start": execution.to_iso(plan["period_start"], plan["frequency"]),
                       "end": execution.to_iso(plan["period_end"], plan["frequency"], end=True)}}
    row = execution.score_case(case, http_status=200, body=body,
                               session=session_for(case, ["DT_101Y001"], [{"PRD_DE": "202101", "DT": "1"}]),
                               snapshot_entry={"rows": 1})
    assert row["checks"]["tables_match"] is False and not row["passed"]


def test_must_not_fetch_case_fails_when_the_runtime_executes():
    case = next(item for item in GOLD if item["workflow_gold"]["resolution"]["agent_status"] == "no_match")
    executed = execution.score_case(case, http_status=200,
                                   body={"status": execution.EXECUTED_STATUS}, session={"result": {}}, snapshot_entry=None)
    assert executed["passed"] is False and executed["checks"]["not_executed"] is False
    quiet = execution.score_case(case, http_status=200,
                                 body={"status": "no_match"}, session=None, snapshot_entry=None)
    assert quiet["passed"] is True


def test_injected_period_is_compared_against_the_available_range():
    case = next(item for item in GOLD
                if item["workflow_gold"]["resolution"]["agent_status"] == "resolved"
                and item["workflow_gold"]["query_interpretation"]["period"] is None)
    plan = case["workflow_gold"]["classification_and_plan"]["series"][0]
    body = {"status": execution.EXECUTED_STATUS, "period": {"start": "2025-07-01", "end": "2026-06-30"},
            "_available": {"min": "1990-01-01", "max": "2026-06-30"}}
    row = execution.score_case(case, http_status=200, body=body,
                               session=session_for(case, [plan["table_id"]], [{"PRD_DE": "202507", "DT": "1"}]),
                               snapshot_entry={"rows": 12}, injected_period=True)
    assert row["checks"]["period_match"] is True


def test_snapshot_matches_the_gold_and_carries_a_reference_date():
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert snapshot["reference_date"] and snapshot["series_count"] == len(snapshot["series"])
    keys = {(entry["case_id"], entry["table_id"], tuple(sorted(entry["classifications"].items())))
            for entry in snapshot["series"].values()}
    expected = {(case["id"], plan["table_id"], tuple(sorted((plan["classifications"] or {}).items())))
                for case in GOLD
                for plan in case["workflow_gold"]["classification_and_plan"]["series"]}
    assert expected == keys, "스냅샷과 골드 계열이 어긋남"
