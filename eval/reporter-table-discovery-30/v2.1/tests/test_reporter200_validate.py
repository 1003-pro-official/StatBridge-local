import copy
import json
from pathlib import Path

import pytest

from importlib.util import module_from_spec, spec_from_file_location

DATASET = Path(__file__).resolve().parents[1]
ROOT = DATASET.parents[2]
spec = spec_from_file_location("reporter200_validate", DATASET / "scripts/validate.py")
validator = module_from_spec(spec)
spec.loader.exec_module(validator)


@pytest.fixture
def inputs():
    cases = [
        json.loads(line)
        for line in (DATASET / "statbridge-reporter200.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    catalog = json.loads(
        (ROOT / "src/agent/stat_dictionary/stat_language_dictionary.json").read_text(encoding="utf-8-sig")
    )
    manifest = json.loads((DATASET / "dataset_manifest.json").read_text(encoding="utf-8"))
    return copy.deepcopy(cases), catalog, manifest


def test_dataset_matches_manifest_and_keeps_v2_intact(inputs):
    cases, catalog, manifest = inputs
    summary = validator.validate_cases(cases, catalog, manifest["counts"]["cases"])
    validator.validate_legacy_preservation(cases)
    assert summary == manifest["counts"]
    assert summary["by_schema"][validator.LEGACY_SCHEMA] == 30
    assert summary["new_cases"] == len(cases) - 30


def test_carried_v2_case_is_rejected_when_its_gold_changes(inputs):
    cases, catalog, manifest = inputs
    carried = next(case for case in cases if case["schema_version"] == validator.LEGACY_SCHEMA)
    carried["workflow_gold"]["query_interpretation"]["frequency"] = "Q"
    with pytest.raises(ValueError, match="legacy case body changed"):
        validator.validate_legacy_preservation(cases)


def test_research_reference_hash_mismatch_is_rejected(inputs):
    cases, catalog, manifest = inputs
    case = next(case for case in cases if case["schema_version"] == validator.SCHEMA)
    case["research_references"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="research file hash mismatch"):
        validator.validate_cases(cases, catalog, manifest["counts"]["cases"])


def test_research_heading_must_match_the_referenced_line(inputs):
    cases, catalog, manifest = inputs
    case = next(case for case in cases if case["schema_version"] == validator.SCHEMA)
    case["research_references"][0]["line"] = 1
    with pytest.raises(ValueError, match="research heading does not match"):
        validator.validate_cases(cases, catalog, manifest["counts"]["cases"])


def test_new_case_without_research_reference_is_rejected(inputs):
    cases, catalog, manifest = inputs
    case = next(case for case in cases if case["schema_version"] == validator.SCHEMA)
    case["research_references"] = []
    with pytest.raises(ValueError, match="missing research reference"):
        validator.validate_cases(cases, catalog, manifest["counts"]["cases"])


def test_invalid_classification_code_is_rejected(inputs):
    cases, catalog, manifest = inputs
    case = next(case for case in cases if case["workflow_gold"]["classification_and_plan"]["series"])
    case["workflow_gold"]["classification_and_plan"]["series"][0]["classifications"]["objL1"] = "INVALID"
    with pytest.raises(ValueError, match="invalid classification code"):
        validator.validate_cases(cases, catalog, manifest["counts"]["cases"]) 


def test_periodless_resolved_case_records_period_missing(inputs):
    cases, catalog, manifest = inputs
    case = next(case for case in cases if case["workflow_gold"]["query_interpretation"]["period"] is None
                and case["workflow_gold"]["resolution"]["agent_status"] == "resolved")
    assert case["workflow_gold"]["resolution"]["api_status"] == "need_period"
    assert case["workflow_gold"]["post_discovery"]["reason"] == "period_missing"
    assert case["workflow_gold"]["post_discovery"]["period_selection_required"] is True
