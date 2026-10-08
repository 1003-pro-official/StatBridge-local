"""Mechanical, source-grounded migration with a preserved pre-change snapshot."""
from __future__ import annotations

import copy
import hashlib
import shutil
from datetime import datetime, timezone

from common import BASE, digest, normalized_unit, read_json, read_jsonl, transform_series, unit_sources, write_json, write_jsonl
from validate import derive_claims


def main():
    cases = read_jsonl(BASE / "dev.jsonl") + read_jsonl(BASE / "test.jsonl")
    if any(c["review"]["human_approved"] for c in cases):
        raise ValueError("approved cases require an explicit separately reviewed migration")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = BASE / "results" / ("before-hardening-" + stamp)
    paths = [BASE / name for name in ("dev.jsonl", "test.jsonl", "pilot.jsonl",
             "series_registry.json", "fixtures/provider.json", "dataset_manifest.json")]
    paths += list((BASE / "fixtures").glob("SBV2-*.json"))
    paths += list((BASE / "claims").glob("*.json"))
    for path in paths:
        target = backup / path.relative_to(BASE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    changes = []
    for path in [BASE / "series_registry.json", BASE / "fixtures/provider.json", *list((BASE / "fixtures").glob("SBV2-*.json"))]:
        value = read_json(path)
        series = value if isinstance(value, list) else value["series"]
        updated = copy.deepcopy(value)
        for s in series:
            if s["provider"] == "kosis":
                s["unit"] = normalized_unit(s["table_id"], s["unit"])
        if value != updated:
            write_json(path, value)
    for case in cases:
        original = copy.deepcopy(case)
        for series in case["expected"].get("resolution", {}).get("series_selection", []):
            series["unit"] = normalized_unit(series["table_id"], series["unit"])
        tables = {s.get("table_id") for s in case["expected"].get("resolution", {}).get("series_selection", [])}
        data = case["expected"].get("data")
        if data:
            fixture_path = BASE / data["fixture"]
            fixture = read_json(fixture_path)
            tables.update(s.get("table_id") for s in fixture["series"])
            if case["input"].get("offline_edit_command", {}).get("value") == "cumulative":
                attached = read_json(BASE / case["input"]["data_fixture"])["series"]
                fixture["series"] = transform_series(attached, case["input"]["offline_edit_command"])
                write_json(fixture_path, fixture)
                case["input"]["actions"][-1]["instruction"] = "첨부된 값으로 누적합을 계산해 주세요."
            data["fixture_sha256"] = digest(fixture_path)
            write_json(BASE / case["expected"]["output"]["claims"],
                       {"fixture_sha256": data["fixture_sha256"], "facts": derive_claims(fixture["series"])})
        for table in tables:
            for source in unit_sources(table):
                if source not in case["evidence"]["sources"]:
                    case["evidence"]["sources"].append(source)
        if case["input"].get("data_fixture"):
            case["input"]["data_fixture_sha256"] = digest(BASE / case["input"]["data_fixture"])
        if original != case:
            changes.append(case["id"])
    for split in ("dev", "test"):
        write_jsonl(BASE / (split + ".jsonl"), [c for c in cases if c["split"] == split])
    pilot_ids = {c["id"] for c in read_jsonl(BASE / "pilot.jsonl")}
    write_jsonl(BASE / "pilot.jsonl", [c for c in cases if c["id"] in pilot_ids])
    write_json(backup / "migration.json", {"annotation_method": "ai-assisted", "changed_cases": changes,
               "human_approval_granted": False, "before_hashes": {str(p.relative_to(backup)): digest(p)
               for p in backup.rglob("*") if p.is_file()}})
    print({"backup": str(backup), "changed_cases": changes})


if __name__ == "__main__":
    main()
