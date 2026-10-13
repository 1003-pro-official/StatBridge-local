"""Build the v2.1 public reporter golden set: v2's 30 cases verbatim plus augmented cases.

Gold values come only from the public catalog; research artifacts supply the topic
and are recorded as hash-verified references. No runtime prediction is read.
"""
from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATASET = Path(__file__).resolve().parents[1]
V2 = DATASET.parent / "v2"
CATALOG = ROOT / "src/agent/stat_dictionary/stat_language_dictionary.json"
RESEARCH_DIR = ROOT / "research/그림표-분석"
SCHEMA = "reporter200-discovery-2.1"
LEGACY_SCHEMA = "reporter30-discovery-2"
REFERENCE_DATE = "2026-10-13"
RELATIONSHIP = "theme_adaptation_not_original_figure_reproduction"
ROLE = "journalistic_context_only_not_numeric_or_table_id_gold"
INTENT = ["statistical_table_discovery"]
SLOT_MATCHING = "semantic_equivalence_allowed_for_names; preserve_metric_and_scope"
NULL_SEMANTICS = "no_explicit_filter; do_not_guess_a_more_specific_target"
EXCLUDED = ["numeric_observations", "chart_rendering", "interpretation_text", "causal_claims"]

_validate_spec = importlib.util.spec_from_file_location(
    "reporter200_validate", DATASET / "scripts/validate.py")
validate = importlib.util.module_from_spec(_validate_spec)
_validate_spec.loader.exec_module(validate)

# (id, topic, status, query, period, series, research figure ids)
# series: (label, metric, target, measure, table_id, {api_param: catalog value_name})
SPECS: list[dict] = [
    {"id": "031", "topic": "물가·심리", "status": "resolved", "period": None,
     "query": "요즘 소비자들의 경기 판단이 어떤지 월별로 보여주는 지표를 찾아줘. 소비자심리지수가 궁금해.",
     "series": [("소비자심리지수", "소비자심리지수", "전체", "지수", "DT_511Y002", {"objL1": "소비자심리지수", "objL2": "전체"})],
     "research": ["BOK-20260312-637f0cd4b14e-그림-68d750eb52ddd08a"]},
    {"id": "032", "topic": "경기·기업심리", "status": "resolved", "period": ("2021", "2025"),
     "query": "2021년 1월부터 2025년 12월까지 제조업 전체의 업황 실적 BSI가 어떻게 움직였는지 월별로 볼 수 있는 통계표를 찾아줘.",
     "series": [("제조업 업황 실적 BSI", "기업경기실사지수", "제조업 전체", "업황 실적", "DT_512Y013",
                 {"objL1": "제 조 업", "objL2": "업황실적BSI 1)"})],
     "research": ["BOK-20251127-47f2bbf60a2a-그림-2b4839345998a674"]},
    {"id": "033", "topic": "지급결제", "status": "resolved", "period": ("2022", "2025"),
     "query": "2022년 1월부터 2025년 12월까지 신용카드 결제 금액이 월별로 얼마였는지 확인할 통계표를 찾아줘.",
     "series": [("신용카드 결제 금액", "지급수단 이용실적", "신용카드", "금액", "DT_602Y002",
                 {"objL1": "신용카드", "objL2": "금액"})],
     "research": ["BOK-20250911-df4c93f2f7f1-그림-5c52277ad2671056"]},
    {"id": "034", "topic": "국제수지", "status": "resolved", "period": ("2020", "2025"),
     "query": "2020년 1월부터 2025년 12월까지 상품수지가 월별로 얼마였는지 확인할 통계표를 찾아줘.",
     "series": [("상품수지", "국제수지", "상품수지", "금액", "DT_301Y013", {"objL1": "상품수지"})],
     "research": ["BOK-20241128-e4915bc41ec3-그림-1da53612c381cef6"]},
    {"id": "035", "topic": "국제수지", "status": "resolved", "period": ("2021", "2025"),
     "query": "2021년 1월부터 2025년 12월까지 상품수지와 서비스수지를 한 그래프에서 비교할 수 있게 월별 자료를 찾아줘.",
     "series": [("상품수지", "국제수지", "상품수지", "금액", "DT_301Y013", {"objL1": "상품수지"}),
                ("서비스수지", "국제수지", "서비스수지", "금액", "DT_301Y013", {"objL1": "서비스수지"})],
     "research": ["BOK-20231130-4a0e2a7937e7-그림-4b24b8da64ef7aeb"]},
    {"id": "036", "topic": "국제수지", "status": "resolved", "period": ("2021", "2025"),
     "query": "2021년 1월부터 2025년 12월까지 본원소득수지와 이전소득수지의 월별 흐름을 나란히 비교하고 싶어.",
     "series": [("본원소득수지", "국제수지", "본원소득수지", "금액", "DT_301Y013", {"objL1": "본원소득수지"}),
                ("이전소득수지", "국제수지", "이전소득수지", "금액", "DT_301Y013", {"objL1": "이전소득수지"})],
     "research": ["BOK-20240222-9ce98d16ec74-그림-16f4465e9b3a8d2f"]},
    {"id": "037", "topic": "금융안정·금리", "status": "resolved", "period": ("2022", "2025"),
     "query": "2022년 1월부터 2025년 12월까지 예금은행의 기업대출 금리와 가계대출 금리를 신규취급액 기준으로 비교할 월별 통계표를 찾아줘.",
     "series": [("예금은행 기업대출 금리", "예금은행 대출금리", "기업대출", "금리", "DT_121Y006", {"objL1": "기업대출"}),
                ("예금은행 가계대출 금리", "예금은행 대출금리", "가계대출", "금리", "DT_121Y006", {"objL1": "가계대출"})],
     "research": ["BOK-20231130-4a0e2a7937e7-그림-d0b85f8275403418"]},
    {"id": "038", "topic": "금융안정·금리", "status": "resolved", "period": ("2022", "2025"),
     "query": "2022년 1월부터 2025년 12월까지 예금은행의 대기업대출 금리와 중소기업대출 금리를 신규취급액 기준으로 비교할 통계표를 찾아줘.",
     "series": [("대기업대출 금리", "예금은행 대출금리", "대기업대출", "금리", "DT_121Y006", {"objL1": "대기업대출"}),
                ("중소기업대출 금리", "예금은행 대출금리", "중소기업대출", "금리", "DT_121Y006", {"objL1": "중소기업대출"})],
     "research": ["BOK-20240222-9ce98d16ec74-그림-56880865911e7c75"]},
    {"id": "039", "topic": "금융안정·금리", "status": "resolved", "period": None,
     "query": "잔액 기준으로 대기업과 중소기업의 대출금리 차이가 최근 얼마나 벌어졌는지 월별로 확인할 통계표를 찾아줘.",
     "series": [("대기업대출 금리", "예금은행 대출금리", "대기업대출", "금리", "DT_121Y015", {"objL1": "대기업대출"}),
                ("중소기업대출 금리", "예금은행 대출금리", "중소기업대출", "금리", "DT_121Y015", {"objL1": "중소기업대출"})],
     "research": ["BOK-20241224-01fdc1c04384-그림-e7bade30223954fd"]},
    {"id": "040", "topic": "금융안정·금리", "status": "resolved", "period": ("2021", "2025"),
     "query": "2021년 1월부터 2025년 12월까지 예금은행 정기예금 금리와 정기적금 금리를 신규취급액 기준으로 비교할 월별 통계표를 찾아줘.",
     "series": [("정기예금 금리", "예금은행 수신금리", "정기예금", "금리", "DT_121Y002", {"objL1": "정기예금"}),
                ("정기적금 금리", "예금은행 수신금리", "정기적금", "금리", "DT_121Y002", {"objL1": "정기적금"})],
     "research": ["BOK-20260312-637f0cd4b14e-그림-a3bc79ccfe059bc4"]},
    {"id": "041", "topic": "금융안정·가계신용", "status": "resolved", "period": ("2020", "2025"),
     "query": "2020년 1분기부터 2025년 4분기까지 예금은행과 상호저축은행의 가계신용 잔액을 나란히 비교할 분기 통계표를 찾아줘.",
     "series": [("예금은행 가계신용", "가계신용", "예금은행", "잔액", "DT_151Y001", {"objL1": "예금은행"}),
                ("상호저축은행 가계신용", "가계신용", "상호저축은행", "잔액", "DT_151Y001", {"objL1": "상호저축은행"})],
     "research": ["BOK-20241224-01fdc1c04384-그림-ecbf55cf9c52bf9a"]},
    {"id": "042", "topic": "경기·투자", "status": "resolved", "period": ("2020", "2025"),
     "query": "2020년 1분기부터 2025년 4분기까지 계절조정 실질 기준 건설투자와 설비투자 수준을 비교할 분기 통계표를 찾아줘.",
     "series": [("건설투자", "국내총생산에 대한 지출", "건설투자", "실질 계절조정", "DT_200Y108", {"objL1": "건설투자"}),
                ("설비투자", "국내총생산에 대한 지출", "설비투자", "실질 계절조정", "DT_200Y108", {"objL1": "설비투자"})],
     "research": ["BOK-20231130-4a0e2a7937e7-그림-1209a1a5e32cf69b"]},
    {"id": "043", "topic": "경기·성장기여도", "status": "resolved", "period": ("2020", "2025"),
     "query": "2020년 1분기부터 2025년 4분기까지 분기 성장에 대한 내수와 순수출의 기여도를 비교할 통계표를 찾아줘.",
     "series": [("내수 기여도", "지출항목별 성장기여도", "내수", "기여도", "DT_200Y125", {"objL1": "내수"}),
                ("순수출 기여도", "지출항목별 성장기여도", "순수출", "기여도", "DT_200Y125", {"objL1": "순수출"})],
     "research": ["BOK-20241128-e4915bc41ec3-그림-671d9fea5ccfcb31"]},
    {"id": "044", "topic": "경기·소비심리", "status": "resolved", "period": ("2021", "2025"),
     "query": "2021년 1월부터 2025년 12월까지 소비자들의 현재 생활형편 판단과 생활형편 전망을 월별로 비교할 통계표를 찾아줘.",
     "series": [("현재생활형편CSI", "소비자동향조사", "현재생활형편", "CSI", "DT_511Y002", {"objL1": "현재생활형편CSI", "objL2": "전체"}),
                ("생활형편전망CSI", "소비자동향조사", "생활형편전망", "CSI", "DT_511Y002", {"objL1": "생활형편전망CSI", "objL2": "전체"})],
     "research": ["BOK-20260312-637f0cd4b14e-그림-74cc71aefca9dcfe"]},
    {"id": "045", "topic": "지급결제", "status": "resolved", "period": None,
     "query": "소액결제시스템을 통한 결제 규모를 최근 월별로 건수와 금액 두 가지로 함께 보고 싶어.",
     "series": [("소액결제 건수", "결제시스템별 통계", "소액결제시스템", "건수", "DT_602Y001", {"objL1": "소액결제시스템", "objL2": "건수"}),
                ("소액결제 금액", "결제시스템별 통계", "소액결제시스템", "금액", "DT_602Y001", {"objL1": "소액결제시스템", "objL2": "금액"})],
     "research": ["BOK-20250421-8d4a319823d7-그림-b89e2b45f09078fb"]},
    {"id": "046", "topic": "금융안정·가계부채", "status": "resolved", "period": ("2021", "2025"),
     "query": "2021년 1월부터 2025년 12월까지 주택담보대출에서 고정금리와 변동금리가 차지하는 비중을 신규취급액 기준으로 비교할 월별 통계표를 찾아줘.",
     "series": [("주택담보대출 고정금리 비중", "고정 및 변동금리대출 비중", "주택담보대출-고정금리대출", "비중", "DT_121Y010",
                 {"objL1": "주택담보대출-고정금리대출 5)"}),
                ("주택담보대출 변동금리 비중", "고정 및 변동금리대출 비중", "주택담보대출-변동금리대출", "비중", "DT_121Y010",
                 {"objL1": "주택담보대출-변동금리대출 5)"})],
     "research": ["BOK-20241224-01fdc1c04384-그림-827f5aec5d0a5777"]},
    {"id": "047", "topic": "금융안정·대출행태", "status": "resolved", "period": ("2019", "2025"),
     "query": "2019년 1분기부터 2025년 4분기까지 국내은행이 평가한 대기업 대출태도와 대기업 신용위험을 나란히 비교할 분기 통계표를 찾아줘.",
     "series": [("국내은행 대기업 대출태도", "대출행태서베이", "국내은행-대기업", "지수", "DT_514Y001", {"objL1": "국내은행-대기업"}),
                ("국내은행 대기업 신용위험", "대출행태서베이", "국내은행-대기업", "지수", "DT_514Y002", {"objL1": "국내은행-대기업"})],
     "research": ["BOK-20241128-e4915bc41ec3-그림-3edd55051744d771"]},
    {"id": "048", "topic": "금융안정·금리", "status": "resolved", "period": ("2022", "2025"),
     "query": "2022년 1월부터 2025년 12월까지 예금은행 가계대출 금리를 신규취급액 기준과 잔액 기준으로 나눠 비교할 월별 통계표를 찾아줘.",
     "series": [("가계대출 금리(신규취급액)", "예금은행 대출금리", "가계대출", "금리", "DT_121Y006", {"objL1": "가계대출"}),
                ("가계대출 금리(잔액)", "예금은행 대출금리", "가계대출", "금리", "DT_121Y015", {"objL1": "가계대출 2)"})],
     "research": ["BOK-20251223-4051c44575eb-그림-a1463055234f6728"]},
    {"id": "049", "topic": "경기·해외", "status": "no_match", "period": None,
     "query": "글로벌 제조업 경기를 보여주는 PMI 지수의 월별 흐름을 한국은행 통계표에서 찾아줘.",
     "series": [("글로벌 PMI", "PMI", "글로벌 제조업", "지수", None, {})],
     "unmatched": ["글로벌 PMI"], "no_match_reason": "PMI는 CPB·JPM 등 외부기관 지표로 한국은행 KOSIS 카탈로그에 포함되지 않음.",
     "research": ["BOK-20231130-4a0e2a7937e7-그림-ee9b8ff5debe1555"]},
    {"id": "050", "topic": "금리·시장", "status": "no_match", "period": None,
     "query": "국고채 10년물 금리의 월별 추이를 확인할 수 있는 한국은행 통계표를 찾아줘.",
     "series": [("국고채 10년물 금리", "국고채 금리", "국고채 10년물", "금리", None, {})],
     "unmatched": ["국고채 10년물 금리"], "no_match_reason": "국고채금리는 금융투자협회 고시 자료로 한국은행 KOSIS 카탈로그에 포함되지 않음.",
     "research": ["BOK-20241224-01fdc1c04384-그림-9a508c932cc8280f"]},
    {"id": "051", "topic": "금리·해외", "status": "no_match", "period": None,
     "query": "주요국 국채금리와 리스크 프리미엄을 함께 비교한 한국은행 통계표를 찾아줘.",
     "series": [("주요국 국채금리", "국채금리", "주요국", "금리", None, {})],
     "unmatched": ["주요국 국채금리", "리스크 프리미엄"],
     "no_match_reason": "주요국 국채금리·리스크 프리미엄은 Bloomberg·JP Morgan 등 외부 자료로 카탈로그에 포함되지 않음.",
     "research": ["BOK-20240329-1d931f5947ea-표-fb54a8a3a3db583b"]},
    {"id": "052", "topic": "금융안정·가계부채", "status": "no_match", "period": None,
     "query": "취약차주가 전체 가계대출에서 차지하는 비중을 월별로 보여주는 한국은행 통계표를 찾아줘.",
     "series": [("취약차주 비중", "취약차주 비중", "취약차주", "비중", None, {})],
     "unmatched": ["취약차주 비중"],
     "no_match_reason": "취약차주 비중은 가계부채DB 기반 한국은행 시산 결과로 정기 카탈로그 통계표가 아님.",
     "research": ["BOK-20231228-62758008cadf-그림-851f1bb9ebad7be9"]},
    {"id": "053", "topic": "금융안정·가계부채", "status": "no_match", "period": None,
     "query": "다주택자 주택담보대출 만기연장 제한 조치의 대상과 조건을 수치로 정리한 통계표를 찾아줘.",
     "series": [("만기연장 제한 조치", "주택담보대출 규제", "다주택자", "대상·조건", None, {})],
     "unmatched": ["다주택자 주택담보대출 만기연장 제한 조치"],
     "no_match_reason": "금융위원회 제도·조치 요약으로 한국은행 KOSIS 카탈로그 통계표가 아님.",
     "research": ["BOK-20260624-91d0ea2e38e8-표-d04a392dd4eb3247"]},
    {"id": "054", "topic": "부동산·가격", "status": "no_match", "period": None,
     "query": "아파트 실거래가격지수의 월별 상승률을 한국은행 통계표에서 확인하고 싶어.",
     "series": [("아파트 실거래가격지수 상승률", "주택가격지수", "아파트", "상승률", None, {})],
     "unmatched": ["아파트 실거래가격지수"],
     "no_match_reason": "주택 실거래가격지수는 국토교통부·한국부동산원 자료로 한국은행 KOSIS 카탈로그에 없음.",
     "research": ["BOK-20241128-e4915bc41ec3-그림-9fde46de2f17a15f"]},
    {"id": "055", "topic": "물가·심리", "status": "need_clarification", "period": None,
     "query": "물가가 최근 어떻게 움직였는지 보여주는 통계표를 찾아줘.",
     "series": [("물가 지표", "물가", None, None, None, {})],
     "clarification_group": "price_index_type",
     "research": ["BOK-20231130-4a0e2a7937e7-그림-7df953b0be673df2"]},
]


def research_index() -> dict[str, dict]:
    """figure id -> hash-verified reference inside the committed research tree."""
    index: dict[str, dict] = {}
    for path in sorted(RESEARCH_DIR.rglob("*.md")):
        if "백업" in path.parts:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        sha = validate.text_sha256(path)
        for number, line in enumerate(lines, 1):
            if "- 결과물ID:" not in line:
                continue
            figure_id = line.split("`")[1]
            heading = next((text.strip() for text in reversed(lines[:number - 1]) if text.startswith("### ")), "")
            index[figure_id] = {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "line": number - 2,
                                "heading": heading, "figure_id": figure_id, "sha256": sha}
    return index


def references(spec: dict, index: dict[str, dict]) -> list[dict]:
    out = []
    for figure_id in spec["research"]:
        ref = index.get(figure_id)
        if ref is None:
            raise SystemExit(f"{spec['id']}: unknown research figure {figure_id}")
        out.append({**ref, "relationship": RELATIONSHIP, "role": ROLE})
    return out


def table(tables: dict[str, dict], table_id: str) -> dict:
    found = tables.get(table_id)
    if found is None:
        raise SystemExit(f"unknown table {table_id}")
    return found


def class_codes(entry: dict, tables: dict[str, dict]) -> dict[str, dict[str, str]]:
    found = table(tables, entry[4])
    dimensions = {dimension["api_param"]: dimension for dimension in found.get("dimensions", [])}
    if set(dimensions) != set(entry[5]):
        raise SystemExit(f"{entry[4]}: dimensions {sorted(dimensions)} != {sorted(entry[5])}")
    codes, labels = {}, {}
    for param, name in entry[5].items():
        match = next((value for value in dimensions[param]["values"] if value["value_name"] == name), None)
        if match is None:
            raise SystemExit(f"{entry[4]}.{param}: unknown value name {name!r}")
        codes[param] = match["value_id"]
        labels[param] = match["value_name"]
    return {"codes": codes, "labels": labels}


def meaning(entry: tuple) -> dict:
    return {"label": entry[0], "metric": entry[1], "target": entry[2], "measure": entry[3],
            "measurement_basis": None, "qualifiers": {}}


def build_case(spec: dict, tables: dict[str, dict], index: dict[str, dict]) -> dict:
    case_id = f"REPORTER30-V2.1-{spec['id']}"
    meanings = [meaning(entry) for entry in spec["series"]]
    period = spec.get("period")
    period_gold = None if period is None else {"start": f"{period[0]}-01-01", "end": f"{period[1]}-12-31",
                                               "inclusive": True, "source": "explicit"}
    catalog_sha = validate.text_sha256(CATALOG)
    interpretation = {"user_intent": INTENT, "period": period_gold, "frequency": None,
                      "comparison": {"required": len(meanings) > 1,
                                     "mode": "series_comparison" if len(meanings) > 1 else "none"},
                      "series": meanings, "slot_matching": SLOT_MATCHING, "null_semantics": NULL_SEMANTICS}

    if spec["status"] == "resolved":
        frequencies = {table(tables, entry[4])["prd_se"] for entry in spec["series"]}
        if len(frequencies) != 1:
            raise SystemExit(f"{case_id}: mixed frequencies {frequencies}")
        frequency = frequencies.pop()
        interpretation["frequency"] = frequency
        probe = {"id": case_id, "query": spec["query"],
                 "workflow_gold": {"query_interpretation": {"period": period_gold}}}
        plans, names, items = [], {}, {}
        for entry in spec["series"]:
            found = table(tables, entry[4])
            resolved = class_codes(entry, tables)
            start, end = validate.expected_plan_period(probe, found, frequency)
            item_id = found["item_ids"][0]
            plans.append({"label": entry[0], "table_id": entry[4], "table_name": found["table_name"],
                          "org_id": "301", "item_id": item_id, "classifications": resolved["codes"],
                          "classification_labels": resolved["labels"], "frequency": frequency,
                          "period_start": start, "period_end": end,
                          "exact_params": {"method": "getList", "format": "json", "jsonVD": "Y", "smblChk": "Y",
                                           "orgId": "301", "tblId": entry[4], "itmId": item_id, "prdSe": frequency,
                                           "startPrdDe": start, "endPrdDe": end, **resolved["codes"]}})
            names[entry[4]] = found["table_name"]
            items[entry[4]] = item_id
        ids = sorted(names)
        workflow = {
            "query_interpretation": interpretation,
            "table_discovery": {"status": "matched", "expected_table_ids": ids, "selected_table_ids": ids,
                                "table_names": names, "unmatched_concepts": []},
            "item_selection": {"item_by_table": items, "matching": "exact_item_code_by_table"},
            "classification_and_plan": {"series": plans,
                                        "matching": "exact_series_identity_set_with_period_and_frequency",
                                        "execution": "not_run"},
            "resolution": {"agent_status": "resolved", "api_status": "need_period",
                           "clarification_required": False, "table_count": len(names),
                           "series_count": len(plans)},
            "post_discovery": {"response_status": "need_period",
                               "reason": "period_missing" if period is None else "execution_deferred",
                               "period_selection_required": period is None, "text_period": period_gold,
                               "execution": False}}
    elif spec["status"] == "no_match":
        workflow = {
            "query_interpretation": interpretation,
            "table_discovery": {"status": "no_match", "expected_table_ids": [], "selected_table_ids": [],
                                "table_names": {}, "unmatched_concepts": spec["unmatched"]},
            "item_selection": {"item_by_table": {}, "matching": "exact_item_code_by_table"},
            "classification_and_plan": {"series": [],
                                        "matching": "exact_series_identity_set_with_period_and_frequency",
                                        "execution": "not_run"},
            "resolution": {"agent_status": "no_match", "api_status": "no_match",
                           "clarification_required": False, "table_count": 0, "series_count": 0,
                           "no_match_reason": spec["no_match_reason"]},
            "post_discovery": {"response_status": "no_match", "reason": "catalog_cannot_cover_request",
                               "execution": False}}
    else:
        group = next((item for item in CATALOG_GROUPS if item["id"] == spec["clarification_group"]), None)
        if group is None:
            raise SystemExit(f"{case_id}: unknown clarification group")
        workflow = {
            "query_interpretation": interpretation,
            "table_discovery": {"status": "clarification_pending", "expected_table_ids": [],
                                "selected_table_ids": [], "table_names": {}, "unmatched_concepts": []},
            "item_selection": {"item_by_table": {}, "matching": "exact_item_code_by_table"},
            "classification_and_plan": {"series": [],
                                        "matching": "exact_series_identity_set_with_period_and_frequency",
                                        "execution": "not_run"},
            "resolution": {"agent_status": "need_clarification", "api_status": "need_clarification",
                           "clarification_required": True, "table_count": 0, "series_count": 0,
                           "clarification": {"id": group["id"], "question": group["question"],
                                             "options": group["options"]}},
            "post_discovery": {"response_status": "need_clarification",
                               "reason": "semantic_scope_ambiguous", "execution": False}}

    return {"id": case_id, "schema_version": SCHEMA, "split": "dev", "topic": spec["topic"],
            "query": spec["query"], "reference_date": REFERENCE_DATE, "workflow_gold": workflow,
            "evidence": {"catalog_path": "src/agent/stat_dictionary/stat_language_dictionary.json",
                         "catalog_sha256": catalog_sha,
                         "gold_basis": "public_BOK_KOSIS_catalog_metadata_and_local_runtime_contract"},
            "research_references": references(spec, index),
            "review": {"ai_assisted": True, "human_approved": False, "status": "draft"},
            "excluded_from_scoring": EXCLUDED}


CATALOG_GROUPS: list[dict] = []


def summarize_markdown(cases: list[dict]) -> str:
    lines = ["# 기자 질의 통계표 탐색 골든셋 v2.1 (200문항)", "",
             "v2의 30문항을 그대로 두고 단계별 정답 형식을 유지하며 증강한 공개 개발용 골든셋입니다.",
             "research 보고서 그림·표는 화제 출처일 뿐이며 정답 근거는 카탈로그 메타데이터입니다.", "",
             "| ID | 주제 | 상태 | 질문 | 정답 표 | 계열 |", "|---|---|---|---|---|---:|"]
    for case in cases:
        gold = case["workflow_gold"]
        tables = ", ".join(sorted({plan["table_id"] for plan in gold["classification_and_plan"]["series"]})) or "-"
        lines.append(f"| {case['id']} | {case['topic']} | {gold['resolution']['agent_status']} | "
                     f"{case['query']} | {tables} | {gold['resolution']['series_count']} |")
    lines.append("")
    return "\n".join(lines)


def build() -> dict:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8-sig"))
    CATALOG_GROUPS[:] = catalog["clarification_groups"]
    tables = {table_["table_id"]: table_ for table_ in catalog["tables"]}
    index = research_index()
    legacy = [json.loads(line) for line in (V2 / "statbridge-reporter30.jsonl")
              .read_text(encoding="utf-8").splitlines() if line]
    cases = legacy + [build_case(spec, tables, index) for spec in SPECS]
    gold_path = DATASET / "statbridge-reporter200.jsonl"
    gold_path.write_text("".join(json.dumps(case, ensure_ascii=False, separators=(",", ":")) + "\n"
                                 for case in cases), encoding="utf-8")
    (DATASET / "statbridge-reporter200.md").write_text(summarize_markdown(cases), encoding="utf-8")
    summary = validate.validate_cases(cases, catalog, len(cases))
    validate.validate_legacy_preservation(cases)
    manifest = {
        "dataset": "reporter-table-discovery-200",
        "version": "v2.1",
        "schema_version": SCHEMA,
        "created_at": REFERENCE_DATE,
        "review": {"human_approved": False, "ai_assisted": True},
        "counts": summary,
        "dataset_sha256": validate.text_sha256(gold_path),
        "catalog_path": "src/agent/stat_dictionary/stat_language_dictionary.json",
        "catalog_sha256": validate.text_sha256(CATALOG),
        "source_dataset": "eval/reporter-table-discovery-30/v2/statbridge-reporter30.jsonl",
        "source_dataset_sha256": validate.text_sha256(V2 / "statbridge-reporter30.jsonl"),
        "research_sources": sorted({ref["path"] for case in cases for ref in case.get("research_references") or []}),
        "benchmark_scope": "query_interpretation_table_item_classification_api_plan_and_resolution",
        "numeric_gold": "not_created",
        "source_boundary": "KOSIS Korea Bank of Korea only",
        "sha256_normalization": "LF",
        "period_policy": "Explicit periods are converted to inclusive KOSIS periods; missing periods retain the runtime plan but expect the API need_period follow-up.",
    }
    (DATASET / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build()["counts"], ensure_ascii=False))
