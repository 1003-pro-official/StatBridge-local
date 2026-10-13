"""v2.1 값 정본: 골드 계열의 KOSIS 값을 기준일로 고정해 스냅샷으로 저장한다.

조회 계층 채점의 값 비교는 이 파일을 정본으로 쓴다. KOSIS가 개정하면 이 파일을 갱신하고
기준일을 올린다(과거 실행과 값이 달라질 수 있음).

키는 .env에서 읽고 출력·저장하지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATASET = Path(__file__).resolve().parents[1]
GOLD = DATASET / "statbridge-reporter200.jsonl"
CATALOG = ROOT / "src/agent/stat_dictionary/stat_language_dictionary.json"
OUTPUT = DATASET / "kosis_snapshot.json"
URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"


def api_key() -> str:
    match = re.search(r"^KOSIS_API_KEY=(.+)$", (ROOT / ".env").read_text(encoding="utf-8").strip(), re.M)
    if not match or not match.group(1).strip():
        raise SystemExit("KOSIS_API_KEY가 .env에 없습니다.")
    return match.group(1).strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def fetch(params: dict, key: str, timeout: int = 45):
    query = urllib.parse.urlencode({**params, "apiKey": key})
    request = urllib.request.Request(f"{URL}?{query}", headers={"User-Agent": "StatBridge-snapshot"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"
    if isinstance(payload, dict) and payload.get("err"):
        return None, f"{payload.get('err')}: {payload.get('errMsg')}"
    return payload if isinstance(payload, list) else [], None


def series_key(case_id: str, plan: dict) -> str:
    parts = [f"{param}={code}" for param, code in sorted((plan["classifications"] or {}).items())]
    return "|".join([case_id, plan["table_id"], *parts])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delay", type=float, default=0.4)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    key = api_key()
    cases = [json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines() if line]
    plans = [(case["id"], plan) for case in cases
             for plan in case["workflow_gold"]["classification_and_plan"]["series"]]
    print(f"계열 {len(plans)}개 스냅샷 생성 (키는 저장하지 않음)")
    snapshot = {}
    failures = []
    for index, (case_id, plan) in enumerate(plans, 1):
        payload, error = fetch(plan["exact_params"], key)
        if error:
            failures.append({"case": case_id, "table": plan["table_id"], "error": error})
            print(f"[{index}/{len(plans)}] FAIL {case_id} {plan['table_id']} {error}", flush=True)
            time.sleep(args.delay)
            continue
        points = {str(row.get("PRD_DE")): row.get("DT") for row in payload}
        snapshot[series_key(case_id, plan)] = {
            "case_id": case_id, "table_id": plan["table_id"], "item_id": plan["item_id"],
            "classifications": plan["classifications"], "frequency": plan["frequency"],
            "period_start": plan["period_start"], "period_end": plan["period_end"],
            "unit": (payload[0].get("UNIT_NM") if payload else None),
            "prd_se": (payload[0].get("PRD_SE") if payload else None),
            "rows": len(payload), "points": points,
        }
        print(f"[{index}/{len(plans)}] OK {case_id} {plan['table_id']} rows={len(payload)} "
              f"range={min(points) if points else '-'}~{max(points) if points else '-'}", flush=True)
        time.sleep(args.delay)
    document = {
        "reference_date": datetime.now(timezone.utc).date().isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "KOSIS openapi Param/statisticsParameterData.do (getList)",
        "gold": str(GOLD.relative_to(ROOT)).replace("\\", "/"),
        "gold_sha256": digest(GOLD),
        "catalog_sha256": digest(CATALOG),
        "series_count": len(snapshot),
        "failures": failures,
        "series": snapshot,
    }
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    size = args.output.stat().st_size
    print(f"\n저장: {args.output} ({size/1024:.0f}KB) | 계열 {len(snapshot)} | 실패 {len(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
