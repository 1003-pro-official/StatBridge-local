"""v2.1 조회(데이터 검색) 계층 평가기.

탐색 골드(표·항목·분류·기간)는 그대로 재사용하고, `/api/query`에 execute=true로 조회를 요청한 뒤
계약과 값을 채점한다. 값 비교는 KOSIS 스냅샷이 있을 때만 하고, 없으면 계약만 채점한다.

- 기간 명시 문항: 질의 텍스트의 기간을 그대로 쓴다(앱이 텍스트 기간을 해석).
- 기간 미지정 문항: 골드 계획 기간을 ISO로 주입해 조회까지 채점하고, 주입 없이 호출했을 때
  need_period로 대기하는지도 별도로 기록한다.
- no_match/역질문 문항: "조회 금지"가 정답이므로 조회가 일어나지 않아야 한다.

수치 호출을 허용하되 차트/출력 생성은 금지한다(조회 계층까지만 평가).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATASET = Path(__file__).resolve().parents[1]
GOLD = DATASET / "statbridge-reporter200.jsonl"
SNAPSHOT = DATASET / "kosis_snapshot.json"
EXECUTED_STATUS = "need_output_config"
CATALOG = ROOT / "src/agent/stat_dictionary/stat_language_dictionary.json"


def text_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def snapshot_identity(entry: dict) -> tuple:
    return (str(entry["case_id"]), str(entry["table_id"]), str(entry["item_id"]),
            tuple(sorted((entry.get("classifications") or {}).items())))


def load_snapshot_index(snapshot_path: Path, gold_path: Path = GOLD, catalog_path: Path = CATALOG) -> dict:
    """Validate frozen snapshot provenance and index entries by full gold series identity."""
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snapshot.get("gold_sha256") != text_sha256(gold_path):
        raise ValueError("snapshot gold_sha256 does not match the current gold dataset")
    if snapshot.get("catalog_sha256") != text_sha256(catalog_path):
        raise ValueError("snapshot catalog_sha256 does not match the current catalog")
    if not isinstance(snapshot.get("series"), dict):
        raise ValueError("snapshot series map is missing")
    index = {}
    for entry in snapshot["series"].values():
        key = snapshot_identity(entry)
        if key in index:
            raise ValueError(f"duplicate snapshot series identity: {key}")
        index[key] = entry
    cases = [json.loads(line) for line in gold_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    expected = {(case["id"], str(plan["table_id"]), str(plan["item_id"]),
                 tuple(sorted((plan.get("classifications") or {}).items())))
                for case in cases if case["workflow_gold"]["resolution"]["agent_status"] == "resolved"
                for plan in case["workflow_gold"]["classification_and_plan"]["series"]}
    missing, extra = expected - index.keys(), index.keys() - expected
    if missing or extra:
        raise ValueError(f"snapshot series identity mismatch: missing={len(missing)}, extra={len(extra)}")
    return {"metadata": {key: value for key, value in snapshot.items() if key != "series"}, "series": index}


def plan_identity(plan: dict) -> tuple:
    start = plan.get("period_start", plan.get("start_period"))
    end = plan.get("period_end", plan.get("end_period"))
    return (str(plan.get("table_id") or ""), str(plan.get("item_id") or ""),
            tuple(sorted((plan.get("classifications") or {}).items())), str(plan.get("frequency") or ""),
            str(start or ""), str(end or ""))


def requested_periods(plan: dict) -> set[str]:
    start, end, frequency = str(plan.get("period_start") or ""), str(plan.get("period_end") or ""), plan.get("frequency")
    if frequency == "M" and len(start) >= 6 and len(end) >= 6:
        y, m = int(start[:4]), int(start[4:6]); ey, em = int(end[:4]), int(end[4:6]); result = set()
        while (y, m) <= (ey, em):
            result.add(f"{y:04d}{m:02d}"); m += 1
            if m == 13: y, m = y + 1, 1
        return result
    if frequency == "Q" and len(start) >= 6 and len(end) >= 6:
        y, q = int(start[:4]), int(start[-1]); ey, eq = int(end[:4]), int(end[-1]); result = set()
        while (y, q) <= (ey, eq):
            result.add(f"{y}{q:02d}"); q += 1
            if q == 5: y, q = y + 1, 1
        return result
    if frequency == "A" and len(start) >= 4 and len(end) >= 4:
        return {str(year) for year in range(int(start[:4]), int(end[:4]) + 1)}
    return {start} if start else set()


def plan_row_matches(row: dict, plan: dict) -> bool:
    if str(row.get("TBL_ID") or "") != str(plan.get("table_id") or ""):
        return False
    if str(row.get("ITM_ID") or "") != str(plan.get("item_id") or ""):
        return False
    if str(row.get("_SOURCE_SERIES_ID") or "") != str(plan.get("table_id") or ""):
        return False
    if str(row.get("_FREQUENCY") or "") != str(plan.get("frequency") or ""):
        return False
    for index, (_key, value) in enumerate(sorted((plan.get("classifications") or {}).items()), 1):
        if str(row.get(f"C{index}") or "") != str(value):
            return False
    return True


def score_series(case_id: str, gold_plan: dict, runtime_plans: list[dict], rows: list[dict], snapshot_entry: dict | None) -> dict:
    target = plan_identity(gold_plan)
    matching = [plan for plan in runtime_plans if plan_identity(plan) == target]
    attributed = [row for row in rows if plan_row_matches(row, gold_plan)]
    actual_periods = {str(row.get("PRD_DE") or "") for row in attributed if row.get("PRD_DE")}
    expected_periods = set((snapshot_entry or {}).get("points", {}))
    missing, extra = sorted(expected_periods - actual_periods), sorted(actual_periods - expected_periods) if expected_periods else []
    checks = {"runtime_plan_match": len(matching) == 1, "rows_present": bool(attributed),
              "periods_match_snapshot": bool(expected_periods) and actual_periods == expected_periods}
    return {"case_id": case_id, "identity": target, "runtime_plan_count": len(matching),
            "expected_rows": len(expected_periods) if expected_periods else None, "fetched_rows": len(attributed),
            "actual_periods": sorted(actual_periods), "expected_periods": sorted(expected_periods),
            "missing_periods": missing, "extra_periods": extra, "checks": checks, "passed": all(checks.values())}


def install_output_guard(api: object, calls: dict) -> bool:
    output_agent = getattr(getattr(api, "agent", None), "output_agent", None)
    if output_agent is None or not callable(getattr(output_agent, "prepare", None)):
        return False
    def output_guard(*_args, **_kwargs):
        calls["output"] = calls.get("output", 0) + 1
        raise RuntimeError("EVALUATION_BOUNDARY: output generation forbidden")
    output_agent.prepare = output_guard
    return True


def evaluation_exit_code(summary: dict, expected_case_count: int, partial_run: bool) -> int:
    if partial_run or summary.get("cases") != expected_case_count:
        return 1
    if not summary.get("complete") or summary.get("contract_failures", 0):
        return 1
    if summary.get("output_guard_installed") is not True or summary.get("output_calls", 0):
        return 1
    return 0


def missing_series_for(case: dict) -> list[dict]:
    if case["workflow_gold"]["resolution"]["agent_status"] != "resolved":
        return []
    return [{"case_id": case["id"], "identity": plan_identity(plan), "runtime_plan_count": 0,
             "expected_rows": None, "fetched_rows": 0, "actual_periods": [], "expected_periods": [],
             "missing_periods": [], "extra_periods": [],
             "checks": {"runtime_plan_match": False, "rows_present": False, "periods_match_snapshot": False},
             "passed": False, "unexpected": False}
            for plan in case["workflow_gold"]["classification_and_plan"]["series"]]


def keep_missing_cases(cases: list[dict], scored: list[dict]) -> list[dict]:
    present = {row["id"] for row in scored}
    result = list(scored)
    for case in cases:
        if case["id"] not in present:
            result.append({"id": case["id"],
                           "expected_status": case["workflow_gold"]["resolution"]["agent_status"],
                           "checks": {"case_record_present": False}, "failed_checks": ["case_record_present"],
                           "passed": False, "reached": False, "note": "case absent from run output",
                           "row_count": 0, "series": missing_series_for(case), "waited_for_period": False})
    return result


def to_iso(period: str, frequency: str, *, end: bool = False) -> str:
    """KOSIS 기간을 UI가 쓰는 ISO 날짜로 바꾼다."""
    value = str(period)
    if frequency == "M" and len(value) >= 6:
        year, month = value[:4], int(value[4:6])
        return f"{year}-{month:02d}-{'31' if end else '01'}"
    if frequency == "Q" and len(value) >= 6:
        year, quarter = value[:4], int(value[4:6])
        month = quarter * 3 if end else quarter * 3 - 2
        return f"{year}-{month:02d}-{'31' if end else '01'}"
    return f"{value[:4]}-12-31" if end else f"{value[:4]}-01-01"


def expected_rows(snapshot_entry: dict | None, gold_plan: dict) -> int | None:
    """스냅샷이 있으면 실제 제공 구간의 행 수를, 없으면 None."""
    if not snapshot_entry:
        return None
    return snapshot_entry.get("rows")


def session_plans(session: dict | None) -> list[dict]:
    result = (session or {}).get("result") or {}
    return result.get("api_plans") or ([result["api_plan"]] if result.get("api_plan") else [])


def score_case(case: dict, *, http_status: int | None, body: dict, session: dict | None,
               snapshot_entry: dict | None, injected_period: bool = False,
               first_body: dict | None = None, injected_interval: dict | None = None) -> dict:
    gold = case["workflow_gold"]
    status = gold["resolution"]["agent_status"]
    plans = gold["classification_and_plan"]["series"]
    checks: dict[str, bool] = {"http_success": http_status == 200}
    note = None
    coverage_limited = False
    if status != "resolved":
        # 조회 금지가 정답: 조회가 일어나지 않아야 한다.
        checks["not_executed"] = not session and body.get("status") != EXECUTED_STATUS
        checks["status_kept"] = body.get("status") == gold["resolution"]["api_status"]
    else:
        executed = body.get("status") == EXECUTED_STATUS and session is not None
        checks["execution_completed"] = executed
        per_series = []
        if not executed:
            note = body.get("status")
            for key in ("plans_match", "period_match", "rows_present", "row_count_match"):
                checks[key] = False
            per_series = missing_series_for(case)
        else:
            execution = (session.get("result") or {}).get("execution") or {}
            rows = execution.get("rows") or []
            applied = (body.get("period") or {})
            runtime_plans = session_plans(session)
            actual_ids = [plan_identity(plan) for plan in runtime_plans]
            expected_ids = [plan_identity(plan) for plan in plans]
            checks["plans_match"] = (len(actual_ids) == len(set(actual_ids)) and
                                      sorted(actual_ids) == sorted(expected_ids))
            gold_frequency = plans[0]["frequency"] if plans else "M"
            want_start = to_iso(plans[0]["period_start"], gold_frequency)
            want_end = to_iso(plans[0]["period_end"], gold_frequency, end=True)
            gold_interval = {"start": want_start, "end": want_end}
            requested_interval = injected_interval or gold_interval
            checks["period_match"] = (str(applied.get("start")) == want_start
                                      and str(applied.get("end")) == want_end
                                      and (not injected_period or requested_interval == gold_interval))
            if injected_period:
                checks["period_followup_passed"] = bool(first_body and first_body.get("status") == "need_period")
            checks["rows_present"] = len(rows) > 0
            series_index = (snapshot_entry or {}).get("series", {})
            for plan in plans:
                key = (case["id"], str(plan["table_id"]), str(plan["item_id"]),
                       tuple(sorted((plan.get("classifications") or {}).items())))
                entry = series_index.get(key) if series_index else snapshot_entry
                per_series.append(score_series(case["id"], plan, runtime_plans, rows, entry))
            gold_identity_set = set(expected_ids)
            for item in per_series:
                item["unexpected"] = False
            unexpected_runtime = [plan for plan in runtime_plans if plan_identity(plan) not in gold_identity_set]
            for plan in unexpected_runtime:
                per_series.append({"case_id": case["id"], "identity": plan_identity(plan),
                                   "runtime_plan_count": 1, "expected_rows": None, "fetched_rows": 0,
                                   "actual_periods": [], "expected_periods": [], "missing_periods": [],
                                   "extra_periods": [], "checks": {"runtime_plan_match": False,
                                                                    "rows_present": False,
                                                                    "periods_match_snapshot": False},
                                   "passed": False, "unexpected": True})
            checks["row_count_match"] = bool(per_series) and all(item["passed"] for item in per_series)
            checks["unexpected_plans"] = len(runtime_plans) == len(plans) and all(
                actual_ids.count(identity) == expected_ids.count(identity) for identity in set(actual_ids + expected_ids))
            checks["period_range_match"] = all(item["checks"]["periods_match_snapshot"] for item in per_series)
            coverage_limited = any(
                bool(series_index.get((case["id"], str(plan["table_id"]), str(plan["item_id"]),
                                      tuple(sorted((plan.get("classifications") or {}).items()))))) and
                not requested_periods(plan).issubset(set(series_index[(case["id"], str(plan["table_id"]),
                    str(plan["item_id"]), tuple(sorted((plan.get("classifications") or {}).items())))].get("points", {})))
                for plan in plans) if series_index else False
            checks["sources_recorded"] = bool(execution.get("sources") or rows)
        if injected_period:
            checks.setdefault("period_followup_passed", bool(first_body and first_body.get("status") == "need_period"))
        else:
            checks["period_followup_passed"] = True
    failed = [key for key, value in checks.items() if not value]
    return {"id": case["id"], "expected_status": status, "checks": checks, "failed_checks": failed,
            "passed": not failed, "note": note, "reached": checks.get("execution_completed", False),
            "row_count": len(((session or {}).get("result") or {}).get("execution", {}).get("rows") or []),
            "source": ((session or {}).get("result") or {}).get("execution", {}).get("sources"),
            "series": per_series if status == "resolved" else [],
            "period_followup_passed": checks.get("period_followup_passed", True),
            "requested_period_coverage": (all(requested_periods(plan).issubset(
                set(next((item["actual_periods"] for item in per_series
                          if item["identity"] == plan_identity(plan)), []))) for plan in plans)
                if status == "resolved" and executed else False),
            "snapshot_coverage_limited": coverage_limited if status == "resolved" and executed else False}


def main() -> int:
    import sys

    sys.path[:0] = [str(ROOT / "src/agent"), str(ROOT / "src/backend"), str(ROOT / "tests")]
    import bridge_api as api
    from authenticated_client import TestClient

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--only-discovery-passed", action="store_true",
                        help="탐색이 통과했던 문항만 조회 채점(미도달 문항 제외)")
    parser.add_argument("--discovery-run", type=Path,
                        default=ROOT / "evaluation_runs" / "full_run_20261013")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    all_cases = [json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines() if line]
    cases = list(all_cases)
    if args.only_discovery_passed:
        passed_ids = set()
        for path in args.discovery_run.glob("REPORTER30-*.json"):
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["agent_status"] == "resolved":
                passed_ids.add(record["id"])
        cases = [case for case in cases if case["id"] in passed_ids]
    if args.limit:
        cases = cases[:args.limit]
    if not SNAPSHOT.exists():
        raise SystemExit("frozen KOSIS snapshot is required; refusing to run retrieval evaluation")
    snapshot_index = load_snapshot_index(SNAPSHOT)
    snapshot = snapshot_index["metadata"]

    # 조회는 허용하고 출력(차트) 생성만 금지한다.
    calls = {"output": 0}

    output_guard_installed = install_output_guard(api, calls)
    if not output_guard_installed:
        raise SystemExit("output guard target unavailable; refusing to run retrieval evaluation")

    output_dir = args.output_dir or ROOT / "evaluation_runs" / (
        "reporter200_v2.1_execution_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
    output_dir.mkdir(parents=True, exist_ok=True)
    scored, rows_dump = [], {}
    with TestClient(api.app) as client:
        for index, case in enumerate(cases, 1):
            gold = case["workflow_gold"]
            plans = gold["classification_and_plan"]["series"]
            body: dict = {"query": case["query"], "execute": True}
            injected = False
            available = {}
            waited_body = None
            injected_interval = None
            if gold["resolution"]["agent_status"] == "resolved" and plans:
                if gold["query_interpretation"]["period"] is None:
                    # 기간 미지정: 먼저 대기 상태를 확인하고, 이어서 골드 기간을 주입해 조회까지 본다.
                    response = client.post("/api/query", json=body)
                    waited_body = response.json()
                    waited = waited_body.get("status")
                    available = waited_body.get("availablePeriod") or {}
                    injected = True
                    frequency = plans[0]["frequency"]
                    body = {"query": case["query"], "execute": True,
                            "period_start": to_iso(plans[0]["period_start"], frequency),
                            "period_end": to_iso(plans[0]["period_end"], frequency, end=True)}
                    injected_interval = {"start": body["period_start"], "end": body["period_end"]}
                else:
                    waited = None
            else:
                waited = None
            response = client.post("/api/query", json=body)
            data = response.json()
            session_id = data.get("outputSessionId")
            session = api.OUTPUT_SESSIONS.get(session_id) if session_id else None
            data["_available"] = available
            case_entries = {key: value for key, value in snapshot_index["series"].items() if key[0] == case["id"]}
            row = score_case(case, http_status=response.status_code, body=data, session=session,
                             snapshot_entry={"series": case_entries}, injected_period=injected,
                             first_body=waited_body, injected_interval=injected_interval)
            row["applied_period"] = data.get("period")
            row["available_period"] = {key: available.get(key) for key in ("min", "max")} if available else None
            row["waited_for_period"] = waited == "need_period"
            if index == 1 and session:
                print("  [debug] session keys:", sorted(session))
                print("  [debug] session table ids:", session.get("selected_table_ids"))
                print("  [debug] session tables:", str(session.get("tables"))[:160])
            scored.append(row)
            if session:
                rows_dump[case["id"]] = ((session.get("result") or {}).get("execution") or {}).get("rows") or []
            print(f"[{index}/{len(cases)}] {case['id']} {data.get('status')} rows={row['row_count']} "
                  f"pass={row['passed']} failed={row['failed_checks']}", flush=True)

    reached = [row for row in scored if row["expected_status"] == "resolved" and row["reached"]]
    must_not = [row for row in scored if row["expected_status"] != "resolved"]
    scored_ids = {row["id"] for row in scored}
    scored = keep_missing_cases(all_cases, scored)
    expected_series = sum(len(case["workflow_gold"]["classification_and_plan"]["series"])
                          for case in all_cases if case["workflow_gold"]["resolution"]["agent_status"] == "resolved")
    expected_no_fetch = sum(1 for case in all_cases if case["workflow_gold"]["resolution"]["agent_status"] != "resolved")
    summary = {
        "cases": len(scored),
        "expected_cases": len(all_cases),
        "resolved_cases": sum(1 for case in all_cases if case["workflow_gold"]["resolution"]["agent_status"] == "resolved"),
        "expected_series": expected_series,
        "fetched_series": sum(1 for row in scored for item in row.get("series", [])
                              if item["checks"]["runtime_plan_match"] and item["fetched_rows"] > 0),
        "missing_series": sum(1 for row in scored for item in row.get("series", [])
                               if not item["checks"]["runtime_plan_match"] or item["fetched_rows"] == 0),
        "unexpected_series": sum(1 for row in scored for item in row.get("series", [])
                                  if item.get("unexpected", False)),
        "no_fetch_expected": expected_no_fetch,
        "discovery_passed_cases": sum(1 for row in scored if row["expected_status"] == "resolved"),
        "retrieval_reached": len(reached),
        "retrieval_contract_passed": sum(1 for row in reached if row["passed"]),
        "not_reached": sum(1 for row in scored if row["expected_status"] == "resolved" and not row["reached"]),
        "must_not_fetch_cases": len(must_not),
        "must_not_fetch_passed": sum(1 for row in must_not if row["passed"]),
        "full_chain_passed": sum(1 for row in scored if row["passed"]),
        "failed_checks": dict(sorted(Counter(key for row in scored for key in row["failed_checks"]).items())),
        "output_calls": calls["output"],
        "output_guard_installed": output_guard_installed,
        "period_waits_observed": sum(1 for row in scored if row["waited_for_period"]),
        "coverage_limited_cases": sum(1 for row in scored if row.get("snapshot_coverage_limited")),
        "complete": len(scored_ids) == len(all_cases) and len(scored) == len(all_cases),
        "contract_failures": sum(1 for row in scored if not row["passed"]),
        "provenance": {"dataset_sha256": text_sha256(GOLD), "catalog_sha256": text_sha256(CATALOG),
                       "snapshot_sha256": text_sha256(SNAPSHOT) if SNAPSHOT.exists() else None,
                       "snapshot_reference_date": snapshot.get("reference_date"),
                       "evaluator_sha256": text_sha256(Path(__file__)),
                       "execution_policy": "in_process_api_query_execute_true_no_output",
                       "injected_period_cases": [row["id"] for row in scored if row.get("waited_for_period")]},
    }
    partial_run = bool(args.limit or args.only_discovery_passed)
    summary["partial_run"] = partial_run
    (output_dir / "execution_scores.json").write_text(
        json.dumps({"summary": summary, "cases": scored}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (output_dir / "execution_rows.json").write_text(json.dumps(rows_dump, ensure_ascii=False) + "\n", encoding="utf-8")
    print()
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("산출물:", output_dir)
    return evaluation_exit_code(summary, len(all_cases), partial_run)


if __name__ == "__main__":
    raise SystemExit(main())
