"""Public v2.1 reporter golden-set runner. Runtime receives queries only; gold scores after inference.

Scoring policy is frozen in POLICY, hashed into the gold manifest and every run record,
and only a run that meets every threshold stores REPORT.md. Failed runs keep diagnostics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATASET = Path(__file__).resolve().parents[1]
GOLD = DATASET / "statbridge-reporter200.jsonl"
MANIFEST = DATASET / "dataset_manifest.json"
LEGACY_SCHEMA = "reporter30-discovery-2"
PAYLOAD_FIELDS = ("table_id", "item_id", "classifications", "exact_params")
RESUME_KEYS = ("policy_sha256", "dataset_sha256", "catalog_sha256", "source_sha256")

# Frozen before the first run. Editing a value changes POLICY_SHA256 and invalidates older runs.
POLICY = {
    "version": "v2.1-scoring-1",
    "legacy_requires_all": True,
    "resolved_min_rate": 0.95,
    "no_match_min_rate": 0.90,
    "clarification_min_count": 5,
    "requires_zero": ["boundary_violations", "http_failures", "unclassified_failures", "gold_suspect"],
    "repeat_sample_plan": {"resolved|single": 3, "resolved|same_table": 9, "resolved|multi_table": 2,
                           "no_match|": 5, "need_clarification|": 1},
    "case_timeout_seconds": 120,
}

# Every observable check maps to exactly one failure class; an unmapped check is an unclassified failure.
FAILURE_CLASS = {
    "http_success": "http_error",
    "agent_status": "status_misjudged",
    "api_boundary_status": "status_misjudged",
    "table_set": "table_set",
    "series_identity_set": "series_identity",
    "exact_api_params": "params",
    "numeric_not_executed": "boundary_violation",
    "chart_not_generated": "boundary_violation",
    "clarification_group": "clarification_group",
    "clarification_options": "clarification_options",
    "period_followup": "period_followup",
}


def policy_sha256(policy: dict | None = None) -> str:
    return hashlib.sha256(json.dumps(policy or POLICY, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def text_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_cases(gold_path: Path = GOLD) -> list[dict]:
    return [json.loads(line) for line in gold_path.read_text(encoding="utf-8").splitlines() if line]


def status_of(case: dict) -> str:
    return case["workflow_gold"]["resolution"]["agent_status"]


def composition_of(case: dict) -> str | None:
    plans = case["workflow_gold"]["classification_and_plan"]["series"]
    if not plans:
        return None
    if len(plans) == 1:
        return "single"
    return "same_table" if len({plan["table_id"] for plan in plans}) == 1 else "multi_table"


def stratified_sample(cases: list[dict], plan: dict | None = None) -> list[dict]:
    """Deterministic even-interval pick per stratum so reruns sample the same cases.

    shortcut: state and composition only; frequency (M/Q/A) coverage is not guaranteed.
    """
    plan = plan or POLICY["repeat_sample_plan"]
    picked = []
    for name, count in plan.items():
        status, _, composition = name.partition("|")
        pool = [case for case in sorted(cases, key=lambda item: item["id"])
                if status_of(case) == status and (composition_of(case) or "") == composition]
        if len(pool) < count:
            raise ValueError(f"stratum {name} has {len(pool)} cases, needs {count}")
        picked += [pool[index * len(pool) // count] for index in range(count)]
    return picked


def identities(plans: list[dict]) -> Counter:
    return Counter((plan["table_id"], plan["item_id"], tuple(sorted(plan["classifications"].items())))
                   for plan in plans)


def param_payloads(plans: list[dict]) -> list[str]:
    """Sorted payloads keep duplicate series identities with swapped periods from matching."""
    return sorted(json.dumps({field: plan[field] for field in PAYLOAD_FIELDS}, ensure_ascii=False, sort_keys=True)
                  for plan in plans)


def score_case(gold: dict, pred: dict) -> dict:
    workflow = gold["workflow_gold"]
    status = workflow["resolution"]["agent_status"]
    body = pred.get("boundary_response") or {}
    plans = pred.get("api_plans") or []
    gold_plans = workflow["classification_and_plan"]["series"]
    checks = {
        "http_success": pred.get("http_status") == 200,
        "agent_status": pred.get("agent_status") == status,
        "api_boundary_status": pred.get("api_status") == workflow["resolution"]["api_status"],
        "table_set": set(pred.get("selected_table_ids") or [])
                     == set(workflow["table_discovery"]["expected_table_ids"]),
        "series_identity_set": identities(plans) == identities(gold_plans),
        "exact_api_params": param_payloads(plans) == param_payloads(gold_plans),
        "numeric_not_executed": pred.get("numeric_calls") == 0,
        "chart_not_generated": pred.get("output_calls") == 0 and not body.get("chart"),
    }
    if status == "need_clarification":
        expected = workflow["resolution"]["clarification"]
        groups = body.get("clarifications") or []
        observed = next((group for group in groups
                         if expected.get("id") in (group.get("id"), group.get("clarification_id"))), None)
        checks["clarification_group"] = observed is not None
        checks["clarification_options"] = observed is not None and (
            {option["value"] for option in observed.get("options", [])}
            == {option["value"] for option in expected.get("options", [])})
    if status == "resolved":
        period_source = (body.get("periodSelection") or {}).get("source")
        checks["period_followup"] = (pred.get("api_status") == "need_period"
                                     and (period_source == "text")
                                     is (not workflow["post_discovery"]["period_selection_required"]))
    failed = [check for check, passed in checks.items() if not passed]
    failures = [FAILURE_CLASS.get(check, "unclassified") for check in failed]
    return {"id": gold["id"], "query": gold["query"], "repeat_of": pred.get("repeat_of"),
            "checks": checks, "failed_checks": failed, "failures": failures, "passed": not failed,
            "expected_status": status, "actual_status": pred.get("agent_status"),
            "expected_table_ids": workflow["table_discovery"]["expected_table_ids"],
            "actual_table_ids": pred.get("selected_table_ids"),
            "duration_s": pred.get("duration_s"), "error": pred.get("error")}


def summarize(scored: list[dict], repeats: list[dict], cases: list[dict], boundary: dict) -> dict:
    by_id = {case["id"]: case for case in cases}
    kind_stats = {}
    for status in ("resolved", "no_match", "need_clarification"):
        rows = [row for row in scored if row["expected_status"] == status]
        kind_stats[status] = {"cases": len(rows), "passed": sum(row["passed"] for row in rows)}
    composition = {name: {"cases": 0, "passed": 0} for name in ("single", "same_table", "multi_table")}
    frequency: dict[str, dict[str, int]] = {}
    for row in scored:
        case = by_id[row["id"]]
        bucket = composition.get(composition_of(case))
        if bucket is not None:
            bucket["cases"] += 1
            bucket["passed"] += row["passed"]
        freq = case["workflow_gold"]["query_interpretation"]["frequency"] or "none"
        frequency.setdefault(freq, {"cases": 0, "passed": 0})
        frequency[freq]["cases"] += 1
        frequency[freq]["passed"] += row["passed"]
    legacy = [row for row in scored if by_id[row["id"]]["schema_version"] == LEGACY_SCHEMA]
    first_checks = {row["id"]: row["checks"] for row in scored}
    durations = sorted(row["duration_s"] or 0.0 for row in scored)
    failures = Counter(name for row in scored for name in row["failures"])
    actual_no_match = [row for row in scored if row["actual_status"] == "no_match"]
    return {
        "cases": len(scored), "passed": sum(row["passed"] for row in scored),
        "failed": sum(not row["passed"] for row in scored),
        "check_results": {check: {"passed": sum(row["checks"].get(check) is True for row in scored),
                                  "total": sum(check in row["checks"] for row in scored)}
                          for check in sorted({check for row in scored for check in row["checks"]})},
        "by_kind": kind_stats, "by_composition": composition, "by_frequency": frequency,
        "legacy": {"cases": len(legacy), "passed": sum(row["passed"] for row in legacy)},
        "status_confusion": dict(sorted(Counter(f"{row['expected_status']}|{row['actual_status']}"
                                                for row in scored).items())),
        "no_match_recall": (kind_stats["no_match"]["passed"] / kind_stats["no_match"]["cases"]
                            if kind_stats["no_match"]["cases"] else None),
        "no_match_precision": (sum(row["expected_status"] == "no_match" for row in actual_no_match)
                               / len(actual_no_match)) if actual_no_match else None,
        "failures": dict(sorted(failures.items())),
        "unclassified_failures": failures.get("unclassified", 0),
        "boundary": boundary,
        "boundary_violations": boundary["numeric_calls"] + boundary["output_calls"],
        "http_failures": sum(row["checks"]["http_success"] is False for row in scored),
        "repeat_agreement": {"cases": len(repeats),
                             "agree": sum(row["checks"] == first_checks.get(row["id"]) for row in repeats),
                             "rate": (sum(row["checks"] == first_checks.get(row["id"]) for row in repeats)
                                      / len(repeats)) if repeats else None},
        "timing": {"total_seconds": round(sum(durations), 3),
                   "p50": round(durations[len(durations) // 2], 3) if durations else None,
                   "p95": round(durations[min(len(durations) - 1, math.ceil(len(durations) * 0.95) - 1)], 3)
                   if durations else None},
    }


def decide(summary: dict, gold_suspect: list[str], policy: dict | None = None) -> dict:
    policy = policy or POLICY
    reasons = []
    for field in policy["requires_zero"]:
        found = len(gold_suspect) if field == "gold_suspect" else summary.get(field, 0)
        if found:
            reasons.append(f"{field}={found}")
    if policy["legacy_requires_all"] and summary["legacy"]["passed"] != summary["legacy"]["cases"]:
        reasons.append(f"legacy={summary['legacy']['passed']}/{summary['legacy']['cases']}")
    for status, key in (("resolved", "resolved_min_rate"), ("no_match", "no_match_min_rate")):
        stats = summary["by_kind"][status]
        if stats["cases"] and stats["passed"] < math.ceil(policy[key] * stats["cases"]):
            reasons.append(f"{status}={stats['passed']}/{stats['cases']}")
    if summary["by_kind"]["need_clarification"]["passed"] < policy["clarification_min_count"]:
        reasons.append(f"need_clarification={summary['by_kind']['need_clarification']['passed']}"
                       f"/{policy['clarification_min_count']}")
    return {"saved": not reasons, "reasons": reasons}


def report_markdown(summary: dict, decision: dict, run_environment: dict, scored: list[dict]) -> str:
    lines = ["# 기자 질의 골든셋 v2.1 평가 결과", "",
             f"**{summary['passed']}/{summary['cases']} PASS, 실패 {summary['failed']}건, 판정 {'저장' if decision['saved'] else '보류'}.**",
             "", "`POST /api/query(query, execute=false)` → 실제 Agent → 카탈로그 표·항목·분류 선택 → 조회 계획 → HTTP 응답.",
             "표 탐색 경계까지 채점하며 수치 조회·CSV·차트·해석 문장은 채점하지 않는다. 공개 dev / ai-assisted / human_approved=false.",
             "", "## 판정", "", f"- 사유: {', '.join(decision['reasons']) if decision['reasons'] else '없음'}",
             "", "## 환경", ""]
    lines += [f"- {key}: `{value}`" for key, value in run_environment.items()]
    lines += ["", "## 집계", "", "| 지표 | 값 |", "|---|---|",
              f"| 전체 | {summary['passed']}/{summary['cases']} |",
              f"| v2 원본 30문항 | {summary['legacy']['passed']}/{summary['legacy']['cases']} |",
              f"| 반복 실행 일치 | {summary['repeat_agreement']['agree']}/{summary['repeat_agreement']['cases']} |",
              f"| 경계 위반 | {summary['boundary_violations']} |",
              f"| 미분류 실패 | {summary['unclassified_failures']} |",
              f"| 소요 P50/P95 | {summary['timing']['p50']}s / {summary['timing']['p95']}s |",
              "", "| 상태 | 통과 | 문항 |", "|---|---:|---:|"]
    lines += [f"| {status} | {stats['passed']} | {stats['cases']} |" for status, stats in summary["by_kind"].items()]
    lines += ["", "| 구성 | 통과 | 문항 |", "|---|---:|---:|"]
    lines += [f"| {name} | {stats['passed']} | {stats['cases']} |" for name, stats in summary["by_composition"].items()]
    lines += ["", "| 체크 | 통과 | 적용 |", "|---|---:|---:|"]
    lines += [f"| {check} | {stats['passed']} | {stats['total']} |" for check, stats in summary["check_results"].items()]
    failed = [row for row in scored if not row["passed"]]
    lines += ["", "## 실패 문항", ""]
    lines += ["없음"] if not failed else [
        f"- `{row['id']}` {row['expected_status']}→{row['actual_status']}: {', '.join(row['failures']) or '분류 없음'}"
        for row in failed]
    lines += ["", "## 남은 제약", "",
              "- 수치 관측값, 로컬 CSV, 차트 렌더링, 해석 문장, 인과 주장은 검증하지 않는다.",
              "- `no_match_reason`·`unmatched_concepts`·역질문 UI 문구는 채점하지 않는다.",
              "- 자동 채점 통과는 골드의 사람 승인을 뜻하지 않는다.", ""]
    return "\n".join(lines)


def write_results(output_dir: Path, result: dict, decision: dict, policy: dict | None = None) -> None:
    policy = policy or POLICY
    summary = result["summary"]
    (output_dir / "scores.json").write_text(json.dumps(
        {**summary, "decision": decision, "policy_sha256": policy_sha256(policy)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    report = report_markdown(summary, decision, result["environment"], result["cases"])
    (output_dir / "diagnostic.md").write_text(report, encoding="utf-8")
    (output_dir / "run_manifest.json").write_text(json.dumps(
        {"policy": policy, "policy_sha256": policy_sha256(policy), "decision": decision,
         "resumed": result.get("resumed", False),
         "dataset_sha256": result["environment"]["dataset_sha256"], "gold_suspect": result["gold_suspect"]},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if decision["saved"]:
        (output_dir / "REPORT.md").write_text(report, encoding="utf-8")


def run_environment(gold_path: Path) -> dict:
    import subprocess
    import sys

    source_files = ["src/agent/agent_runtime.py", "src/agent/catalog_request_planner.py", "src/agent/bridge_api.py",
                    "src/agent/stat_dictionary/stat_language_resolver.py", "src/agent/langgraph_workflow.py",
                    "src/agent/output_agent.py", "src/agent/mcp_gateway.py"]
    return {
        "source_sha256": {name: text_sha256(ROOT / name) for name in source_files},
        "catalog_sha256": text_sha256(ROOT / "src/agent/stat_dictionary/stat_language_dictionary.json"),
        "dataset_sha256": text_sha256(gold_path),
        "policy_sha256": policy_sha256(),
        "python": sys.executable,
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "endpoint": "POST /api/query (in-process TestClient, actual application)",
        "execution": False,
        "case_timeout_seconds": POLICY["case_timeout_seconds"],
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


def install_guards(api) -> dict:
    """Numeric or output execution must fail loudly; a missing guard target would fake a pass."""
    calls = {"numeric": 0, "output": 0}

    def numeric_guard(*args, **kwargs):
        calls["numeric"] += 1
        raise RuntimeError("EVALUATION_BOUNDARY: numeric execution forbidden")

    def output_guard(*args, **kwargs):
        calls["output"] += 1
        raise RuntimeError("EVALUATION_BOUNDARY: output generation forbidden")

    targets = [(api.agent.service, "get_statistics", numeric_guard),
               (api.agent.output_agent, "prepare", output_guard)]
    if hasattr(api, "mcp_gateway"):
        targets.append((api.mcp_gateway, "get_statistics", numeric_guard))
    for owner, name, replacement in targets:
        if not hasattr(owner, name):
            raise RuntimeError(f"EVALUATION_BOUNDARY: guard target missing: {name}")
        setattr(owner, name, replacement)
    return calls


def run_case(client, api, case: dict, calls: dict, timeout: int, repeat_of: str | None = None) -> dict:
    from concurrent.futures import ThreadPoolExecutor

    latest: dict = {}
    original_run, original_validate = api.agent.run, api.agent.validate_resolution

    def traced_run(*args, **kwargs):
        result = original_run(*args, **kwargs)
        latest["resolution"] = result
        return result

    def traced_validate(*args, **kwargs):
        result = original_validate(*args, **kwargs)
        latest["validated"] = result
        return result

    before, start = dict(calls), time.perf_counter()
    try:
        api.agent.run, api.agent.validate_resolution = traced_run, traced_validate
        with ThreadPoolExecutor(max_workers=1) as pool:
            # shortcut: a timed-out call thread is abandoned, not cancelled; thread reuse must stay one-per-case.
            response = pool.submit(
                lambda: client.post("/api/query", json={"query": case["query"], "execute": False})
            ).result(timeout=timeout)
        body, http_status, error = response.json(), response.status_code, None
    except Exception as exc:  # timeout, transport and application errors all score as http_error
        body, http_status, error = {}, None, f"{type(exc).__name__}: {exc}"
    finally:
        api.agent.run, api.agent.validate_resolution = original_run, original_validate
    resolution = latest.get("validated") or latest.get("resolution") or {}
    plans = resolution.get("api_plans") or ([resolution["api_plan"]] if resolution.get("api_plan") else [])
    return {"id": case["id"], "query": case["query"], "repeat_of": repeat_of, "http_status": http_status,
            "agent_status": resolution.get("status"), "api_status": body.get("status"),
            "selected_table_ids": sorted({plan["table_id"] for plan in plans}), "api_plans": plans,
            "boundary_response": body, "numeric_calls": calls["numeric"] - before["numeric"],
            "output_calls": calls["output"] - before["output"],
            "duration_s": round(time.perf_counter() - start, 3), "error": error,
            "completed_at": datetime.now(timezone.utc).isoformat()}


def write_run_inputs(output_dir: Path, cases: list[dict], run_environment: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "query_only_inputs.jsonl").write_text(
        "".join(json.dumps({"id": case["id"], "query": case["query"]}, ensure_ascii=False) + "\n"
                for case in cases), encoding="utf-8")
    (output_dir / "environment.json").write_text(
        json.dumps(run_environment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_suite(api, client, cases: list[dict], output_dir: Path, *, policy: dict | None = None,
              limit: int | None = None, resume: bool = False, gold_suspect: list[str] | None = None,
              progress=None) -> dict:
    """Run the cases plus the stratified repeats, then score, decide and write the run artifacts.

    The CLI and the review notebook share this function so the run sequence and the artifacts
    cannot drift apart. `limit` is a wiring-only prefix; `resume` reuses cases already on disk.
    """
    policy = policy or POLICY
    gold_suspect = list(gold_suspect or [])
    output_dir = Path(output_dir)
    run_env = run_environment(GOLD)
    if (output_dir / "environment.json").exists():
        if not resume:
            raise SystemExit(f"output dir already holds a run: {output_dir}")
        saved_env = json.loads((output_dir / "environment.json").read_text(encoding="utf-8"))
        for key in RESUME_KEYS:
            if saved_env.get(key) != run_env.get(key):
                raise SystemExit(f"cannot resume: {key} differs from the existing run")
        run_env = saved_env
    else:
        if output_dir.exists() and any(output_dir.iterdir()):
            raise SystemExit(f"output dir is not empty and holds no run: {output_dir}")
        write_run_inputs(output_dir, cases, run_env)
    calls = install_guards(api)
    schedule = [(case, None) for case in cases]
    schedule += [(case, case["id"]) for case in stratified_sample(cases)]
    if limit:
        schedule = schedule[:limit]
    predictions: list[dict] = []
    repeats: list[dict] = []
    with (output_dir / "endpoint_logs.jsonl").open("a", encoding="utf-8") as logs:
        for index, (case, repeat_of) in enumerate(schedule, 1):
            path = output_dir / (f"{case['id']}.repeat.json" if repeat_of else f"{case['id']}.json")
            if resume and path.exists():
                record = json.loads(path.read_text(encoding="utf-8"))
            else:
                record = run_case(client, api, case, calls, policy["case_timeout_seconds"], repeat_of)
                if record["http_status"] == 401:
                    raise SystemExit(
                        f"401 Unauthorized on {case['id']}: 인증 미들웨어가 /api/query를 보호하고 있습니다. "
                        "tests/authenticated_client.py의 로그인 클라이언트로 실행하세요.")
                path.write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n",
                                encoding="utf-8")
                logs.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            (repeats if repeat_of else predictions).append(record)
            if progress:
                progress(index, len(schedule), record)
    by_id = {case["id"]: case for case in cases}
    scored = [score_case(by_id[record["id"]], record) for record in predictions]
    repeat_scores = [score_case(by_id[record["id"]], record) for record in repeats]
    boundary = {"numeric_calls": calls["numeric"], "output_calls": calls["output"]}
    summary = summarize(scored, repeat_scores, cases, boundary)
    decision = decide(summary, gold_suspect, policy)
    write_results(output_dir, {"environment": run_env, "summary": summary, "cases": scored,
                               "gold_suspect": gold_suspect, "resumed": resume}, decision, policy)
    return {"output_dir": output_dir, "environment": run_env, "summary": summary, "decision": decision,
            "cases": scored, "repeats": repeat_scores, "gold_suspect": gold_suspect, "resumed": resume}


def main() -> int:
    import sys

    sys.path[:0] = [str(ROOT / "src/agent"), str(ROOT / "src/backend"), str(ROOT / "tests")]
    import bridge_api as api
    try:
        # 인증 미들웨어가 /api/query를 보호하므로 리포의 로그인 클라이언트를 씁니다.
        from authenticated_client import TestClient
    except ImportError as exc:
        raise SystemExit(f"tests/authenticated_client.py를 불러오지 못했습니다: {exc}") from exc

    parser = argparse.ArgumentParser(description="v2.1 discovery boundary evaluation; REPORT.md needs the frozen policy")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--limit", type=int, default=None, help="wiring-only prefix of the schedule; never a score")
    parser.add_argument("--resume", action="store_true", help="reuse case files already written in --output-dir")
    parser.add_argument("--gold-suspect-file", type=Path, default=None,
                        help="JSON list of case ids a reviewer judged suspect; any entry blocks the report")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cases = load_cases()
    if len(cases) != manifest["counts"]["cases"]:
        raise SystemExit("gold case count differs from the manifest")
    if manifest.get("scoring_policy_sha256") != policy_sha256():
        raise SystemExit("scoring policy differs from the gold manifest; re-validate the gold first")
    gold_suspect = json.loads(args.gold_suspect_file.read_text(encoding="utf-8")) if args.gold_suspect_file else []
    output_dir = args.output_dir or ROOT / "evaluation_runs" / (
        "reporter200_v2.1_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))

    started = time.monotonic()

    def report_progress(index: int, total: int, record: dict) -> None:
        elapsed = time.monotonic() - started
        remaining = elapsed / index * (total - index) if index else 0.0
        print(f"[{index}/{total}] {record['id']}{' (repeat)' if record['repeat_of'] else ''} "
              f"agent={record['agent_status']} api={record['api_status']} http={record['http_status']} "
              f"numeric={record['numeric_calls']} seconds={record['duration_s']} "
              f"| 경과 {elapsed / 60:.1f}m 예상 잔여 {remaining / 60:.1f}m", flush=True)

    with TestClient(api.app) as client:
        result = run_suite(api, client, cases, output_dir, limit=args.limit, resume=args.resume,
                           gold_suspect=gold_suspect, progress=report_progress)
    print("SCORES", json.dumps(result["summary"], ensure_ascii=False), flush=True)
    if not result["decision"]["saved"]:
        print("NOT_SAVED: " + ", ".join(result["decision"]["reasons"]), flush=True)
    return 0 if result["decision"]["saved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
