#!/usr/bin/env python3
"""Validate the v3 pilot and exchange human review through CSV."""

import argparse
import copy
import csv
import json
import os
import re
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
CASES = ROOT / "cases.jsonl"
REVIEW_CSV = ROOT / "review.csv"
CATALOG = REPO / "data/kosis/hankook_tables.json"
READONLY_COLUMNS = (
    "id", "query", "prior_turns", "type", "expected_status", "slots",
    "table_ids", "candidate_table_ids", "clarification_dimension", "evidence",
)
REVIEW_COLUMNS = ("decision", "approved_table_ids", "reviewer", "reviewed_at", "review_notes")
COLUMNS = READONLY_COLUMNS + REVIEW_COLUMNS
DECISIONS = {"", "승인", "수정", "보류", "제외"}
TYPE_COUNTS = {"single": 10, "multi": 4, "clarify": 5, "no_match": 3, "catalog_only": 2, "followup": 6}
FREQUENCIES = {"월": {"M"}, "분기": {"Q"}, "연": {"A", "Y"}, "년": {"A", "Y"}, "반기": {"S"}, "일": {"D"}}


def joined(values):
    return ";".join(values)


def review_row(case):
    review = case["review"]
    return {
        "id": case["id"], "query": case["query"],
        "prior_turns": json.dumps(case["prior_turns"], ensure_ascii=False),
        "type": case["type"], "expected_status": case["expected_status"],
        "slots": json.dumps(case["slots"], ensure_ascii=False, sort_keys=True),
        "table_ids": joined(case["table_ids"]),
        "candidate_table_ids": joined(case["candidate_table_ids"]),
        "clarification_dimension": joined(case["clarification_dimension"]),
        "evidence": case["evidence"],
        "decision": review["decision"] or "",
        "approved_table_ids": joined(review["approved_table_ids"]),
        "reviewer": review["reviewer"] or "",
        "reviewed_at": review["reviewed_at"] or "",
        "review_notes": review["review_notes"] or "",
    }


def export_review(cases, path, *, force=False):
    if path.exists() and not force:
        raise ValueError(f"{path} already exists; use --force only after saving human edits")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(review_row(case) for case in cases)


def import_review_rows(cases, path, known_ids):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError("review.csv columns differ from the exported template")
        rows = list(reader)
    if len(rows) != len(cases):
        raise ValueError(f"review.csv has {len(rows)} rows; expected {len(cases)}")
    by_id = {case["id"]: case for case in cases}
    if len({row["id"] for row in rows}) != len(rows) or {row["id"] for row in rows} != set(by_id):
        raise ValueError("review.csv IDs are missing, duplicated, or unknown")
    updated = copy.deepcopy(cases)
    updated_by_id = {case["id"]: case for case in updated}
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"{row.get('id', '?')}: malformed CSV row")
        case = by_id[row["id"]]
        if any(row[column] != review_row(case)[column] for column in READONLY_COLUMNS):
            raise ValueError(f"{row['id']}: proposal columns changed; edit review columns only")
        decision = row["decision"].strip()
        approved = [value.strip() for value in row["approved_table_ids"].split(";") if value.strip()]
        reviewer = row["reviewer"].strip()
        notes = row["review_notes"].strip()
        reviewed_at = row["reviewed_at"].strip()
        if decision not in DECISIONS:
            raise ValueError(f"{row['id']}: invalid decision")
        if len(approved) != len(set(approved)) or any(value not in known_ids for value in approved):
            raise ValueError(f"{row['id']}: invalid approved table IDs")
        if decision == "승인":
            expected = case["table_ids"] if case["expected_status"] in {"select", "catalog_only"} else []
            if set(approved) != set(expected) or not reviewer:
                raise ValueError(f"{row['id']}: approval needs matching IDs and reviewer")
        elif approved:
            raise ValueError(f"{row['id']}: approved IDs require an approval decision")
        if decision in {"수정", "보류", "제외"} and (not reviewer or not notes):
            raise ValueError(f"{row['id']}: decision needs reviewer and reason")
        if reviewed_at:
            try:
                date.fromisoformat(reviewed_at)
            except ValueError as exc:
                raise ValueError(f"{row['id']}: reviewed_at must be YYYY-MM-DD") from exc
        if decision and not reviewed_at:
            reviewed_at = date.today().isoformat()
        updated_by_id[row["id"]]["review"] = {
            "decision": decision or None, "approved_table_ids": approved,
            "reviewer": reviewer or None, "reviewed_at": reviewed_at or None,
            "review_notes": notes or None,
        }
    return updated


def read_cases(path=CASES):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def normalize_query(query):
    return re.sub(r"[^\w]", "", query.casefold())


def local_table_csv(csv_root, table_id):
    matches = sorted(Path(csv_root).glob(f"{table_id}__*.csv"))
    if matches:
        return matches[0]
    plain = Path(csv_root) / f"{table_id}.csv"
    return plain if plain.is_file() else None


def validate_rows(cases, known_ids, csv_root, *, pilot=True):
    errors = []
    if pilot:
        if len(cases) != 30 or Counter(case.get("type") for case in cases) != Counter(TYPE_COUNTS):
            errors.append("pilot must have 30 cases with the planned type counts")
        if [case.get("id") for case in cases] != [f"GS-{number:04d}" for number in range(1, 31)]:
            errors.append("pilot IDs must be GS-0001 through GS-0030 in order")
    seen = set()
    seen_ids = set()
    for case in cases:
        cid = case.get("id", "?")
        if cid in seen_ids:
            errors.append(f"{cid}: duplicate ID")
        seen_ids.add(cid)
        query = case.get("query", "")
        normalized = normalize_query(query)
        if not query.strip() or normalized in seen:
            errors.append(f"{cid}: duplicate query or empty query")
        seen.add(normalized)
        if case.get("split") != "dev":
            errors.append(f"{cid}: first 30 cases must be dev")
        if case.get("review_status") not in {"review_required", "needs_adjudication", "approved", "excluded"}:
            errors.append(f"{cid}: invalid review_status")
        if not isinstance(case.get("review"), dict) or not all(key in case["review"] for key in ("decision", "approved_table_ids", "reviewer", "reviewed_at", "review_notes")):
            errors.append(f"{cid}: review fields missing")
        if not isinstance(case.get("prior_turns"), list) or (case.get("type") == "followup") != bool(case.get("prior_turns")):
            errors.append(f"{cid}: prior_turns do not match type")
        slots = case.get("slots")
        if not isinstance(slots, dict) or not all(key in slots for key in ("metrics", "target", "period", "frequency", "qualifiers", "comparison")):
            errors.append(f"{cid}: slots incomplete")
            slots = {}
        if case.get("type") != "followup":
            for metric in slots.get("metrics", []):
                if not isinstance(metric, str) or normalize_query(metric) not in normalized:
                    errors.append(f"{cid}: metric not grounded in user query: {metric}")
        if not case.get("intent") or not case.get("normalized_concepts") or not case.get("evidence"):
            errors.append(f"{cid}: intent, concepts, or evidence missing")
        status = case.get("expected_status")
        selected = case.get("table_ids", [])
        options = case.get("candidate_table_ids", [])
        dimensions = case.get("clarification_dimension", [])
        if not isinstance(selected, list) or not isinstance(options, list) or not isinstance(dimensions, list):
            errors.append(f"{cid}: table and clarification fields must be arrays")
            continue
        if any(table_id not in known_ids for table_id in selected + options):
            errors.append(f"{cid}: unknown catalog table ID")
        if case.get("type") == "clarify":
            if status != "clarify" or selected:
                errors.append(f"{cid}: clarify has accepted table IDs or wrong status")
            if not options or not dimensions:
                errors.append(f"{cid}: clarification needs options and dimensions")
        elif case.get("type") == "no_match":
            if status != "no_match" or selected or options:
                errors.append(f"{cid}: no_match has table IDs or wrong status")
        elif case.get("type") == "catalog_only":
            if status != "catalog_only" or len(selected) != 1 or options:
                errors.append(f"{cid}: catalog_only needs one table ID")
            for table_id in selected:
                if local_table_csv(csv_root, table_id) is not None:
                    errors.append(f"{cid}: catalog_only local CSV exists")
        else:
            if status != "select" or not selected or options:
                errors.append(f"{cid}: select needs accepted table IDs")
            if case.get("type") == "single" and len(selected) != 1:
                errors.append(f"{cid}: single needs one table ID")
            if case.get("type") == "multi" and len(selected) < 2:
                errors.append(f"{cid}: multi needs at least two table IDs")
            for table_id in selected:
                path = local_table_csv(csv_root, table_id)
                if path is None:
                    errors.append(f"{cid}: {table_id} local CSV missing")
                    continue
                with path.open(encoding="utf-8-sig", newline="") as stream:
                    data = list(csv.DictReader(stream))
                frequency = slots.get("frequency")
                if frequency in FREQUENCIES and not FREQUENCIES[frequency].intersection(row.get("PRD_SE") for row in data):
                    errors.append(f"{cid}: {table_id} requested frequency unavailable")
                period = slots.get("period") or ""
                year = re.search(r"(?:19|20)\d{2}", period)
                if year and not any(row.get("PRD_DE", "").startswith(year.group()) for row in data):
                    errors.append(f"{cid}: {table_id} requested year unavailable")
                if table_id not in case.get("evidence", ""):
                    errors.append(f"{cid}: {table_id} absent from evidence")
    if pilot:
        catalog_only_ids = [case["table_ids"][0] for case in cases if case.get("type") == "catalog_only" and case.get("table_ids")]
        if set(catalog_only_ids) != {"DT_284Y001", "DT_284Y002"}:
            errors.append("catalog_only must cover the two missing CSV tables")
    return errors


def write_cases_atomic(path, cases):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        for case in cases:
            stream.write(json.dumps(case, ensure_ascii=False, separators=(",", ":")) + "\n")
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    exporter = commands.add_parser("export-review")
    exporter.add_argument("--force", action="store_true")
    importer = commands.add_parser("import-review")
    importer.add_argument("path", nargs="?", type=Path, default=REVIEW_CSV)
    args = parser.parse_args()
    cases = read_cases()
    known_ids = {row["tbl_id"] for row in json.loads(CATALOG.read_text(encoding="utf-8"))["tables"]}
    errors = validate_rows(cases, known_ids, REPO / "data/tables")
    if errors:
        raise SystemExit("\n".join(errors))
    if args.command == "export-review":
        export_review(cases, REVIEW_CSV, force=args.force)
        print(f"wrote {REVIEW_CSV}")
    elif args.command == "import-review":
        updated = import_review_rows(cases, args.path, known_ids)
        write_cases_atomic(CASES, updated)
        print(f"recorded review fields for {len(updated)} cases; gold and review_status unchanged")
    else:
        if REVIEW_CSV.exists():
            import_review_rows(cases, REVIEW_CSV, known_ids)
        print(f"cases={len(cases)} type={dict(Counter(case['type'] for case in cases))}")


if __name__ == "__main__":
    main()
