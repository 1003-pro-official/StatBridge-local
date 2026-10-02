#!/usr/bin/env python3
"""Validate cases, export a review workbook, refresh KOSIS metadata, or import review inputs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
CASES = ROOT / "cases.jsonl"
MANIFEST = ROOT / "catalog_manifest.json"
WORKBOOK = ROOT / "review.xlsx"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships", "p": "http://schemas.openxmlformats.org/package/2006/relationships"}
PRIMARY_COUNTS = {
    "clear_single_table": 30,
    "colloquial_alias": 25,
    "ambiguous_metric": 20,
    "multi_indicator_table": 20,
    "conditions": 20,
    "no_match_out_of_scope": 15,
    "conversation_followup": 20,
}
SPLIT_COUNTS = {"dev": 30, "validation": 30, "locked_test": 90}
DECISIONS = ["승인", "수정", "보류", "제외"]


def read_cases(path: Path = CASES) -> list[dict]:
    cases = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL line {line_number}: {exc}") from exc
            if not isinstance(case, dict):
                raise ValueError(f"JSONL line {line_number}: object required")
            cases.append(case)
    return cases


def validate(cases: list[dict]) -> list[str]:
    errors: list[str] = []
    ids = [c.get("case_id") for c in cases]
    if len(cases) != 150:
        errors.append(f"case count {len(cases)} != 150")
    if None in ids or len(set(ids)) != len(ids):
        errors.append("case_id missing or duplicated")
    if Counter(c.get("primary_type") for c in cases) != Counter(PRIMARY_COUNTS):
        errors.append(f"primary type counts differ: {dict(Counter(c.get('primary_type') for c in cases))}")
    if Counter(c.get("split") for c in cases) != Counter(SPLIT_COUNTS):
        errors.append(f"split counts differ: {dict(Counter(c.get('split') for c in cases))}")
    manifest_ids = set()
    if MANIFEST.exists():
        manifest_ids = {t["table_id"] for t in json.loads(MANIFEST.read_text(encoding="utf-8"))["tables"]}
    for case in cases:
        tag = case.get("case_id", "?")
        for key in ("case_id", "split", "primary_type", "tags", "conversation", "gold", "annotation", "review"):
            if key not in case:
                errors.append(f"{tag}: missing {key}")
        review_status = case.get("annotation", {}).get("review_status")
        if review_status not in {"draft", "review_required", "needs_adjudication", "approved", "excluded"}:
            errors.append(f"{tag}: invalid review status")
        decision = case.get("review", {}).get("decision")
        approved_ids = case.get("review", {}).get("approved_table_ids")
        if review_status == "approved" and (decision != "승인" or approved_ids in (None, "", "N/A")):
            errors.append(f"{tag}: approved status requires human decision and approved table ID or NO_MATCH")
        if review_status == "excluded" and decision != "제외":
            errors.append(f"{tag}: excluded status requires human decision 제외")
        gold = case.get("gold", {})
        for stage in ("input", "interpretation", "concepts", "ambiguity", "clarification", "data_strategy", "tool_plan", "retrieval"):
            if stage not in gold:
                errors.append(f"{tag}: missing gold.{stage}")
        required_fields = {
            "interpretation": ("acceptable_intents", "slots", "unspecified_fields"),
            "concepts": ("acceptable_candidates", "must_preserve_ambiguity", "evidence_requirements"),
            "ambiguity": ("present", "conflicts"),
            "clarification": ("expected", "must_resolve", "acceptable_question_criteria", "answer_branches"),
            "tool_plan": ("expected_next_action", "acceptable_plans", "required_order", "validation_conditions"),
            "retrieval": ("expected_status", "candidates", "acceptable_table_ids", "no_match_reason", "search_scope"),
        }
        for stage, fields in required_fields.items():
            missing = [field for field in fields if field not in gold.get(stage, {})]
            if missing: errors.append(f"{tag}: gold.{stage} missing {','.join(missing)}")
        retrieval = gold.get("retrieval", {})
        if retrieval.get("expected_status") == "NO_MATCH" and (not retrieval.get("search_scope") or not retrieval.get("no_match_reason")):
            errors.append(f"{tag}: NO_MATCH requires recorded scope and reason")
        for candidate in retrieval.get("candidates", []):
            tid = candidate.get("table_id")
            if not tid or (manifest_ids and tid not in manifest_ids):
                errors.append(f"{tag}: candidate table not linked to manifest: {tid}")
            if not candidate.get("metadata"):
                errors.append(f"{tag}: candidate {tid} has no metadata")
            if candidate.get("relatedness") not in {0, 1, 2, 3, None}:
                errors.append(f"{tag}: invalid proposed relatedness for {tid}")
            meta_fields = ("catalog_path", "frequency", "unit", "period_start", "period_end", "items", "classification_axes", "comments", "kosis_live_status")
            if any(field not in candidate.get("metadata", {}) for field in meta_fields):
                errors.append(f"{tag}: candidate {tid} metadata fields incomplete")
    return errors


def _col(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _xml(value: str) -> str:
    return (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&apos;"))


def _sheet_xml(rows: list[list[str]], widths: list[int], *, filter_rows: bool = False, input_start: int = 0) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
           '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>', '<cols>']
    for i, width in enumerate(widths, 1):
        out.append(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>')
    out.append('</cols><sheetData>')
    for row_num, row in enumerate(rows, 1):
        out.append(f'<row r="{row_num}">')
        for col_num, value in enumerate(row, 1):
            if value is None or value == "":
                if input_start and col_num >= input_start and row_num > 1:
                    out.append(f'<c r="{_col(col_num)}{row_num}" s="3"/>')
                continue
            style = 1 if row_num == 1 else (3 if input_start and col_num >= input_start else 2)
            ref = f'{_col(col_num)}{row_num}'
            out.append(f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{_xml(str(value))}</t></is></c>')
        out.append('</row>')
    out.append('</sheetData>')
    if filter_rows and rows:
        out.append(f'<autoFilter ref="A1:{_col(len(widths))}{len(rows)}"/>')
    if input_start and len(rows) > 1:
        out.append(f'<dataValidations count="1"><dataValidation type="list" allowBlank="1" showErrorMessage="1" sqref="O2:O{len(rows)}"><formula1>"승인,수정,보류,제외"</formula1></dataValidation></dataValidations>')
    out.append('</worksheet>')
    return ''.join(out)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _freq_code(value: str) -> str:
    return {"월": "M", "분기": "Q", "년": "Y", "연": "Y", "반기": "S", "일": "D"}.get(value, value)


def _period_code(value: str, frequency: str) -> str:
    text = str(value or "").strip()
    year = re.search(r"(\d{4})", text)
    if not year:
        return text
    if frequency == "Y":
        return year.group(1)
    if frequency == "Q":
        part = re.search(r"(\d)\s*/\s*4", text)
        return year.group(1) + (f"{int(part.group(1)):02d}" if part else "")
    if frequency == "S":
        part = re.search(r"(\d)\s*/\s*2", text)
        return year.group(1) + (f"{int(part.group(1)):02d}" if part else "")
    if frequency == "M":
        part = re.search(r"\d{4}\D*(\d{1,2})(?:\D|$)", text)
        return year.group(1) + (f"{int(part.group(1)):02d}" if part else "")
    return re.sub(r"\D", "", text)


def enrich_from_api(cases: list[dict], export_path: Path = ROOT / "kosis_metadata_export.json") -> int:
    if not export_path.exists():
        raise FileNotFoundError(f"KOSIS export missing: {export_path}")
    api = json.loads(export_path.read_text(encoding="utf-8"))
    changed = 0
    for case in cases:
        for candidate in case["gold"]["retrieval"]["candidates"]:
            tid = candidate["table_id"]
            live = api["tables"].get(tid)
            metadata = candidate["metadata"]
            if not live or live.get("status") != "ok":
                metadata["kosis_live_status"] = "unavailable"
                continue
            periods: dict[str, set[str]] = defaultdict(set)
            raw_periods: dict[str, set[str]] = defaultdict(set)
            for row in live.get("period_rows", []):
                raw_freq = str(row.get("PRD_SE", "")).strip()
                raw_period = str(row.get("PRD_DE", "")).strip()
                if not raw_freq or not raw_period:
                    continue
                freq = _freq_code(raw_freq)
                raw_periods[freq].add(raw_period)
                periods[freq].add(_period_code(raw_period, freq))
            item_rows = live.get("item_class_rows", [])
            item_pairs = []
            axes: dict[str, dict] = {}
            for row in item_rows:
                oid = str(row.get("OBJ_ID", "")).strip()
                iid = str(row.get("ITM_ID", "")).strip()
                name = str(row.get("ITM_NM", "")).strip()
                if oid == "ITEM":
                    pair = {"id": iid, "name": name}
                    if iid and pair not in item_pairs:
                        item_pairs.append(pair)
                elif oid:
                    axis = axes.setdefault(oid, {"obj_id": oid, "obj_name": row.get("OBJ_NM", ""), "count": 0, "examples": []})
                    axis["count"] += 1
                    example = {"id": iid, "name": name}
                    if iid and example not in axis["examples"] and len(axis["examples"]) < 8:
                        axis["examples"].append(example)
            metadata.update({
                "kosis_live_status": "queried_partial",
                "kosis_live_checked_at": api["exported_at_utc"],
                "kosis_live_frequencies": sorted(periods),
                "kosis_live_periods_by_frequency": {
                    freq: {"start": min(values), "end": max(values), "count": len(values), "raw_start": min(raw_periods[freq]), "raw_end": max(raw_periods[freq])}
                    for freq, values in sorted(periods.items()) if values
                },
                "kosis_live_item_count": len(item_pairs),
                "kosis_live_items": item_pairs[:8],
                "kosis_live_classifications": list(axes.values()),
                "kosis_live_not_provided_by_checked_endpoints": ["unit", "comments/series_definition"],
            })
            changed += 1
            evidence = f"KOSIS Open API getMeta(PRD, ITM): golden-set/kosis_metadata_export.json#{tid}"
            if evidence not in case["annotation"]["evidence"]:
                case["annotation"]["evidence"].append(evidence)
    return changed


def write_workbook(cases: list[dict], destination: Path = WORKBOOK) -> None:
    help_rows = [
        ["항목", "설명 / 입력 방법"],
        ["목적", "각 사례의 초안 라벨과 KOSIS 근거를 사람이 검토하는 파일입니다. 초안은 승인 전까지 정답이 아닙니다."],
        ["검토 절차", "1) 원문·대화·전체 단계 라벨·후보 메타정보를 확인  2) 검토 결정 입력  3) 수정이면 수정 라벨과 메모 기재  4) 합의가 안 되면 보류 또는 조정 대상으로 남김"],
        ["검토 결정", "O열에서 승인 / 수정 / 보류 / 제외 중 입력합니다. 이 값은 검토자의 결정 기록이며 가져오기 스크립트가 최종 라벨을 자동 승인하지 않습니다."],
        ["승인할 통계표 ID", "검토자가 선택한 ID를 입력합니다. 허용 후보가 여러 개면 쉼표로 구분합니다. 무결과 사례는 NO_MATCH라고 입력할 수 있습니다."],
        ["수정 라벨 또는 정답", "수정한 전체 gold JSON 또는 변경된 필드와 값을 JSON 객체로 입력합니다. 수정하지 않으면 비워둡니다."],
        ["검토 메모", "근거, 불일치, 필요한 추가 확인을 입력합니다."],
        ["초안 / 입력 분리", "A:N은 초안과 근거(읽기 전용 관례), O:R은 검토 입력 칸입니다. 초안 상태는 N열에 표시됩니다."],
        ["단계 라벨", "의도·슬롯, 개념 후보, 모호성, 역질문/답변 분기, 데이터 전략, 도구 계획, 계획 검증, Retrieval 및 후보 관련도를 모두 표시합니다."],
        ["메타정보 근거", "후보별 카탈로그 경로, 주기, 단위, 수록기간, 항목·분류 예시, KOSIS API 확인 상태와 미확인 필드를 확인합니다."],
        ["JSONL 반영", "python golden-set/scripts/manage_golden_set.py import-review review.xlsx 로 입력 내용을 cases.jsonl의 review 객체에만 반영합니다. gold와 review_status는 변경하지 않습니다."],
        ["최종 승인", "사례별 정답은 사람이 수정·판정하고 검토자 기록을 확인한 뒤 별도의 명시적 수동 변경으로 상태를 갱신합니다. import-review 실행만으로 승인되지 않습니다."],
        ["Split", "dev 30 / validation 30 / locked_test 90. 같은 실행 경로의 후속 답변은 한 사례에 묶여 있으며 사례 수를 늘리지 않습니다."],
        ["N/A", "해당하지 않거나 출처에 없는 값입니다. 비어 있는 검토 입력 칸은 검토자가 아직 입력하지 않았다는 뜻입니다."],
    ]
    headers = ["case_id", "split", "primary_type", "tags", "원문 질의·대화 맥락", "기대 의도·슬롯", "미지정 슬롯·개념 후보·근거", "모호성·역질문·답변 분기", "데이터 전략", "도구 계획·계획 검증", "탐색 상태·후보·관련도", "후보 메타정보", "증거 출처", "초안 검토 상태", "검토 결정", "승인할 통계표 ID", "수정 라벨 또는 정답", "검토 메모"]
    rows = [headers]
    for c in cases:
        g = c["gold"]
        retrieval = g["retrieval"]
        conversation = "\n".join(f"[{m['role']}] {m['text']}" for m in c["conversation"])
        candidates = [{k: v for k, v in item.items() if k != "metadata"} | {"metadata": item["metadata"]} for item in retrieval["candidates"]]
        rows.append([
            c["case_id"], c["split"], c["primary_type"], ", ".join(c["tags"]), conversation,
            _json(g["interpretation"]), _json({"unspecified_fields":g["interpretation"].get("unspecified_fields"),"concepts":g["concepts"]}),
            _json({"ambiguity":g["ambiguity"],"clarification":g["clarification"]}), _json(g["data_strategy"]),
            _json(g["tool_plan"]), _json({"expected_status":retrieval["expected_status"],"acceptable_table_ids":retrieval["acceptable_table_ids"],"candidates":candidates,"no_match_reason":retrieval["no_match_reason"],"search_scope":retrieval["search_scope"]}),
            _json([{"table_id":x["table_id"],"table_name":x["table_name"],"metadata":x["metadata"]} for x in retrieval["candidates"]]),
            _json(c["annotation"]["evidence"]), c["annotation"]["review_status"],
            "" if c["review"].get("decision") in (None, "미입력") else str(c["review"].get("decision")),
            "" if c["review"].get("approved_table_ids") in (None, "N/A") else str(c["review"].get("approved_table_ids")),
            "" if c["review"].get("edited_gold") in (None, "N/A") else str(c["review"].get("edited_gold")),
            "" if c["review"].get("review_notes") in (None, "N/A") else str(c["review"].get("review_notes")),
        ])
    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF244062"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFFF2CC"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf><xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'''
    workbook = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="안내" sheetId="1" r:id="rId1"/><sheet name="사례 검토" sheetId="2" r:id="rId2"/></sheets></workbook>'''
    relroot = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'''
    package_rel = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'''
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", package_rel)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", relroot)
        z.writestr("xl/styles.xml", styles)
        z.writestr("xl/worksheets/sheet1.xml", _sheet_xml(help_rows, [24, 120]))
        z.writestr("xl/worksheets/sheet2.xml", _sheet_xml(rows, [14, 14, 24, 26, 46, 48, 48, 56, 38, 48, 64, 64, 48, 18, 14, 24, 44, 40], filter_rows=True, input_start=15))


def _read_workbook(path: Path) -> tuple[list[list[str]], list[list[str]]]:
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.attrib["Id"]: "xl/" + r.attrib["Target"] for r in rels}
        sheets = []
        for sheet in wb.findall("m:sheets/m:sheet", NS):
            target = targets[sheet.attrib[f"{{{NS['r']}}}id"]]
            root = ET.fromstring(z.read(target))
            rows = []
            for row in root.findall("m:sheetData/m:row", NS):
                cells = []
                for cell in row.findall("m:c", NS):
                    ref = cell.attrib["r"]
                    match = re.match(r"([A-Z]+)", ref)
                    index = 0
                    for ch in match.group(1): index = index * 26 + ord(ch) - 64
                    while len(cells) < index: cells.append("")
                    text = "".join(t.text or "" for t in cell.findall(".//m:t", NS))
                    if cell.attrib.get("t") == "s":
                        shared = ET.fromstring(z.read("xl/sharedStrings.xml"))
                        text = "".join(x.text or "" for x in shared.findall("m:si/m:t", NS)[int(cell.findtext("m:v", namespaces=NS))])
                    cells[index - 1] = text
                rows.append(cells)
            sheets.append(rows)
        return sheets[0], sheets[1]


def import_review(path: Path, cases_path: Path = CASES) -> int:
    _, rows = _read_workbook(path)
    if not rows:
        raise ValueError("review sheet is empty")
    headers = rows[0]
    indexes = {name: headers.index(name) for name in ("case_id", "검토 결정", "승인할 통계표 ID", "수정 라벨 또는 정답", "검토 메모")}
    cases = read_cases(cases_path); by_id = {c["case_id"]: c for c in cases}; changed = 0
    for row in rows[1:]:
        if not row: continue
        case_id = row[indexes["case_id"]] if len(row) > indexes["case_id"] else ""
        if case_id not in by_id: continue
        values = {key: row[i] if len(row) > i else "" for key, i in indexes.items()}
        if values["검토 결정"] and values["검토 결정"] not in DECISIONS:
            raise ValueError(f"{case_id}: 검토 결정은 {', '.join(DECISIONS)} 중 하나여야 합니다")
        review = by_id[case_id]["review"]
        review.update({"decision": values["검토 결정"] or "미입력", "approved_table_ids": values["승인할 통계표 ID"] or "N/A", "edited_gold": values["수정 라벨 또는 정답"] or "N/A", "review_notes": values["검토 메모"] or "N/A"})
        changed += 1
    cases_path.write_text("".join(json.dumps(c, ensure_ascii=False, separators=(",", ":")) + "\n" for c in cases), encoding="utf-8", newline="\n")
    if Path(cases_path).resolve() == CASES.resolve():
        build_manifest()
    return changed


def build_manifest() -> None:
    cases = read_cases()
    catalog_path = REPO / "data/kosis/hankook_tables.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    table_summary_path = ROOT.parent / "src/backend/data_full/collection/table_summary.csv"
    with table_summary_path.open(encoding="utf-8-sig", newline="") as stream:
        summary = {row["tbl_id"]: row for row in csv.DictReader(stream)}
    api = json.loads((ROOT / "kosis_metadata_export.json").read_text(encoding="utf-8")) if (ROOT / "kosis_metadata_export.json").exists() else {"tables": {}, "exported_at_utc": None, "table_count": 0, "failure_count": 0}
    case_ids_by_table: dict[str, list[str]] = defaultdict(list)
    relation_counts: dict[str, Counter] = defaultdict(Counter)
    cases_by_path: dict[str, set[str]] = defaultdict(set)
    used_path_roots = set()
    for case in cases:
        for item in case["gold"]["retrieval"]["candidates"]:
            tid = item["table_id"]
            if case["case_id"] not in case_ids_by_table[tid]: case_ids_by_table[tid].append(case["case_id"])
            relation_counts[tid][str(item.get("relatedness", "N/A"))] += 1
            path = item["metadata"].get("catalog_path", [])
            if path:
                cases_by_path[path[0]].add(case["case_id"]); used_path_roots.add(path[0])
    tables = []
    for table in catalog["tables"]:
        tid = table["tbl_id"]
        api_status = api["tables"].get(tid, {}).get("status", "not_queried")
        unit = summary.get(tid, {}).get("units", "")
        tables.append({"table_id": tid, "table_name": table["tbl_nm"], "org_id": table.get("org_id"), "stat_id": table.get("stat_id"), "catalog_path": table.get("path", []), "snapshot_csv_available": (ROOT.parent / f"src/backend/data_full/tables/{tid}.csv").exists(), "case_ids": case_ids_by_table.get(tid, []), "proposed_relatedness_counts": dict(relation_counts.get(tid, {})), "kosis_api_status": api_status, "local_unit_recorded": bool(unit)})
    count_types = Counter(c["primary_type"] for c in cases)
    count_splits = Counter(c["split"] for c in cases)
    status_counts = Counter(c["annotation"]["review_status"] for c in cases)
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "dataset": "ClaBi KOSIS Golden Set v1 Pilot",
        "version": "v1-draft-2026-09-23",
        "catalog_version": "hankook_tables_2026-09-14",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reused_sources": [
            "eval/goldenset/single_table.json (query and proposed slots/candidate seeds only)",
            "eval/goldenset/alias.json (query and proposed concept/table seeds only)",
            "eval/goldenset/multi_table.json (query and proposed pair seeds only)",
            "eval/goldenset/no_match.json (query and proposed no-match seeds only)",
            "data/kosis/hankook_tables.json",
            "src/backend/data_full/collection/table_summary.csv",
            "src/backend/data_full/tables/*.csv",
        ],
        "new_artifacts": ["golden-set/cases.jsonl", "golden-set/schema.json", "golden-set/review.xlsx", "golden-set/catalog_manifest.json", "golden-set/coverage.csv", "golden-set/kosis_metadata_export.json", "golden-set/README.md", "golden-set/scripts/manage_golden_set.py"],
        "sources": {
            "catalog": {"path": "data/kosis/hankook_tables.json", "collected_at": catalog.get("collected_at"), "record_count": catalog.get("count"), "sha256": sha(catalog_path)},
            "local_metadata_and_data": {"table_summary_path": "src/backend/data_full/collection/table_summary.csv", "table_summary_rows": len(summary), "snapshot_csv_count": sum(t["snapshot_csv_available"] for t in tables), "snapshot_csv_encoding": "UTF-8 with BOM tolerated; all read with utf-8-sig"},
            "api_export": {"path": "golden-set/kosis_metadata_export.json", "source": "project statbridge_mcp.kosis_client KOSIS getMeta(PRD, ITM)", "exported_at_utc": api.get("exported_at_utc"), "unique_candidate_tables_queried": api.get("table_count", 0), "failed_tables": api.get("failure_count", 0), "records_with_any_metadata": sum(v.get("status") == "ok" for v in api.get("tables", {}).values()), "metadata_scope": "period and item/classification endpoints; unit, comments and series definitions are not returned by these endpoints"},
            "hashes": {"table_summary_csv_sha256": sha(table_summary_path)},
        },
        "counts": {"cases": len(cases), "by_primary_type": dict(count_types), "by_split": dict(count_splits), "by_review_status": dict(status_counts), "unique_candidate_tables": len(case_ids_by_table), "catalog_table_count": len(tables), "catalog_paths_represented": len(used_path_roots), "catalog_paths_total": len({tuple(t.get("path", [])[:1]) for t in catalog["tables"]})},
        "review": {"by_decision": dict(Counter(c["review"].get("decision", "미입력") for c in cases)), "approved_cases": status_counts.get("approved", 0), "excluded_cases": status_counts.get("excluded", 0), "awaiting_human_review": sum(status_counts.get(s, 0) for s in ("draft", "review_required", "needs_adjudication")), "policy": "No generated or imported value changes annotation.review_status; only a human adjudicator can explicitly edit final labels and status."},
        "no_match": {"cases": [c["case_id"] for c in cases if c["gold"]["retrieval"]["expected_status"] == "NO_MATCH"], "verification_state": "review_required", "scope": "349-row Korean Bank project catalog snapshot; no live all-KOSIS catalog search endpoint was used; inspect recorded query phrase, terms, aliases and paths before accepting NO_MATCH"},
        "limits": ["The catalog and local data snapshot is dated 2026-09-14; KOSIS API partial metadata was queried 2026-09-23.", "Live metadata calls verify frequencies, periods, item and classification rows only. Units, comments and full series definitions remain unverified by the queried endpoints.", "A row in the current catalog is not automatically a relevant answer. All candidate relatedness scores and gold labels are proposals.", "The 150-case pilot is not statistically powered to settle small model differences."],
        "tables": tables,
    }
    (ROOT / "catalog_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    coverage_rows = [["record_type", "primary_type", "split", "catalog_path", "table_count", "case_count", "case_ids", "status"]]
    catalog_roots = sorted({(t.get("path") or ["N/A"])[0] for t in catalog["tables"]})
    for path in catalog_roots:
        tids = [t["table_id"] for t in tables if t["catalog_path"] and t["catalog_path"][0] == path]
        ids = sorted(cases_by_path.get(path, set()))
        coverage_rows.append(["catalog_path", "N/A", "N/A", path, str(len(tids)), str(len(ids)), ",".join(ids), "covered" if ids else "uncovered_review_required"])
    for kind in PRIMARY_COUNTS:
        for split in SPLIT_COUNTS:
            selected = [c for c in cases if c["primary_type"] == kind and c["split"] == split]
            coverage_rows.append(["type_split", kind, split, "N/A", "N/A", str(len(selected)), ",".join(c["case_id"] for c in selected), "draft"])
    with (ROOT / "coverage.csv").open("w", encoding="utf-8", newline="") as stream:
        csv.writer(stream, lineterminator="\n").writerows(coverage_rows)


def refresh_kosis() -> None:
    try:
        from statbridge_mcp.kosis_client import KosisClient
    except ImportError as exc:
        raise SystemExit("KOSIS client dependencies unavailable; install src/backend/requirements.txt") from exc
    cases = read_cases(); tids = sorted({x["table_id"] for c in cases for x in c["gold"]["retrieval"]["candidates"]})
    catalog = json.loads((REPO / "data/kosis/hankook_tables.json").read_text(encoding="utf-8-sig"))
    orgs = {t["tbl_id"]: t.get("org_id", "301") for t in catalog["tables"]}
    client = KosisClient(); result = {}
    for i, tid in enumerate(tids, 1):
        try:
            prd = client.get_prd_meta(orgs.get(tid, "301"), tid)
            itm = client.get_itm_meta(orgs.get(tid, "301"), tid)
            result[tid] = {"org_id": orgs.get(tid, "301"), "table_id": tid, "period_rows": prd, "item_class_rows": itm, "status": "ok" if prd or itm else "empty"}
        except Exception as exc:  # keep metadata gaps visible; never print request parameters or key
            result[tid] = {"org_id": orgs.get(tid, "301"), "table_id": tid, "status": "unavailable", "error_type": type(exc).__name__}
        if i % 10 == 0: print(f"KOSIS metadata {i}/{len(tids)}")
    payload = {"source": "KOSIS Open API via project KosisClient", "exported_at_utc": datetime.now(timezone.utc).isoformat(), "api_key_value_included": False, "table_count": len(tids), "failure_count": sum(v["status"] == "unavailable" for v in result.values()), "tables": result}
    (ROOT / "kosis_metadata_export.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"exported {len(tids)} table metadata records; failures={payload['failure_count']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    sub.add_parser("workbook")
    sub.add_parser("manifest")
    sub.add_parser("refresh-kosis")
    sub.add_parser("enrich-kosis")
    review = sub.add_parser("import-review"); review.add_argument("workbook", type=Path)
    args = parser.parse_args()
    if args.command == "refresh-kosis":
        refresh_kosis(); return
    if args.command == "enrich-kosis":
        cases = read_cases(); count = enrich_from_api(cases)
        CASES.write_text("".join(json.dumps(c, ensure_ascii=False, separators=(",", ":")) + "\n" for c in cases), encoding="utf-8", newline="\n")
        print(f"enriched {count} candidate metadata entries; unit/comments remain marked unavailable")
        return
    if args.command == "manifest":
        build_manifest()
        print(f"wrote {MANIFEST} and {ROOT / 'coverage.csv'}")
        return
    if args.command == "import-review":
        count = import_review(args.workbook)
        print(f"imported review inputs for {count} cases; gold and review_status unchanged; manifest refreshed")
        return
    cases = read_cases(); errors = validate(cases)
    for error in errors: print(error)
    if errors: raise SystemExit(1)
    print(f"OK: {len(cases)} cases; splits={dict(Counter(c['split'] for c in cases))}; review_status={dict(Counter(c['annotation']['review_status'] for c in cases))}")
    if args.command == "workbook":
        write_workbook(cases)
        print(f"wrote {WORKBOOK}")


if __name__ == "__main__":
    main()
