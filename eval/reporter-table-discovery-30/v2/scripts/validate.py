"""Validate stagewise public table-discovery gold without calling external APIs."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATASET = Path(__file__).resolve().parents[1]
STATUSES = {"resolved", "need_clarification", "no_match"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def text_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def normalized_period(raw: str, frequency: str, *, end: bool = False) -> str:
    digits = re.sub(r"[^0-9Qq]", "", str(raw or ""))
    if frequency == "M":
        if len(digits) >= 6:
            return digits[:6]
        if len(digits) == 4:
            return digits + ("12" if end else "01")
    elif frequency == "Q":
        match = re.fullmatch(r"(\d{4})[Qq]?0?([1-4])", digits)
        if match:
            return f"{match.group(1)}{int(match.group(2)):02d}"
        if len(digits) == 6 and digits[-2:] in {"01", "02", "03", "04"}:
            return digits
        if len(digits) == 4:
            return digits + ("04" if end else "01")
    elif frequency in {"Y", "A"}:
        return digits[:4] if len(digits) >= 4 else str(raw)
    return str(raw)


def subtract_months(value: str, count: int) -> str:
    year, month = int(value[:4]), int(value[4:6])
    index = year * 12 + month - 1 - count
    new_year, month_zero = divmod(index, 12)
    return f"{new_year:04d}{month_zero + 1:02d}"


def subtract_quarters(value: str, count: int) -> str:
    year, quarter = int(value[:4]), int(value[4:6])
    index = year * 4 + quarter - 1 - count
    new_year, quarter_zero = divmod(index, 4)
    return f"{new_year:04d}{quarter_zero + 1:02d}"


def expected_plan_period(case: dict, table: dict, frequency: str) -> tuple[str, str]:
    period = case["workflow_gold"]["query_interpretation"]["period"]
    if period:
        years = [int(x) for x in re.findall(r"((?:19|20)\d{2})\s*년?", case["query"])]
        require(len(years) >= 2, f"{case['id']}: explicit period years missing from query")
        start_year, end_year = min(years), max(years)
        if frequency == "M":
            return f"{start_year}01", f"{end_year}12"
        if frequency == "Q":
            return f"{start_year}01", f"{end_year}04"
        return str(start_year), str(end_year)

    observed_start = normalized_period(str(table.get("period_start_observed") or ""), frequency)
    observed_end = normalized_period(str(table.get("period_end_observed") or ""), frequency, end=True)
    if frequency == "M" and observed_end:
        return subtract_months(observed_end, 11), observed_end
    if frequency == "Q" and observed_end:
        return subtract_quarters(observed_end, 7), observed_end
    if frequency in {"Y", "A"} and observed_end:
        start = max(int(observed_start[:4] or observed_end[:4]), int(observed_end[:4]) - 4)
        return str(start), observed_end[:4]
    return observed_start, observed_end


def validate_cases(cases: list[dict], catalog: dict) -> dict:
    tables = {str(table["table_id"]): table for table in catalog["tables"]}
    require(len(cases) == 30, "Expected exactly 30 cases")
    require(len({case["id"] for case in cases}) == 30, "Duplicate case ID")
    require(len({case["query"] for case in cases}) == 30, "Duplicate natural-language query")
    status_counts = Counter()
    all_table_ids: set[str] = set()
    series_count = 0

    for case in cases:
        prefix = case["id"]
        require(case.get("schema_version") == "reporter30-discovery-2", f"{prefix}: schema version")
        require(case.get("split") == "dev", f"{prefix}: public dev set only")
        require(case.get("review", {}).get("ai_assisted") is True and
                case["review"].get("human_approved") is False, f"{prefix}: approval state")
        require(case.get("query", "").strip(), f"{prefix}: empty query")

        workflow = case.get("workflow_gold") or {}
        interpretation = workflow.get("query_interpretation") or {}
        discovery = workflow.get("table_discovery") or {}
        item_selection = workflow.get("item_selection") or {}
        plan = workflow.get("classification_and_plan") or {}
        resolution = workflow.get("resolution") or {}
        post = workflow.get("post_discovery") or {}
        status = resolution.get("agent_status")
        require(status in STATUSES, f"{prefix}: unknown agent status")
        status_counts[status] += 1

        meanings = interpretation.get("series") or []
        plans = plan.get("series") or []
        selected_ids = set(discovery.get("selected_table_ids") or [])
        require(set(discovery.get("expected_table_ids") or []) == selected_ids,
                f"{prefix}: expected table set differs from selected gold")
        require(interpretation.get("comparison", {}).get("required") == (len(meanings) > 1),
                f"{prefix}: comparison slot mismatch")

        if status == "need_clarification":
            require(resolution.get("clarification_required") is True, f"{prefix}: clarification flag")
            require(discovery.get("status") == "clarification_pending", f"{prefix}: discovery state")
            require(not selected_ids and not plans and not item_selection.get("item_by_table"),
                    f"{prefix}: selected before clarification")
            clarification = resolution.get("clarification") or {}
            groups = {group["id"]: group for group in catalog.get("clarification_groups", [])}
            group = groups.get(clarification.get("id"))
            require(group is not None, f"{prefix}: unknown clarification group")
            require(clarification.get("question") == group.get("question"),
                    f"{prefix}: clarification question differs from runtime contract")
            expected_options = {option["value"] for option in group.get("options", [])}
            actual_options = {option["value"] for option in clarification.get("options", [])}
            require(actual_options == expected_options, f"{prefix}: clarification options differ from runtime contract")
            require(resolution.get("api_status") == "need_clarification" and
                    post.get("response_status") == "need_clarification", f"{prefix}: API clarification status")
            require(resolution.get("table_count") == 0 and resolution.get("series_count") == 0,
                    f"{prefix}: pending resolution counts")
            continue

        if status == "no_match":
            require(discovery.get("status") == "no_match", f"{prefix}: no_match discovery state")
            require(not selected_ids and not plans and not item_selection.get("item_by_table"),
                    f"{prefix}: no_match contains selected gold")
            require(bool(resolution.get("no_match_reason")), f"{prefix}: missing no_match evidence")
            require(resolution.get("api_status") == "no_match" and
                    post.get("response_status") == "no_match", f"{prefix}: API no_match status")
            require(resolution.get("table_count") == 0 and resolution.get("series_count") == 0,
                    f"{prefix}: no_match counts")
            continue

        require(discovery.get("status") == "matched", f"{prefix}: resolved discovery state")
        require(bool(plans), f"{prefix}: resolved case has no series plan")
        require(len(meanings) == len(plans), f"{prefix}: series count mismatch")
        require({meaning.get("label") for meaning in meanings} == {item.get("label") for item in plans},
                f"{prefix}: interpreted series do not match selected series")
        table_names: dict[str, str] = {}
        expected_items: dict[str, str] = {}
        seen: set[tuple] = set()
        for item in plans:
            table_id = str(item.get("table_id") or "")
            table = tables.get(table_id)
            require(table is not None and str(table.get("org_id")) == "301",
                    f"{prefix}: table missing or outside BOK KOSIS scope")
            require(item.get("table_name") == table.get("table_name"), f"{prefix}: table name mismatch")
            require(item.get("org_id") == "301", f"{prefix}: plan organization")
            require(item.get("item_id") in table.get("item_ids", []), f"{prefix}: invalid item code")
            frequency = item.get("frequency")
            require(frequency == interpretation.get("frequency") == table.get("prd_se"),
                    f"{prefix}: frequency mismatch")

            dimensions = {str(dimension["api_param"]): dimension for dimension in table.get("dimensions", [])}
            classes = item.get("classifications") or {}
            labels = item.get("classification_labels") or {}
            require(set(classes) == set(dimensions), f"{prefix}: missing or extra classification dimension")
            require(set(labels) == set(dimensions), f"{prefix}: classification label dimensions")
            for param, dimension in dimensions.items():
                values = {str(value["value_id"]): str(value["value_name"])
                          for value in dimension.get("values", [])}
                code = str(classes[param])
                require(code in values, f"{prefix}: invalid classification code")
                require(labels[param] == values[code], f"{prefix}: classification label mismatch")

            start, end = expected_plan_period(case, table, frequency)
            require(item.get("period_start") == start and item.get("period_end") == end,
                    f"{prefix}: planned period differs from runtime policy")
            params = item.get("exact_params") or {}
            expected_params = {"method":"getList","format":"json","jsonVD":"Y","smblChk":"Y",
                "orgId":"301","tblId":table_id,"itmId":item["item_id"],"prdSe":frequency,
                "startPrdDe":start,"endPrdDe":end,**classes}
            require(params == expected_params, f"{prefix}: exact KOSIS API parameters mismatch")

            identity = (table_id, item["item_id"], tuple(sorted(classes.items())))
            require(identity not in seen, f"{prefix}: duplicate selected series")
            seen.add(identity)
            table_names[table_id] = str(table["table_name"])
            expected_items[table_id] = str(item["item_id"])
            all_table_ids.add(table_id)
            series_count += 1

        require(selected_ids == set(table_names), f"{prefix}: selected table set mismatch")
        require(discovery.get("table_names") == table_names, f"{prefix}: table-name mapping mismatch")
        require(item_selection.get("item_by_table") == expected_items, f"{prefix}: item-by-table mismatch")
        require(resolution.get("clarification_required") is False, f"{prefix}: unexpected clarification")
        require(resolution.get("table_count") == len(table_names) and
                resolution.get("series_count") == len(plans), f"{prefix}: resolution counts")
        require(resolution.get("api_status") == "need_period" and
                post.get("response_status") == "need_period", f"{prefix}: discovery API boundary")
        require(post.get("execution") is False, f"{prefix}: numeric execution must be excluded")
        period = interpretation.get("period")
        expected_reason = "period_missing" if period is None else "execution_deferred"
        require(post.get("reason") == expected_reason and
                post.get("period_selection_required") is (period is None),
                f"{prefix}: post-discovery period behavior")

    return {"cases":len(cases),"statuses":dict(sorted(status_counts.items())),
            "series":series_count,"tables":len(all_table_ids)}


def main() -> None:
    case_path = DATASET / "statbridge-reporter30.jsonl"
    cases = [json.loads(line) for line in case_path.read_text(encoding="utf-8").splitlines() if line]
    catalog_path = ROOT / "src/agent/stat_dictionary/stat_language_dictionary.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    summary = validate_cases(cases, catalog)
    manifest = json.loads((DATASET / "dataset_manifest.json").read_text(encoding="utf-8"))
    require(summary == manifest.get("counts"), "Manifest counts mismatch")
    require(text_sha256(case_path) == manifest.get("dataset_sha256"), "Dataset SHA256 mismatch")
    require(text_sha256(catalog_path) == manifest.get("catalog_sha256"), "Catalog SHA256 mismatch")
    for case in cases:
        require(case.get("evidence", {}).get("catalog_sha256") == manifest["catalog_sha256"],
                f"{case['id']}: catalog provenance mismatch")
    print("VALIDATION OK " + json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
