import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v41_public_corpus_has_no_holdout_answers():
    base = ROOT / "eval" / "table-discovery" / "v4.1"
    validator = runpy.run_path(str(base / "scripts" / "validate_v41.py"))
    assert validator["main"]() == 0
    holdout = [json.loads(line) for line in (base / "holdout_queries.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(holdout) == 30
    assert all("table_ids" not in case and "expected_status" not in case for case in holdout)


def test_evaluation_scopes_are_separate():
    for version in ("v1", "v2", "v3"):
        assert (ROOT / "eval" / "table-discovery" / version / "cases.jsonl").is_file()
    assert (ROOT / "eval" / "end-to-end" / "v1" / "manifest.json").is_file()
    assert (ROOT / "eval" / "end-to-end" / "v2" / "manifest.json").is_file()
