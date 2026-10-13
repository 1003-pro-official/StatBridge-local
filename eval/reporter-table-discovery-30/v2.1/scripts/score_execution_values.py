"""v2.1 조회 값 채점: 저장된 조회 rows와 KOSIS 스냅샷을 비교한다(오프라인).

조회 실행기(`evaluate_execution.py`)가 남긴 `execution_rows.json`과
`kosis_snapshot.json`을 입력으로 받아 계열별 값 일치를 본다.

- 값 비교는 스냅샷 값의 소수 자릿수에 맞춘 허용오차를 쓴다(지수 2자리 → ±0.005).
- 결측은 결측으로 본다(0으로 대체하면 불일치).
- 조회한 계열 집합이 골드와 다르면 그 자체를 불일치로 기록한다(대체 조회 탐지).
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATASET = Path(__file__).resolve().parents[1]
GOLD = DATASET / "statbridge-reporter200.jsonl"
SNAPSHOT = DATASET / "kosis_snapshot.json"


def tolerance(value: str | None) -> float:
    text = str(value or "").strip().replace(",", "")
    if "." in text:
        decimals = len(text.split(".")[1])
        return 0.5 * (10 ** -decimals) + 1e-9
    return 0.5 + 1e-9


def values_equal(expected: str | None, actual: str | None) -> bool:
    left, right = (expected or "").strip(), (actual or "").strip()
    if not left or not right:
        return left == right
    try:
        return abs(float(left.replace(",", "")) - float(right.replace(",", ""))) <= tolerance(left)
    except ValueError:
        return left == right


def row_signature(row: dict) -> tuple:
    """응답의 C1..Cn 코드를 골드와 같은 objL1..objLn 표기로 맞춘다."""
    codes = tuple(sorted((f"objL{key[1:]}", str(row[key]))
                         for key in row if key.startswith("C") and key[1:].isdigit() and row.get(key)))
    return (str(row.get("TBL_ID")), codes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, required=True, help="조회 실행기의 execution_rows.json")
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    rows_by_case = json.loads(args.rows.read_text(encoding="utf-8"))
    cases = {json.loads(line)["id"]: json.loads(line)
             for line in GOLD.read_text(encoding="utf-8").splitlines()}

    # 스냅샷 인덱스: (case, table, codes) -> points
    index = {}
    for key, entry in snapshot["series"].items():
        codes = tuple(sorted(entry["classifications"].items()))
        index[(entry["case_id"], entry["table_id"], codes)] = entry

    results = []
    totals = Counter()
    for case_id, rows in rows_by_case.items():
        case = cases[case_id]
        plans = case["workflow_gold"]["classification_and_plan"]["series"]
        fetched = {}
        for row in rows:
            fetched.setdefault(row_signature(row), {})[str(row.get("PRD_DE"))] = row.get("DT")
        case_result = {"id": case_id, "series": [], "passed": True}
        for plan in plans:
            codes = tuple(sorted((plan["classifications"] or {}).items()))
            entry = index.get((case_id, plan["table_id"], codes))
            actual = fetched.get((plan["table_id"], codes))
            totals["series_expected"] += 1
            detail = {"table_id": plan["table_id"], "classifications": dict(codes)}
            if entry is None:
                detail.update(status="snapshot_missing")
                totals["snapshot_missing"] += 1
            elif actual is None:
                detail.update(status="not_fetched")
                totals["series_not_fetched"] += 1
                case_result["passed"] = False
            else:
                expected_points = entry["points"]
                mismatch = [key for key, value in expected_points.items()
                            if not values_equal(value, actual.get(key))]
                missing = [key for key in expected_points if key not in actual]
                extra = [key for key in actual if key not in expected_points]
                totals["points_compared"] += len(expected_points)
                totals["points_mismatched"] += sum(
                    1 for key, value in expected_points.items() if not values_equal(value, actual.get(key)))
                totals["points_missing"] += len(missing)
                totals["points_extra"] += len(extra)
                detail.update(status="ok" if not (mismatch or missing) else "value_mismatch",
                              rows=len(actual), expected_rows=entry["rows"],
                              mismatches=mismatch[:5], mismatch_count=len(mismatch),
                              missing=missing[:5], missing_count=len(missing), extra=len(extra),
                              unit=entry.get("unit"))
                if mismatch or missing or extra:
                    case_result["passed"] = False
                    totals["series_value_mismatch"] += 1
                else:
                    totals["series_value_ok"] += 1
            case_result["series"].append(detail)
        totals["cases"] += 1
        totals["cases_passed"] += 1 if case_result["passed"] else 0
        results.append(case_result)

    summary = dict(totals)
    summary["case_pass_rate"] = round(totals["cases_passed"] / totals["cases"], 4) if totals["cases"] else None
    summary["point_match_rate"] = (
        round(1 - totals["points_mismatched"] / totals["points_compared"], 4)
        if totals["points_compared"] else None)
    summary["snapshot_reference_date"] = snapshot.get("reference_date")
    output = args.output or ROOT / "evaluation_runs" / (
        "reporter200_v2.1_values_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
    output.mkdir(parents=True, exist_ok=True)
    (output / "value_scores.json").write_text(
        json.dumps({"summary": summary, "cases": results}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("산출물:", output / "value_scores.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
