from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))

from common import identity, read_json, read_jsonl, transform_series, write_json
from run import FrozenProvider, NoNetwork, execute_input, observation_hash
from score import check_plotly, check_resolution, compare_series, score_case
from validate import catalog_contract, validate_cases, validate_fixture


@pytest.fixture
def cases():
    return read_jsonl(BASE / "pilot.jsonl")


@pytest.fixture
def example(cases):
    # Attachment cases are retained ONLY as component regression tests.
    c = next(c for c in read_jsonl(BASE / "internal/components/cases.jsonl") if c["mode"] == "output")
    return c, read_json(BASE / c["expected"]["data"]["fixture"])["series"]


def test_public_cases_and_source_hashes():
    cases = read_jsonl(BASE / "dev.jsonl") + read_jsonl(BASE / "test.jsonl")
    result = validate_cases(cases, verify_sources=True)
    assert result["errors"] == []
    assert result["count"] == 72
    assert result["human_approved"] == 0


@pytest.mark.parametrize("mutation", ["classification", "item", "unit", "frequency", "duplicate_series",
                                    "duplicate_period", "missing", "extra", "number"])
def test_numeric_adversaries(example, mutation):
    _, gold = example
    actual = copy.deepcopy(gold)
    s = actual[0]
    if mutation == "classification":
        # Attachment identity is independent of KOSIS classification.
        s["series_id"] += ":wrong"
    elif mutation == "item":
        s["series_id"] = "attachment:unregistered"
    elif mutation == "unit": s["unit"] = "wrong"
    elif mutation == "frequency": s["frequency"] = "Y"
    elif mutation == "duplicate_series": actual.append(copy.deepcopy(s))
    elif mutation == "duplicate_period": s["points"].append(copy.deepcopy(s["points"][0]))
    elif mutation == "missing": s["points"].pop()
    elif mutation == "extra": s["points"].append({"period": "209901", "value": 1})
    elif mutation == "number": s["points"][0]["value"] += 1
    assert compare_series(gold, actual, 0.000001)


def test_kosis_classification_item_frequency_unit():
    s = read_json(BASE / "fixtures/provider.json")["series"][0]
    for field, value in [("classifications", {"objL1": "not-real"}), ("item_id", "not-real"),
                         ("frequency", "Q"), ("unit", "조원")]:
        actual = copy.deepcopy(s)
        actual[field] = value
        assert compare_series([s], [actual], 0)
    invalid = copy.deepcopy(s)
    invalid["classifications"]["objL1"] = "not-real"
    assert "unknown classification" in validate_fixture({"series": [invalid]}, catalog_contract())


def test_missing_must_not_be_interpolated():
    s = {"provider": "attachment", "series_id": "attachment:missing", "frequency": "M", "unit": "%",
         "label": "x", "points": [{"period": "202401", "value": None}, {"period": "202402", "value": 1}]}
    actual = copy.deepcopy(s)
    actual["points"][0]["value"] = 0
    assert "missing_value_imputed" in compare_series([s], [actual], 0)


def test_whole_alternatives_not_optional_multiple_tables():
    gold = {"decision": "resolved", "acceptable_table_sets": [["a", "b"], ["c"]],
            "clarification": {"required": False, "dimensions": [], "option_groups": []}}
    assert check_resolution(gold, {"decision": "resolved", "table_ids": ["a", "b"]}) == []
    assert check_resolution(gold, {"decision": "resolved", "table_ids": ["c"]}) == []
    assert "selected_tables" in check_resolution(gold, {"decision": "resolved", "table_ids": ["a"]})
    assert "selected_tables" in check_resolution(gold, {"decision": "resolved", "table_ids": ["a", "c"]})


def test_wrong_or_extra_clarification_options():
    gold = {"decision": "clarify", "acceptable_table_sets": [],
            "clarification": {"required": True, "dimensions": ["기준"], "option_groups": [["명목", "실질"]]}}
    valid = {"decision": "clarify", "table_ids": [], "clarification": {"asked": True, "question": "기준을 선택", "options": ["명목", "실질"]}}
    assert check_resolution(gold, valid) == []
    wrong = copy.deepcopy(valid)
    wrong["clarification"]["options"] = ["명목", "환율"]
    assert "clarification_options" in check_resolution(gold, wrong)
    wrong["clarification"]["options"] = ["명목", "실질", "환율"]
    assert "clarification_extra_options" in check_resolution(gold, wrong)


def test_plotly_uses_real_values_and_layout(example):
    _, series = example
    figure = {"data": [{"type": "scatter", "name": s["label"],
                       "x": [p["period"] for p in s["points"]], "y": [p["value"] for p in s["points"]]} for s in series]}
    assert check_plotly(series, figure, "line") == []
    changed = copy.deepcopy(figure)
    changed["data"][0]["y"][0] += 1
    assert "plotly_values" in check_plotly(series, changed, "line")
    assert "plotly_subplot_layout" in check_plotly(series, figure, "line", "separate")
    figure["data"].pop()
    assert "plotly_trace_count" in check_plotly(series, figure, "line")


def test_independent_transform_calculations():
    s = {"provider": "attachment", "series_id": "attachment:x", "frequency": "M", "unit": "원", "label": "x",
         "points": [{"period": "2024" + str(i+1).zfill(2), "value": i+1} for i in range(12)] +
                   [{"period": "202501", "value": 2}]}
    transformed = transform_series([s], {"operation": "set_transform", "value": "year_over_year"})[0]
    assert transformed["unit"] == "%"
    assert transformed["points"] == [{"period": "202501", "value": 100}]
    s["points"][0]["value"] = 0
    assert transform_series([s], {"operation": "set_transform", "value": "growth_rate"})[0]["points"][0]["value"] is None
    s["points"] = [{"period": "202401", "value": 10}, {"period": "202403", "value": 20}]
    assert transform_series([s], {"operation": "set_transform", "value": "growth_rate"})[0]["points"] == [{"period": "202403", "value": None}]


@pytest.mark.parametrize("mutation", ["unknown_id", "missing_hash", "followup", "conflict", "split", "comparison"])
def test_validator_blocks_bad_cases(cases, mutation):
    changed = copy.deepcopy(cases)
    c = next(c for c in changed if c["mode"] == "e2e")
    if mutation == "unknown_id": c["expected"]["resolution"]["acceptable_table_sets"] = [["DT_NOT_REAL"]]
    elif mutation == "missing_hash": del c["evidence"]["sources"][0]["sha256"]
    elif mutation == "followup":
        c["tags"].append("followup")
        c["input"]["prior_turns"] = []
    elif mutation == "conflict":
        duplicate = copy.deepcopy(c)
        duplicate["id"] = "SBV2-9999"
        duplicate["expected"]["resolution"]["decision"] = "unsupported"
        changed.append(duplicate)
    elif mutation == "split":
        duplicate = copy.deepcopy(c)
        duplicate["id"] = "SBV2-9999"
        duplicate["split"] = "test" if c["split"] == "dev" else "dev"
        duplicate["input"]["query"] += " 다른 질문"
        changed.append(duplicate)
    elif mutation == "comparison":
        c["expected"]["resolution"]["acceptable_table_sets"][0].append("DT_121Y002")
    assert validate_cases(changed, enforce_counts=False)["errors"]


def test_input_fixture_and_claims_hash_block_tampering(example, tmp_path):
    c, series = example
    c = copy.deepcopy(c)
    for relative in [c["input"]["data_fixture"], c["expected"]["data"]["fixture"], c["expected"]["output"]["claims"]]:
        write_json(tmp_path / relative, read_json(BASE / relative))
    bad = copy.deepcopy(series)
    bad[0]["unit"] = "invented"
    write_json(tmp_path / c["input"]["data_fixture"], {"series": bad})
    errors = validate_cases([c], base=tmp_path, enforce_counts=False)["errors"]
    assert any("input fixture hash" in e for e in errors)
    assert any("output contradicts input" in e for e in errors)


def test_provider_uses_actual_parameters_not_gold():
    provider = FrozenProvider(NoNetwork(), BASE / "fixtures/provider.json")
    s = provider.series[0]
    request = {k: s[k] for k in ("table_id", "item_id", "classifications", "frequency")}
    value = provider.get_statistics(**request, start_period=s["points"][0]["period"], end_period=s["points"][-1]["period"])
    assert value["row_count"] == len(s["points"])
    request["classifications"] = {"objL1": "wrong"}
    with pytest.raises(ValueError, match="unregistered"):
        provider.get_statistics(**request)


def test_real_edit_preserves_raw_and_checks_change(cases):
    c = next(c for c in read_jsonl(BASE / "internal/components/cases.jsonl") if c["mode"] == "edit" and c["input"]["offline_edit_command"]["operation"] == "set_title")
    observed, trace = execute_input("edit", c["input"])
    assert observed["source_data_preserved"] is True
    assert observed["statistics_calls_during_edit"] == 0
    assert observed["chart_state"]["title"] == c["input"]["offline_edit_command"]["value"]
    assert [t["stage"] for t in trace] == ["OutputAgent.prepare", "OutputAgent.edit"]


def test_human_review_required_and_bound_to_observation(example):
    c, _ = example
    observed, _ = execute_input("output", c["input"])
    p = {"id": c["id"], "execution_status": "observed", **observed}
    p["input_sha256"] = hashlib.sha256(json.dumps(c["input"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    p["observation_sha256"] = observation_hash(p)
    assert score_case(c, p)["status"] == "pending_review"
    review = {"prediction_sha256": p["observation_sha256"], "reviewer": "human-test-reviewer", "human_approved": True,
              "facts_correct": True, "no_contradiction": True, "no_unsupported_claim": True, "claims_covered": True}
    assert score_case(c, p, review)["status"] == "passed"
    p["explanation"] = "changed after review"
    assert score_case(c, p, review)["status"] == "pending_review"


def test_unexecuted_and_unobserved_not_success(example):
    c, _ = example
    assert score_case(c, None)["status"] == "not_executed"
    assert score_case(c, {"execution_status": "unobserved"})["status"] == "unobserved"


def test_real_session_ids_are_used_not_filled_from_gold():
    from output_agent import OutputAgent
    from run import fixture_rows
    provider = FrozenProvider(NoNetwork(), BASE / "fixtures/provider.json")
    s = provider.series[0]
    plan = {k: s[k] for k in ("table_id", "item_id", "classifications", "frequency")}
    provider.plans = [plan]
    provider.calls = [{"provider": "kosis", **plan}]
    output = OutputAgent().prepare({"execution": {"rows": fixture_rows([s])}}, {"chart_type": "line"})
    calls = []
    class Response:
        status_code = 200
        def __init__(self, value): self.value = value
        def json(self): return self.value
        def raise_for_status(self): pass
    class Client:
        def post(self, path, json):
            calls.append((path, copy.deepcopy(json)))
            if path == "/api/output":
                assert json["session_ids"] == ["issued-at-runtime"]
                return Response({"status": "resolved", "outputSpec": output})
            if json["execute"]:
                if len(calls) == 1:
                    assert "state" not in json
                    return Response({"status": "need_period", "state": {"server_state": 17},
                                     "tables": [{"tableId": s["table_id"]}]})
                assert json["state"] == {"server_state": 17}
                return Response({"status": "need_output_config", "outputSessionId": "issued-at-runtime",
                                 "tables": [{"tableId": s["table_id"]}]})
            return Response({"status": "need_period", "state": {"server_state": 17},
                             "tables": [{"tableId": s["table_id"]}]})
    payload = {"query": "x", "prior_turns": [], "actions": [
        {"kind": "confirm_period", "start": "2003-01-01", "end": "2003-12-31"},
        {"kind": "configure_output", "chart_type": "line", "layout": "combined"}]}
    actual, trace = execute_input("e2e", payload, Client(), provider)
    assert [p for p, _ in calls] == ["/api/query", "/api/query", "/api/output"]
    assert len(trace) == 3
    assert identity(actual["series"][0]) == identity(s)


def test_supported_outside_question_has_no_selected_tables():
    gold = {"decision": "unsupported", "acceptable_table_sets": [],
            "clarification": {"required": False, "dimensions": [], "option_groups": []}}
    assert check_resolution(gold, {"decision": "unsupported", "table_ids": []}) == []
    assert check_resolution(gold, {"decision": "resolved", "table_ids": ["wrong"]})


def test_bad_period_hash_source_and_group_contracts(cases):
    for mutation in ("period", "source", "group"):
        changed = copy.deepcopy(cases)
        c = next(c for c in changed if c["mode"] == "e2e")
        if mutation == "period":
            c["input"]["actions"][0]["start"] = "2025-01-01"
        elif mutation == "source":
            c["evidence"]["sources"][0]["sha256"] = "0" * 64
        else:
            other = copy.deepcopy(c)
            other["id"] = "SBV2-9998"
            other["group_id"] = "wrong-group"
            other["input"]["query"] += " 또 확인"
            changed.append(other)
        assert validate_cases(changed, enforce_counts=False)["errors"]
