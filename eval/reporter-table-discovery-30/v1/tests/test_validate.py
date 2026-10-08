import copy
import importlib.util
import json
from pathlib import Path

import pytest

DATASET = Path(__file__).resolve().parents[1]
ROOT = DATASET.parents[2]
spec = importlib.util.spec_from_file_location("reporter30_validate", DATASET / "scripts/validate.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


@pytest.fixture
def inputs():
    cases = [json.loads(line) for line in (DATASET / "statbridge-reporter30.jsonl").read_text(encoding="utf-8").splitlines()]
    catalog = json.loads((ROOT / "src/agent/stat_dictionary/stat_language_dictionary.json").read_text(encoding="utf-8-sig"))
    return copy.deepcopy(cases), catalog


def test_public_draft_is_consistent(inputs):
    cases, catalog = inputs
    summary = validator.validate_cases(cases, catalog)
    assert (summary["cases"], summary["series"], summary["tables"]) == (30, 57, 26)


def test_invalid_code_cannot_pass_even_when_both_gold_copies_agree(inputs):
    cases, catalog = inputs
    cases[0]["expected_series"][0]["classifications"]["objL1"] = "INVALID"
    cases[0]["workflow_gold"]["classification_and_plan"]["series"][0]["classifications"]["objL1"] = "INVALID"
    with pytest.raises(ValueError, match="invalid classification code"):
        validator.validate_cases(cases, catalog)


def test_residual_balance_label_cannot_use_new_loan_table(inputs):
    cases, catalog = inputs
    cases[0]["workflow_gold"]["query_interpretation"]["series"][0]["measurement_basis"] = "잔액"
    with pytest.raises(ValueError, match="measurement basis"):
        validator.validate_cases(cases, catalog)


def test_multi_series_plan_must_include_every_requested_series(inputs):
    cases, catalog = inputs
    cases[8]["workflow_gold"]["classification_and_plan"]["series"].pop()
    with pytest.raises(ValueError, match="missing lookup series"):
        validator.validate_cases(cases, catalog)


def test_source_hash_is_stable_across_windows_and_git_line_endings(tmp_path):
    windows = tmp_path / "windows.txt"
    git = tmp_path / "git.txt"
    windows.write_bytes(b"catalog\r\nsecond line\r\n")
    git.write_bytes(b"catalog\nsecond line\n")
    assert validator.text_sha256(windows) == validator.text_sha256(git)
