"""Validate the public reporter30 draft without invoking models or data APIs."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATASET = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def text_sha256(path: Path) -> str:
    """Hash UTF-8 source bytes with LF line endings on every checkout."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def validate_cases(cases: list[dict], catalog: dict) -> dict:
    tables = {table["table_id"]: table for table in catalog["tables"]}
    require(len(cases) == 30, "Expected 30 cases")
    require(len({case["id"] for case in cases}) == 30, "Duplicate case ID")
    require(len({case["query"] for case in cases}) == 30, "Duplicate query")
    categories = Counter(case["category"] for case in cases)
    require(categories == {"single_series": 8, "same_table_multi_series": 10,
                           "cross_table_multi_series": 12}, "Category counts changed")
    for case in cases:
        prefix = case["id"]
        require(case["schema_version"] == "reporter30-draft-2", f"{prefix}: schema")
        require(case["split"] == "dev", f"{prefix}: public development set only")
        require(not case["review"]["human_approved"], f"{prefix}: draft approval")
        require(not case["downstream_gold"]["end_to_end_complete"], f"{prefix}: E2E claim")
        require(case["query"].startswith("2023년") and "2024년" in case["query"], f"{prefix}: explicit period")
        expected = case["expected_series"]
        require(len(expected) == case["expected_series_count"], f"{prefix}: series count")
        table_ids = {series["table_id"] for series in expected}
        require(set(case["table_ids"]) == table_ids, f"{prefix}: table set")
        category = case["category"]
        require((len(expected) == 1 and len(table_ids) == 1) if category == "single_series"
                else (len(expected) >= 2 and (len(table_ids) == 1 if category == "same_table_multi_series" else len(table_ids) >= 2)),
                f"{prefix}: category/series mismatch")
        workflow = case["workflow_gold"]
        slots = workflow["query_interpretation"]
        require(slots["period"] == {"start": "2023-01-01", "end": "2024-12-31", "inclusive": True, "source": "explicit"}, f"{prefix}: period slots")
        require(len(slots["series"]) == len(expected), f"{prefix}: semantic slot count")
        require(slots["comparison"]["required"] == (len(expected) > 1), f"{prefix}: comparison")
        require(set(workflow["table_discovery"]["table_ids"]) == table_ids, f"{prefix}: workflow table set")
        require(set(workflow["item_selection"]["item_by_table"]) == table_ids, f"{prefix}: item table set")
        plans = workflow["classification_and_plan"]["series"]
        require(len(plans) == len(expected), f"{prefix}: missing lookup series")
        require(workflow["resolution"] == {"status": "resolved", "clarification_required": False,
                                          "table_count": len(table_ids), "series_count": len(expected)}, f"{prefix}: resolution")
        seen = set()
        for index, (series, meaning, plan) in enumerate(zip(expected, slots["series"], plans), 1):
            table = tables.get(series["table_id"])
            require(table is not None, f"{prefix}: unknown table")
            require(series["table_name"] == table["table_name"], f"{prefix}: table name")
            require(series["org_id"] == table["org_id"], f"{prefix}: organization")
            require(series["item_id"] in table["item_ids"], f"{prefix}: item code")
            require(workflow["item_selection"]["item_by_table"][series["table_id"]] == series["item_id"], f"{prefix}: workflow item")
            frequency = series["frequency"]
            require(frequency == slots["frequency"] == table["prd_se"], f"{prefix}: frequency")
            require(series["period_start"] == "202301" and series["period_end"] == ("202412" if frequency == "M" else "202404"), f"{prefix}: API period")
            require(int(table["period_start_observed"][:4]) <= 2023 and int(table["period_end_observed"][:4]) >= 2024, f"{prefix}: catalog period")
            require(set(series["classifications"]) == {dimension["api_param"] for dimension in table["dimensions"]}, f"{prefix}: classification parameters")
            for dimension in table["dimensions"]:
                param = dimension["api_param"]
                values = {value["value_id"]: value for value in dimension["values"]}
                code = series["classifications"][param]
                require(code in values, f"{prefix}: invalid classification code")
                require(series["classification_labels"][param] == values[code]["value_name"], f"{prefix}: classification label")
            identity = (series["table_id"], series["item_id"], tuple(sorted(series["classifications"].items())))
            require(identity not in seen, f"{prefix}: duplicate series")
            seen.add(identity)
            require(meaning["series_index"] == index and meaning["series_label"] == series["label"], f"{prefix}: semantic binding")
            require(bool(meaning["metric"] and meaning["target"] and meaning["measure"]), f"{prefix}: empty semantic slot")
            basis = meaning["measurement_basis"]
            if basis in ("신규취급액", "잔액") and meaning["measure"] in ("금리", "비중"):
                require(basis in table["table_name"], f"{prefix}: measurement basis")
            for qualifier, value in meaning["qualifiers"].items():
                if qualifier == "currency_basis":
                    require(value == "원화" and series["classification_labels"].get("objL2") == "원화기준", f"{prefix}: currency basis")
                if qualifier == "price_basis" or (qualifier == "seasonal_adjustment" and value == "계절조정"):
                    require(value in table["table_name"], f"{prefix}: {qualifier}")
            require(all(plan.get(key) == value for key, value in series.items() if key in plan), f"{prefix}: plan binding")
            require(set(plan) == {"label", "table_id", "table_name", "org_id", "item_id", "classifications", "classification_labels", "frequency", "period_start", "period_end"}, f"{prefix}: plan fields")
    summary = {"cases": len(cases), "categories": dict(categories),
               "series": sum(case["expected_series_count"] for case in cases),
               "tables": len({tid for case in cases for tid in case["table_ids"]})}
    require(summary["series"] == 57 and summary["tables"] == 26, "Dataset totals changed")
    return summary


def main() -> None:
    case_path = DATASET / "statbridge-reporter30.jsonl"
    cases = [json.loads(line) for line in case_path.read_text(encoding="utf-8").splitlines()]
    source = ROOT / "src/agent/stat_dictionary/stat_language_dictionary.json"
    summary = validate_cases(cases, json.loads(source.read_text(encoding="utf-8-sig")))
    manifest = json.loads((DATASET / "dataset_manifest.json").read_text(encoding="utf-8"))
    require(summary == manifest["counts"], "Manifest counts")
    require(manifest["sha256_normalization"] == "LF", "Hash normalization")
    require(text_sha256(case_path) == manifest["dataset_sha256"], "Dataset SHA256")
    source_hash = text_sha256(source)
    require(source_hash == manifest["catalog_sha256"], "Catalog snapshot SHA256")
    for case in cases:
        require(case["evidence"]["source_sha256"] == source_hash, f"{case['id']}: catalog provenance")
        for reference in case["research_references"]:
            path = ROOT / reference["path"]
            lines = path.read_text(encoding="utf-8-sig").splitlines()
            require(lines[reference["line"] - 1] == reference["heading"], f"{case['id']}: research heading")
            require(text_sha256(path) == reference["sha256"], f"{case['id']}: research SHA256")
    print("VALIDATION OK " + json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
