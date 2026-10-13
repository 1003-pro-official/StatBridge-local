"""KOSIS verifier helpers: period math stays offline so CI can check it without keys."""
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


verify = load("reporter200_verify_kosis", "verify_kosis.py")


def test_expected_rows_counts_the_requested_span():
    assert verify.expected_rows("202001", "202512", "M") == 72
    assert verify.expected_rows("201901", "202404", "Q") == 24
    assert verify.expected_rows("2020", "2024", "A") == 5
    assert verify.expected_rows("202604", "202604", "M") == 1


def test_every_resolved_gold_plan_spans_at_least_one_period():
    cases = verify.load_cases()
    for case in cases:
        for plan in case["workflow_gold"]["classification_and_plan"]["series"]:
            assert verify.expected_rows(plan["period_start"], plan["period_end"], plan["frequency"]) >= 1


def test_api_key_is_read_from_the_env_file_without_being_written_anywhere():
    if not (ROOT / ".env").exists():
        pytest.skip(".env가 없는 환경")
    key = verify.api_key()
    assert key and len(key) > 10
    assert key not in (DATASET / "scripts" / "verify_kosis.py").read_text(encoding="utf-8")
