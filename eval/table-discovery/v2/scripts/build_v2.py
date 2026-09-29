#!/usr/bin/env python3
"""Build the v2 review draft from v1 seeds and the current frozen catalog snapshot."""
from __future__ import annotations

import csv
import json
import re
import argparse
import shutil
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
SOURCE = ROOT.parent / "v1/cases.jsonl"
CATALOG_PATH = REPO / "data/kosis/hankook_tables.json"
SUMMARY_PATH = REPO / "data/statbridge_mcp_server/data_full/collection/table_summary.csv"
API_PATH = ROOT / "kosis_metadata_export.json"
REFERENCE_DATE = "2026-09-23"

NO_MATCH_TERMS = {
    "GS-0116": ["기준금리", "통화정책", "금리"],
    "GS-0117": ["영업이익", "기업경영", "기업"],
    "GS-0118": ["코로나", "확진", "감염병", "질병"],
    "GS-0119": ["소비자물가", "물가지수", "물가"],
    "GS-0120": ["실업률", "고용률", "고용"],
    "GS-0121": ["코스피", "주가", "주식", "증권"],
    "GS-0122": ["수출액", "수출", "무역"],
    "GS-0123": ["아파트", "주택가격", "주택", "부동산"],
    "GS-0124": ["주가", "주식", "증권"],
    "GS-0125": ["인구이동", "인구", "가구"],
    "GS-0126": ["실업률", "고용률", "고용", "지역별"],
    "GS-0127": ["확진자", "감염병", "질병"],
    "GS-0128": ["미국", "기준금리", "금리", "해외"],
    "GS-0129": ["환율", "원달러", "미국달러"],
    "GS-0130": ["강수량", "기상", "날씨", "지역별"],
}
TOOLS = {
    "search_tables": {"status": "implemented", "required": ["nl_query"]},
    "get_meta": {"status": "implemented", "required": ["table_id"]},
    "fetch_data": {"status": "implemented", "required": ["table_id"]},
    "merge_datasets": {"status": "planned", "required": ["datasets"]},
    "render_chart": {"status": "planned", "required": ["data", "chart_type"]},
}
DECISIONS = ["승인", "수정", "보류", "제외"]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")


def safe_json(value: str, fallback):
    try:
        return json.loads(value) if value else fallback
    except (TypeError, json.JSONDecodeError):
        return fallback


def clean(value):
    if isinstance(value, str) and value.strip().lower() in {"n/a", "na", "unspecified", "from_context_or_followup", "not_recorded_in_local_csv"}:
        return None
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value if v is not None and v != "N/A"]
    return value


def last_user_text(conversation: list[dict]) -> str:
    return next((m["text"] for m in reversed(conversation) if m["role"] == "user"), "")


def relative_time(text: str):
    match = re.search(r"최근\s*(\d+)\s*년", text)
    if match:
        return {"type": "relative", "amount": int(match.group(1)), "unit": "year", "reference_date": REFERENCE_DATE, "boundary_policy": "calendar_window; resolve period end from latest available observation on or before reference_date", "source_text": match.group(0)}
    match = re.search(r"최근\s*(\d+)\s*개월", text)
    if match:
        return {"type": "relative", "amount": int(match.group(1)), "unit": "month", "reference_date": REFERENCE_DATE, "boundary_policy": "calendar_window; resolve period end from latest available observation on or before reference_date", "source_text": match.group(0)}
    return None


def normalize_time(value, query: str):
    rel = relative_time(query)
    if rel:
        return rel
    value = clean(value)
    if value is None:
        return None
    text = str(value)
    if re.fullmatch(r"\d{4}(?:\d{2})?", text):
        return {"type": "absolute_start", "start_period": text, "end_period": None, "source_text": text, "verification": "review_required; confirm source query meaning"}
    return {"type": "unresolved", "source_text": text, "verification": "review_required"}


def load_sources():
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig"))
    with SUMMARY_PATH.open(encoding="utf-8-sig", newline="") as stream:
        summary = {row["tbl_id"]: row for row in csv.DictReader(stream)}
    if not API_PATH.exists():
        source_api = REPO / "golden-set/kosis_metadata_export.json"
        if source_api.exists(): shutil.copyfile(source_api, API_PATH)
    api = json.loads(API_PATH.read_text(encoding="utf-8")) if API_PATH.exists() else {"tables": {}, "exported_at_utc": None, "table_count": 0, "failure_count": 0}
    return catalog, summary, api


def table_text(table: dict, summary: dict) -> tuple[str, str]:
    row = summary.get(table["tbl_id"], {})
    title_path = " ".join([table.get("tbl_nm", ""), *(table.get("path") or [])])
    detail = " ".join(str(row.get(k, "")) for k in ("category", "items", "units", "cls_axes"))
    return title_path, detail


def propose_catalog_challengers(case_id: str, catalog: dict, summary: dict) -> list[dict]:
    terms = NO_MATCH_TERMS.get(case_id, [])
    ranked = []
    for table in catalog["tables"]:
        title_path, detail = table_text(table, summary)
        norm_title = title_path.replace(" ", "").lower()
        norm_all = (title_path + " " + detail).replace(" ", "").lower()
        hits_title = [term for term in terms if term.replace(" ", "").lower() in norm_title]
        hits_detail = [term for term in terms if term.replace(" ", "").lower() in norm_all]
        score = sum(min(4, len(term)) * (2 if term in hits_title else 1) for term in set(hits_detail))
        if score:
            ranked.append((score, table["tbl_id"], table, hits_detail))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [{"table_id": t["tbl_id"], "table_name": t["tbl_nm"], "role": "catalog_challenger_proposal", "proposed_relatedness": 1 if score < 8 else 2, "assessment_status": "review_required", "selection_basis": {"method": "literal substring overlap in table title/path/local summary", "matched_terms": hits, "score": score, "semantic_relevance_verified": False}} for score, _, t, hits in ranked[:3]]


def local_metadata(table: dict, summary: dict, api: dict, fallback: dict | None = None) -> dict:
    row = summary.get(table["tbl_id"], {})
    live = api.get("tables", {}).get(table["tbl_id"], {})
    fallback = fallback or {}
    unit_raw = row.get("units", "").strip()
    unit = safe_json(unit_raw, unit_raw if unit_raw else fallback.get("unit"))
    if isinstance(unit, str) and unit.upper().startswith("NOT_RECORDED"):
        unit = None
    fallback_unit = fallback.get("unit")
    if isinstance(fallback_unit, str) and fallback_unit.upper().startswith("NOT_RECORDED"):
        fallback_unit = None
    if unit is None:
        unit = fallback_unit
    freq = [x.strip() for x in row.get("freq", "").split(",") if x.strip()]
    if freq:
        freq = [{"월": "M", "분기": "Q", "년": "Y", "연": "Y", "반기": "S", "일": "D"}.get(x, x) for x in freq]
    local_axes = [x for x in row.get("cls_axes", "").split("|") if x]
    live_details = {"status": live.get("status", fallback.get("kosis_live_status", "not_queried")), "checked_at_utc": api.get("exported_at_utc"), "comments_checked": False} if live.get("status") == "ok" else None
    return {
        "catalog_path": table.get("path", []),
        "frequency": freq or fallback.get("frequency"),
        "unit": unit,
        "period_start": row.get("start") or fallback.get("period_start"),
        "period_end": row.get("end") or fallback.get("period_end"),
        "item_count": int(row["items"]) if row.get("items", "").isdigit() else fallback.get("item_count"),
        "items": fallback.get("items") or None,
        "classification_axes": fallback.get("classification_axes") or ([{"name": x, "examples": None, "source": "local_table_summary_axis_name_only"} for x in local_axes] or None),
        "comments": None,
        "metadata_source_status": {
            "catalog": "verified_snapshot",
            "local_summary": "verified_snapshot" if row else "unavailable",
            "unit": "not_recorded_in_local_summary" if unit is None else "local_summary",
            "kosis_api": live.get("status", "not_queried"),
            "comments_and_series_definition": "not_checked_by_getMeta_PRD_ITM",
        },
        "kosis_live_metadata": live_details,
        "snapshot_csv": f"data/statbridge_mcp_server/data_full/tables/{table['tbl_id']}.csv" if (REPO / f"data/statbridge_mcp_server/data_full/tables/{table['tbl_id']}.csv").exists() else None,
    }


def normalize_candidate(candidate: dict, table_map: dict, summary: dict, api: dict, *, role="v1_candidate_proposal") -> dict:
    table = table_map.get(candidate["table_id"], {"tbl_id": candidate["table_id"], "tbl_nm": candidate.get("table_name", ""), "path": candidate.get("metadata", {}).get("catalog_path", [])})
    return {
        "table_id": candidate["table_id"],
        "table_name": table.get("tbl_nm", candidate.get("table_name", "")),
        "role": role,
        "proposed_relevance": candidate.get("relatedness"),
        "assessment_status": "review_required",
        "relevance_rationale": candidate.get("rationale", "Imported as an unapproved v1 candidate proposal."),
        "metadata": local_metadata(table, summary, api, candidate.get("metadata", {})),
    }


def build_case(source: dict, catalog: dict, summary: dict, api: dict) -> dict:
    old = source["gold"]
    conversation = source["conversation"]
    query = last_user_text(conversation)
    slots = {k: clean(v) for k, v in old["interpretation"]["slots"].items()}
    slots["time_range"] = normalize_time(old["interpretation"]["slots"].get("time_range"), " ".join(m["text"] for m in conversation))
    unspecified = sorted(k for k, v in slots.items() if v is None)
    prior = conversation[:-1] if source["primary_type"] == "conversation_followup" else []
    overridden = {}
    last = query
    for pattern, field, value in ((r"분기별", "frequency", "Q"), (r"월별", "frequency", "M"), (r"연간|연도별", "frequency", "Y"), (r"수입", "series", "import"), (r"수출", "series", "export")):
        if re.search(pattern, last): overridden[field] = value
    contextual = {k: v for k, v in slots.items() if v is not None and k not in overridden and k not in {"metric_raw", "metrics_raw", "follow_up_raw"}}
    must_preserve = sorted(contextual) if prior else []
    input_label = {
        "original_query": query,
        "prior_turns": prior,
        "required_context": contextual,
        "overridden_context": overridden,
        "must_preserve_context_fields": must_preserve,
        "must_overwrite_context_fields": sorted(overridden),
        "context_extraction_status": "review_required" if source["primary_type"] == "conversation_followup" else "not_applicable",
    }
    old_candidates = old["retrieval"]["candidates"]
    candidate_labels = [normalize_candidate(c, {t["tbl_id"]: t for t in catalog["tables"]}, summary, api) for c in old_candidates]
    if source["primary_type"] == "no_match_out_of_scope":
        seen = {c["table_id"] for c in candidate_labels}
        for challenger in propose_catalog_challengers(source["case_id"], catalog, summary):
            if challenger["table_id"] in seen: continue
            raw = {**challenger, "relatedness": challenger["proposed_relatedness"]}
            candidate_labels.append(normalize_candidate(raw, {t["tbl_id"]: t for t in catalog["tables"]}, summary, api, role="catalog_challenger_proposal"))
    clarification = old["clarification"]
    expected_question = clarification.get("expected") == "ASK_USER"
    branches = []
    raw_branches = clarification.get("answer_branches", [])
    if not isinstance(raw_branches, list): raw_branches = []
    for branch in raw_branches:
        next_action = branch.get("expected_next_action")
        ready = "search_tables" in next_action if isinstance(next_action, list) else isinstance(next_action, str) and "search_tables" in next_action
        branches.append({
            "user_answer": branch.get("user_answer", ""),
            "expected_slot_update": clean(branch.get("expected_slot_update", {})) or {},
            "expected_after_answer": {"ambiguity_resolved": ready and "ask again" not in str(next_action).lower(), "query_plan_ready": ready and "ask again" not in str(next_action).lower(), "next_action": "SEARCH_CATALOG" if ready else "ASK_AGAIN_OR_WAIT", "remaining_question_criteria": "review_required" if not ready else []},
        })
    criteria = clarification.get("acceptable_question_criteria")
    if isinstance(criteria, str): criteria = [criteria] if clean(criteria) else []
    must_not_ask = sorted(k for k, v in slots.items() if v is not None and k not in {"metric_raw", "metrics_raw", "follow_up_raw"})
    expected_status = old["retrieval"]["expected_status"]
    if expected_question:
        strategy_type = "wait_for_clarification"
        required_tools = []
        action = "WAIT_FOR_USER"
    elif expected_status == "NO_MATCH":
        strategy_type = "catalog_scope_search"
        required_tools = ["search_tables"]
        action = "SEARCH_AND_DOCUMENT_SCOPE"
    elif source["primary_type"] == "multi_indicator_table":
        strategy_type = "multi_table_compare"
        required_tools = ["search_tables", "get_meta"]
        action = "SEARCH_AND_VERIFY_CANDIDATES"
    else:
        strategy_type = "single_table_lookup"
        required_tools = ["search_tables", "get_meta"]
        action = "SEARCH_AND_VERIFY_CANDIDATES"
    search_candidate_ids = [c["table_id"] for c in candidate_labels]
    must_checks = ["catalog_version", "frequency", "unit", "items_and_classifications", "period_coverage", "comments_or_series_definition"]
    if source["primary_type"] == "multi_indicator_table": must_checks += ["frequency_compatibility", "unit_compatibility", "period_overlap"]
    acceptable_plans = [{"steps": required_tools[:], "note": "Draft plan template; reviewer must confirm ordering and necessity."}] if required_tools else []
    source_plan = old["tool_plan"]
    tool_plan = {
        "expected_next_action": action,
        "allowed_tools": [name for name, t in TOOLS.items() if t["status"] == "implemented"],
        "conditionally_allowed_tools": ["fetch_data"],
        "planned_tools": [name for name, t in TOOLS.items() if t["status"] == "planned"],
        "required_tools": required_tools,
        "forbidden_tools": ["unknown_tool", "fetch_data_before_clarification", "fetch_data_before_get_meta"],
        "required_arguments_by_tool": {name: TOOLS[name]["required"] for name in TOOLS},
        "acceptable_plans": acceptable_plans,
        "required_order": [["search_tables", "get_meta"], ["get_meta", "fetch_data"]],
        "validation_conditions": must_checks + ["all parameters supported by tool schema", "no tool call before required clarification", "fetch_data only after table, item/classification and period selection is validated", "planned tools are not executable"],
        "source_v1_plan": source_plan,
        "review_status": "review_required",
    }
    retrieval_candidates = []
    for candidate in candidate_labels:
        retrieval_candidates.append({k: candidate[k] for k in ("table_id", "table_name", "role", "proposed_relevance", "assessment_status", "relevance_rationale", "metadata")})
    no_match = expected_status == "NO_MATCH"
    retrieval = {
        "expected_status": expected_status,
        "status_is_proposal": True,
        "candidates": retrieval_candidates,
        "acceptable_table_ids": clean(old["retrieval"].get("acceptable_table_ids", [])) or [],
        "no_match_reason": "NOT_ESTABLISHED; catalog challenger proposals require human check against the entire frozen project catalog." if no_match else clean(old["retrieval"].get("no_match_reason")),
        "search_scope": {"catalog_version": source["catalog_version"], "table_count": 349, "scope": "frozen Korean Bank project catalog snapshot", "query_terms_checked": NO_MATCH_TERMS.get(source["case_id"], []), "scan_method": "literal substring scan of table title, catalog path, summary category, unit, and classification-axis names; item CSV contents were not scanned", "candidate_proposals_returned": len([x for x in candidate_labels if x["role"] == "catalog_challenger_proposal"]), "live_all_KOSIS_catalog_search": False, "verification_status": "review_required", "out_of_scope_vs_catalog_search_miss": "unresolved_until_human_review"},
        "acceptable_answer_range": {"table_ids": clean(old["retrieval"].get("acceptable_table_ids", [])) or [], "allow_multiple": source["primary_type"] == "multi_indicator_table", "no_match_allowed_only_after_scope_check": True},
    }
    plan_validation = {
        "expected_result": "WAIT_FOR_USER" if expected_question else "PASS_AFTER_SCHEMA_AND_ORDER_CHECKS",
        "must_reject": ["unknown tool", "missing required argument", "unexpected argument", "invalid tool order", "retrieval before clarification"],
        "must_check": ["tool name exists in frozen contract", "required arguments present", "additionalProperties false respected", "metadata checked before data fetch", "clarification gate respected"],
        "case_specific_preconditions": ["user clarification received"] if expected_question else [],
        "fixture_ids": [],
        "review_status": "review_required",
    }
    handoff_ready = not expected_question
    handoff = {
        "target": "table_retrieval_agent",
        "expected_status": "ready_for_catalog_search" if handoff_ready else "blocked_waiting_for_user",
        "required_fields": ["original_query", "prior_turns", "resolved_slots", "unresolved_slots", "concept_candidates", "catalog_version", "plan_status"],
        "expected_payload": {"original_query": query, "prior_turns": prior, "resolved_slots": {k: v for k, v in slots.items() if v is not None}, "unresolved_slots": unspecified, "concept_candidates": clean(old["concepts"].get("acceptable_candidates", [])) or [], "catalog_version": source["catalog_version"], "plan_status": "ready" if handoff_ready else "waiting_for_user"},
        "review_status": "review_required",
    }
    evidence = list(source["annotation"].get("evidence", []))
    return {
        "case_id": source["case_id"],
        "split": source["split"],
        "primary_type": source["primary_type"],
        "tags": source["tags"],
        "leakage_group": source.get("leakage_group", source["case_id"]),
        "catalog_version": source["catalog_version"],
        "conversation": conversation,
        "gold": {
            "input": input_label,
            "interpretation": {"acceptable_intents": old["interpretation"].get("acceptable_intents", []), "slots": slots, "unspecified_slots": unspecified, "slot_provenance": {k: "query_or_context_candidate_from_v1; verify against original conversation" for k in slots}, "time_reference_policy": {"reference_date": REFERENCE_DATE, "relative_period_resolution": "Preserve the relative expression; resolve the latest available period from table metadata at or before this date."}},
            "concepts": {"source_query_text": query, "acceptable_candidates": clean(old["concepts"].get("acceptable_candidates", [])) or [], "alternative_candidates": [], "candidate_evidence": source["annotation"].get("evidence", []), "must_preserve_ambiguity": bool(old["concepts"].get("must_preserve_ambiguity")), "candidate_status": "review_required", "evidence_requirements": ["connect every accepted concept to catalog path and KOSIS item/classification metadata", "do not choose a unique alias mapping without evidence"]},
            "ambiguity": {"present": bool(old["ambiguity"].get("present")), "conflicts": clean(old["ambiguity"].get("conflicts")) or [], "must_not_ask": must_not_ask, "review_status": "review_required"},
            "clarification": {"expected": "ASK_USER" if expected_question else "PROCEED", "must_resolve": clean(clarification.get("must_resolve", [])) or [], "acceptable_question_criteria": criteria or [], "answer_branches": branches, "review_status": "review_required"},
            "data_strategy": {"type": strategy_type, "required_checks": must_checks, "merge_allowed": source["primary_type"] == "multi_indicator_table", "calculation_required": False, "source_v1_proposal": source["gold"].get("data_strategy"), "review_status": "review_required"},
            "tool_plan": tool_plan,
            "plan_validation": plan_validation,
            "retrieval": retrieval,
            "handoff": handoff,
        },
        "annotation": {"evidence": evidence, "review_status": "review_required", "reviewer": None, "reviewed_at": None, "notes": "V2 structural migration; semantic labels remain unreviewed."},
        "review": {"decision": None, "approved_table_ids": [], "edited_gold": None, "reviewer": None, "reviewed_at": None, "review_notes": None},
        "provenance": {"source_case_id": source["case_id"], "source_dataset": "golden-set v1 draft", "source_review_status": source["annotation"]["review_status"], "migration_status": "automated_structure_migration; semantic correctness not certified"},
    }


def build_plan_validation_fixtures(cases: list[dict]) -> list[dict]:
    seeds = [
        ("PV-0001", "valid_search_and_meta", "PASS", [], [{"tool": "search_tables", "arguments": {"nl_query": "물가"}}, {"tool": "get_meta", "arguments": {"table_id": "DT_404Y014"}}]),
        ("PV-0002", "clarification_wait", "WAIT_FOR_USER", [], []),
        ("PV-0003", "unknown_tool", "REJECT", ["UNKNOWN_TOOL"], [{"tool": "search_table", "arguments": {"nl_query": "금리"}}]),
        ("PV-0004", "missing_required_argument", "REJECT", ["MISSING_REQUIRED_ARGUMENT"], [{"tool": "search_tables", "arguments": {}}]),
        ("PV-0005", "invalid_order", "REJECT", ["INVALID_TOOL_ORDER"], [{"tool": "get_meta", "arguments": {"table_id": "DT_404Y014"}}, {"tool": "search_tables", "arguments": {"nl_query": "물가"}}]),
        ("PV-0006", "premature_fetch", "REJECT", ["MISSING_METADATA_CHECK"], [{"tool": "search_tables", "arguments": {"nl_query": "물가"}}, {"tool": "fetch_data", "arguments": {"table_id": "DT_404Y014"}}]),
        ("PV-0007", "premature_retrieval", "REJECT", ["CLARIFICATION_REQUIRED"], [{"tool": "search_tables", "arguments": {"nl_query": "금리"}}]),
        ("PV-0008", "unexpected_argument", "REJECT", ["UNEXPECTED_ARGUMENT"], [{"tool": "search_tables", "arguments": {"nl_query": "금리", "not_in_schema": True}}]),
        ("PV-0009", "planned_tool_unavailable", "REJECT", ["TOOL_NOT_IMPLEMENTED"], [{"tool": "merge_datasets", "arguments": {"datasets": []}}]),
        ("PV-0010", "valid_search_only", "PASS", [], [{"tool": "search_tables", "arguments": {"nl_query": "기준금리", "top_k": 5}}]),
        ("PV-0011", "valid_metadata_only_after_prior_search", "PASS", [], [{"tool": "search_tables", "arguments": {"nl_query": "실업률"}}, {"tool": "get_meta", "arguments": {"table_id": "DT_404Y014"}}]),
        ("PV-0012", "clarification_then_search", "PASS", [], [{"tool": "search_tables", "arguments": {"nl_query": "한국은행 기준금리"}}]),
    ]
    by_id = {c["case_id"]: c for c in cases}
    rows = []
    for i, (fid, kind, expected, errors, plan) in enumerate(seeds):
        parent = cases[i % len(cases)]
        parent_case = by_id["GS-0056"] if kind in {"clarification_wait", "premature_retrieval", "clarification_then_search"} else parent
        rows.append({"fixture_id": fid, "split": parent_case["split"], "parent_case_id": parent_case["case_id"], "fixture_type": kind, "plan": plan, "expected_validation": expected, "expected_error_codes": errors, "review_status": "review_required", "review_notes": None})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="overwrite generated v2 draft files")
    args = parser.parse_args()
    if (ROOT / "cases.jsonl").exists() and not args.force:
        raise SystemExit("v2 draft already exists; refusing to overwrite without --force")
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "scripts").mkdir(exist_ok=True)
    catalog, summary, api = load_sources()
    old = read_jsonl(SOURCE)
    cases = [build_case(c, catalog, summary, api) for c in old]
    write_jsonl(ROOT / "cases.jsonl", cases)
    write_jsonl(ROOT / "plan_validation_cases.jsonl", build_plan_validation_fixtures(cases))
    print(f"built {len(cases)} draft cases and 12 draft plan-validation fixtures")
    print("status counts", dict(Counter(c["annotation"]["review_status"] for c in cases)))
    print("unique candidate tables", len({x["table_id"] for c in cases for x in c["gold"]["retrieval"]["candidates"]}))


if __name__ == "__main__":
    main()
