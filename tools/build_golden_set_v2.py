"""Create the v2 regression snapshot and an explicitly unscored authoring queue."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from evaluate_golden_set import DEFAULT_CORPUS, load_cases


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "eval" / "golden-set-v2"
FAMILIES = [
    ("통화신용정책보고서", 10), ("금융안정보고서", 10), ("경제전망보고서", 10),
    ("기업경영분석", 10), ("지급결제보고서", 5), ("지역경제보고서", 5),
]
TASK_COUNTS = {"follow_up": 20, "catalog_only": 10,
               "clear_no_clarification": 10, "chart_e2e": 10}


def migrate_case(case: dict) -> dict:
    migrated = json.loads(json.dumps(case, ensure_ascii=False))
    migrated["case_origin"] = "golden-set-v1-regression"
    migrated["review"] = {"status": "inherited", "eligible_for_scoring": True}
    expected = migrated.setdefault("expected", {})
    groups = expected.get("retrieval_groups", [])
    if expected.get("status") == "no_match":
        intent, clarification, table_ids = "unsupported", "none", []
    elif migrated.get("evaluation", {}).get("current_check") == "clarification":
        intent, clarification = "ambiguous", "semantic"
        table_ids = list(expected.get("clarification_options") or [])
    else:
        intent, clarification = "resolved", "none"
        table_ids = list(dict.fromkeys(group[0] for group in groups if group))
    expected["resolution"] = {
        "intent": intent,
        "clarification_kind": clarification,
        "table_ids": table_ids,
        "retrieval_groups": groups,
    }
    return migrated


def make_queue() -> list[dict]:
    queue = []
    remaining = dict(TASK_COUNTS)
    for family, family_count in FAMILIES:
        for index in range(family_count):
            task_type = next(name for name, count in remaining.items() if count)
            remaining[task_type] -= 1
            queue.append({
                "id": f"v2-draft-{len(queue) + 1:03}",
                "family": family,
                "case_type": task_type,
                "status": "needs_source_and_human_review",
                "eligible_for_scoring": False,
                "authoring_requirements": {
                    "source_locator": "기존 v1 근거를 복사하지 말고 실제 보고서 쪽·표·그림을 확인해 기록",
                    "supported_target": "실제 카탈로그에서 table/item/classification ID와 데이터 가용성을 검증",
                    "independent_review": "작성자와 다른 검토자가 질문 의도·정답·역질문 결정을 확인",
                },
            })
    return queue


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cases_dir = OUTPUT / "cases"
    cases_dir.mkdir(exist_ok=True)
    cases = [migrate_case(case) for case in load_cases(DEFAULT_CORPUS)]
    (cases_dir / "v1_regression.json").write_text(
        json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    queue = make_queue()
    (OUTPUT / "authoring_queue.json").write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copytree(DEFAULT_CORPUS / "fixtures", OUTPUT / "fixtures", dirs_exist_ok=True)
    manifest = json.loads((DEFAULT_CORPUS / "manifest.json").read_text(encoding="utf-8"))
    manifest.update({
        "schema_version": "2.0-draft",
        "name": "StatBridge golden set v2",
        "status": "not_release_ready",
        "baseline": {"source": "eval/golden-set", "cases": len(cases),
                     "use": "회귀 전용; 기존 holdout은 개발 중 노출되어 블라인드 평가로 해석 금지"},
        "target": {"public_cases": 200, "new_cases": 50, "private_blind_cases": 60},
        "public_additions": {"authoring_tasks": len(queue), "scored_cases": 0,
                             "family_targets": dict(FAMILIES),
                             "types": {"follow_up": 20, "catalog_only": 10,
                                       "clear_no_clarification": 10, "chart_e2e": 10}},
        "private_holdout": {
            "cases": 60,
            "distribution": {"single": 15, "multi": 10, "clarify_required": 10,
                             "follow_up": 10, "no_match": 10, "catalog_only": 5},
            "storage": "answers and scorer must live outside this repository and outside model/index inputs",
            "status": "not_created; requires independently authored and reviewed cases",
        },
        "release_metric_targets": {
            "recall_at_5": 0.93, "top1": 0.82, "single_exact": 0.90,
            "multi_exact": 0.80, "clarification_sensitivity": 0.85,
            "clarification_suppression": 0.85, "follow_up": 0.70,
            "no_match": 0.95, "catalog_only": 1.0,
        },
        "v1_untouched": True,
        "golden_set_v3_used": False,
    })
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
