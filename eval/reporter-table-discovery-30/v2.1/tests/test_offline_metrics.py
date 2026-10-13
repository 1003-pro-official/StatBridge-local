"""Offline evaluator metrics: rank math, denominators, and a real resolver smoke run."""
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


offline = load("reporter200_offline", "evaluate_offline.py")


def test_score_computes_ranks_and_missing_tables():
    gold = {"status": "resolved", "tables": ["A", "B"], "frequency": "M", "clarification": {}}
    row = offline.score({"id": "X", "ranked": ["C", "A"], "clarification_id": None,
                         "clarification_options": [], "frequency": "M"}, gold)
    assert row["best_rank"] == 2 and row["all_tables_found"] is False
    assert row["missing_tables"] == ["B"] and row["top1_hit"] is False


def test_rate_ignores_not_applicable_rows():
    rows = [{"flag": True}, {"flag": False}, {"flag": None}]
    assert offline.rate(rows, "flag") == 0.5
    assert offline.rate([{"flag": None}], "flag") is None


def synthetic_row(case_id: str, best_rank):
    rank = best_rank
    return {"id": case_id, "status": "resolved", "top1_hit": rank == 1, "best_rank": rank,
            "all_tables_found": rank is not None, "frequency_match": True,
            "clarification_expected": None, "clarification_observed": None,
            "clarification_group_match": None, "options_subset": None, "missing_options": [],
            "candidate_count": 40, "top1_table": "T", "missing_tables": [],
            "recall1": rank == 1, "recall3": rank is not None and rank <= 3,
            "recall5": rank is not None and rank <= 5}


def test_mrr_uses_every_resolved_case_as_denominator():
    rows = [synthetic_row("a", 1), synthetic_row("b", None)]
    summary = offline.summarize(rows, rows)
    assert summary["mrr"] == 0.5           # 찾지 못한 문항을 0으로 센다
    assert summary["mrr_of_found"] == 1.0  # 찾은 문항만 보면 부풀려진다
    assert summary["any_gold_table_found"] == 0.5


def test_resolver_runs_offline_and_matches_the_contract():
    resolver = pytest.importorskip("stat_dictionary.stat_language_resolver")
    del resolver
    cases = [json.loads(line) for line in (DATASET / "statbridge-reporter200.jsonl")
             .read_text(encoding="utf-8").splitlines() if line]
    try:
        engine = offline.load_resolver()
    except (ImportError, ModuleNotFoundError) as exc:  # 런타임 의존성이 없는 환경
        pytest.skip(f"리졸버를 불러올 수 없음: {exc}")
    case = next(item for item in cases if item["id"] == "REPORTER30-V2.1-037")
    observation = offline.observe(engine, case, top_k=10)
    assert "DT_121Y006" in observation["ranked"]
    row = offline.score(observation, offline.expected(case))
    assert row["best_rank"] == 1
    clarification_case = next(item for item in cases if item["id"] == "REPORTER30-V2.1-055")
    assert offline.observe(engine, clarification_case, top_k=5)["clarification_id"] == "price_index_type"
    assert offline.observe(engine, clarification_case, top_k=5)["clarification_options"]
