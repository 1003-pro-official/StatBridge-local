"""Gold-only self-audit for the v2.1 case set: catalog contract and query evidence.

Read-only. It never edits gold and never grants human approval. Hard findings mean the gold
contradicts the published catalog contract; warnings are lexical hints a human should read.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATASET = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "src/agent/stat_dictionary/stat_language_dictionary.json"
GOLD = DATASET / "statbridge-reporter200.jsonl"


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8-sig"))


def clarification_contract(case: dict, catalog: dict) -> list[str]:
    """The expected clarification group must be reachable for this query, per the catalog lexicon."""
    resolution = case["workflow_gold"]["resolution"]
    if resolution["agent_status"] != "need_clarification":
        return []
    expected = resolution["clarification"]
    group = next((item for item in catalog["clarification_groups"] if item["id"] == expected.get("id")), None)
    if group is None:
        return [f"{case['id']}: 카탈로그에 없는 역질문 그룹 {expected.get('id')}"]
    query = normalize(case["query"])
    findings = []
    if not any(normalize(term) in query for term in group.get("trigger_terms", [])):
        findings.append(f"{case['id']}: [{group['id']}] 질의에 트리거 단어가 없어 이 역질문이 뜨지 않음")
    hit = [term for term in group.get("skip_if_terms", []) if normalize(term) in query]
    if hit:
        findings.append(f"{case['id']}: [{group['id']}] 제외 단어 포함으로 역질문이 건너뛰어짐 {hit}")
    return findings


def table_evidence(case: dict, catalog: dict) -> list[str]:
    """Warning-only: the chosen table should be reachable from the query wording."""
    workflow = case["workflow_gold"]
    plans = workflow["classification_and_plan"]["series"]
    if not plans:
        return []
    tables = {table["table_id"]: table for table in catalog["tables"]}
    query = normalize(case["query"])
    warnings = []
    for table_id in sorted({plan["table_id"] for plan in plans}):
        table = tables.get(table_id, {})
        terms = [table.get("table_name", "")] + list(table.get("aliases") or []) \
            + list(table.get("semantic_aliases") or []) + list(table.get("public_query_terms") or []) \
            + list(table.get("keywords") or [])
        if not any(normalize(term) and normalize(term) in query for term in terms):
            warnings.append(f"{case['id']}: [{table_id}] {table.get('table_name','?')} — 질의에서 이 표를 가리키는 단어를 찾지 못함")
    return warnings


def frequency_evidence(case: dict) -> list[str]:
    """Info-only: gold frequency comes from the table, so a query without a period word is expected."""
    workflow = case["workflow_gold"]
    if workflow["resolution"]["agent_status"] != "resolved":
        return []
    frequency = workflow["query_interpretation"]["frequency"]
    words = {"M": ("월", "매월"), "Q": ("분기", "3개월"), "A": ("연", "해")}
    query = normalize(case["query"])
    if frequency in words and not any(word in query for word in words[frequency]):
        return [f"{case['id']}: 주기 {frequency}를 표에서 유도했고 질의에 주기 표현은 없음"]
    return []


def no_match_evidence(case: dict, catalog: dict) -> list[str]:
    """Warning-only: an unmatched concept should not appear verbatim in table or value names."""
    workflow = case["workflow_gold"]
    if workflow["resolution"]["agent_status"] != "no_match":
        return []
    names = []
    for table in catalog["tables"]:
        names.append(normalize(table.get("table_name", "")))
        for dimension in table.get("dimensions") or []:
            names += [normalize(value["value_name"]) for value in dimension.get("values", [])]
    warnings = []
    for concept in workflow["table_discovery"]["unmatched_concepts"]:
        compact = normalize(concept)
        if compact and any(compact in name for name in names):
            warnings.append(f"{case['id']}: '{concept}'가 카탈로그 표·분류값 이름에 그대로 있음 — 부재 판정 재확인")
    return warnings


def audit(cases: list[dict], catalog: dict) -> dict:
    hard, warnings = [], []
    for case in cases:
        hard += clarification_contract(case, catalog)
        warnings += table_evidence(case, catalog)
        warnings += frequency_evidence(case)
        warnings += no_match_evidence(case, catalog)
    return {"cases": len(cases), "hard_findings": hard, "warnings": warnings,
            "hard_count": len(hard), "warning_count": len(warnings)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=GOLD)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    catalog = load_catalog()
    cases = [json.loads(line) for line in args.gold.read_text(encoding="utf-8").splitlines() if line]
    report = audit(cases, catalog)
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["gold"] = str(args.gold)
    output = args.output or ROOT / "evaluation_runs" / (
        "reporter200_v2.1_self_audit_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
    output.mkdir(parents=True, exist_ok=True)
    (output / "self_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"문항 {report['cases']} | 하드 위반 {report['hard_count']} | 경고 {report['warning_count']}")
    for finding in report["hard_findings"]:
        print("  HARD:", finding)
    for warning in report["warnings"]:
        print("  warn:", warning)
    print("보고서:", output / "self_audit.json")
    return 1 if report["hard_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
