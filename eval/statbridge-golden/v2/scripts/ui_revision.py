"""Replace attachment assumptions with supported query/API scenarios; ai-assisted."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone

from common import BASE, ROOT, csv_rows, digest, identity, normalized_unit, read_json, read_jsonl, transform_series, write_json, write_jsonl
from validate import derive_claims

REVISION = "ui-aligned-20261007"
FOLLOWUPS = {"SBV2-0022": "SBV2-0004", "SBV2-0023": "SBV2-0005",
             "SBV2-0032": "SBV2-0015", "SBV2-0033": "SBV2-0011",
             "SBV2-0034": "SBV2-0014", "SBV2-0035": "SBV2-0018"}
OUTPUTS = {
    "SBV2-0055": ("SBV2-0019", "line", "combined"),
    "SBV2-0056": ("SBV2-0020", "line", "separate"),
    "SBV2-0057": ("SBV2-0005", "bar", "combined"),
    "SBV2-0058": ("SBV2-0021", "line", "separate"),
    "SBV2-0059": ("SBV2-0004", "area", "combined"),
    "SBV2-0060": ("SBV2-0029", "line", "combined"),
    "SBV2-0061": ("SBV2-0010", "line", "combined"),
    "SBV2-0062": ("SBV2-0012", "bar", "combined"),
    "SBV2-0063": ("SBV2-0015", "line", "combined"),
    "SBV2-0064": ("SBV2-0031", "line", "combined"),
    "SBV2-0065": ("SBV2-0014", "area", "combined"),
    "SBV2-0066": ("SBV2-0016", "bar", "combined"),
}
EDITS = {
    "SBV2-0067": ("SBV2-0004", {"operation": "set_title", "kind": "STYLE_EDIT", "value": "2023년 신규취급액 대출금리"}, "제목을 '2023년 신규취급액 대출금리'로 변경해 주세요."),
    "SBV2-0068": ("SBV2-0005", {"operation": "set_legend", "kind": "STYLE_EDIT", "value": False}, "범례를 숨겨 주세요. 데이터와 출처는 유지해 주세요."),
    "SBV2-0069": ("SBV2-0004", {"operation": "set_transform", "kind": "DATA_EDIT", "value": "growth_rate"}, "전기 대비 증감률(%)로 변경해 주세요."),
    "SBV2-0070": ("SBV2-0011", {"operation": "set_title", "kind": "STYLE_EDIT", "value": "2024년 가계대출 잔액 기준 금리"}, "제목을 '2024년 가계대출 잔액 기준 금리'로 변경해 주세요."),
    "SBV2-0071": ("SBV2-0015", {"operation": "filter_period", "kind": "DATA_EDIT", "start": "202404", "end": "202409"}, "2024년 4월부터 9월까지로 표시 기간을 좁혀 주세요."),
    "SBV2-0072": ("SBV2-0011", {"operation": "set_transform", "kind": "DATA_EDIT", "value": "year_over_year"}, "전년 같은 달 대비 증감률(%)로 변경해 주세요."),
}


def extracted_series(seed, start=None, end=None):
    """Re-extract numeric values, never use previous fixture values as authority."""
    selected = seed["expected"]["resolution"]["series_selection"]
    old = read_json(BASE / seed["expected"]["data"]["fixture"])["series"]
    output, sources = [], []
    for contract, previous in zip(selected, old):
        original = next(s for s in seed["evidence"]["sources"]
                        if s["path"].split("/")[-1].startswith(contract["table_id"] + "__"))
        path = ROOT / original["path"]
        if digest(path) != original["sha256"]:
            raise ValueError("original changed: " + str(path))
        first, last = start or previous["points"][0]["period"], end or previous["points"][-1]["period"]
        points = []
        for row in csv_rows(path):
            if row["ITM_ID"] != contract["item_id"] or row["PRD_SE"] != contract["frequency"]:
                continue
            if any(row.get("C" + key[-1]) != value for key, value in contract["classifications"].items()):
                continue
            period = row["PRD_DE"]
            if contract["frequency"] == "Q" and "Q" not in period:
                period = period[:4] + "Q" + str(int(period[-2:]))
            if first <= period <= last:
                if normalized_unit(contract["table_id"], row.get("UNIT_NM", "")) != contract["unit"]:
                    raise ValueError("unit differs from documented contract")
                raw = row["DT"].replace(",", "")
                points.append({"period": period, "value": None if raw in ("", "-", "...") else float(raw)})
        points.sort(key=lambda p: p["period"])
        if not points or len({p["period"] for p in points}) != len(points):
            raise ValueError("empty/duplicate original periods")
        expected_count = ((int(last[:4])-int(first[:4]))*12 + int(last[-2:])-int(first[-2:])+1
                          if contract["frequency"] == "M" else (int(last[:4])-int(first[:4]))*4+int(last[-1])-int(first[-1])+1)
        if len(points) != expected_count:
            raise ValueError("incomplete original coverage")
        output.append({**contract, "points": points})
        source = copy.deepcopy(original)
        source["locator"] = "CSV: ITM_ID=" + contract["item_id"] + ", C1=" + contract["classifications"]["objL1"] + ", PRD_SE=" + contract["frequency"] + ", PRD_DE=" + first + ".." + last
        sources.append(source)
    return output, sources


def revise():
    cases = read_jsonl(BASE / "dev.jsonl") + read_jsonl(BASE / "test.jsonl")
    if any(c["review"]["human_approved"] for c in cases):
        raise ValueError("refusing to overwrite human-approved cases")
    policy_path = BASE / "dataset_policy.json"
    if policy_path.exists() and read_json(policy_path).get("revision") == REVISION:
        print("Already revised; unchanged.")
        return
    backup = BASE / "results" / ("before-ui-revision-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    for folder in ("fixtures", "claims", "scripts", "notebooks", "review"):
        shutil.copytree(BASE / folder, backup / folder)
    for path in BASE.iterdir():
        if path.is_file():
            shutil.copy2(path, backup / path.name)
    by_id = {c["id"]: c for c in cases}
    internal = BASE / "internal/components"
    archived = []
    for case in cases:
        if case["mode"] not in {"output", "edit"}:
            continue
        row = copy.deepcopy(case)
        for owner, key in ((row["input"], "data_fixture"), (row["expected"]["data"], "fixture"), (row["expected"]["output"], "claims")):
            old_path = owner[key]
            new_path = "internal/components/" + old_path
            target = BASE / new_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(BASE / old_path, target)
            owner[key] = new_path
        archived.append(row)
    write_jsonl(internal / "cases.jsonl", archived)
    shutil.copy2(BASE / "attachment_registry.json", internal / "attachment_registry.json")
    for case_id, seed_id in FOLLOWUPS.items():
        case, seed = by_id[case_id], by_id[seed_id]
        case["input"]["query"] = seed["input"]["query"].replace("선그래프", "막대그래프")
        case["input"]["prior_turns"] = []
        case["tags"] = ["single", "explicit_period", "bar"]
    provider = read_json(BASE / "fixtures/provider.json")
    replacements = []
    for case_id in [*OUTPUTS, *EDITS]:
        old_case = by_id[case_id]
        seed_id = OUTPUTS[case_id][0] if case_id in OUTPUTS else EDITS[case_id][0]
        seed = by_id[seed_id]
        case = copy.deepcopy(seed)
        case.update(id=case_id, mode=old_case["mode"], review=copy.deepcopy(old_case["review"]))
        case["review"].update(status="ready_for_review", reviewer=None, human_approved=False)
        case["input"]["prior_turns"] = []
        case["input"]["query"] = seed["input"]["query"].rstrip("。.")
        series, csv_sources = extracted_series(seed, "202301" if case_id == "SBV2-0072" else None,
                                               "202412" if case_id == "SBV2-0072" else None)
        case["evidence"]["sources"] = [s for s in seed["evidence"]["sources"] if not s["path"].endswith(".csv")] + csv_sources
        if case_id in OUTPUTS:
            _, chart, layout = OUTPUTS[case_id]
            case["input"]["query"] += " 첫 값·마지막 값·변화와 결측 여부를 설명해 주세요."
            case["tags"] = ["queried_output", chart, "comparison" if len(series) > 1 else "single"]
            command = None
        else:
            _, command, instruction = EDITS[case_id]
            chart, layout = "line", "combined"
            case["tags"] = ["queried_edit", command["operation"], "state_preservation"]
            case["input"]["offline_edit_command"] = command
        if case_id == "SBV2-0072":
            case["input"]["query"] = "2023년 1월부터 2024년 12월까지 예금은행 잔액 기준 가계대출 금리를 월별 선그래프로 보여주세요."
            for existing in provider["series"]:
                if identity(existing) == identity(series[0]):
                    existing["points"] = series[0]["points"]
        if case_id in OUTPUTS and chart != "line":
            case["input"]["query"] = case["input"]["query"].replace("선그래프", "막대그래프" if chart == "bar" else "영역그래프")
        case["input"]["query"] += " 각 계열을 나누어 표시해 주세요." if layout == "separate" else ""
        dates = copy.deepcopy(seed["input"]["actions"][0])
        if case_id == "SBV2-0072":
            dates.update(start="2023-01-01", end="2024-12-31")
        case["input"]["actions"] = [dates, {"kind": "configure_output", "chart_type": chart, "layout": layout}]
        case["input"]["output_request"] = {"chart_type": chart, "layout": layout}
        if command:
            case["input"]["actions"].append({"kind": "edit", "instruction": instruction})
        final = transform_series(series, command or {})
        source_path = "fixtures/" + case_id + "-source.json"
        write_json(BASE / source_path, {"series": series})
        path = "fixtures/" + case_id + ".json"
        write_json(BASE / path, {"series": final})
        case["expected"]["data"] = {"fixture": path, "fixture_sha256": digest(BASE / path),
                                   "source_fixture": source_path, "source_fixture_sha256": digest(BASE / source_path),
                                   "absolute_tolerance": 0.000001 if command else 0.0000001,
                                   "period_policy": "exact", "missing_policy": "preserve"}
        claims = "claims/" + case_id + ".json"
        write_json(BASE / claims, {"fixture_sha256": digest(BASE / path), "facts": derive_claims(final)})
        case["expected"]["output"] = {"acceptable_chart_types": [chart], "layout": layout, "claims": claims}
        if command:
            state = {"title": command["value"]} if command["operation"] == "set_title" else {"show_legend": command["value"]} if command["operation"] == "set_legend" else {"transform": command["value"]} if command["operation"] == "set_transform" else {"period_start": command["start"], "period_end": command["end"]}
            case["expected"]["output"].update(state=state, preserve_data=True)
        replacements.append(case)
    replacement_map = {c["id"]: c for c in replacements}
    cases = [replacement_map.get(c["id"], c) for c in cases]
    for split in ("dev", "test"):
        write_jsonl(BASE / (split + ".jsonl"), [c for c in cases if c["split"] == split])
    pilot_ids = [c["id"] for c in read_jsonl(BASE / "pilot.jsonl")]
    current = {c["id"]: c for c in cases}
    write_jsonl(BASE / "pilot.jsonl", [current[cid] for cid in pilot_ids])
    write_json(BASE / "fixtures/provider.json", provider)
    inventory = read_json(BASE / "source_inventory.json")
    research = csv_rows(ROOT / "research/그림표-분석/그림표_마스터.csv")
    selected_ids = {rid for c in cases for rid in c["evidence"]["research_result_ids"]}
    inventory["selected_unique_results"] = len(selected_ids)
    inventory["selected_unique_result_ids_by_report_type"] = dict(Counter(r["보고서"].split(" ")[0] for r in research if r["결과물ID"] in selected_ids))
    inventory["selection_note"] = "UI-aligned public cases; original attachment cases retained ONLY in internal/components."
    inventory["originals"] = {s["path"]: s["sha256"] for c in cases for s in c["evidence"]["sources"]}
    write_json(BASE / "source_inventory.json", inventory)
    write_jsonl(BASE / "review/gold-review-ui-template.jsonl", [
        {"id": c["id"], "input_sha256": hashlib.sha256(json.dumps(c["input"], sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
         "status": "pending", "reviewer": None, "human_approved": False, "question_clear": None,
         "original_locator_verified": None, "numbers_units_frequency_verified": None,
         "acceptable_answers_verified": None, "split_independence_verified": None,
         "source_relationship": c["evidence"]["relationship"], "notes": ""} for c in cases])
    write_json(policy_path, {"revision": REVISION, "ai_assisted": True, "human_approved": False,
                            "public_scope": "supported query/output/edit API scenarios; NOT browser UI verification",
                            "e2e_subtypes": {"single": 24, "multi": 6}, "internal_component_cases": 18,
                            "offline_edit_scope": "command replay, not natural-language interpretation"})
    write_json(backup / "revision.json", {"replaced": list(replacement_map), "rewritten": list(FOLLOWUPS),
                                         "internal_cases": len(archived), "human_approval_granted": False})
    print({"backup": str(backup), "replaced": 18, "rewritten": 6, "public": len(cases)})


if __name__ == "__main__":
    revise()
