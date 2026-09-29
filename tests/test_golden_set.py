import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v41_public_corpus_has_no_holdout_answers():
    base = ROOT / "eval" / "golden-set-v4.1"
    validator = runpy.run_path(str(base / "scripts" / "validate_v41.py"))
    assert validator["main"]() == 0
    holdout = [json.loads(line) for line in (base / "holdout_queries.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(holdout) == 30
    assert all("table_ids" not in case and "expected_status" not in case for case in holdout)


def test_earlier_public_corpora_are_preserved():
    assert (ROOT / "eval" / "golden-set-v1" / "manifest.json").is_file()
    assert (ROOT / "eval" / "golden-set-v2" / "manifest.json").is_file()
