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
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATASET = Path(__file__).resolve().parents[1]
GOLD = DATASET / "statbridge-reporter200.jsonl"
SNAPSHOT = DATASET / "kosis_snapshot.json"
EXECUTED_STATUS = "need_output_config"


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
               snapshot_entry: dict | None, injected_period: bool = False) -> dict:
    gold = case["workflow_gold"]
    status = gold["resolution"]["agent_status"]
    plans = gold["classification_and_plan"]["series"]
    checks: dict[str, bool] = {"http_success": http_status == 200}
    note = None
    if status != "resolved":
        # 조회 금지가 정답: 조회가 일어나지 않아야 한다.
        checks["not_executed"] = not session and body.get("status") != EXECUTED_STATUS
        checks["status_kept"] = body.get("status") == gold["resolution"]["api_status"]
    else:
        executed = body.get("status") == EXECUTED_STATUS and session is not None
        checks["execution_completed"] = executed
        if not executed:
            note = body.get("status")
            for key in ("tables_match", "period_match", "rows_present", "row_count_match"):
                checks[key] = False
        else:
            execution = (session.get("result") or {}).get("execution") or {}
            rows = execution.get("rows") or []
            applied = (body.get("period") or {})
            gold_frequency = plans[0]["frequency"] if plans else "M"
            want_start = to_iso(plans[0]["period_start"], gold_frequency)
            want_end = to_iso(plans[0]["period_end"], gold_frequency, end=True)
            selected = sorted({plan["table_id"] for plan in plans})
            actual_tables = sorted({str(plan["table_id"]) for plan in session_plans(session)})
            checks["tables_match"] = actual_tables == selected
            if injected_period:
                # 기간을 우리가 주입한 문항은 앱이 제공 범위에 맞춰 조정할 수 있다. 적용 기간이 제공 범위 안인지만 본다.
                available = body.get("_available") or {}
                checks["period_match"] = bool(applied.get("start")) and bool(applied.get("end")) and (
                    (not available.get("min") or str(applied.get("start")) >= str(available.get("min")))
                    and (not available.get("max") or str(applied.get("end")) <= str(available.get("max"))))
            else:
                checks["period_match"] = (str(applied.get("start")) == want_start
                                          and str(applied.get("end")) == want_end)
            checks["rows_present"] = len(rows) > 0
            want_rows = expected_rows(snapshot_entry, plans[0]) if plans else None
            checks["row_count_match"] = True if want_rows is None else len(rows) >= want_rows
            checks["period_range_match"] = bool(rows) and all(
                str(row.get("PRD_DE")) for row in rows[:1] + rows[-1:]) and (
                min(str(row.get("PRD_DE")) for row in rows) == str(plans[0]["period_start"])
                or len(rows) >= (want_rows or 0))
            checks["sources_recorded"] = bool(execution.get("sources") or rows)
    failed = [key for key, value in checks.items() if not value]
    return {"id": case["id"], "expected_status": status, "checks": checks, "failed_checks": failed,
            "passed": not failed, "note": note, "reached": checks.get("execution_completed", False),
            "row_count": len(((session or {}).get("result") or {}).get("execution", {}).get("rows") or []),
            "source": ((session or {}).get("result") or {}).get("execution", {}).get("sources")}


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

    cases = [json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines() if line]
    if args.only_discovery_passed:
        passed_ids = set()
        for path in args.discovery_run.glob("REPORTER30-*.json"):
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["agent_status"] == "resolved":
                passed_ids.add(record["id"])
        cases = [case for case in cases if case["id"] in passed_ids]
    if args.limit:
        cases = cases[:args.limit]
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {}

    # 조회는 허용하고 출력(차트) 생성만 금지한다.
    calls = {"output": 0}

    def output_guard(*a, **k):
        calls["output"] += 1
        raise RuntimeError("EVALUATION_BOUNDARY: output generation forbidden")

    if hasattr(api.agent.output_agent, "prepare"):
        api.agent.output_agent.prepare = output_guard

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
                else:
                    waited = None
            else:
                waited = None
            response = client.post("/api/query", json=body)
            data = response.json()
            session_id = data.get("outputSessionId")
            session = api.OUTPUT_SESSIONS.get(session_id) if session_id else None
            entry = snapshot.get(case["id"])
            data["_available"] = available
            row = score_case(case, http_status=response.status_code, body=data, session=session,
                             snapshot_entry=entry, injected_period=injected)
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
    summary = {
        "cases": len(scored),
        "discovery_passed_cases": sum(1 for row in scored if row["expected_status"] == "resolved"),
        "retrieval_reached": len(reached),
        "retrieval_contract_passed": sum(1 for row in reached if row["passed"]),
        "not_reached": sum(1 for row in scored if row["expected_status"] == "resolved" and not row["reached"]),
        "must_not_fetch_cases": len(must_not),
        "must_not_fetch_passed": sum(1 for row in must_not if row["passed"]),
        "full_chain_passed": sum(1 for row in scored if row["passed"]),
        "failed_checks": dict(sorted(Counter(key for row in scored for key in row["failed_checks"]).items())),
        "output_calls": calls["output"],
        "period_waits_observed": sum(1 for row in scored if row["waited_for_period"]),
    }
    (output_dir / "execution_scores.json").write_text(
        json.dumps({"summary": summary, "cases": scored}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (output_dir / "execution_rows.json").write_text(json.dumps(rows_dump, ensure_ascii=False) + "\n", encoding="utf-8")
    print()
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("산출물:", output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
