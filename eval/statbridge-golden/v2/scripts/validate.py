"""Validate public v2 contracts, provenance and split independence."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter

from jsonschema import Draft202012Validator, FormatChecker
from common import BASE, ROOT, csv_rows, digest, finite_number, identity, local_path, read_json, read_jsonl, transform_series, unit_sources
from edit_contract import CLARIFICATION_GROUPS, instruction_command


def catalog_contract():
    tables = {r["TBL_ID"] for r in csv_rows(ROOT / "data/processed/bok_items.csv")}
    items = {(r["TBL_ID"], r["ITM_ID"]) for r in csv_rows(ROOT / "data/processed/bok_items.csv")}
    classes = {(r["TBL_ID"], "objL" + r["OBJ_ID_SN"], r["ITM_ID"])
               for r in csv_rows(ROOT / "data/processed/bok_classifications.csv")}
    return tables, items, classes


def validate_fixture(fixture, contract):
    errors = []
    tables, items, classes = contract
    keys = []
    for s in fixture.get("series", []):
        try:
            keys.append(identity(s))
            if not s.get("label") or s["frequency"] not in {"D", "W", "M", "Q", "Y", "H"}:
                errors.append("series label/frequency")
            if not isinstance(s.get("unit"), str) or not s["unit"].strip():
                errors.append("missing documented unit")
            if s["provider"] == "kosis":
                if (s["table_id"], s["item_id"]) not in items:
                    errors.append("unknown table/item")
                if not s["classifications"] or any((s["table_id"], k, v) not in classes for k, v in s["classifications"].items()):
                    errors.append("unknown classification")
            elif s["provider"] != "attachment" or not s["series_id"].startswith("attachment:"):
                errors.append("unknown provider/attachment ID")
            points = s["points"]
            periods = [p["period"] for p in points]
            pattern = {"D": r"\d{8}", "W": r"\d{8}", "M": r"\d{6}", "Q": r"\d{4}Q[1-4]", "Y": r"\d{4}", "H": r"\d{4}H[12]"}[s["frequency"]]
            if not points or periods != sorted(set(periods)) or any(not re.fullmatch(pattern, p) for p in periods):
                errors.append("empty/duplicate/unordered/invalid periods")
            from datetime import datetime
            for p in periods:
                if s["frequency"] in {"D", "W", "M"}:
                    try:
                        datetime.strptime(p, "%Y%m" if s["frequency"] == "M" else "%Y%m%d")
                    except ValueError:
                        errors.append("invalid calendar period")
            if any(p["value"] is not None and not finite_number(p["value"]) for p in points):
                errors.append("invalid numeric value")
        except (KeyError, TypeError, ValueError):
            errors.append("missing series contract")
    if not keys or len(keys) != len(set(keys)):
        errors.append("empty/duplicate series")
    return errors


def derive_claims(series):
    claims = []
    for s in series:
        valid = [p for p in s["points"] if p["value"] is not None]
        facts = {"identity": list(identity(s)), "unit": s["unit"], "frequency": s["frequency"],
                 "missing_periods": [p["period"] for p in s["points"] if p["value"] is None]}
        if valid:
            facts.update(first=valid[0], last=valid[-1], minimum=min(valid, key=lambda p: p["value"]),
                         maximum=max(valid, key=lambda p: p["value"]),
                         absolute_change=valid[-1]["value"] - valid[0]["value"],
                         change_formula="last - first")
        claims.append(facts)
    # JSON roundtrip normalizes nested identity tuples for stable file equality.
    return json.loads(json.dumps(claims))


def validate_cases(cases, base=BASE, verify_sources=False, enforce_counts=True):
    errors, warnings = [], []
    contract = catalog_contract()
    schema = Draft202012Validator(read_json(BASE / "schema.json"), format_checker=FormatChecker())
    research = {r["결과물ID"] for r in csv_rows(ROOT / "research/그림표-분석/그림표_마스터.csv")}
    catalog_hash = digest(ROOT / "data/processed/bok_table_master.csv")
    registry = read_json(BASE / "series_registry.json")
    attachments = read_json(BASE / "attachment_registry.json")
    groups, sources, inputs, ids, periods_seen = {}, {}, {}, set(), {}
    for c in cases:
        rid = c.get("id", "<missing>")
        failures = [e.message for e in schema.iter_errors(c)]
        if failures:
            errors.extend(rid + ": schema: " + e for e in failures)
            continue
        if rid in ids:
            errors.append(rid + ": duplicate ID")
        ids.add(rid)
        for index, key in ((groups, c["group_id"]), *[(sources, r) for r in c["evidence"]["research_result_ids"]]):
            value = c["split"] if index is groups else (c["split"], c["group_id"])
            if key in index and index[key] != value:
                errors.append(rid + ": group/source crosses splits")
            index[key] = value
        signature = json.dumps(c["input"], sort_keys=True, ensure_ascii=False)
        if signature in inputs:
            errors.append(rid + ": duplicate input (including conflicting answers)")
        inputs[signature] = rid
        review = c["review"]
        if review["human_approved"] != (review["status"] == "approved") or (review["human_approved"] and not review["reviewer"]):
            errors.append(rid + ": inconsistent human approval")
        evidence = c["evidence"]
        if evidence["catalog_snapshot"] != catalog_hash:
            errors.append(rid + ": catalog hash")
        if not set(evidence["research_result_ids"]).issubset(research):
            errors.append(rid + ": unknown research result ID")
        for source in evidence["sources"]:
            try:
                path = local_path(ROOT, source["path"])
                if not path.exists():
                    (errors if verify_sources else warnings).append(rid + ": original unavailable: " + source["path"])
                elif digest(path) != source["sha256"]:
                    errors.append(rid + ": original hash mismatch")
                if not source.get("extraction"):
                    errors.append(rid + ": missing extraction rule")
            except ValueError as exc:
                errors.append(rid + ": " + str(exc))
        expected = c["expected"]
        edits = [a for a in c["input"]["actions"] if a["kind"] == "edit"]
        command = c["input"].get("offline_edit_command")
        if edits or command:
            if len(edits) != 1 or not command:
                errors.append(rid + ": missing/duplicate edit instruction or command")
            elif instruction_command(edits[0]["instruction"]) is None:
                errors.append(rid + ": edit instruction requires semantic annotation review")
            elif instruction_command(edits[0]["instruction"]) != command:
                errors.append(rid + ": edit instruction/command mismatch")
        if "data_fixture" not in c["input"] and "resolution" not in expected:
            errors.append(rid + ": missing resolution")
        if c["mode"] != "discovery" and not {"data", "output"}.issubset(expected):
            errors.append(rid + ": missing data/output")
        if "data" in expected and not finite_number(expected["data"]["absolute_tolerance"]):
            errors.append(rid + ": nonfinite numeric tolerance")
        resolution = expected.get("resolution", {})
        referenced_tables = {s.get("table_id") for s in resolution.get("series_selection", [])}
        if "data" in expected:
            try:
                referenced_tables.update(s.get("table_id") for s in read_json(local_path(base, expected["data"]["fixture"]))["series"])
            except (OSError, ValueError, KeyError, TypeError):
                pass
        for table in referenced_tables:
            for source in unit_sources(table):
                if source not in evidence["sources"]:
                    errors.append(rid + ": missing unit-definition provenance")
        sets = resolution.get("acceptable_table_sets", [])
        if any(t not in contract[0] for option in sets for t in option):
            errors.append(rid + ": nonexistent table ID")
        if resolution.get("decision") == "resolved" and not sets:
            errors.append(rid + ": no acceptable complete answer")
        for s in resolution.get("series_selection", []):
            try:
                if not isinstance(s.get("unit"), str) or not s["unit"].strip():
                    errors.append(rid + ": missing documented selection unit")
                if identity(s) not in [identity(r) for r in registry]:
                    errors.append(rid + ": invalid selection identity/unit/frequency")
            except (KeyError, TypeError, ValueError):
                errors.append(rid + ": incomplete selection identity")
        if resolution.get("decision") != "resolved" and sets:
            errors.append(rid + ": unresolved answer contains tables")
        clarify = resolution.get("clarification", {})
        if resolution.get("decision") == "clarify" and not (clarify.get("required") and clarify.get("dimensions") and clarify.get("option_groups")):
            errors.append(rid + ": incomplete clarification")
        if clarify.get("required") and any(frozenset(group) not in CLARIFICATION_GROUPS or len(group) != len(set(group))
                                           for group in clarify.get("option_groups", [])):
            errors.append(rid + ": undocumented clarification option group")
        if "followup" in c["tags"] and (len(c["input"]["prior_turns"]) < 2 or not any(re.search(r"20\d{2}", t["text"]) for t in c["input"]["prior_turns"])):
            errors.append(rid + ": insufficient followup context")
        for action in c["input"]["actions"]:
            if action["kind"] == "confirm_period" and not (action.get("start") and action.get("end") and action["start"] <= action["end"]):
                errors.append(rid + ": invalid period action")
        paths = []
        if "data_fixture" in c["input"]:
            paths.append(c["input"]["data_fixture"])
        if "data" in expected:
            paths.append(expected["data"]["fixture"])
            if expected["data"].get("source_fixture"):
                paths.append(expected["data"]["source_fixture"])
        for relative in set(paths):
            try:
                fixture_path = local_path(base, relative)
                fixture = read_json(fixture_path)
                errors.extend(rid + ": " + e for e in validate_fixture(fixture, contract))
                for s in fixture["series"]:
                    if s["provider"] == "kosis":
                        originals = [r for r in registry if r["table_id"] == s["table_id"] and r["item_id"] == s["item_id"] and r["classifications"] == s["classifications"]]
                        calculated_unit = (relative == expected.get("data", {}).get("fixture")
                                           and expected.get("data", {}).get("source_fixture")
                                           and c["input"].get("offline_edit_command", {}).get("operation") == "set_transform")
                        if not originals or s["frequency"] not in {r["frequency"] for r in originals} or (not calculated_unit and s["unit"] not in {r["unit"] for r in originals}):
                            errors.append(rid + ": fixture identity/unit/frequency not in source registry")
                    elif relative == c["input"].get("data_fixture"):
                        matches = [a for a in attachments if a["series_id"] == s["series_id"]]
                        if not matches or identity(s) not in [identity(a) for a in matches]:
                            errors.append(rid + ": unknown attachment identity/unit/frequency")
                original_relative = c["input"].get("data_fixture") or expected.get("data", {}).get("source_fixture") or expected.get("data", {}).get("fixture")
                if relative == expected.get("data", {}).get("source_fixture") and digest(fixture_path) != expected["data"].get("source_fixture_sha256"):
                    errors.append(rid + ": source fixture hash")
                if relative == original_relative:
                    for s in fixture["series"]:
                        core = identity(s) if s["provider"] == "kosis" else (
                            "attachment_subject", re.sub(r"\s+", "", s["label"]), re.sub(r"\s+", "", s["unit"]), s["frequency"])
                        for point in s["points"]:
                            key = (core, point["period"])
                            value = (c["split"], c["group_id"])
                            if key in periods_seen and periods_seen[key] != value:
                                errors.append(rid + ": same series-period outside its source group")
                            periods_seen[key] = value
                if relative == c["input"].get("data_fixture") and digest(fixture_path) != c["input"].get("data_fixture_sha256"):
                    errors.append(rid + ": input fixture hash")
                if "data" in expected and relative == expected["data"]["fixture"]:
                    if digest(fixture_path) != expected["data"]["fixture_sha256"]:
                        errors.append(rid + ": fixture hash")
                    if resolution.get("decision") == "resolved" and {s["table_id"] for s in fixture["series"] if s["provider"] == "kosis"} not in [set(a) for a in sets]:
                        errors.append(rid + ": fixture/answer mismatch")
                    if "output" in expected:
                        claims = read_json(local_path(base, expected["output"]["claims"]))
                        if claims.get("fixture_sha256") != digest(fixture_path) or claims.get("facts") != derive_claims(fixture["series"]):
                            errors.append(rid + ": claims not derived from fixture")
                    if c["mode"] in {"output", "edit"}:
                        raw_path = c["input"].get("data_fixture") or expected["data"].get("source_fixture")
                        attached = read_json(local_path(base, raw_path))["series"]
                        command = c["input"].get("offline_edit_command", {})
                        if transform_series(attached, command) != fixture["series"]:
                            errors.append(rid + ": output contradicts input/independent calculation")
                    if c["mode"] == "e2e":
                        periods = [a for a in c["input"]["actions"] if a["kind"] == "confirm_period"]
                        if len(periods) != 1:
                            errors.append(rid + ": missing/duplicate absolute period")
                        else:
                            action = periods[0]
                            for s in fixture["series"]:
                                p = s["points"]
                                start, end = action["start"].replace("-", "")[:6], action["end"].replace("-", "")[:6]
                                if s["frequency"] == "Q":
                                    start = start[:4] + "Q" + str((int(start[4:])-1)//3+1)
                                    end = end[:4] + "Q" + str((int(end[4:])-1)//3+1)
                                if p[0]["period"] != start or p[-1]["period"] != end:
                                    errors.append(rid + ": period/fixture mismatch")
                                if p[0]["period"][:4] not in c["input"]["query"]:
                                    errors.append(rid + ": query/fixture year mismatch")
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append(rid + ": fixture/claims: " + str(exc))
        if c["mode"] in {"output", "edit"} and "data_fixture" not in c["input"]:
            if not expected.get("data", {}).get("source_fixture"):
                errors.append(rid + ": missing queried source fixture")
        if enforce_counts and (c["input"]["prior_turns"] or "data_fixture" in c["input"] or "첨부" in c["input"]["query"] or "앞서" in c["input"]["query"]):
            errors.append(rid + ": public UI scenario assumes attachment or prior dialogue")
    counts = Counter((c.get("split"), c.get("mode")) for c in cases)
    target = {("dev", "discovery"): 10, ("test", "discovery"): 14, ("dev", "e2e"): 12,
              ("test", "e2e"): 18, ("dev", "output"): 5, ("test", "output"): 7,
              ("dev", "edit"): 3, ("test", "edit"): 3}
    if enforce_counts and dict(counts) != target:
        errors.append("public mode/split counts differ from 72-case contract")
    if enforce_counts:
        decisions = Counter(c.get("expected", {}).get("resolution", {}).get("decision") for c in cases if c.get("mode") == "discovery")
        if decisions != {"resolved": 12, "clarify": 8, "unsupported": 4}:
            errors.append("discovery decision quotas")
        kinds = Counter(tag for c in cases if c.get("mode") == "e2e" for tag in c.get("tags", []) if tag in {"single", "multi", "followup"})
        if kinds != {"single": 24, "multi": 6}:
            errors.append("e2e subtype quotas")
        if any("queried_output" not in c.get("tags", []) for c in cases if c.get("mode") == "output"):
            errors.append("public output must use queried data, not attachment injection")
    return {"errors": errors, "warnings": warnings, "count": len(cases),
            "human_approved": sum(c.get("review", {}).get("human_approved", False) for c in cases)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", default=[str(BASE / "dev.jsonl"), str(BASE / "test.jsonl")])
    parser.add_argument("--verify-sources", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    result = validate_cases([c for p in args.cases for c in read_jsonl(p)], verify_sources=args.verify_sources, enforce_counts=not args.pilot)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return bool(result["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
