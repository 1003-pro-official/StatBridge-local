from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
from common import normalized_unit, read_json, read_jsonl, transform_series, write_jsonl
from edit_contract import instruction_command
from run import observation_hash
from score import check_plotly, check_resolution, compare_series, score_case
from validate import catalog_contract, validate_cases, validate_fixture


def all_cases():
    return read_jsonl(BASE / "dev.jsonl") + read_jsonl(BASE / "test.jsonl")


@pytest.mark.parametrize("mode", ["markers", "text", "none", "markers+text", ""])
def test_line_requires_a_visible_line(mode):
    series = [{"label": "x", "points": [{"period": "202401", "value": 1}]}]
    figure = {"data": [{"type": "scatter", "mode": mode, "name": "x", "x": ["202401"], "y": [1]}]}
    assert "plotly_line_mode" in check_plotly(series, figure, "line")


@pytest.mark.parametrize("mode", [None, "lines", "lines+markers", "lines+text"])
def test_valid_plotly_line_modes_and_default(mode):
    series = [{"label": "x", "points": [{"period": "202401", "value": 1}]}]
    trace = {"type": "scatter", "name": "x", "x": ["202401"], "y": [1]}
    if mode is not None:
        trace["mode"] = mode
    assert check_plotly(series, {"data": [trace]}, "line") == []


def test_empty_unit_is_blocked():
    series = copy.deepcopy(read_json(BASE / "fixtures/provider.json")["series"][0])
    series["unit"] = "  "
    assert "missing documented unit" in validate_fixture({"series": [series]}, catalog_contract())


@pytest.mark.parametrize("mutation", [None, "day", "month", "value", "axis", "frequency"])
def test_iso_monthly_plotly_coordinates_preserve_exact_period_and_value(mutation):
    series = [{"label": "x", "frequency": "M", "points": [{"period": "202401", "value": 1}]}]
    figure = {"data": [{"type": "scatter", "mode": "lines", "name": "x", "x": ["2024-01-01"], "y": [1]}],
              "layout": {"xaxis": {"type": "date"}}}
    if mutation == "day":
        figure["data"][0]["x"] = ["2024-01-02"]
    elif mutation == "month":
        figure["data"][0]["x"] = ["2024-02-01"]
    elif mutation == "value":
        figure["data"][0]["y"] = [2]
    elif mutation == "axis":
        figure["layout"]["xaxis"]["type"] = "category"
    elif mutation == "frequency":
        series[0]["frequency"] = "Q"
    failures = check_plotly(series, figure, "line")
    assert failures == ([] if mutation is None else ["plotly_values"])


def test_unit_normalization_is_explicit_and_unscaled():
    assert normalized_unit("DT_514Y001", "") == "지수"
    assert normalized_unit("unknown", "") == ""
    assert normalized_unit("DT_514Y001", "%") == "%"
    for case in all_cases():
        if case["id"] in {"SBV2-0016", "SBV2-0017", "SBV2-0018", "SBV2-0031", "SBV2-0035"}:
            assert all(s["unit"] == "지수" for s in read_json(BASE / case["expected"]["data"]["fixture"])["series"])


def test_normalized_unit_requires_definition_provenance():
    case = copy.deepcopy(next(c for c in all_cases() if c["id"] == "SBV2-0016"))
    case["evidence"]["sources"] = [s for s in case["evidence"]["sources"] if not s["path"].endswith("unit_rules.json")]
    assert any("missing unit-definition provenance" in e for e in validate_cases([case], enforce_counts=False)["errors"])


def test_cumulative_flow_is_not_a_monthly_flow_unit():
    case = next(c for c in read_jsonl(BASE / "internal/components/cases.jsonl") if c["id"] == "SBV2-0064")
    original = read_json(BASE / case["input"]["data_fixture"])["series"]
    snapshot = copy.deepcopy(original)
    result = transform_series(original, case["input"]["offline_edit_command"])
    assert original == snapshot
    assert all(s["unit"] == "조원" and "누적 변화량" in s["label"] for s in result)
    assert result == read_json(BASE / case["expected"]["data"]["fixture"])["series"]


def test_contradictory_choice_is_not_an_automatic_pass_and_can_be_reviewed():
    case = next(c for c in all_cases() if c["id"] == "SBV2-0043")
    clarification = case["expected"]["resolution"]["clarification"]
    prediction = {"id": case["id"], "execution_status": "observed",
                  "input_sha256": hashlib.sha256(json.dumps(case["input"], ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                  "resolution": {"decision": "clarify", "table_ids": [], "clarification": {"asked": True,
                    "question": " ".join(clarification["dimensions"]),
                    "options": [term + "은 선택 불가입니다" for group in clarification["option_groups"] for term in group]}}}
    assert "clarification_semantics_unreviewed" in check_resolution(case["expected"]["resolution"], prediction["resolution"])
    prediction["observation_sha256"] = observation_hash(prediction)
    assert score_case(case, prediction)["status"] == "pending_review"
    assert score_case(case, prediction)["automatic_pass"] is False
    review = {"prediction_sha256": prediction["observation_sha256"], "reviewer": "test-human",
              "human_approved": True, "clarification_options_correct": False}
    assert score_case(case, prediction, review)["status"] == "failed"
    # A human judgment is bound to this exact response, not the next response.
    prediction["resolution"]["clarification"]["question"] += " changed"
    assert score_case(case, prediction, review)["status"] == "pending_review"


def test_edit_instruction_drift_is_blocked():
    case = copy.deepcopy(next(c for c in all_cases() if c["id"] == "SBV2-0067"))
    case["input"]["actions"][-1]["instruction"] = "데이터를 모두 삭제해 주세요."
    assert any("semantic annotation review" in e for e in validate_cases([case], enforce_counts=False)["errors"])
    case["input"]["actions"][-1]["instruction"] = "제목을 '다른 제목'로 변경해 주세요."
    assert any("instruction/command mismatch" in e for e in validate_cases([case], enforce_counts=False)["errors"])


def test_all_public_edit_annotations_match_bounded_contract():
    for case in all_cases():
        command = case["input"].get("offline_edit_command")
        if command:
            edit = next(a for a in case["input"]["actions"] if a["kind"] == "edit")
            assert instruction_command(edit["instruction"]) == command


def test_invalid_gold_clarification_options_are_blocked():
    case = copy.deepcopy(next(c for c in all_cases() if c["id"] == "SBV2-0043"))
    case["expected"]["resolution"]["clarification"]["option_groups"] = [["말잔", "환율"]]
    assert any("undocumented clarification" in e for e in validate_cases([case], enforce_counts=False)["errors"])


@pytest.mark.parametrize("field,value", [("kind", "STYLE_EDIT"), ("value", "made_up"), ("unexpected", True)])
def test_invalid_structured_edit_commands_are_blocked(field, value):
    case = copy.deepcopy(next(c for c in all_cases() if c["id"] == "SBV2-0069"))
    case["input"]["offline_edit_command"][field] = value
    assert validate_cases([case], enforce_counts=False)["errors"]


@pytest.mark.parametrize("change", [{"visible": False}, {"visible": "legendonly"}, {"opacity": 0}, {"line": {"width": 0}}])
def test_hidden_line_does_not_pass(change):
    series = [{"label": "x", "points": [{"period": "202401", "value": 1}]}]
    trace = {"type": "scatter", "mode": "lines", "name": "x", "x": ["202401"], "y": [1], **change}
    assert "plotly_hidden_line" in check_plotly(series, {"data": [trace]}, "line")


def test_missing_or_wrong_input_hash_cannot_pass():
    case = next(c for c in all_cases() if c["mode"] == "discovery" and c["expected"]["resolution"]["decision"] == "unsupported")
    prediction = {"execution_status": "observed", "resolution": {"decision": "unsupported", "table_ids": []}}
    assert "input_hash_missing" in score_case(case, prediction)["failures"]
    prediction["input_sha256"] = "0" * 64
    assert "input_hash_mismatch" in score_case(case, prediction)["failures"]


def test_malformed_schema_does_not_crash_count_validation():
    assert validate_cases([{"id": "SBV2-9999", "mode": "discovery"}])["errors"]


def test_review_packet_preserves_existing_human_work(tmp_path, monkeypatch):
    import review_packet
    path = tmp_path / "results/review.jsonl"
    path.parent.mkdir()
    path.write_text("human work", encoding="utf-8")
    monkeypatch.setattr(review_packet, "BASE", tmp_path)
    monkeypatch.setattr(sys, "argv", ["review_packet", "unused-cases", "unused-predictions", "--output", "results/review.jsonl"])
    with pytest.raises(ValueError, match="overwrite"):
        review_packet.main()
    assert path.read_text(encoding="utf-8") == "human work"


def test_review_packet_rejects_observation_without_input_binding(tmp_path, monkeypatch):
    import review_packet
    case = next(c for c in all_cases() if c["id"] == "SBV2-0043")
    prediction = {"id": case["id"], "execution_status": "observed"}
    prediction["observation_sha256"] = observation_hash(prediction)
    write_jsonl(tmp_path / "cases.jsonl", [case])
    write_jsonl(tmp_path / "predictions.jsonl", [prediction])
    monkeypatch.setattr(review_packet, "BASE", tmp_path)
    monkeypatch.setattr(sys, "argv", ["review_packet", str(tmp_path / "cases.jsonl"), str(tmp_path / "predictions.jsonl"), "--output", "results/review.jsonl"])
    with pytest.raises(ValueError, match="input hash"):
        review_packet.main()
    assert not (tmp_path / "results/review.jsonl").exists()


def test_unknown_provider_cannot_impersonate_kosis():
    series = read_json(BASE / "fixtures/provider.json")["series"][0]
    changed = copy.deepcopy(series)
    changed["provider"] = "invented"
    assert compare_series([series], [changed], 0)
    assert validate_fixture({"series": [changed]}, catalog_contract())


def test_missing_value_field_is_not_an_explicit_null():
    series = {"provider": "attachment", "series_id": "attachment:null", "label": "x", "unit": "%",
              "frequency": "M", "points": [{"period": "202401", "value": None}]}
    changed = copy.deepcopy(series)
    del changed["points"][0]["value"]
    assert "missing_point_value" in compare_series([series], [changed], 0)


@pytest.mark.parametrize("tolerance", [float("inf"), float("nan")])
def test_unbounded_or_nan_tolerance_is_blocked(tolerance):
    case = copy.deepcopy(next(c for c in all_cases() if "data" in c["expected"]))
    case["expected"]["data"]["absolute_tolerance"] = tolerance
    assert any("nonfinite numeric tolerance" in e for e in validate_cases([case], enforce_counts=False)["errors"])
