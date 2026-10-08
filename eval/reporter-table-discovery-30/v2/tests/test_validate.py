import copy
import json
from pathlib import Path

import pytest

from importlib.util import module_from_spec, spec_from_file_location

DATASET = Path(__file__).resolve().parents[1]
ROOT = DATASET.parents[2]
spec = spec_from_file_location("reporter30_v2_validate", DATASET / "scripts/validate.py")
validator = module_from_spec(spec)
spec.loader.exec_module(validator)


@pytest.fixture
def inputs():
    cases = [
        json.loads(line)
        for line in (DATASET / "statbridge-reporter30.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    catalog = json.loads(
        (ROOT / "src/agent/stat_dictionary/stat_language_dictionary.json").read_text(encoding="utf-8-sig")
    )
    return copy.deepcopy(cases), catalog


def test_stagewise_dataset_has_thirty_complete_cases(inputs):
    cases, catalog = inputs
    summary = validator.validate_cases(cases, catalog)
    assert summary["cases"] == 30
    assert summary["statuses"] == {"need_clarification": 1, "no_match": 8, "resolved": 21}
    assert all("workflow_gold" in case for case in cases)


def test_invalid_classification_code_is_rejected(inputs):
    cases, catalog = inputs
    selected = next(case for case in cases if case["workflow_gold"]["classification_and_plan"]["series"])
    selected["workflow_gold"]["classification_and_plan"]["series"][0]["classifications"]["objL1"] = "INVALID"
    with pytest.raises(ValueError, match="invalid classification code"):
        validator.validate_cases(cases, catalog)


def test_missing_requested_series_is_rejected(inputs):
    cases, catalog = inputs
    selected = next(
        case for case in cases
        if len(case["workflow_gold"]["classification_and_plan"]["series"]) > 1
    )
    selected["workflow_gold"]["classification_and_plan"]["series"].pop()
    with pytest.raises(ValueError, match="series count"):
        validator.validate_cases(cases, catalog)


def test_periodless_resolved_case_records_post_discovery_period_request(inputs):
    cases, catalog = inputs
    case = next(case for case in cases if case["workflow_gold"]["query_interpretation"]["period"] is None
                and case["workflow_gold"]["resolution"]["agent_status"] == "resolved")
    assert case["workflow_gold"]["resolution"]["api_status"] == "need_period"
    assert case["workflow_gold"]["post_discovery"]["reason"] == "period_missing"


def test_dataset_hash_normalizes_line_endings(tmp_path):
    lf = tmp_path / "lf.txt"
    crlf = tmp_path / "crlf.txt"
    lf.write_bytes(b"first\nsecond\n")
    crlf.write_bytes(b"first\r\nsecond\r\n")
    assert validator.text_sha256(lf) == validator.text_sha256(crlf)
