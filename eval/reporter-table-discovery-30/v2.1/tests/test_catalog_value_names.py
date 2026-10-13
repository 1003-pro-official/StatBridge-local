"""The dictionary's classification names must match the tracked source metadata.

A wrong code -> name pairing makes the whole golden set (and the product) fetch a different
series while still looking self-consistent, so it is asserted here rather than trusted.
"""
import importlib.util
import json
from collections import defaultdict
from pathlib import Path

DATASET = Path(__file__).resolve().parents[1]
ROOT = DATASET.parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


repair_tool = load("reporter200_repair_values", ROOT / "tools/repair_dictionary_values.py")
CATALOG = json.loads((ROOT / "src/agent/stat_dictionary/stat_language_dictionary.json")
                     .read_text(encoding="utf-8-sig"))
SOURCE = repair_tool.read_source()


def mismatches() -> list[str]:
    found = []
    for table in CATALOG["tables"]:
        reference = SOURCE.get(table["table_id"], {})
        for dimension in table.get("dimensions") or []:
            for value in dimension.get("values") or []:
                name = reference.get(value["value_id"])
                if name and name != value["value_name"]:
                    found.append(f"{table['table_id']}.{dimension['api_param']}:{value['value_id']}")
    return found


def test_every_catalog_value_name_matches_the_source_metadata():
    found = mismatches()
    assert found == [], f"카탈로그 코드-이름 불일치 {len(found)}건 (예: {found[:5]})"


def test_every_catalog_value_code_exists_in_the_source():
    missing = []
    for table in CATALOG["tables"]:
        reference = SOURCE.get(table["table_id"], {})
        for dimension in table.get("dimensions") or []:
            for value in dimension.get("values") or []:
                if value["value_id"] not in reference:
                    missing.append(f"{table['table_id']}:{value['value_id']}")
    assert missing == [], f"소스 메타데이터에 없는 코드 {len(missing)}건 (예: {missing[:5]})"


def test_legacy_repairs_are_recorded_and_consistent():
    manifest = json.loads((DATASET / "dataset_manifest.json").read_text(encoding="utf-8"))
    repairs = manifest["legacy_value_repair"]
    assert repairs["count"] == len(repairs["entries"]) > 0
    cases = {case["id"]: case for case in
             (json.loads(line) for line in (DATASET / "statbridge-reporter200.jsonl")
              .read_text(encoding="utf-8").splitlines() if line)}
    for case in cases.values():
        for entry in case.get("legacy_value_repair") or []:
            table = next(item for item in CATALOG["tables"] if item["table_id"] == entry["table_id"])
            dimension = next(dim for dim in table["dimensions"] if dim["api_param"] == entry["param"])
            name = next(value["value_name"] for value in dimension["values"]
                        if value["value_id"] == entry["to"])
            assert name == entry["label"], f"{case['id']}: 교정된 코드의 카탈로그 이름이 다름"


def test_repair_tool_is_idempotent_on_a_repaired_catalog():
    import copy
    clone = copy.deepcopy(CATALOG)
    report = repair_tool.repair(clone, SOURCE)
    assert report["summary"].get("values", 0) == 0
    assert report["remaining"] == []
