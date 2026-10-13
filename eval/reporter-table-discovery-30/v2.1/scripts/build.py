"""Build the v2.1 public reporter golden set: v2's 30 cases verbatim plus augmented cases.

Gold values come only from the public catalog; research artifacts supply the topic
and are recorded as hash-verified references. No runtime prediction is read.
"""
from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATASET = Path(__file__).resolve().parents[1]
V2 = DATASET.parent / "v2"
CATALOG = ROOT / "src/agent/stat_dictionary/stat_language_dictionary.json"
RESEARCH_DIR = ROOT / "research/그림표-분석"
SCHEMA = "reporter200-discovery-2.1"
LEGACY_SCHEMA = "reporter30-discovery-2"
REFERENCE_DATE = "2026-10-13"
RELATIONSHIP = "theme_adaptation_not_original_figure_reproduction"
ROLE = "journalistic_context_only_not_numeric_or_table_id_gold"
INTENT = ["statistical_table_discovery"]
SLOT_MATCHING = "semantic_equivalence_allowed_for_names; preserve_metric_and_scope"
NULL_SEMANTICS = "no_explicit_filter; do_not_guess_a_more_specific_target"
EXCLUDED = ["numeric_observations", "chart_rendering", "interpretation_text", "causal_claims"]

_validate_spec = importlib.util.spec_from_file_location(
    "reporter200_validate", DATASET / "scripts/validate.py")
validate = importlib.util.module_from_spec(_validate_spec)
_validate_spec.loader.exec_module(validate)

_runner_spec = importlib.util.spec_from_file_location(
    "reporter200_runner", DATASET / "scripts/evaluate_runtime.py")
runner = importlib.util.module_from_spec(_runner_spec)
_runner_spec.loader.exec_module(runner)

# (id, topic, status, query, period, series, research figure ids)
# series: (label, metric, target, measure, table_id, {api_param: catalog value_name})
SPECS_DIR = Path(__file__).resolve().parent / "specs"


def load_specs() -> list[dict]:
    """One JSON file per authoring batch keeps merged gold reviewable."""
    specs = []
    for path in sorted(SPECS_DIR.glob("*.json")):
        specs.extend(json.loads(path.read_text(encoding="utf-8")))
    ids = [spec["id"] for spec in specs]
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate spec id across batches")
    return specs


def research_index() -> dict[str, dict]:
    """figure id -> hash-verified reference inside the committed research tree."""
    index: dict[str, dict] = {}
    for path in sorted(RESEARCH_DIR.rglob("*.md")):
        if "백업" in path.parts:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        sha = validate.text_sha256(path)
        for number, line in enumerate(lines, 1):
            if "- 결과물ID:" not in line:
                continue
            figure_id = line.split("`")[1]
            heading = next((text.strip() for text in reversed(lines[:number - 1]) if text.startswith("### ")), "")
            index[figure_id] = {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "line": number - 2,
                                "heading": heading, "figure_id": figure_id, "sha256": sha}
    return index


def references(spec: dict, index: dict[str, dict]) -> list[dict]:
    out = []
    for figure_id in spec["research"]:
        ref = index.get(figure_id)
        if ref is None:
            raise SystemExit(f"{spec['id']}: unknown research figure {figure_id}")
        out.append({**ref, "relationship": RELATIONSHIP, "role": ROLE})
    return out


def table(tables: dict[str, dict], table_id: str) -> dict:
    found = tables.get(table_id)
    if found is None:
        raise SystemExit(f"unknown table {table_id}")
    return found


def class_codes(entry: dict, tables: dict[str, dict]) -> dict[str, dict[str, str]]:
    found = table(tables, entry[4])
    dimensions = {dimension["api_param"]: dimension for dimension in found.get("dimensions", [])}
    if set(dimensions) != set(entry[5]):
        raise SystemExit(f"{entry[4]}: dimensions {sorted(dimensions)} != {sorted(entry[5])}")
    codes, labels = {}, {}
    for param, name in entry[5].items():
        match = next((value for value in dimensions[param]["values"] if value["value_name"] == name), None)
        if match is None:
            raise SystemExit(f"{entry[4]}.{param}: unknown value name {name!r}")
        codes[param] = match["value_id"]
        labels[param] = match["value_name"]
    return {"codes": codes, "labels": labels}


def meaning(entry: tuple) -> dict:
    return {"label": entry[0], "metric": entry[1], "target": entry[2], "measure": entry[3],
            "measurement_basis": None, "qualifiers": {}}


def build_case(spec: dict, tables: dict[str, dict], index: dict[str, dict]) -> dict:
    case_id = f"REPORTER30-V2.1-{spec['id']}"
    meanings = [meaning(entry) for entry in spec["series"]]
    period = spec.get("period")
    period_gold = None if period is None else {"start": f"{period[0]}-01-01", "end": f"{period[1]}-12-31",
                                               "inclusive": True, "source": "explicit"}
    catalog_sha = validate.text_sha256(CATALOG)
    interpretation = {"user_intent": INTENT, "period": period_gold, "frequency": None,
                      "comparison": {"required": len(meanings) > 1,
                                     "mode": "series_comparison" if len(meanings) > 1 else "none"},
                      "series": meanings, "slot_matching": SLOT_MATCHING, "null_semantics": NULL_SEMANTICS}

    if spec["status"] == "resolved":
        frequencies = {table(tables, entry[4])["prd_se"] for entry in spec["series"]}
        if len(frequencies) != 1:
            raise SystemExit(f"{case_id}: mixed frequencies {frequencies}")
        frequency = frequencies.pop()
        interpretation["frequency"] = frequency
        probe = {"id": case_id, "query": spec["query"],
                 "workflow_gold": {"query_interpretation": {"period": period_gold}}}
        plans, names, items = [], {}, {}
        for entry in spec["series"]:
            found = table(tables, entry[4])
            resolved = class_codes(entry, tables)
            start, end = validate.expected_plan_period(probe, found, frequency)
            item_id = found["item_ids"][0]
            plans.append({"label": entry[0], "table_id": entry[4], "table_name": found["table_name"],
                          "org_id": "301", "item_id": item_id, "classifications": resolved["codes"],
                          "classification_labels": resolved["labels"], "frequency": frequency,
                          "period_start": start, "period_end": end,
                          "exact_params": {"method": "getList", "format": "json", "jsonVD": "Y", "smblChk": "Y",
                                           "orgId": "301", "tblId": entry[4], "itmId": item_id, "prdSe": frequency,
                                           "startPrdDe": start, "endPrdDe": end, **resolved["codes"]}})
            names[entry[4]] = found["table_name"]
            items[entry[4]] = item_id
        ids = sorted(names)
        workflow = {
            "query_interpretation": interpretation,
            "table_discovery": {"status": "matched", "expected_table_ids": ids, "selected_table_ids": ids,
                                "table_names": names, "unmatched_concepts": []},
            "item_selection": {"item_by_table": items, "matching": "exact_item_code_by_table"},
            "classification_and_plan": {"series": plans,
                                        "matching": "exact_series_identity_set_with_period_and_frequency",
                                        "execution": "not_run"},
            "resolution": {"agent_status": "resolved", "api_status": "need_period",
                           "clarification_required": False, "table_count": len(names),
                           "series_count": len(plans)},
            "post_discovery": {"response_status": "need_period",
                               "reason": "period_missing" if period is None else "execution_deferred",
                               "period_selection_required": period is None, "text_period": period_gold,
                               "execution": False}}
    elif spec["status"] == "no_match":
        workflow = {
            "query_interpretation": interpretation,
            "table_discovery": {"status": "no_match", "expected_table_ids": [], "selected_table_ids": [],
                                "table_names": {}, "unmatched_concepts": spec["unmatched"]},
            "item_selection": {"item_by_table": {}, "matching": "exact_item_code_by_table"},
            "classification_and_plan": {"series": [],
                                        "matching": "exact_series_identity_set_with_period_and_frequency",
                                        "execution": "not_run"},
            "resolution": {"agent_status": "no_match", "api_status": "no_match",
                           "clarification_required": False, "table_count": 0, "series_count": 0,
                           "no_match_reason": spec["no_match_reason"]},
            "post_discovery": {"response_status": "no_match", "reason": "catalog_cannot_cover_request",
                               "execution": False}}
    else:
        group = next((item for item in CATALOG_GROUPS if item["id"] == spec["clarification_group"]), None)
        if group is None:
            raise SystemExit(f"{case_id}: unknown clarification group")
        workflow = {
            "query_interpretation": interpretation,
            "table_discovery": {"status": "clarification_pending", "expected_table_ids": [],
                                "selected_table_ids": [], "table_names": {}, "unmatched_concepts": []},
            "item_selection": {"item_by_table": {}, "matching": "exact_item_code_by_table"},
            "classification_and_plan": {"series": [],
                                        "matching": "exact_series_identity_set_with_period_and_frequency",
                                        "execution": "not_run"},
            "resolution": {"agent_status": "need_clarification", "api_status": "need_clarification",
                           "clarification_required": True, "table_count": 0, "series_count": 0,
                           "clarification": {"id": group["id"], "question": group["question"],
                                             "options": group["options"]}},
            "post_discovery": {"response_status": "need_clarification",
                               "reason": "semantic_scope_ambiguous", "execution": False}}

    return {"id": case_id, "schema_version": SCHEMA, "split": "dev", "topic": spec["topic"],
            "query": spec["query"], "reference_date": REFERENCE_DATE, "workflow_gold": workflow,
            "evidence": {"catalog_path": "src/agent/stat_dictionary/stat_language_dictionary.json",
                         "catalog_sha256": catalog_sha,
                         "gold_basis": "public_BOK_KOSIS_catalog_metadata_and_local_runtime_contract"},
            "research_references": references(spec, index),
            "review": {"ai_assisted": True, "human_approved": False, "status": "draft"},
            "excluded_from_scoring": EXCLUDED}


CATALOG_GROUPS: list[dict] = []


def repair_legacy_case(case: dict, tables: dict[str, dict]) -> list[dict]:
    """v2 원본은 카탈로그 결함 시절의 코드를 담고 있다. 이름(의도)은 두고 코드만 교정한다."""
    repairs = []
    for plan in case["workflow_gold"]["classification_and_plan"]["series"]:
        dimensions = {dimension["api_param"]: dimension
                      for dimension in tables[plan["table_id"]].get("dimensions", [])}
        for param, label in (plan["classification_labels"] or {}).items():
            dimension = dimensions.get(param)
            if dimension is None:
                continue
            found = next((value for value in dimension["values"] if value["value_name"] == label), None)
            if found is None:
                raise SystemExit(f"{case['id']}: {param} 이름 {label!r}을(를) 카탈로그에서 찾지 못함")
            if found["value_id"] != plan["classifications"][param]:
                repairs.append({"table_id": plan["table_id"], "param": param, "label": label,
                                "from": plan["classifications"][param], "to": found["value_id"]})
                plan["classifications"][param] = found["value_id"]
                plan["exact_params"][param] = found["value_id"]
    if repairs:
        case["legacy_value_repair"] = repairs
    return repairs


def summarize_markdown(cases: list[dict]) -> str:
    lines = ["# 기자 질의 통계표 탐색 골든셋 v2.1 (200문항)", "",
             "v2의 30문항을 그대로 두고 단계별 정답 형식을 유지하며 증강한 공개 개발용 골든셋입니다.",
             "research 보고서 그림·표는 화제 출처일 뿐이며 정답 근거는 카탈로그 메타데이터입니다.", "",
             "| ID | 주제 | 상태 | 질문 | 정답 표 | 계열 |", "|---|---|---|---|---|---:|"]
    for case in cases:
        gold = case["workflow_gold"]
        tables = ", ".join(sorted({plan["table_id"] for plan in gold["classification_and_plan"]["series"]})) or "-"
        lines.append(f"| {case['id']} | {case['topic']} | {gold['resolution']['agent_status']} | "
                     f"{case['query']} | {tables} | {gold['resolution']['series_count']} |")
    lines.append("")
    return "\n".join(lines)


def build() -> dict:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8-sig"))
    CATALOG_GROUPS[:] = catalog["clarification_groups"]
    SPECS = load_specs()
    tables = {table_["table_id"]: table_ for table_ in catalog["tables"]}
    index = research_index()
    legacy = [json.loads(line) for line in (V2 / "statbridge-reporter30.jsonl")
              .read_text(encoding="utf-8").splitlines() if line]
    legacy_repairs = [entry for case in legacy for entry in repair_legacy_case(case, tables)]
    legacy_evidence = {case["evidence"]["catalog_sha256"] for case in legacy}
    if len(legacy_evidence) != 1:
        raise SystemExit("legacy cases disagree on their recorded catalog hash")
    cases = legacy + [build_case(spec, tables, index) for spec in SPECS]
    gold_path = DATASET / "statbridge-reporter200.jsonl"
    gold_path.write_text("".join(json.dumps(case, ensure_ascii=False, separators=(",", ":")) + "\n"
                                 for case in cases), encoding="utf-8")
    (DATASET / "statbridge-reporter200.md").write_text(summarize_markdown(cases), encoding="utf-8")
    summary = validate.validate_cases(cases, catalog, len(cases))
    validate.validate_legacy_preservation(cases)
    manifest = {
        "dataset": "reporter-table-discovery-200",
        "version": "v2.1",
        "schema_version": SCHEMA,
        "created_at": REFERENCE_DATE,
        "review": {"human_approved": False, "ai_assisted": True},
        "counts": summary,
        "dataset_sha256": validate.text_sha256(gold_path),
        "catalog_path": "src/agent/stat_dictionary/stat_language_dictionary.json",
        "catalog_sha256": validate.text_sha256(CATALOG),
        "source_dataset": "eval/reporter-table-discovery-30/v2/statbridge-reporter30.jsonl",
        "source_dataset_sha256": validate.text_sha256(V2 / "statbridge-reporter30.jsonl"),
        "research_sources": sorted({ref["path"] for case in cases for ref in case.get("research_references") or []}),
        "legacy_catalog_sha256": legacy_evidence.pop(),
        "legacy_value_repair": {"count": len(legacy_repairs), "entries": legacy_repairs,
                                "reason": "v2 원본이 카탈로그 코드-이름 결함 시절의 코드를 담고 있어 이름(의도)은 두고 코드만 교정했다."},
        "benchmark_scope": "query_interpretation_table_item_classification_api_plan_and_resolution",
        "numeric_gold": "not_created",
        "source_boundary": "KOSIS Korea Bank of Korea only",
        "sha256_normalization": "LF",
        "scoring_policy_sha256": runner.policy_sha256(),
        "period_policy": "Explicit periods are converted to inclusive KOSIS periods; missing periods retain the runtime plan but expect the API need_period follow-up.",
    }
    (DATASET / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build()["counts"], ensure_ascii=False))
