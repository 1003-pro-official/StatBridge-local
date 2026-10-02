#!/usr/bin/env python3
"""Validate, export, and import human review for the v2 draft."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
CASES = ROOT / "cases.jsonl"
FIXTURES = ROOT / "plan_validation_cases.jsonl"
MANIFEST = ROOT / "catalog_manifest.json"
WORKBOOK = ROOT / "review.xlsx"
API_EXPORT = ROOT / "kosis_metadata_export.json"
CATALOG_PATH = REPO / "data/kosis/hankook_tables.json"
SUMMARY_PATH = REPO / "src/backend/data_full/collection/table_summary.csv"
DECISIONS = {"승인", "수정", "보류", "제외"}
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try: rows.append(json.loads(line))
        except json.JSONDecodeError as exc: raise ValueError(f"{path.name}:{n}: {exc}") from exc
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n" for x in rows), encoding="utf-8", newline="\n")


def j(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def validate(cases: list[dict]) -> list[str]:
    errors = []
    if len(cases) != 150: errors.append(f"case count {len(cases)} != 150")
    ids = [c.get("case_id") for c in cases]
    if len(set(ids)) != len(ids): errors.append("duplicate case IDs")
    if Counter(c.get("split") for c in cases) != Counter({"dev": 30, "validation": 30, "locked_test": 90}): errors.append("split allocation differs from v1 pilot")
    by_group = {}
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig"))
    table_ids = {x["tbl_id"] for x in catalog["tables"]}
    for c in cases:
        cid = c.get("case_id", "?")
        if c.get("annotation", {}).get("review_status") not in {"draft", "review_required", "needs_adjudication", "approved", "excluded"}: errors.append(f"{cid}: invalid review status")
        if c.get("annotation", {}).get("review_status") == "approved" and (c.get("review", {}).get("decision") != "승인" or not c.get("review", {}).get("approved_table_ids")): errors.append(f"{cid}: approved requires a human approval decision and approved ID/NO_MATCH")
        if c.get("annotation", {}).get("review_status") == "excluded" and c.get("review", {}).get("decision") != "제외": errors.append(f"{cid}: excluded without human exclusion decision")
        group = c.get("leakage_group", cid)
        by_group.setdefault(group, set()).add(c.get("split"))
        gold = c.get("gold", {})
        for stage in ("input", "interpretation", "concepts", "ambiguity", "clarification", "data_strategy", "tool_plan", "plan_validation", "retrieval", "handoff"):
            if stage not in gold: errors.append(f"{cid}: missing gold.{stage}")
        plan = gold.get("tool_plan", {})
        if not isinstance(plan.get("planned_tools"), list): errors.append(f"{cid}: tool_plan.planned_tools must be an array")
        if set(plan.get("planned_tools", [])) & set(plan.get("allowed_tools", [])): errors.append(f"{cid}: planned tools must not be executable allowed_tools")
        if any(x not in {"merge_datasets", "render_chart"} for x in plan.get("planned_tools", [])): errors.append(f"{cid}: unknown planned tool")
        if not isinstance(gold.get("interpretation", {}).get("unspecified_slots"), list): errors.append(f"{cid}: unspecified_slots must be an array")
        if not isinstance(gold.get("ambiguity", {}).get("conflicts"), list): errors.append(f"{cid}: ambiguity.conflicts must be an array")
        def has_na(value):
            if value == "N/A": return True
            if isinstance(value, dict): return any(has_na(x) for x in value.values())
            if isinstance(value, list): return any(has_na(x) for x in value)
            return False
        if has_na(gold): errors.append(f"{cid}: gold contains N/A sentinel; use null or a typed empty value")
        if c.get("annotation", {}).get("review_status") == "review_required" and c.get("provenance", {}).get("migration_status") != "automated_structure_migration; semantic correctness not certified": errors.append(f"{cid}: draft provenance missing")
        for candidate in gold.get("retrieval", {}).get("candidates", []):
            tid = candidate.get("table_id")
            if tid not in table_ids: errors.append(f"{cid}: candidate ID not in catalog: {tid}")
            meta = candidate.get("metadata")
            required = ("catalog_path", "frequency", "unit", "period_start", "period_end", "item_count", "items", "classification_axes", "comments", "metadata_source_status", "kosis_live_metadata")
            if not isinstance(meta, dict) or any(k not in meta for k in required): errors.append(f"{cid}: candidate {tid} metadata fields incomplete")
            if candidate.get("assessment_status") not in {"review_required", "approved", "rejected", "conditional"}: errors.append(f"{cid}: candidate {tid} has invalid assessment status")
        if gold.get("retrieval", {}).get("expected_status") == "NO_MATCH" and gold.get("retrieval", {}).get("search_scope", {}).get("verification_status") != "review_required": errors.append(f"{cid}: NO_MATCH must remain unverified until human review")
    if any(len(splits) > 1 for splits in by_group.values()): errors.append("leakage_group crosses splits")
    fixtures = read_jsonl(FIXTURES)
    fixture_ids = [x.get("fixture_id") for x in fixtures]
    if len(fixtures) != 12 or len(set(fixture_ids)) != len(fixtures): errors.append("plan-validation fixture count or IDs invalid")
    return errors


def _col(index: int) -> str:
    out = ""
    while index:
        index, rem = divmod(index - 1, 26); out = chr(65 + rem) + out
    return out


def _xml(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")


def _sheet(rows: list[list[str]], widths: list[int], input_start: int = 0) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews><cols>']
    for i, width in enumerate(widths, 1): out.append(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>')
    out.append('</cols><sheetData>')
    for rn, row in enumerate(rows, 1):
        out.append(f'<row r="{rn}">')
        for cn, value in enumerate(row, 1):
            if value is None or value == "":
                if input_start and cn >= input_start and rn > 1: out.append(f'<c r="{_col(cn)}{rn}" s="3"/>')
                continue
            style = 1 if rn == 1 else 3 if input_start and cn >= input_start else 2
            out.append(f'<c r="{_col(cn)}{rn}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{_xml(value)}</t></is></c>')
        out.append('</row>')
    out.append('</sheetData><autoFilter ref="A1:'+_col(len(widths))+str(len(rows))+'"/>')
    if input_start: out.append(f'<dataValidations count="1"><dataValidation type="list" allowBlank="1" showErrorMessage="1" sqref="S2:S{len(rows)}"><formula1>"승인,수정,보류,제외"</formula1></dataValidation></dataValidations>')
    out.append('</worksheet>')
    return ''.join(out)


def write_workbook(cases: list[dict]) -> None:
    guide = [
        ["항목", "설명"],
        ["목적", "v2 단계별 정답 초안을 사람 검토하는 문서입니다. 모든 gold 값은 승인 전 제안입니다."],
        ["검토 순서", "원문·맥락 → 의도/슬롯 → 개념/모호성 → 답변 분기 → 전략/도구/계획 검증 → 후보 메타정보 → handoff 순으로 확인합니다."],
        ["초안 열", "A:R은 JSONL 초안과 출처입니다. 수정해도 JSONL에 자동 반영되지 않습니다."],
        ["검토 입력", "S:W는 검토 결정, 승인 표 ID, 수정 정답(JSON), 검토자, 검토 메모입니다."],
        ["승인", "승인할 표 ID 또는 NO_MATCH를 입력합니다. 사람이 gold를 최종 확정한 뒤에만 annotation.review_status를 approved로 수동 변경합니다."],
        ["수정", "수정 JSON 또는 수정 필드/값을 입력하고 근거를 적습니다. import-review는 검토 입력만 저장하며 gold나 상태를 변경하지 않습니다."],
        ["보류/제외", "보류는 needs_adjudication, 제외는 excluded로 사람만 확정합니다. 두 상태는 채점에서 제외합니다."],
        ["상대 기간", "기준일은 2026-09-23입니다. 기간 끝은 요청 표의 기준일 이전 최신 수록시점으로 메타정보를 확인해 결정합니다."],
        ["N/A/null", "비적용 목록은 빈 배열, 미지정 scalar는 null, 확인 불가 메타정보는 null과 metadata_source_status로 나타냅니다."],
        ["후보 메타정보", "카탈로그/로컬 스냅샷/KOSIS API의 근거 범위와 미확인 필드를 함께 표시합니다. 후보 관련성은 승인 전 제안입니다."],
        ["NO_MATCH", "초안 NO_MATCH는 확정 판정이 아닙니다. 프로젝트 349표 목록의 탐색 범위와 유사 후보를 먼저 검토하세요. 전체 KOSIS 카탈로그 검색을 수행한 것은 아닙니다."],
        ["H fixture", "plan_validation_cases.jsonl은 150개 질의 건수에 포함되지 않는 독립 계획검증 fixture입니다."],
        ["Split", "dev 30 / validation 30 / locked_test 90. 같은 leakage_group은 한 split에만 배정합니다."],
        ["재생성 주의", "Excel 입력을 JSONL로 import-review 하기 전에는 workbook을 재생성하지 마세요."],
    ]
    headers = ["case_id","split","primary_type","tags","원문 질의·맥락","입력/유지·변경 맥락","의도·슬롯·미지정 조건","개념 후보·근거","모호성·충돌·질문/비질문","역질문·답변 후 상태","데이터 전략","도구 계획","계획 검증","탐색 결과·허용 ID","후보 표·메타정보·근거","handoff","검토 상태","출처/마이그레이션","검토 결정","승인할 통계표 ID","수정 라벨 또는 정답 JSON","검토자","검토 메모"]
    rows = [headers]
    for c in cases:
        g = c["gold"]
        conversation = "\n".join(f"[{m['role']}] {m['text']}" for m in c["conversation"])
        candidates = [{k: v for k, v in x.items() if k != "metadata"} | {"metadata": x["metadata"]} for x in g["retrieval"]["candidates"]]
        rows.append([c["case_id"],c["split"],c["primary_type"],", ".join(c["tags"]),conversation,j(g["input"]),j(g["interpretation"]),j(g["concepts"]),j(g["ambiguity"]),j(g["clarification"]),j(g["data_strategy"]),j(g["tool_plan"]),j(g["plan_validation"]),j({k:g["retrieval"][k] for k in ("expected_status","acceptable_table_ids","no_match_reason","search_scope","acceptable_answer_range")}),j(candidates),j(g["handoff"]),c["annotation"]["review_status"],j(c["provenance"]),c["review"].get("decision") or "",c["review"].get("approved_table_ids") or "",j(c["review"].get("edited_gold")) if c["review"].get("edited_gold") else "",c["review"].get("reviewer") or "",c["review"].get("review_notes") or ""])
    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF244062"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFFF2CC"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf><xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'''
    workbook = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="안내" sheetId="1" r:id="rId1"/><sheet name="사례 검토" sheetId="2" r:id="rId2"/></sheets></workbook>'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'''
    package = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'''
    content = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'''
    with zipfile.ZipFile(WORKBOOK, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content); z.writestr("_rels/.rels", package); z.writestr("xl/workbook.xml", workbook); z.writestr("xl/_rels/workbook.xml.rels", rels); z.writestr("xl/styles.xml", styles)
        z.writestr("xl/worksheets/sheet1.xml", _sheet(guide, [24, 120])); z.writestr("xl/worksheets/sheet2.xml", _sheet(rows, [14,14,24,24,46,58,58,58,48,56,44,60,52,64,80,58,18,48,14,28,48,22,44], 19))


def _read_workbook(path: Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml")); rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.attrib["Id"]: "xl/" + r.attrib["Target"] for r in rels}
        sheet = wb.findall("m:sheets/m:sheet", NS)[1]
        root = ET.fromstring(z.read(targets[sheet.attrib[f"{{{NS['r']}}}id"]]))
        result = []
        for row in root.findall("m:sheetData/m:row", NS):
            cells = []
            for cell in row.findall("m:c", NS):
                m = re.match(r"([A-Z]+)", cell.attrib["r"]); idx = 0
                for ch in m.group(1): idx = idx * 26 + ord(ch) - 64
                while len(cells) < idx: cells.append("")
                cells[idx - 1] = "".join(t.text or "" for t in cell.findall(".//m:t", NS))
            result.append(cells)
        return result


def import_review(path: Path) -> int:
    rows = _read_workbook(path)
    headers = rows[0]
    keys = ["case_id", "검토 결정", "승인할 통계표 ID", "수정 라벨 또는 정답 JSON", "검토자", "검토 메모"]
    ix = {k: headers.index(k) for k in keys}
    cases = read_jsonl(CASES); by_id = {c["case_id"]: c for c in cases}; count = 0
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig")); known_ids = {x["tbl_id"] for x in catalog["tables"]}
    for row in rows[1:]:
        cid = row[ix["case_id"]] if len(row) > ix["case_id"] else ""
        if cid not in by_id: continue
        values = {k: row[ix[k]] if len(row) > ix[k] else "" for k in keys}
        if values["검토 결정"] and values["검토 결정"] not in DECISIONS: raise ValueError(f"{cid}: invalid review decision")
        approved = [x.strip() for x in values["승인할 통계표 ID"].split(",") if x.strip()]
        if any(x != "NO_MATCH" and x not in known_ids for x in approved): raise ValueError(f"{cid}: 승인 ID는 카탈로그 표 ID 또는 NO_MATCH여야 합니다")
        if values["검토 결정"] == "승인" and not approved: raise ValueError(f"{cid}: 승인 결정에는 표 ID 또는 NO_MATCH가 필요합니다")
        by_id[cid]["review"].update({"decision": values["검토 결정"] or None, "approved_table_ids": approved, "edited_gold": json.loads(values["수정 라벨 또는 정답 JSON"]) if values["수정 라벨 또는 정답 JSON"].strip().startswith("{") else values["수정 라벨 또는 정답 JSON"] or None, "reviewer": values["검토자"] or None, "reviewed_at": datetime.now(timezone.utc).date().isoformat() if values["검토 결정"] or values["검토자"] or values["검토 메모"] else None, "review_notes": values["검토 메모"] or None})
        count += 1
    write_jsonl(CASES, cases); return count


def refresh_kosis() -> None:
    try: from statbridge_mcp.kosis_client import KosisClient
    except ImportError as exc: raise SystemExit("KOSIS client dependency unavailable; use src/backend/requirements.txt") from exc
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig")); org = {x["tbl_id"]: x.get("org_id", "301") for x in catalog["tables"]}
    ids = sorted({x["table_id"] for c in read_jsonl(CASES) for x in c["gold"]["retrieval"]["candidates"]})
    old = json.loads(API_EXPORT.read_text(encoding="utf-8")) if API_EXPORT.exists() else {"tables": {}}
    result = dict(old.get("tables", {})); client = KosisClient()
    for i, tid in enumerate(ids, 1):
        try:
            prd = client.get_prd_meta(org.get(tid, "301"), tid); itm = client.get_itm_meta(org.get(tid, "301"), tid)
            result[tid] = {"org_id": org.get(tid, "301"), "table_id": tid, "period_rows": prd, "item_class_rows": itm, "status": "ok" if prd or itm else "empty"}
        except Exception as exc:
            result[tid] = {"org_id": org.get(tid, "301"), "table_id": tid, "status": "unavailable", "error_type": type(exc).__name__}
        if i % 10 == 0: print(f"KOSIS metadata {i}/{len(ids)}")
    payload = {"source": "KOSIS Open API via project KosisClient getMeta(PRD, ITM)", "exported_at_utc": datetime.now(timezone.utc).isoformat(), "api_key_value_included": False, "table_count": len(result), "failure_count": sum(x.get("status") == "unavailable" for x in result.values()), "tables": result, "scope": "candidate table IDs only; not a full KOSIS catalog search"}
    API_EXPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    enrich_metadata(payload)
    print(f"metadata records {len(result)}; unavailable={payload['failure_count']}")


def enrich_metadata(api: dict | None = None) -> None:
    api = api or json.loads(API_EXPORT.read_text(encoding="utf-8"))
    cases = read_jsonl(CASES)
    for c in cases:
        for cand in c["gold"]["retrieval"]["candidates"]:
            meta = cand["metadata"]; live = api.get("tables", {}).get(cand["table_id"], {})
            if live.get("status") != "ok":
                meta["metadata_source_status"]["kosis_api"] = live.get("status", "not_queried"); meta["kosis_live_metadata"] = live or None; continue
            period_rows = live.get("period_rows", [])
            periods = sorted({str(x.get("PRD_SE", "")).strip() for x in period_rows if str(x.get("PRD_SE", "")).strip()})
            period_dates = sorted({str(x.get("PRD_DE", "")).strip() for x in period_rows if str(x.get("PRD_DE", "")).strip()})
            item_rows = live.get("item_class_rows", []); items = []; axes = {}
            for r in item_rows:
                oid = str(r.get("OBJ_ID", "")).strip(); iid = str(r.get("ITM_ID", "")).strip(); name = str(r.get("ITM_NM", "")).strip()
                if oid == "ITEM":
                    if iid and not any(x["id"] == iid for x in items): items.append({"id": iid, "name": name})
                elif oid:
                    axis = axes.setdefault(oid, {"obj_id": oid, "obj_name": r.get("OBJ_NM", ""), "count": 0, "examples": []})
                    axis["count"] += 1
                    if iid and len(axis["examples"]) < 8 and not any(x["id"] == iid for x in axis["examples"]): axis["examples"].append({"id": iid, "name": name})
            meta["frequency"] = meta.get("frequency") or periods or None
            meta["items"] = items[:8] if items else meta.get("items")
            meta["classification_axes"] = list(axes.values()) or meta.get("classification_axes")
            meta["metadata_source_status"].update({"kosis_api": "queried_partial", "comments_and_series_definition": "not_returned_by_checked_PRD_ITM_endpoints"})
            meta["kosis_live_metadata"] = {"status": "ok", "checked_at_utc": api.get("exported_at_utc"), "frequencies": periods, "period_range": {"start": min(period_dates), "end": max(period_dates), "distinct_periods": len(period_dates)} if period_dates else None, "item_count": len(items), "classification_axes": list(axes.values()), "comments_checked": False, "series_definition_checked": False, "raw_response_in": "kosis_metadata_export.json"}
    write_jsonl(CASES, cases)


def build_manifest() -> None:
    cases = read_jsonl(CASES); fixtures = read_jsonl(FIXTURES)
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig"))
    with SUMMARY_PATH.open(encoding="utf-8-sig", newline="") as f: summaries = {x["tbl_id"]: x for x in csv.DictReader(f)}
    api = json.loads(API_EXPORT.read_text(encoding="utf-8")) if API_EXPORT.exists() else {"tables": {}, "table_count": 0, "failure_count": 0}
    cases_by_table = {}
    candidate_counts = Counter()
    for c in cases:
        for x in c["gold"]["retrieval"]["candidates"]:
            cases_by_table.setdefault(x["table_id"], []).append(c["case_id"]); candidate_counts[x["role"]] += 1
    statuses = Counter(c["annotation"]["review_status"] for c in cases)
    paths = sorted({(x.get("path") or ["N/A"])[0] for x in catalog["tables"]})
    represented = {path for c in cases for x in c["gold"]["retrieval"]["candidates"] for path in [x["metadata"].get("catalog_path", [None])[0]] if path}
    tables = []
    for t in catalog["tables"]:
        s = summaries.get(t["tbl_id"], {})
        tables.append({"table_id": t["tbl_id"], "table_name": t["tbl_nm"], "catalog_path": t.get("path", []), "frequency": s.get("freq"), "period_start": s.get("start"), "period_end": s.get("end"), "unit": s.get("units"), "case_ids": cases_by_table.get(t["tbl_id"], []), "kosis_api_status": api.get("tables", {}).get(t["tbl_id"], {}).get("status", "not_queried")})
    manifest = {"dataset": "ClaBi KOSIS Golden Set v2", "version": "v2-draft-2026-09-23", "generated_at_utc": datetime.now(timezone.utc).isoformat(), "catalog_version": "hankook_tables_2026-09-14", "reused_sources": ["golden-set/cases.jsonl (query text, contexts, category/split and unapproved label seeds only)", "golden-set/kosis_metadata_export.json (59 prior candidate metadata records)", "data/kosis/hankook_tables.json", "src/backend/data_full/collection/table_summary.csv", "src/backend/data_full/tables/*.csv", "schemas/mcp_tools.json"], "new_artifacts": ["golden-set-v2/cases.jsonl", "golden-set-v2/plan_validation_cases.jsonl", "golden-set-v2/review.xlsx", "golden-set-v2/schema.json", "golden-set-v2/catalog_manifest.json", "golden-set-v2/coverage.csv", "golden-set-v2/kosis_metadata_export.json", "golden-set-v2/README.md", "golden-set-v2/scripts/build_v2.py", "golden-set-v2/scripts/manage_v2.py"], "counts": {"cases": len(cases), "by_type": dict(Counter(c["primary_type"] for c in cases)), "by_split": dict(Counter(c["split"] for c in cases)), "by_review_status": dict(statuses), "approved": statuses.get("approved", 0), "excluded": statuses.get("excluded", 0), "awaiting_human_review": sum(statuses.get(x, 0) for x in ("draft", "review_required", "needs_adjudication")), "plan_validation_fixtures": len(fixtures), "unique_candidate_tables": len(cases_by_table), "candidates_by_role": dict(candidate_counts), "catalog_tables": len(tables), "catalog_paths_covered": len(represented), "catalog_paths_total": len(paths)}, "review": {"decision_counts": dict(Counter(c["review"].get("decision") or "미입력" for c in cases)), "policy": "import-review writes review inputs only; only a human may apply gold edits and update review_status"}, "sources": {"catalog_collected_at": catalog.get("collected_at"), "catalog_sha256": hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest(), "summary_rows": len(summaries), "kosis_candidate_tables_queried": api.get("table_count", 0), "kosis_failed_tables": api.get("failure_count", 0), "kosis_metadata_endpoints": ["getMeta(PRD)", "getMeta(ITM)"], "kosis_unverified_fields": ["comments", "full series definitions"], "catalog_search_scope": "349-row Korean Bank project catalog snapshot; no live all-KOSIS catalog search"}, "no_match_cases": [{"case_id": c["case_id"], "verification_status": "review_required", "candidate_count": len(c["gold"]["retrieval"]["candidates"]), "scope": c["gold"]["retrieval"]["search_scope"]} for c in cases if c["gold"]["retrieval"]["expected_status"] == "NO_MATCH"], "tables": tables}
    (ROOT / "catalog_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (ROOT / "coverage.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["record_type", "primary_type", "split", "catalog_path", "case_count", "case_ids", "status"])
        for path in paths: w.writerow(["catalog_path", "N/A", "N/A", path, sum(path in [z["metadata"].get("catalog_path", [None])[0] for z in c["gold"]["retrieval"]["candidates"]] for c in cases), "", "covered" if path in represented else "uncovered_review_required"])
        for c in cases: w.writerow(["case", c["primary_type"], c["split"], "", 1, c["case_id"], c["annotation"]["review_status"]])


def main():
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest="cmd", required=True)
    for cmd in ("validate", "workbook", "manifest", "refresh-kosis", "enrich-kosis"): sub.add_parser(cmd)
    imp = sub.add_parser("import-review"); imp.add_argument("workbook", type=Path)
    a = p.parse_args()
    if a.cmd == "refresh-kosis": refresh_kosis(); build_manifest(); return
    if a.cmd == "enrich-kosis": enrich_metadata(); build_manifest(); return
    if a.cmd == "import-review":
        n = import_review(a.workbook); build_manifest(); print(f"imported review fields for {n} cases; gold/status unchanged"); return
    if a.cmd == "manifest": build_manifest(); print(f"wrote {MANIFEST}"); return
    cases = read_jsonl(CASES); errors = validate(cases)
    if errors:
        for e in errors: print(e)
        raise SystemExit(1)
    print(f"OK cases={len(cases)} split={dict(Counter(c['split'] for c in cases))} review_status={dict(Counter(c['annotation']['review_status'] for c in cases))}")
    if a.cmd == "workbook": write_workbook(cases); print(f"wrote {WORKBOOK}")


if __name__ == "__main__": main()
