"""Verify every gold plan against the real KOSIS API: parameters, returned period range, classification names.

This is the only check in the suite that leaves the catalog. It answers two questions the
catalog-consistency validator cannot: does the server accept these parameters, and does the
classification code we send mean what the catalog says it means.

Needs KOSIS_API_KEY (read from .env). The key is never printed or written.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATASET = Path(__file__).resolve().parents[1]
URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
GOLD = DATASET / "statbridge-reporter200.jsonl"

sys.path.insert(0, str(DATASET / "scripts"))
from evaluate_runtime import load_cases, stratified_sample  # noqa: E402


def api_key() -> str:
    text = (ROOT / ".env").read_text(encoding="utf-8")
    match = re.search(r"^KOSIS_API_KEY=(.+)$", text.strip(), re.M)
    if not match or not match.group(1).strip():
        raise SystemExit("KOSIS_API_KEY가 .env에 없습니다.")
    return match.group(1).strip()


def expected_rows(start: str, end: str, frequency: str) -> int:
    """기간 길이로 기대 행 수를 센다(월/분기/연)."""
    if frequency == "M":
        return (int(end[:4]) - int(start[:4])) * 12 + (int(end[4:]) - int(start[4:])) + 1
    if frequency == "Q":
        return (int(end[:4]) - int(start[:4])) * 4 + (int(end[4:]) - int(start[4:])) + 1
    return int(end) - int(start) + 1


def fetch(params: dict, key: str, timeout: int = 40) -> tuple[int, object]:
    query = urllib.parse.urlencode({**params, "apiKey": key})
    request = urllib.request.Request(f"{URL}?{query}", headers={"User-Agent": "StatBridge-eval-check"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}"


def check_plan(case_id: str, plan: dict, key: str) -> dict:
    status, payload = fetch(plan["exact_params"], key)
    record = {"case": case_id, "table": plan["table_id"], "http": status, "rows": None, "error": None,
              "returned_range": None, "label_mismatch": {}, "short_rows": None}
    if isinstance(payload, dict) and payload.get("err"):
        record["error"] = f"{payload.get('err')}: {payload.get('errMsg')}"
        return record
    if not isinstance(payload, list) or not payload:
        record["error"] = "empty payload"
        return record
    periods = sorted({item.get("PRD_DE") for item in payload})
    record["rows"] = len(payload)
    record["returned_range"] = [periods[0], periods[-1]]
    expected = expected_rows(plan["period_start"], plan["period_end"], plan["frequency"])
    record["short_rows"] = record["rows"] < expected
    for param, label in (plan["classification_labels"] or {}).items():
        actual = payload[0].get(f"C{param.replace('objL', '')}_NM")
        if actual != label:
            record["label_mismatch"][param] = {"gold": label, "api": actual}
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=int, default=20, help="0 or --all 이면 전체 계열 검증")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--delay", type=float, default=0.4)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    key = api_key()
    cases = load_cases(GOLD)
    selected = cases if args.all or args.sample == 0 else stratified_sample(cases)[:args.sample]
    plans = [(case["id"], plan) for case in selected
             for plan in case["workflow_gold"]["classification_and_plan"]["series"]]
    print(f"문항 {len(selected)}건 / 계열 {len(plans)}개 검증 (키는 출력하지 않음)")
    records = []
    for index, (case_id, plan) in enumerate(plans, 1):
        record = check_plan(case_id, plan, key)
        records.append(record)
        state = "OK" if record["rows"] and not record["label_mismatch"] else "확인"
        print(f"[{index}/{len(plans)}] {state} {case_id} {plan['table_id']} rows={record['rows']} "
              f"range={record['returned_range']} label_diff={record['label_mismatch'] or '-'} error={record['error']}",
              flush=True)
        time.sleep(args.delay)
    responded = [row for row in records if row["rows"]]
    summary = {
        "cases": len(selected), "plans": len(plans), "responded": len(responded),
        "no_response": [row for row in records if not row["rows"]],
        "classification_name_mismatch": {row["case"] + "/" + row["table"]: row["label_mismatch"]
                                         for row in responded if row["label_mismatch"]},
        "fewer_rows_than_requested": {row["case"] + "/" + row["table"] + "/" + str(row["rows"]):
                                     row["returned_range"] for row in responded if row["short_rows"]},
        "affected_tables": dict(Counter(row["table"] for row in records if row["label_mismatch"]).most_common()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    output = args.output or ROOT / "evaluation_runs" / (
        "reporter200_v2.1_kosis_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
    output.mkdir(parents=True, exist_ok=True)
    (output / "kosis_report.json").write_text(
        json.dumps({"summary": summary, "records": records}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print()
    print(f"응답 {summary['responded']}/{summary['plans']} | 분류 이름 불일치 {sum(len(v) for v in summary['classification_name_mismatch'].values())} | "
          f"행 부족 {len(summary['fewer_rows_than_requested'])}")
    print("영향 표:", summary["affected_tables"])
    print("보고서:", output / "kosis_report.json")
    return 0 if summary["responded"] == summary["plans"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
