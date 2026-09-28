from pathlib import Path
import sys
import json
from collections import Counter

from statbridge_mcp.metadata_store import MetadataStore


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from evaluate_golden_set import load_cases, score_retrieval, validate_cases  # noqa: E402
from evaluate_golden_set_v2 import score_resolution  # noqa: E402


def test_retrieval_metrics_cover_each_required_series_group():
    metrics = score_retrieval(
        [["table-a", "table-a-alt"], ["table-b"]],
        ["unrelated", "table-b", "table-a-alt"],
        k=3,
    )

    assert metrics == {"recall_at_k": 1.0, "mrr": 0.5, "top1": 0.0}


def test_bok_golden_corpus_is_complete_and_uses_supported_tables():
    corpus_dir = ROOT / "eval" / "golden-set"
    cases = load_cases(corpus_dir)
    supported_ids = set(MetadataStore().table_ids())

    errors = validate_cases(cases, supported_ids)

    assert not errors, "\n".join(errors)
    assert len(cases) == 150
    assert sum("chart" in case["tags"] for case in cases) == 30
    assert sum(case["split"] == "development" for case in cases) == 50
    assert sum(case["split"] == "holdout" for case in cases) == 100
    assert all(case.get("source", {}).get("url") for case in cases)
    assert {case["category"] for case in cases} == {
        "single_table", "alias", "conditions", "close_distinctions",
        "multi_indicator", "clarification", "out_of_scope",
    }


def test_v2_keeps_v1_cases_as_regression_and_marks_additions_unscored():
    corpus_dir = ROOT / "eval" / "golden-set-v2"
    cases = load_cases(corpus_dir)
    manifest = json.loads((corpus_dir / "manifest.json").read_text(encoding="utf-8"))
    queue = json.loads((corpus_dir / "authoring_queue.json").read_text(encoding="utf-8"))
    errors = validate_cases(cases, set(MetadataStore().table_ids()), corpus_dir)

    assert not errors, "\n".join(errors)
    assert manifest["status"] == "not_release_ready"
    assert len(cases) == 150
    assert len(queue) == 50
    assert Counter(item["case_type"] for item in queue) == {
        "follow_up": 20, "catalog_only": 10, "clear_no_clarification": 10, "chart_e2e": 10,
    }
    assert all(not item["eligible_for_scoring"] for item in queue)
    assert all("resolution" in case["expected"] for case in cases)


def test_resolution_metrics_score_actual_proposal_and_clarification_decision():
    scores = score_resolution(
        {"resolution": {"intent": "resolved", "clarification_kind": "none",
                         "proposed_table_ids": ["a", "b"]},
         "ranked_table_ids": ["a", "b"]},
        {"intent": "resolved", "clarification_kind": "none", "table_ids": ["b", "a"],
         "retrieval_groups": [["a"], ["b"]]},
    )
    assert scores == {"table_set_exact": 1.0, "intent_exact": 1.0, "clarification_exact": 1.0,
                      "recall_at_5": 1.0, "top1": 1.0}


def test_analysis_api_adds_resolution_without_changing_legacy_status():
    from analysis_service import AnalysisService
    from statbridge_mcp.statistics_service import StatisticsService

    result = AnalysisService(StatisticsService()).analyze({"query": "경제심리지수 순환변동치"})

    assert result["status"] == "need_clarification"
    assert result["resolution"] == {
        "intent": "resolved", "clarification_kind": "none", "proposed_table_ids": ["DT_513Y001"]
    }


def test_analysis_resolution_marks_underspecified_and_unsupported_queries():
    from analysis_service import AnalysisService
    from statbridge_mcp.statistics_service import StatisticsService

    analysis = AnalysisService(StatisticsService())
    ambiguous = analysis.analyze({"query": "금리 알려줘"})
    unsupported = analysis.analyze({"query": "스포츠 경기 결과 예측해"})

    assert ambiguous["resolution"]["intent"] == "ambiguous"
    assert ambiguous["resolution"]["clarification_kind"] == "semantic"
    assert len(ambiguous["resolution"]["proposed_table_ids"]) >= 2
    assert unsupported["resolution"] == {
        "intent": "unsupported", "clarification_kind": "none", "proposed_table_ids": []
    }
