"""Self-audit behaviour: hard findings block, lexical hints only warn."""
import copy
import json
from pathlib import Path

import pytest

from importlib.util import module_from_spec, spec_from_file_location

DATASET = Path(__file__).resolve().parents[1]
ROOT = DATASET.parents[2]


def load(name, filename):
    spec = spec_from_file_location(name, DATASET / "scripts" / filename)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit_module = load("reporter200_self_audit", "self_audit.py")
GOLD = [json.loads(line) for line in (DATASET / "statbridge-reporter200.jsonl")
        .read_text(encoding="utf-8").splitlines() if line]
CATALOG = json.loads((ROOT / "src/agent/stat_dictionary/stat_language_dictionary.json").read_text(encoding="utf-8-sig"))


def replace_query(case: dict, query: str) -> dict:
    clone = copy.deepcopy(case)
    clone["query"] = query
    return clone


def test_reference_set_has_exactly_one_hard_finding():
    report = audit_module.audit(GOLD, CATALOG)
    assert report["hard_count"] == 1, report["hard_findings"]
    assert "REPORTER30-V2.1-153" in report["hard_findings"][0]
    assert "[seasonal_adjustment]" in report["hard_findings"][0]


def test_unreachable_clarification_is_a_hard_finding():
    case = next(item for item in GOLD if item["workflow_gold"]["resolution"]["agent_status"] == "need_clarification")
    reachable = audit_module.clarification_contract(case, CATALOG)
    assert reachable == []
    broken = replace_query(case, "최근 실질 국내총생산이 분기별로 어떻게 움직였는지 보여주는 통계표를 찾아줘.")
    assert audit_module.clarification_contract(broken, CATALOG)


def test_skip_terms_block_a_clarification():
    case = next(item for item in GOLD
                if item["workflow_gold"]["resolution"]["agent_status"] == "need_clarification"
                and item["workflow_gold"]["resolution"]["clarification"]["id"] == "loan_type")
    blocked = replace_query(case, "가계대출 잔액 추이를 월별로 보여주는 통계표를 찾아줘.")
    findings = audit_module.clarification_contract(blocked, CATALOG)
    assert findings and "제외 단어" in findings[0]


def test_table_evidence_warns_only_when_the_query_lacks_a_link():
    case = next(item for item in GOLD if item["workflow_gold"]["classification_and_plan"]["series"])
    assert audit_module.table_evidence(case, CATALOG) == []
    assert audit_module.table_evidence(replace_query(case, "아무 관련 없는 문장"), CATALOG)


def test_frequency_hint_is_resolved_only():
    resolved = next(item for item in GOLD if item["workflow_gold"]["resolution"]["agent_status"] == "resolved")
    assert audit_module.frequency_evidence(replace_query(resolved, "주기 표현이 없는 질문")) != []
    no_match = next(item for item in GOLD if item["workflow_gold"]["resolution"]["agent_status"] == "no_match")
    assert audit_module.frequency_evidence(no_match) == []


def test_no_match_evidence_flags_a_concept_present_in_the_catalog():
    case = next(item for item in GOLD if item["workflow_gold"]["resolution"]["agent_status"] == "no_match")
    clone = copy.deepcopy(case)
    clone["workflow_gold"]["table_discovery"]["unmatched_concepts"] = ["본원통화"]
    assert audit_module.no_match_evidence(clone, CATALOG), "카탈로그 표 이름에 있는 개념은 경고여야 함"

    clone["workflow_gold"]["table_discovery"]["unmatched_concepts"] = ["존재하지않는지표"]
    assert audit_module.no_match_evidence(clone, CATALOG) == []
