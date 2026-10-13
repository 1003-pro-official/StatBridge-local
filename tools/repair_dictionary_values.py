"""Align dictionary dimension value names with the tracked source metadata.

`src/agent/stat_dictionary/stat_language_dictionary.json` pairs some classification codes
with the wrong name. `data/processed/bok_classifications.csv` holds the authoritative
(code, name) pairing and matches the live KOSIS API.

The repair only rewrites the name fields of a value that keeps its own code. It never moves
values between codes and never invents values, because a dimension mixes hierarchy levels and
repeated names, where object re-pairing is unsafe.

Default is a dry run. `--apply` backs the dictionary up and rewrites it.

Usage:
    python3 tools/repair_dictionary_values.py                 # dry run
    python3 tools/repair_dictionary_values.py --apply         # apply (writes a backup first)
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DICTIONARY = ROOT / "src/agent/stat_dictionary/stat_language_dictionary.json"
SOURCE = ROOT / "data/processed/bok_classifications.csv"
BACKUP_DIR = ROOT / ".venv/cache/evaluation_runs"
FOOTNOTE = re.compile(r"\s*\d+\)\s*$")
PARENTHETICAL = re.compile(r"\([^)]*\)")


def read_source() -> dict[str, dict[str, str]]:
    mapping: dict[str, dict[str, str]] = defaultdict(dict)
    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            mapping[row["TBL_ID"]][row["ITM_ID"]] = row["ITM_NM"]
    return mapping


def derived_terms(name: str) -> tuple[str, list[str]]:
    normalized = FOOTNOTE.sub("", name).strip()
    terms = [name]
    for candidate in (normalized, PARENTHETICAL.sub("", name).strip()):
        if candidate and candidate != name and candidate not in terms:
            terms.append(candidate)
    return normalized, terms


def rename(value: dict, name: str) -> dict:
    """이름과 이름에서 파생된 필드만 다시 쓴다. 코드와 다른 속성은 그대로 둔다."""
    normalized, terms = derived_terms(name)
    return {**value, "value_name": name, "normalized": normalized,
            "natural_language_terms": list(terms), "aliases": list(terms)}


def repair(catalog: dict, reference: dict[str, dict[str, str]]) -> dict:
    summary = Counter()
    detail = []
    for table in catalog["tables"]:
        table_id = table["table_id"]
        for dimension in table.get("dimensions") or []:
            changed = 0
            for index, value in enumerate(dimension.get("values") or []):
                name = reference.get(table_id, {}).get(value["value_id"])
                if name and name != value["value_name"]:
                    dimension["values"][index] = rename(value, name)
                    changed += 1
            if changed:
                summary["dimensions"] += 1
                summary["values"] += changed
                detail.append(f"{table_id}.{dimension['api_param']}: {changed}개")
                summary["clear_derived"] += sum(
                    1 for value in dimension["values"]
                    if any(value.get(field) for field in ("layman_terms", "related_concepts",
                                                          "negative_terms", "value_question_terms")))
    remaining = [value["value_name"] for table in catalog["tables"]
                 for dimension in table.get("dimensions") or []
                 for value in dimension.get("values") or []
                 if reference.get(table["table_id"], {}).get(value["value_id"])
                 and reference[table["table_id"]][value["value_id"]] != value["value_name"]]
    return {"summary": dict(summary), "detail": detail, "remaining": remaining}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="dictionary를 실제로 수정(백업 생성)")
    args = parser.parse_args()
    catalog = json.loads(DICTIONARY.read_text(encoding="utf-8-sig"))
    reference = read_source()
    report = repair(catalog, reference)
    summary = report["summary"]
    print(f"영향 차원 {summary.get('dimensions', 0)} | 이름 교정 값 {summary.get('values', 0)} "
          f"| 파생 목록이 남은 값 {summary.get('clear_derived', 0)}")
    for line in report["detail"][:10]:
        print("  ", line)
    if len(report["detail"]) > 10:
        print(f"   ... 외 {len(report['detail']) - 10}개 차원")
    print(f"수정 후에도 CSV와 다른 값: {len(report['remaining'])}")
    for name in report["remaining"][:10]:
        print("   남음:", name)
    if not args.apply:
        print("\n(dry run) 적용하려면 --apply")
        return 0 if not report["remaining"] else 1
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"stat_language_dictionary_before_value_repair_{datetime.now():%Y%m%d_%H%M%S}.json"
    shutil.copy2(DICTIONARY, backup)
    DICTIONARY.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n적용 완료. 백업: {backup}")
    return 0 if not report["remaining"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
