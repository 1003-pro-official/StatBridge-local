"""Validator coverage: every case must reject a deliberately broken field.

The validator is the gate that keeps gold honest, so this proves it is not blind anywhere.
"""
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


validate = load("reporter200_validate_mutation", "validate.py")
GOLD = [json.loads(line) for line in (DATASET / "statbridge-reporter200.jsonl")
        .read_text(encoding="utf-8").splitlines() if line]
CATALOG = json.loads((ROOT / "src/agent/stat_dictionary/stat_language_dictionary.json").read_text(encoding="utf-8-sig"))
EXPECTED = json.loads((DATASET / "dataset_manifest.json").read_text(encoding="utf-8"))["counts"]["cases"]


def unused_table_id(case: dict) -> str:
    used = set(case["workflow_gold"]["table_discovery"]["expected_table_ids"])
    for table_id in ("DT_102Y001", "DT_101Y001", "DT_101Y002", "DT_101Y003"):
        if table_id not in used:
            return table_id
    raise AssertionError("mutation table pool exhausted")


def mutations(case: dict) -> list[tuple[str, dict]]:
    """(label, mutated case) pairs the validator must reject."""

    def broken(step):
        clone = copy.deepcopy(case)
        step(clone)
        return clone

    def workflow(clone):
        return clone["workflow_gold"]

    def first_plan(clone):
        return workflow(clone)["classification_and_plan"]["series"][0]

    out = [
        ("schema_version", broken(lambda c: c.update(schema_version="other"))),
        ("split", broken(lambda c: c.update(split="holdout"))),
        ("approval", broken(lambda c: c["review"].update(human_approved=True))),
        ("expected_tables", broken(lambda c: workflow(c)["table_discovery"]["selected_table_ids"].append(
            unused_table_id(case)))),
    ]
    status = case["workflow_gold"]["resolution"]["agent_status"]
    if status == "resolved":
        out += [
            ("table_id", broken(lambda c: first_plan(c).update(table_id="DT_999Y999"))),
            ("table_name", broken(lambda c: first_plan(c).update(table_name="다른 표"))),
            ("item_id", broken(lambda c: first_plan(c).update(item_id="0"))),
            ("period", broken(lambda c: first_plan(c).update(period_start="190001"))),
            ("params", broken(lambda c: first_plan(c)["exact_params"].pop("prdSe"))),
            ("classification_code", broken(lambda c: first_plan(c)["classifications"].update(objL1="INVALID"))),
            ("classification_label", broken(lambda c: first_plan(c)["classification_labels"].update(objL1="다른 이름"))),
            ("frequency", broken(lambda c: first_plan(c).update(
                frequency="A" if first_plan(c)["frequency"] != "A" else "M"))),
            ("post_period", broken(lambda c: workflow(c)["post_discovery"].update(
                reason="period_missing" if workflow(c)["post_discovery"]["reason"] != "period_missing"
                else "execution_deferred"))),
        ]
    elif status == "need_clarification":
        out += [
            ("clarification_id", broken(lambda c: workflow(c)["resolution"]["clarification"].update(id="nope"))),
            ("clarification_options", broken(lambda c: workflow(c)["resolution"]["clarification"].update(options=[]))),
            ("clarification_question", broken(lambda c: workflow(c)["resolution"]["clarification"].update(question="?"))),
        ]
    else:
        out += [
            ("no_match_selection", broken(lambda c: workflow(c)["table_discovery"].update(status="matched"))),
            ("no_match_reason", broken(lambda c: workflow(c)["resolution"].update(no_match_reason=""))),
            ("no_match_plan", broken(lambda c: workflow(c)["classification_and_plan"]["series"].append(
                {"label": "x", "table_id": "DT_102Y001", "table_name": "본원통화", "org_id": "301",
                 "item_id": "13103134511999", "classifications": {}, "classification_labels": {},
                 "frequency": "M", "period_start": "202501", "period_end": "202512", "exact_params": {}}))),
        ]
    return out


def test_every_case_rejects_its_mutations():
    checked, missed = 0, []
    for case in GOLD:
        for label, broken_case in mutations(case):
            checked += 1
            try:
                validate.validate_cases([broken_case], CATALOG, 1)
            except ValueError:
                continue
            missed.append(f"{case['id']}:{label}")
    assert missed == [], f"검증기가 거부하지 못한 변조: {missed[:10]} (총 {len(missed)})"
    assert checked >= 7 * len(GOLD)


def test_research_reference_mutations_are_rejected():
    case = next(item for item in GOLD if item["schema_version"] == validate.SCHEMA)
    for label, step in (("sha256", lambda ref: ref.update(sha256="0" * 64)),
                        ("line", lambda ref: ref.update(line=1)),
                        ("figure_id", lambda ref: ref.update(figure_id="NOPE")),
                        ("role", lambda ref: ref.update(role="gold_source"))):
        broken = copy.deepcopy(case)
        step(broken["research_references"][0])
        with pytest.raises(ValueError, match="research"):
            validate.validate_cases([broken], CATALOG, 1)


def test_case_count_must_match_the_manifest():
    with pytest.raises(ValueError, match="manifest case count"):
        validate.validate_cases(GOLD[:1], CATALOG, EXPECTED)
