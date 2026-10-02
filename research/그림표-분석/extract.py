#!/usr/bin/env python3
"""Extract figure and table catalogs across the archived Bank of Korea reports.

The default run processes every report edition found in the archive. Known web
reports are snapshotted locally and reused unless --refresh-web is supplied.
Outputs are deterministic for a fixed archive and snapshot set.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
from html.parser import HTMLParser
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

try:
    from openpyxl import load_workbook
except ImportError as exc:  # pragma: no cover - environment diagnostic
    raise SystemExit("openpyxl이 필요합니다. Codex 번들 Python을 사용하세요.") from exc

try:
    import pdfplumber
except ImportError as exc:  # pragma: no cover - environment diagnostic
    raise SystemExit("pdfplumber가 필요합니다. Codex 번들 Python을 사용하세요.") from exc


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "research" / "bok-archive" / "01-통화신용정책보고서" / "2026-03-12_통화신용정책보고서(2026년 3월)"
OUT_DIR = ROOT / "research" / "그림표-분석"
SNAPSHOT_DIR = OUT_DIR / "원본스냅샷"
REPORT_URL = "https://www.bok.or.kr/portal/bbs/B0000156/view.do?nttId=10096935&menuNo=200067"
JS_BASE = "https://static-cdn.bok.or.kr/static/portal/js/mcp/202603/"
WEB_ASSETS = {
    "report.html": REPORT_URL,
    "charts.js": JS_BASE + "charts.js",
    "data.js": JS_BASE + "data.js",
}
REPORT_NAME = "통화신용정책보고서 2026년 3월"
PUB_DATE = "2026-03-12"
UNKNOWN = "불명"
ROMAN_CHARS = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ"
ROMAN_RE = r"[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫIVXivx]+"
NUM_RE = re.compile(
    rf"(?:{ROMAN_RE}\s*[-‐‑‒–—.]\s*\d+(?:\s*[-‐‑‒–—.]\s*\d+)*|"
    r"(?:개요|참고)\s*\d+(?:[-.]\d+)*|박\s*[-‐‑‒–—.]\s*\d+|"
    r"\d+(?:[-.]\d+)+|(?<![\w])\d+(?=[\s.．]))"
)
TYPE_NAMES = {"line", "column", "bar", "scatter", "area", "spline", "pie"}
COMMON_FIELDS = [
    "보고서", "발간일", "구분", "번호", "제목", "사용 데이터·출처", "단위",
    "데이터 형태", "종류", "분석 목적", "통계기법·지수", "설명", "근거",
]
MASTER_FIELDS = ["결과물ID", *COMMON_FIELDS]
REVIEW_FIELDS = ["결과물ID", "필드", "자동추출값", "판단근거유형", "검수상태", "확정값", "수정이유"]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_or_fetch_snapshots(refresh: bool = False) -> tuple[dict[str, bytes], dict[str, dict[str, str]]]:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = SNAPSHOT_DIR / "manifest.json"
    try:
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous = {}
    old_records = {item.get("path"): item for item in previous.get("sources", [])}
    payloads: dict[str, bytes] = {}
    records: dict[str, dict[str, str]] = {}
    for filename, url in WEB_ASSETS.items():
        path = SNAPSHOT_DIR / filename
        if path.exists() and not refresh:
            content = path.read_bytes()
            old = old_records.get(filename, {})
            records[filename] = {
                "url": old.get("url", url),
                "path": filename,
                "captured_at_utc": old.get("captured_at_utc", "기존 스냅샷(수집시각 미기록)"),
                "sha256": sha256_bytes(content),
                "status": "snapshot",
            }
            payloads[filename] = content
            continue
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; BOK-report-research/1.0)"})
        try:
            with urlopen(request, timeout=45) as response:
                content = response.read()
                status = str(response.status)
            if filename == "report.html" and b"report-wrap" not in content:
                raise ValueError("응답에 report-wrap이 없습니다.")
            path.write_bytes(content)
            captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            records[filename] = {
                "url": url,
                "path": filename,
                "captured_at_utc": captured_at,
                "sha256": sha256_bytes(content),
                "status": status,
            }
            payloads[filename] = content
        except Exception as exc:  # Keep local inputs usable when web is unavailable.
            if path.exists():
                content = path.read_bytes()
                payloads[filename] = content
                old = old_records.get(filename, {})
                records[filename] = {
                    "url": old.get("url", url), "path": filename,
                    "captured_at_utc": old.get("captured_at_utc", "기존 스냅샷"),
                    "sha256": sha256_bytes(content), "status": "snapshot-fallback",
                }
            else:
                records[filename] = {
                    "url": url, "path": filename, "captured_at_utc": "불명",
                    "sha256": "불명", "status": f"접근 실패: {type(exc).__name__}: {exc}",
                }
    manifest = {
        "report": REPORT_NAME,
        "sources": [records[name] for name in WEB_ASSETS],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payloads, records


class Node:
    __slots__ = ("tag", "attrs", "parent", "children")

    def __init__(self, tag: str, attrs: dict[str, str] | None = None, parent: "Node | None" = None):
        self.tag = tag
        self.attrs = attrs or {}
        self.parent = parent
        self.children: list[Node | str] = []

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self) -> str:
        pieces: list[str] = []
        for child in self.children:
            pieces.append(child.text() if isinstance(child, Node) else child)
        return " ".join(" ".join(pieces).split())


VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class TreeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, dict(attrs), self.stack[-1]))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if data.strip():
            self.stack[-1].children.append(data)


def report_html_fragment(document: str) -> str:
    match = re.search(r"<div\b[^>]*class\s*=\s*['\"][^'\"]*\breport-wrap\b[^'\"]*['\"][^>]*>", document, re.I)
    if not match:
        return ""
    start = match.start()
    depth = 0
    token_re = re.compile(r"</?div\b[^>]*>", re.I)
    for token in token_re.finditer(document, start):
        if token.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                return document[start:token.end()]
        elif not token.group(0).rstrip().endswith("/>"):
            depth += 1
    return document[start:]


def norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def extract_number(text: str) -> str:
    m = NUM_RE.search(norm_text(text))
    return canonical_number(m.group(0)) if m else UNKNOWN


def canonical_number(value: str) -> str:
    value = unicodedata.normalize("NFKC", norm_text(value)).upper()
    value = re.sub(r"\s*[-‐‑‒–—.]\s*", "-", value)
    value = re.sub(r"^(개요|참고)\s*", lambda m: m.group(1) + " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


def item_id(kind: str, number: str, title: str) -> str:
    key = canonical_number(number) if number != UNKNOWN else re.sub(r"[^0-9A-Za-z가-힣]+", "", title).lower()[:48]
    if not key:
        key = hashlib.sha256(title.encode("utf-8")).hexdigest()[:12]
    return f"MCP2603-{kind}-{key or 'UNKNOWN'}"


def make_record(kind: str, number: str, title: str, evidence: str) -> dict[str, str]:
    row = {field: UNKNOWN for field in COMMON_FIELDS}
    row.update({
        "보고서": REPORT_NAME, "발간일": PUB_DATE, "구분": kind,
        "번호": number or UNKNOWN, "제목": title or UNKNOWN,
        "사용 데이터·출처": UNKNOWN, "단위": UNKNOWN, "데이터 형태": UNKNOWN,
        "종류": UNKNOWN, "분석 목적": UNKNOWN, "통계기법·지수": UNKNOWN,
        "설명": UNKNOWN, "근거": evidence or UNKNOWN,
    })
    row["결과물ID"] = item_id(kind, row["번호"], row["제목"])
    return row


def row_key(record: dict[str, str]) -> tuple[str, str]:
    if record["번호"] != UNKNOWN:
        return record["구분"], canonical_number(record["번호"])
    title = re.sub(r"[^0-9A-Za-z가-힣]+", "", record["제목"]).lower()
    return record["구분"], title or "@" + record.get("근거", UNKNOWN)


def parse_caption(text: str) -> tuple[str, str, str] | None:
    text = norm_text(text)
    text = re.split(r"\s+자료\s*:", text, maxsplit=1)[0].strip()
    m = re.search(r"(그림|표)\s*(.*?)\s*[.．]\s*(.*)$", text)
    if not m:
        m = re.search(r"(그림|표)\s*(.*?)\s+(.*)$", text)
    if not m:
        return None
    kind = "그림" if m.group(1) == "그림" else "표"
    num_part = m.group(2).strip(" .．")
    num_m = NUM_RE.search(num_part)
    if num_m:
        number = canonical_number(num_m.group(0))
        title = m.group(3).strip()
    else:
        number = UNKNOWN
        title = (num_part + " " + m.group(3)).strip()
    return kind, number, title or UNKNOWN


def parse_html_sources(html_bytes: bytes, chart_js: bytes | None, source_records: dict[str, dict[str, str]]):
    text = html_bytes.decode("utf-8", "replace")
    if "report-wrap" not in text:
        return [], {"error": "report-wrap 없음", "figures": 0, "tables": 0}
    parser = TreeParser()
    parser.feed(text)
    roots = list(parser.root.walk())
    # The page has a placeholder report-wrap followed by the actual rendered
    # report-wrap text-wrap, both inside template_wrap. Select the report
    # container with the richest figure/table content.
    wrappers = [n for n in roots if n.tag == "div" and (
        "template_wrap" in n.attrs.get("class", "").split() or
        "report-wrap" in n.attrs.get("class", "").split())]
    report_node = max(wrappers, key=lambda n: sum(z.tag in {"figure", "table"} for z in n.walk()), default=parser.root)
    nodes = list(report_node.walk())
    js_map = parse_chart_types(chart_js.decode("utf-8", "replace")) if chart_js else {}
    html_chart_ids = {n.attrs.get("id", "") for n in nodes if re.fullmatch(r"graph\d+_\d+", n.attrs.get("id", ""))}
    results: list[dict[str, str]] = []
    figures = [n for n in nodes if n.tag == "figure"]
    for idx, fig in enumerate(figures, 1):
        cap = next((n for n in fig.walk() if n.tag == "figcaption"), None)
        cap_text = cap.text() if cap else fig.text()
        parsed = parse_caption(cap_text)
        kind, number, title = parsed if parsed and parsed[0] == "그림" else ("그림", UNKNOWN, cap_text or UNKNOWN)
        eid = fig.attrs.get("id", "")
        types = js_map.get(eid, [])
        has_image = any(n.tag == "img" for n in fig.walk())
        record = make_record(kind, number, title, f"HTML report-wrap figure {idx}; {REPORT_URL}")
        record["사용 데이터·출처"] = extract_source(fig.text())
        record["단위"] = extract_unit(fig.text())
        record["종류"] = "+".join(types) if types else ("이미지/사진" if has_image else UNKNOWN)
        if has_image and not types:
            record["근거"] += "; HTML figure contains img; chart type not declared"
        elif types:
            record["근거"] += f"; charts.js #{eid}"
        record["설명"] = html_context(fig) or UNKNOWN
        record["_source"] = "HTML"
        results.append(record)

    table_info_nodes = [n for n in nodes if "table-info" in n.attrs.get("class", "").split()]
    seen_blocks: set[int] = set()
    table_count = 0
    for info in table_info_nodes:
        block = info.parent
        while block and not any(child.tag == "table" for child in block.walk()):
            block = block.parent
        if block is None or id(block) in seen_blocks:
            continue
        # Select the nearest table container, preventing nested outer wrappers from duplicating a table.
        table_nodes = [n for n in block.walk() if n.tag == "table"]
        if not table_nodes:
            continue
        seen_blocks.add(id(block))
        table_count += 1
        info_text = info.text()
        title, source, unit = parse_table_info(info)
        table = table_nodes[0]
        caption_node = next((n for n in block.walk() if n.tag == "caption"), None)
        if caption_node is None:
            caption_node = next((n for n in block.walk() if "sr-only" in n.attrs.get("class", "").split()), None)
        caption = caption_node.text() if caption_node else ""
        cap_parsed = parse_caption(caption)
        info_parsed = parse_caption(title)
        if info_parsed and info_parsed[0] == "표":
            _, number, clean_title = info_parsed
            title = clean_title
        elif cap_parsed and cap_parsed[0] == "표":
            _, number, cap_title = cap_parsed
            title = title if title != UNKNOWN else cap_title
        else:
            number = extract_number(info_text + " " + caption)
        rows = [n for n in table.walk() if n.tag == "tr"]
        col_count = max((sum(1 for c in row.walk() if c.tag in {"td", "th"}) for row in rows), default=0)
        head = next((" / ".join(c.text() for c in row.walk() if c.tag in {"th", "td"}) for row in rows if row), "")
        record = make_record("표", number, title, f"HTML table-info block {table_count}; {REPORT_URL}")
        record["사용 데이터·출처"] = source or UNKNOWN
        record["단위"] = unit or UNKNOWN
        record["데이터 형태"] = f"단면 표, 행 {len(rows)}개, 열 {col_count}개"
        record["종류"] = f"표 구조: {len(rows)}행 × {col_count}열; 머리글/첫 행: {text_excerpt(head, 160) or UNKNOWN}"
        record["설명"] = text_excerpt(caption, 500) if caption else (html_context(block) or UNKNOWN)
        record["근거"] += "; HTML 표 구조 파싱, 수치 원문 시각 검수 필요"
        record["_source"] = "HTML"
        results.append(record)
    return results, {"figures": len(figures), "tables": table_count, "report_wrap": True,
                     "js_chart_ids": len(js_map), "html_chart_ids": len(html_chart_ids),
                     "js_html_chart_id_matches": len(html_chart_ids & set(js_map))}


def parse_table_info(node: Node) -> tuple[str, str, str]:
    title = source = unit = ""
    spans = [n for n in node.walk() if n.tag in {"span", "strong", "p"}]
    for span in spans:
        text = span.text()
        cls = span.attrs.get("class", "").split()
        if "unit" in cls:
            unit = text
        elif "자료:" in text or text.startswith("자료"):
            source = re.sub(r"^자료\s*:\s*", "", text)
        elif text and title == "" and not any(x in text for x in ("자료:", "단위:")):
            title = text
    if not source:
        source = extract_source(node.text())
    if not unit:
        unit = extract_unit(node.text())
    return title or UNKNOWN, source or UNKNOWN, unit or UNKNOWN


def html_context(node: Node) -> str:
    section = node.parent
    while section and "report-section" not in section.attrs.get("class", "").split():
        section = section.parent
    if section is None:
        return ""
    branch = node
    while branch.parent and branch.parent is not section:
        branch = branch.parent
    try:
        index = section.children.index(branch)
    except ValueError:
        return ""
    for sibling in reversed(section.children[max(0, index - 6):index]):
        if isinstance(sibling, Node) and sibling.tag == "p":
            text = sibling.text()
            if len(text) >= 25 and not text.startswith(("자료:", "주:")):
                sentences = re.split(r"(?<=[.!?])\s+", text)
                selected = [sentence.strip() for sentence in sentences if sentence.strip()][:2]
                return text_excerpt(" ".join(selected), 500)
    return ""


def extract_source(text: str) -> str:
    match = re.search(r"자료\s*:\s*([^()\n]+?)(?=\s*(?:단위\s*:|\([^)]{0,60}\)\s*$)|$)", norm_text(text))
    return norm_text(match.group(1)).strip(" ,") if match else UNKNOWN


def extract_unit(text: str) -> str:
    match = re.search(r"단위\s*:\s*([^\n]+)", text)
    if match:
        return norm_text(match.group(1))
    match = re.search(r"\((?:전년동기대비|전기대비|단위|%|억|조|bp|%p)[^)]*\)", norm_text(text))
    return match.group(0) if match else UNKNOWN


def parse_chart_types(source: str) -> dict[str, list[str]]:
    """Associate generated graph container IDs with declared series types."""
    found: dict[str, set[str]] = defaultdict(set)
    id_matches = list(re.finditer(r"\bconst\s+id\s*=\s*(['\"])([^'\"]+)\1", source))
    for i, match in enumerate(id_matches):
        chart_id = match.group(2)
        if not re.fullmatch(r"graph\d+_\d+", chart_id):
            continue
        end = id_matches[i + 1].start() if i + 1 < len(id_matches) else len(source)
        snippet = source[match.start():end]
        for t in re.findall(r"\btype\s*:\s*['\"]([A-Za-z]+)['\"]", snippet):
            t = t.lower()
            if t in TYPE_NAMES:
                found[chart_id].add(t)
    if found:
        return {key: sorted(value) for key, value in found.items()}
    # Fallback for bundles that pass literal IDs directly to Highcharts.chart.
    call = re.compile(r"(?:Highcharts\.(?:chart|stockChart)|Highcharts\.chart)\s*\(")
    for match in call.finditer(source):
        pos = match.end()
        arg = re.match(r"\s*(['\"])([^'\"]+)\1\s*,", source[pos:])
        if not arg:
            continue
        chart_id = arg.group(2)
        obj_start = pos + arg.end()
        brace = source.find("{", obj_start)
        if brace < 0:
            continue
        obj_end = balanced_end(source, brace, "{", "}")
        snippet = source[brace:obj_end] if obj_end > brace else source[brace:brace + 5000]
        for t in re.findall(r"\btype\s*:\s*['\"]([A-Za-z]+)['\"]", snippet):
            t = t.lower()
            if t in TYPE_NAMES:
                found[chart_id].add(t)
    return {key: sorted(value) for key, value in found.items()}


def balanced_end(text: str, start: int, opening: str, closing: str) -> int:
    depth = 0
    quote = ""
    escaped = False
    line_comment = block_comment = False
    i = start
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if line_comment:
            if ch == "\n": line_comment = False
        elif block_comment:
            if ch == "*" and nxt == "/": block_comment = False; i += 1
        elif quote:
            if escaped: escaped = False
            elif ch == "\\": escaped = True
            elif ch == quote: quote = ""
        elif ch == "/" and nxt == "/": line_comment = True; i += 1
        elif ch == "/" and nxt == "*": block_comment = True; i += 1
        elif ch in "'\"`": quote = ch
        elif ch == opening: depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0: return i + 1
        i += 1
    return len(text)


def parse_excel_serial(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and 20000 <= value <= 60000:
        return date(1899, 12, 30) + timedelta(days=int(value))
    if isinstance(value, str):
        s = value.strip()
        m = re.match(r"^(\d{4})[./-](\d{1,2})(?:[./-](\d{1,2}))?$", s)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3) or 1))
            except ValueError:
                return None
        m = re.match(r"^(\d{4})\s*년\s*(\d{1,2})\s*월", s)
        if m:
            return date(int(m.group(1)), int(m.group(2)), 1)
        m = re.match(r"^(\d{4})\s*[Qq]([1-4])$", s)
        if m:
            return date(int(m.group(1)), (int(m.group(2)) - 1) * 3 + 1, 1)
    return None


def sheet_number(name: str) -> str:
    if name.startswith("참고"):
        match = NUM_RE.search(name)
        return canonical_number("참고 " + match.group(0)) if match else UNKNOWN
    normalized = unicodedata.normalize("NFKC", name)
    match = re.search(r"(?:그림|표)[>\s]*([IVX]+\s*[-.‐‑‒–—]\s*\d+(?:[-.]\d+)*|\d+(?:[-.]\d+)*)", normalized, re.I)
    if match:
        return canonical_number(match.group(1))
    # Some workbook tabs end with a bare chart index before a closing bracket,
    # e.g. "<금융안정 주요 지표1>".
    match = re.search(r"(\d+(?:[-.]\d+)*)\s*>\s*$", normalized)
    if match:
        return canonical_number(match.group(1))
    match = NUM_RE.search(name)
    return canonical_number(match.group(0)) if match else UNKNOWN


def analyse_sheet(sheet) -> dict[str, str]:
    rows = list(sheet.iter_rows(values_only=True))
    flat = [[v for v in row] for row in rows]
    title = ""
    source = unit = ""
    for row in flat[:18]:
        texts = [norm_text(str(v)) for v in row if v is not None]
        for text in texts:
            if text.startswith("자료") and text.strip() != "자료":
                source = re.sub(r"^자료\s*:\s*", "", text)
            if text.startswith("단위") and text.strip() != "단위":
                unit = re.sub(r"^단위\s*:\s*", "", text)
        if not title:
            for text in texts:
                tagged = re.match(r"^<[^>]+>\s*(.+)$", text)
                if tagged and tagged.group(1).strip():
                    title = tagged.group(1).strip()
                    break
                if re.match(r"^\d+[.]\s+\S", text) or re.match(r"^(?:그림|표)\s*\S", text):
                    title = re.sub(r"^(?:\d+[.]\s*|그림\s*|표\s*)", "", text)
                    break
    header_row_idx = None
    for i, row in enumerate(flat[:30]):
        if any(norm_text(str(v)).startswith("항목") for v in row if v is not None):
            header_row_idx = i
            break
    if header_row_idx is not None:
        headers = flat[header_row_idx]
        units = flat[header_row_idx + 1] if header_row_idx + 1 < len(flat) else []
        if not unit:
            units_text = [norm_text(str(v)) for v in units[1:] if v is not None and norm_text(str(v))]
            unit = "; ".join(dict.fromkeys(units_text))
        data_start = header_row_idx + 2
        series = [norm_text(str(v)) for v in headers[1:] if v is not None and norm_text(str(v)) not in {"항목", "단위"}]
        first_col = [row[0] if row else None for row in flat[data_start:] if row and row[0] is not None]
    else:
        header_row_idx = next((i for i, row in enumerate(flat[:30]) if row and any(norm_text(str(v)) in {"그림", "항목"} for v in row if v is not None)), None)
        headers = flat[header_row_idx] if header_row_idx is not None else []
        units = flat[header_row_idx + 1] if header_row_idx is not None and header_row_idx + 1 < len(flat) else []
        data_start = (header_row_idx + 2) if header_row_idx is not None else len(flat)
        series = [norm_text(str(v)) for v in headers[1:] if v is not None and norm_text(str(v)) not in {"항목", "단위"}]
        first_col = [row[0] if row and row[0] is not None else None for row in flat[data_start:]]
    dates = sorted({dt for value in first_col if (dt := parse_excel_serial(value)) is not None})
    nobs = len([v for v in first_col if v is not None])
    if dates:
        diffs = [(b - a).days for a, b in zip(dates, dates[1:]) if b > a]
        gap = median(diffs) if diffs else 0
        freq = "일" if gap <= 7 else "월" if gap <= 45 else "분기" if gap <= 140 else "연"
        shape = f"시계열, {freq}, {dates[0].isoformat()}~{dates[-1].isoformat()}, 계열 {len(series)}개"
    else:
        shape = f"단면, 관측 {nobs}건, 계열 {len(series)}개" if nobs else f"데이터 구조 불명, 계열 {len(series)}개"
    all_text = " ".join(norm_text(str(v)) for row in flat[:18] for v in row if v is not None)
    if not source:
        source = extract_source(all_text)
    return {"title": title or UNKNOWN, "source": source or UNKNOWN, "unit": unit or UNKNOWN,
            "shape": shape, "series": " / ".join(series) or UNKNOWN,
            "observations": str(nobs), "first_date": dates[0].isoformat() if dates else UNKNOWN,
            "last_date": dates[-1].isoformat() if dates else UNKNOWN}


def parse_workbook(xlsx_path: Path) -> tuple[list[dict[str, str]], dict[str, dict[str, str]], dict[str, int]]:
    book = load_workbook(xlsx_path, data_only=True, read_only=True)
    sheet_data: dict[str, dict[str, str]] = {}
    for sheet in book.worksheets:
        if sheet.title == "목차":
            continue
        sheet_data[sheet.title] = analyse_sheet(sheet)
    results: list[dict[str, str]] = []
    toc_count = 0
    toc = book["목차"] if "목차" in book.sheetnames else None
    if toc:
        for row in toc.iter_rows(values_only=True):
            for value in row:
                if not isinstance(value, str):
                    continue
                parsed = parse_caption(value.strip("<> "))
                if parsed and parsed[0] == "그림":
                    kind, number, title = parsed
                    if number == UNKNOWN:
                        continue
                    sheet_name = match_sheet(number, sheet_data)
                    meta = sheet_data.get(sheet_name or "", {})
                    record = make_record("그림", number, title, f"xlsx:목차; xlsx:{sheet_name or UNKNOWN}")
                    apply_sheet_meta(record, meta)
                    record["제목"] = title or meta.get("title", UNKNOWN)
                    record["_source"] = "XLSX"
                    record["_sheet"] = sheet_name or UNKNOWN
                    results.append(record)
                    toc_count += 1
    # Summary figures and appendix chart-data sheets are not always listed as ordinary body figures.
    for sheet_name, meta in sheet_data.items():
        if re.fullmatch(r"개요\s*\d+", sheet_name):
            n = re.search(r"\d+", sheet_name).group(0)
            num = f"개요 {n}"
            if not any(row["번호"] == num for row in results):
                row = make_record("그림", num, meta["title"], f"xlsx:{sheet_name}")
                apply_sheet_meta(row, meta)
                row["_source"] = "XLSX"
                row["_sheet"] = sheet_name
                results.append(row)
        elif sheet_name.startswith("참고"):
            num = sheet_number(sheet_name)
            if num != UNKNOWN and not any(row["번호"] == num for row in results):
                row = make_record("그림", num, meta["title"], f"xlsx:{sheet_name}")
                apply_sheet_meta(row, meta)
                row["_source"] = "XLSX"
                row["_sheet"] = sheet_name
                results.append(row)
    counts = {"workbook_sheets": len(sheet_data), "toc_figures": toc_count,
              "overview_sheets": sum(bool(re.fullmatch(r"개요\s*\d+", s)) for s in sheet_data),
              "appendix_sheets": sum(s.startswith("참고") for s in sheet_data)}
    book.close()
    return results, sheet_data, counts


def match_sheet(number: str, data: dict[str, dict[str, str]]) -> str | None:
    target = canonical_number(number)
    for name in data:
        if sheet_number(name) == target:
            return name
    return None


def apply_sheet_meta(record: dict[str, str], meta: dict[str, str]):
    if not meta:
        return
    record["제목"] = meta.get("title", UNKNOWN) if record["제목"] == UNKNOWN else record["제목"]
    record["사용 데이터·출처"] = meta.get("source", UNKNOWN)
    record["단위"] = meta.get("unit", UNKNOWN)
    record["데이터 형태"] = meta.get("shape", UNKNOWN)
    record["_series"] = meta.get("series", UNKNOWN)


def parse_pdf(pdf_path: Path):
    records: list[dict[str, str]] = []
    page_reviews: list[dict[str, str]] = []
    page_count = 0
    total_text_chars = 0
    toc_figures = toc_tables = body_captions = 0
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        toc_mode = ""
        for pageno, page in enumerate(pdf.pages, 1):
            text = page.extract_text(layout=False) or ""
            total_text_chars += len(text)
            normalized = norm_text(text)
            if len(normalized) < 24:
                reasons = ["텍스트가 거의 없어 이미지형 페이지 여부 확인 필요"]
                try:
                    if page.images:
                        reasons.append("이미지 객체가 있으나 캡션 텍스트를 찾지 못함")
                except Exception:
                    reasons.append("이미지 객체 점검 실패")
                page_reviews.append({"page": str(pageno), "text_length": str(len(normalized)),
                                     "reason": "; ".join(reasons)})
            lines = [norm_text(line) for line in text.splitlines()]
            heading_mode = ""
            if re.search(r"그림\s*차례", text[:1200]):
                heading_mode = "그림"
            elif re.search(r"(?:통계표|표)\s*차례", text[:1200]):
                heading_mode = "표"
            if heading_mode:
                toc_mode = heading_mode
                is_index = True
            elif toc_mode:
                # Continue a multi-page list only while its leading lines keep
                # the caption-plus-page-number pattern. Do not let a TOC label
                # leak into subsequent body pages.
                continued = sum(bool(re.match(r"^\s*(?:그림|표)\s*" + NUM_RE.pattern + r".*\s+\d{1,3}$", line))
                                for line in lines[:24])
                is_index = continued >= 3
                if not is_index:
                    toc_mode = ""
            else:
                is_index = False
            for i, line in enumerate(lines):
                # Reports use several caption layouts: plain "그림 I-1.",
                # bracketed "[그림 1.22]", or multiple captions on one line.
                marker = re.compile(r"(?:\[|<)?\s*(그림|표)\s*(" + NUM_RE.pattern + r")\s*(?:\]|>)?")
                matches = list(marker.finditer(line))
                for match_index, match in enumerate(matches):
                    prefix = line[:match.start()]
                    if prefix.strip() and not match.group(0).lstrip().startswith("["):
                        continue
                    kind = "그림" if match.group(1) == "그림" else "표"
                    if is_index and kind != toc_mode:
                        continue
                    number = canonical_number(match.group(2))
                    end = matches[match_index + 1].start() if match_index + 1 < len(matches) else len(line)
                    title = line[match.end():end].strip(" .．:;[]<> ")
                    reported_page = ""
                    if is_index:
                        page_match = re.search(r"\s+(\d{1,3})\s*$", title)
                        if page_match:
                            reported_page = page_match.group(1)
                            title = title[:page_match.start()].rstrip()
                        evidence = f"PDF p.{pageno} 그림·통계표 차례"
                        if reported_page:
                            evidence += f"; 보고서 쪽수 {reported_page}"
                        context = ""
                        toc_figures += kind == "그림"
                        toc_tables += kind == "표"
                    else:
                        evidence = f"PDF p.{pageno} (본문 텍스트 추출)"
                        context = nearest_explanatory_sentence(lines, i)
                        body_captions += 1
                    if not title and not is_index and i + 1 < len(lines):
                        title = lines[i + 1]
                    if kind == "표":
                        evidence += "; 표 텍스트 정확도 낮음, 원본 페이지 대조 필요"
                    row = make_record(kind, number, title or UNKNOWN, evidence)
                    row["설명"] = context or UNKNOWN
                    neighbor = " ".join(lines[max(0, i - 2):min(len(lines), i + 3)]) if not is_index else ""
                    row["사용 데이터·출처"] = extract_source(neighbor)
                    row["단위"] = extract_unit(neighbor)
                    row["데이터 형태"] = UNKNOWN
                    row["_source"] = "PDF"
                    row["_page"] = str(pageno)
                    row["_reported_page"] = reported_page or UNKNOWN
                    records.append(row)
    return records, {"pdf_pages": page_count, "pdf_text_chars": total_text_chars,
                     "pdf_caption_candidates": len(records), "pdf_toc_figures": int(toc_figures),
                     "pdf_toc_tables": int(toc_tables), "pdf_body_captions": body_captions,
                     "page_reviews": page_reviews}


def nearest_explanatory_sentence(lines: list[str], index: int) -> str:
    # Prefer a complete Korean prose sentence. Chart labels and axis ticks often
    # sit next to PDF captions but do not end in a Korean sentence predicate.
    starts = sorted((j for j in range(len(lines)) if j != index), key=lambda j: (abs(j - index), j > index))
    for start in starts:
        if abs(start - index) > 8:
            continue
        for direction in (1, -1):
            chunk = []
            for step in range(4):
                j = start + direction * step
                if j < 0 or j >= len(lines) or j == index:
                    break
                part = lines[j]
                if re.match(r"^(?:그림|표|자료\s*:|단위\s*:|주\s*:)", part):
                    break
                chunk.append(part)
                candidate = " ".join(chunk if direction == 1 else reversed(chunk))
                candidate = norm_text(candidate)
                ending = re.search(r"([^.!?]{20,}(?:다\.|한다\.|있다\.|된다\.|이었다\.|했다\.|것이다\.?))\s*$", candidate)
                if ending:
                    sentence = ending.group(1)
                    korean = len(re.findall(r"[가-힣]", sentence))
                    digits = len(re.findall(r"\d", sentence))
                    if korean >= 20 and digits < korean:
                        return text_excerpt(sentence, 400)
    return ""


def merge_records(groups: list[list[dict[str, str]]], chart_js: bytes | None) -> list[dict[str, str]]:
    merged: dict[tuple[str, str], dict[str, str]] = {}
    source_order = {"XLSX": 0, "HTML": 1, "PDF": 2}
    for group in groups:
        for incoming in group:
            key = row_key(incoming)
            if key not in merged:
                merged[key] = incoming.copy()
                continue
            current = merged[key]
            # XLSX wins for figures' series metadata; HTML/PDF fill descriptions and source evidence.
            for field in COMMON_FIELDS:
                if current.get(field, UNKNOWN) == UNKNOWN and incoming.get(field, UNKNOWN) != UNKNOWN:
                    current[field] = incoming[field]
            if incoming.get("설명", UNKNOWN) != UNKNOWN and current.get("설명", UNKNOWN) == UNKNOWN:
                current["설명"] = incoming["설명"]
            current["근거"] = join_evidence(current.get("근거", ""), incoming.get("근거", ""))
            current["_sources"] = sorted(set(current.get("_sources", [current.get("_source", "불명")]) + [incoming.get("_source", "불명")]))
            # Keep the canonical number and prefer the most informative title.
            if current["제목"] == UNKNOWN and incoming["제목"] != UNKNOWN:
                current["제목"] = incoming["제목"]
    js_map = parse_chart_types(chart_js.decode("utf-8", "replace")) if chart_js else {}
    for record in merged.values():
        record.setdefault("_sources", [record.get("_source", "불명")])
        if record["구분"] == "그림" and record["종류"] == UNKNOWN:
            types = types_for_record(record, js_map)
            if types:
                record["종류"] = "+".join(types)
                chart_id = chart_id_for_number(record["번호"])
                record["근거"] += f"; HTML #{chart_id}; charts.js #{chart_id}에 선언된 type"
            else:
                record["종류"] = UNKNOWN
                record["근거"] += "; 결과물별 차트 ID 연결 불가, 데이터 형태만으로 그래프 종류를 확정할 수 없음"
        record["분석 목적"] = purpose(record["구분"], record["제목"], record.get("_series", UNKNOWN))
        record["통계기법·지수"] = methods_tags(record["제목"] + " " + record.get("_series", "") + " " + record["설명"])
        record["결과물ID"] = item_id(record["구분"], record["번호"], record["제목"], record.get("_scope", "main"))
        for field in COMMON_FIELDS:
            if not record.get(field):
                record[field] = UNKNOWN
        # A title inferred from the first cell of an XLSX sheet needs an explicit status in evidence.
    return sorted(merged.values(), key=lambda r: (r["구분"] != "그림", number_sort_key(r["번호"]), r["제목"]))


def types_for_record(record: dict[str, str], mapping: dict[str, list[str]]) -> list[str]:
    chart_id = chart_id_for_number(record["번호"])
    return mapping.get(chart_id, [])


def chart_id_for_number(value: str) -> str:
    num = canonical_number(value)
    match = re.fullmatch(r"I-(\d+)", num)
    if match:
        return f"graph1_{match.group(1)}"
    else:
        match = re.fullmatch(r"II-(\d+)", num)
        if match:
            return f"graph3_{match.group(1)}"
        else:
            match = re.fullmatch(r"III-(\d+)", num)
            if match:
                return f"graph4_{match.group(1)}"
            else:
                match = re.fullmatch(r"개요\s+(\d+)", num)
                return f"graph0_{match.group(1)}" if match else ""


def join_evidence(a: str, b: str) -> str:
    items = [x.strip() for x in (a or "").split("; ") + (b or "").split("; ") if x.strip() and x.strip() != UNKNOWN]
    return "; ".join(dict.fromkeys(items)) or UNKNOWN


def number_sort_key(value: str):
    if value == UNKNOWN:
        return (99, 99, 99, value)
    s = canonical_number(value)
    roman = re.match(r"(개요|참고)?\s*([IVX]+)?-?(\d+)?(?:-(\d+))?", s)
    return (0, (roman.group(2) or "") if roman else "", int(roman.group(3) or 0) if roman else 0,
            int(roman.group(4) or 0) if roman else 0, s)


def purpose(kind: str, title: str, series: str) -> str:
    if title == UNKNOWN:
        return UNKNOWN
    combined = title + " " + series
    if kind == "표":
        return f"‘{title}’ 관련 수치와 항목 구성을 정리한 표로 해석됨(제목 기반 추론)."
    if any(word in combined for word in ("전망", "예상")):
        return f"‘{title}’의 전망 경로를 제시하는 목적(제목 기반 추론)."
    if "기여도" in combined or "기여" in combined:
        return f"‘{title}’의 구성 항목별 기여도를 비교하는 목적(제목 기반 추론)."
    if any(word in combined for word in ("비중", "구성", "구성비")):
        return f"‘{title}’의 항목별 구성 또는 비중 변화를 보이는 목적(제목 기반 추론)."
    if any(word in combined for word in ("차", "스프레드", "금리차")):
        return f"‘{title}’의 차이 또는 스프레드 변화를 비교하는 목적(제목 기반 추론)."
    return f"‘{title}’의 수준과 변화를 보이는 목적(제목 기반 추론)."


def methods_tags(text: str) -> str:
    terms = [
        (r"성장률|증가율|상승률|하락률", "성장률/변화율"),
        (r"기여도", "기여도"),
        (r"FSI|금융스트레스지수", "지수(FSI)"),
        (r"FVI|금융취약성지수", "지수(FVI)"),
        (r"PMI|구매관리자지수", "지수(PMI)"),
        (r"M2", "통화지표(M2)"),
        (r"DXY|달러화지수", "지수(DXY)"),
        (r"스프레드|금리차|금리 격차", "스프레드"),
        (r"스트레스.?테스트|스트레스.?테스트", "스트레스테스트"),
        (r"회귀|회귀분석", "회귀"),
        (r"DSGE", "DSGE"),
        (r"나우캐스팅|nowcasting", "nowcasting"),
        (r"지수", "지수"),
    ]
    found = [label for pattern, label in terms if re.search(pattern, text, re.I)]
    if any(label.startswith("지수(") for label in found):
        found = [label for label in found if label != "지수"]
    return "; ".join(dict.fromkeys(found)) if found else UNKNOWN


def text_excerpt(value: str, limit: int) -> str:
    value = norm_text(value)
    if not value:
        return ""
    return value if len(value) <= limit else value[:limit - 1].rstrip() + "…"


def file_hashes(report_dir: Path) -> dict[str, str]:
    hashes = {}
    seen: dict[str, str] = {}
    for path in sorted(report_dir.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file():
            continue
        digest = sha256_bytes(path.read_bytes())
        if digest in seen:
            hashes[path.name] = f"중복 제외: {seen[digest]} (SHA-256 {digest})"
        else:
            seen[digest] = path.name
            hashes[path.name] = digest
    return hashes


def write_master(rows: list[dict[str, str]]):
    path = OUT_DIR / "그림표_마스터.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MASTER_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) or UNKNOWN for field in MASTER_FIELDS})
    return path


def write_review_log(rows: list[dict[str, str]]):
    path = OUT_DIR / "검수대장.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        for row in rows:
            for field in COMMON_FIELDS:
                writer.writerow({"결과물ID": row["결과물ID"], "필드": field,
                                 "자동추출값": row.get(field, UNKNOWN),
                                 "판단근거유형": evidence_type(field, row), "검수상태": "미검수",
                                 "확정값": "", "수정이유": ""})
    return path


def evidence_type(field: str, row: dict[str, str]) -> str:
    value = row.get(field, UNKNOWN)
    if value == UNKNOWN:
        return "불명"
    if field in {"분석 목적", "통계기법·지수"}:
        return "추론"
    if field == "종류":
        if "추론" in value:
            return "추론"
        if row["구분"] == "표" and value.startswith("표 구조:"):
            return "직접확인(HTML 구조 파싱)"
        return "직접확인"
    if field == "데이터 형태" and row["구분"] == "그림":
        return "직접+추론(원자료 관측값 및 주기 계산)"
    if field == "설명":
        return "직접인용"
    return "직접확인"


def write_markdown(rows: list[dict[str, str]], report_dir: Path, metrics: dict, sources: dict):
    board_dir = OUT_DIR / "01-통화신용정책보고서"
    board_dir.mkdir(parents=True, exist_ok=True)
    path = board_dir / "통화신용정책보고서_2026년_3월.md"
    report_files = file_hashes(report_dir)
    figures = [r for r in rows if r["구분"] == "그림"]
    tables = [r for r in rows if r["구분"] == "표"]
    chart_kind_counts = Counter(
        "추론" if "추론" in r["종류"] else "이미지" if r["종류"] == "이미지/사진" else
        "불명" if r["종류"] == UNKNOWN else "표 구조" if r["구분"] == "표" else "JS 직접확인"
        for r in rows
    )
    unresolved = {field: sum(r[field] == UNKNOWN for r in rows) for field in COMMON_FIELDS if field not in {"보고서", "발간일", "구분", "제목", "분석 목적", "근거"}}
    lines = [f"# {REPORT_NAME}", "", f"- 발간일: {PUB_DATE}",
             f"- 추출 결과: 그림 {len(figures)}건, 표 {len(tables)}건, 총 {len(rows)}건",
             f"- 출처별 인벤토리 합집합 {metrics['union_denominator']}건 중 출력 {len(rows)}건 ({metrics['coverage_percent']}). 이는 발견된 출처 목록 간 커버리지이며, PDF 모든 페이지의 수동 시각 검토율은 아닙니다.",
             f"- 출처별 발견: XLSX 목차 {metrics['xlsx_toc_figures']}건, 웹 그림 {metrics['html_figures']}건, 웹 표 {metrics['html_tables']}건, PDF 캡션 {metrics['pdf_captions']}건",
             f"- 종류 판정: 데이터 기반 추론 {chart_kind_counts['추론']}건, 이미지 {chart_kind_counts['이미지']}건, 표 구조 {chart_kind_counts['표 구조']}건, JS 번호별 직접 확인 {chart_kind_counts['JS 직접확인']}건, 불명 {chart_kind_counts['불명']}건",
             "- 주요 미확인 필드 건수: " + ", ".join(f"{field} {count}건" for field, count in unresolved.items() if count) + ".",
             "", "## 그림", ""]
    lines.extend(render_items(figures))
    lines.extend(["", "## 표", ""])
    lines.extend(render_items(tables))
    lines += ["", "## 추출 범위와 한계", "",
              f"- XLSX: {metrics['xlsx_sheets']}개 데이터 시트를 조사했습니다. 목차 그림 {metrics['xlsx_toc_figures']}건, 개요 그림 시트 {metrics['overview_sheets']}개, 참고 시트 {metrics['appendix_sheets']}개를 확인했습니다.",
              f"- 웹 HTML: report-wrap 안에서 그림 {metrics['html_figures']}개, table-info 표 블록 {metrics['html_tables']}개를 찾았습니다.",
              f"- PDF: {metrics['pdf_pages']}쪽에서 텍스트 {metrics['pdf_text_chars']:,}자를 읽었고 캡션 후보 {metrics['pdf_captions']}건을 찾았습니다. 캡션 검색만으로 발견되지 않은 이미지형 결과물은 XLSX·HTML 목록과 페이지 검토가 필요합니다.",
              f"- PDF 차례: 그림 {metrics.get('pdf_toc_figures', 0)}건, 표 {metrics.get('pdf_toc_tables', 0)}건을 인벤토리로 사용하고, 본문 캡션 후보 {metrics.get('pdf_body_captions', 0)}건을 별도 수집했습니다.",
              "- HTML 표의 행·열 요약은 구조 파싱값입니다. 숫자와 셀 병합의 정확성은 원본 PDF 대조 전까지 보장하지 않습니다.",
              f"- 버전 고정 charts.js·data.js를 보존했습니다. charts.js에서 결과물 번호에 매핑 가능한 ID {metrics.get('js_chart_ids', 0)}개, 그중 HTML에 존재하는 ID {metrics.get('js_html_chart_id_matches', 0)}개를 확인해 그래프 종류를 채웠습니다. 매핑되지 않는 그래프는 데이터 형태만으로 line/column 혼합을 구분할 수 없어 불명으로 남겼습니다.",
              "- 분석 목적은 제목·계열명에서 자동 추론한 문구입니다. 보고서 설명 인용이 없는 항목은 설명에 불명을 표시했습니다.",
              "", "## 원본 입력과 해시", ""]
    for filename, digest in report_files.items():
        lines.append(f"- `{filename}`: {digest}")
    lines += ["", "## 웹 스냅샷", ""]
    for name, item in sources.items():
        lines.append(f"- `{name}`: {item['status']}; SHA-256 `{item['sha256']}`; URL {item['url']}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def render_items(rows: list[dict[str, str]]) -> list[str]:
    lines: list[str] = []
    for row in rows:
        lines += [f"### {row['번호']} · {row['제목']}", "", f"- 결과물ID: `{row['결과물ID']}`"]
        for field in COMMON_FIELDS:
            lines.append(f"- **{field}:** {row.get(field, UNKNOWN)}")
        lines.append(f"- **데이터 요약:** {row.get('_series', UNKNOWN)}; {row.get('데이터 형태', UNKNOWN)}")
        lines.append("")
    return lines


def union_count(groups: list[list[dict[str, str]]]) -> int:
    keys = set()
    for group in groups:
        keys.update(row_key(item) for item in group)
    return len(keys)


ARCHIVE_DIR = ROOT / "research" / "bok-archive"
SNAPSHOT_ROOT = OUT_DIR / "원본스냅샷"
PAGE_REVIEW_FIELDS = ["보고서", "발간일", "파일", "PDF쪽", "텍스트길이", "검수사유"]


def report_key(name: str) -> str:
    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]


def report_identity(report_name: str, pub_date: str) -> str:
    return f"BOK-{pub_date.replace('-', '')}-{report_key(report_name)}"


def item_id(kind: str, number: str, title: str, scope: str = "main") -> str:
    stable = "|".join((REPORT_NAME, scope, kind, canonical_number(number), norm_text(title).casefold()))
    suffix = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]
    return f"{report_identity(REPORT_NAME, PUB_DATE)}-{kind}-{suffix}"


def row_key(record: dict[str, str]) -> tuple[str, str]:
    number = canonical_number(record.get("번호", UNKNOWN))
    scope = record.get("_scope", "main")
    title = norm_text(record.get("제목", "")).casefold()
    # Korean PDF captions often append footnote markers (1), 1), 1)2))
    # that are absent from the workbook title or web table title.
    title = re.sub(r"\s*\d+\)", "", title)
    title = re.sub(r"[^0-9a-z가-힣]+", "", title)
    # Printed hierarchical numbers uniquely identify a result within its
    # source document. Join TOC, body, XLSX and HTML variants by number;
    # source scope keeps identically numbered items in separate attachments apart.
    identity = number if number != UNKNOWN else (title or "unknown-title")
    return record.get("구분", UNKNOWN), scope + "|" + identity


def report_metadata(report_dir: Path) -> tuple[str, str, str]:
    board_dir = report_dir.parent
    board = re.sub(r"^\d+-", "", board_dir.name)
    date_match = re.match(r"^(\d{4}-\d{2}-\d{2})_", report_dir.name)
    pub_date = date_match.group(1) if date_match else UNKNOWN
    folder_title = report_dir.name[date_match.end():] if date_match else report_dir.name
    edition = re.search(r"\(([^()]*)\)", folder_title)
    if edition:
        publication = edition.group(1).strip()
    else:
        publication = folder_title
        if publication.startswith(board):
            publication = publication[len(board):].strip(" _-()")
        elif publication.endswith(board):
            publication = publication[:-len(board)].strip(" _-()")
        publication = publication or folder_title
    report_name = f"{board} {publication}".strip()
    return board, report_name, pub_date


def manifest_rows() -> dict[str, list[dict[str, str]]]:
    path = ARCHIVE_DIR / "manifest.csv"
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    if not path.exists():
        return grouped
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            relative = (row.get("저장경로") or "").replace("\\", "/")
            grouped[relative.split("/", 1)[0] + "/" + relative.split("/", 2)[1] if relative.count("/") >= 1 else relative].append(row)
    return grouped


def valid_input(path: Path, expected: str) -> bool:
    try:
        with path.open("rb") as stream:
            head = stream.read(16)
    except OSError:
        return False
    if expected == "pdf":
        return b"%PDF-" in head
    if expected == "xlsx":
        return head.startswith(b"PK\x03\x04")
    return False


def hash_unique_files(paths: list[Path]) -> tuple[list[Path], dict[str, str]]:
    seen: dict[str, Path] = {}
    hashes: dict[str, str] = {}
    unique: list[Path] = []
    for path in sorted(paths, key=lambda p: p.name.casefold()):
        digest = sha256_bytes(path.read_bytes())
        if digest in seen:
            hashes[path.name] = f"중복 제외: {seen[digest].name} (SHA-256 {digest})"
        else:
            seen[digest] = path
            hashes[path.name] = digest
            unique.append(path)
    return unique, hashes


def ensure_numbered_workbook_sheets(rows: list[dict[str, str]], sheet_data: dict[str, dict[str, str]], report_id: str):
    present = {row_key(row) for row in rows}
    for name, meta in sheet_data.items():
        number = sheet_number(name)
        is_overview = re.fullmatch(r"개요\s*\d+", name) is not None
        is_reference = name.startswith("참고")
        if number == UNKNOWN and not is_overview and not is_reference:
            continue
        if number == UNKNOWN:
            number = canonical_number(name)
        if meta.get("title", UNKNOWN) == UNKNOWN and meta.get("series", UNKNOWN) == UNKNOWN:
            continue
        row = make_record("그림", number, meta.get("title", UNKNOWN), f"xlsx:{name}; 목차 항목이 없어 시트명에서 번호 연결")
        apply_sheet_meta(row, meta)
        row["번호"] = number
        row["_source"] = "XLSX"
        row["_sheet"] = name
        # Bracketed labels such as <개관 1> and <현황Ⅰ-1-2> are workbook
        # navigation tabs, not necessarily the printed figure number.
        if name.startswith("<") and not re.match(r"^<(?:그림|표)\s*[IVX]+\s*[-.]\s*\d+", unicodedata.normalize("NFKC", name), re.I):
            row["_local_sheet_number"] = number
            row["번호"] = UNKNOWN
        row["결과물ID"] = item_id(row["구분"], row["번호"], row["제목"])
        key = row_key(row)
        if key in present:
            continue
        rows.append(row)
        present.add(key)


def title_match_key(value: str) -> str:
    value = norm_text(value).casefold()
    value = re.sub(r"\s*\d+\)", "", value)
    return re.sub(r"[^0-9a-z가-힣]", "", value)


def reconcile_local_workbook_rows(workbook_rows: list[dict[str, str]], other_rows: list[dict[str, str]]):
    """Map workbook navigation-tab labels to printed caption numbers by title."""
    from difflib import SequenceMatcher
    candidates = [row for row in other_rows if row.get("번호", UNKNOWN) != UNKNOWN]
    matched = unmatched = 0
    for row in workbook_rows:
        if not row.get("_local_sheet_number"):
            continue
        title = title_match_key(row.get("제목", ""))
        if len(title) < 5:
            unmatched += 1
            continue
        ranked = []
        for candidate in candidates:
            if candidate["구분"] != row["구분"]:
                continue
            other_title = title_match_key(candidate.get("제목", ""))
            if len(other_title) < 5:
                continue
            if title in other_title or other_title in title:
                score = min(len(title), len(other_title)) / max(len(title), len(other_title))
            else:
                score = SequenceMatcher(None, title, other_title).ratio()
            if score >= 0.82:
                ranked.append((score, candidate))
        ranked.sort(key=lambda pair: (-pair[0], pair[1]["번호"], pair[1]["제목"]))
        if not ranked:
            unmatched += 1
            row["번호"] = UNKNOWN
            row["_scope"] = "xlsx-sheet:" + compact_name(row.get("_sheet", ""))
            row["근거"] = join_evidence(row["근거"], f"xlsx 시트 내부 번호 {row['_local_sheet_number']}는 보고서 캡션과 연결되지 않아 불명")
            row["결과물ID"] = item_id(row["구분"], row["번호"], row["제목"], row["_scope"])
            continue
        best_score = ranked[0][0]
        best_matches = {(candidate.get("_scope", "main"), candidate["번호"])
                        for score, candidate in ranked if score >= best_score - 0.02}
        if len(best_matches) != 1:
            unmatched += 1
            row["번호"] = UNKNOWN
            row["_scope"] = "xlsx-sheet:" + compact_name(row.get("_sheet", ""))
            row["근거"] = join_evidence(row["근거"], "제목 일치 후보의 보고서 번호가 여러 개여서 번호 연결을 보류")
            row["결과물ID"] = item_id(row["구분"], row["번호"], row["제목"], row["_scope"])
            continue
        row["_scope"], row["번호"] = next(iter(best_matches))
        row["근거"] = join_evidence(row["근거"], f"xlsx 시트 제목을 PDF/HTML 캡션과 대조해 번호 연결 (유사도 {best_score:.2f})")
        row["_local_sheet_number"] = ""
        row["결과물ID"] = item_id(row["구분"], row["번호"], row["제목"], row["_scope"])
        matched += 1
    return {"matched_local_sheet_numbers": matched, "unmatched_local_sheet_numbers": unmatched}


def known_web_report(board: str, report_name: str) -> bool:
    return ((board == "통화신용정책보고서" and any(x in report_name for x in ("2025년 9월", "2026년 3월"))) or
            (board == "연차보고서" and "2025년도" in report_name))


def compact_name(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", value.casefold())


def choose_pdf_sources(paths: list[Path], board: str, report_name: str):
    """Use a combined report PDF plus separately titled research attachments.

    BOK folders often contain the complete book and separate PDF exports of
    its chapters. When a combined book exists, those chapter exports are
    covered by it and need not be parsed a second time.
    """
    primary = []
    board_token = compact_name(board)
    for path in paths:
        stem = compact_name(path.stem)
        if "indigobook" in stem or (board_token in stem and any(ch.isdigit() for ch in stem) and
                                     compact_name(report_name.split(" ", 1)[-1]) in stem):
            primary.append(path)
    if not primary:
        return paths, [], None
    # If several candidate book files exist, prefer the largest complete PDF.
    primary.sort(key=lambda path: (-path.stat().st_size, path.name.casefold()))
    chosen = [primary[0]]
    covered = [path.name for path in paths if path != primary[0]]
    for path in paths:
        if path == primary[0]:
            continue
        name = path.stem.casefold()
        if re.search(r"(?:참고\s*[1-9]|현안\s*[1-9]|\bbox\b|보충설명|executive\s*summary)", name, re.I):
            chosen.append(path)
            covered.remove(path.name)
    return sorted(chosen, key=lambda path: path.name.casefold()), covered, primary[0]


def snapshot_web(report_name: str, board: str, pub_date: str, page_url: str, refresh: bool):
    folder = SNAPSHOT_ROOT / report_identity(report_name, pub_date)
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / "manifest.json"
    try:
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        old = {"sources": []}
    old_by_url = {source.get("url"): source for source in old.get("sources", [])}
    legacy_manifest_path = SNAPSHOT_ROOT / "manifest.json"
    try:
        legacy_manifest = json.loads(legacy_manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        legacy_manifest = {"sources": []}
    legacy_by_path = {source.get("path"): source for source in legacy_manifest.get("sources", [])}
    results: dict[str, bytes] = {}
    records: list[dict[str, str]] = []

    def fetch(name: str, url: str) -> bytes | None:
        target = folder / name
        if target.exists() and not refresh:
            content = target.read_bytes()
            previous = old_by_url.get(url, {})
            records.append({"name": name, "url": url, "path": name,
                            "captured_at_utc": previous.get("captured_at_utc", "기존 스냅샷"),
                            "sha256": sha256_bytes(content), "status": previous.get("status", "snapshot")})
            results[name] = content
            return content
        legacy_path = SNAPSHOT_ROOT / name
        if ("2026년 3월" in report_name and not refresh and legacy_path.exists()):
            content = legacy_path.read_bytes()
            previous = legacy_by_path.get(name, {})
            target.write_bytes(content)
            records.append({"name": name, "url": previous.get("url", url), "path": name,
                            "captured_at_utc": previous.get("captured_at_utc", "기존 스냅샷"),
                            "sha256": sha256_bytes(content), "status": "snapshot-migrated"})
            results[name] = content
            return content
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; BOK-report-research/1.0)"})
            with urlopen(request, timeout=35) as response:
                content = response.read()
                status = str(response.status)
            if name == "report.html" and b"<html" not in content[:10000].lower() and b"<!doctype" not in content[:10000].lower():
                raise ValueError("HTML 문서 응답이 아닙니다")
            target.write_bytes(content)
            records.append({"name": name, "url": url, "path": name,
                            "captured_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                            "sha256": sha256_bytes(content), "status": status})
            results[name] = content
            return content
        except Exception as exc:
            if target.exists():
                content = target.read_bytes()
                records.append({"name": name, "url": url, "path": name,
                                "captured_at_utc": old_by_url.get(url, {}).get("captured_at_utc", "기존 스냅샷"),
                                "sha256": sha256_bytes(content), "status": f"snapshot-fallback: {type(exc).__name__}"})
                results[name] = content
                return content
            records.append({"name": name, "url": url, "path": name, "captured_at_utc": UNKNOWN,
                            "sha256": UNKNOWN, "status": f"접근 실패: {type(exc).__name__}: {exc}"})
            return None

    html_bytes = fetch("report.html", page_url) if page_url else None
    if html_bytes:
        text = html_bytes.decode("utf-8", "replace")
        script_urls = []
        for src in re.findall(r"<script\b[^>]*\bsrc\s*=\s*['\"]([^'\"]+)['\"]", text, re.I):
            full_url = urljoin(page_url, html.unescape(src))
            if re.search(r"(?:charts?|data)[^/]*\.js(?:\?|$)", full_url, re.I) and not re.search(r"(?:highcharts|/lib/|/vendor/)",full_url,re.I):
                script_urls.append(full_url)
        if board == "통화신용정책보고서" and "2026년 3월" in report_name:
            script_urls = ["https://static-cdn.bok.or.kr/static/portal/js/mcp/202603/charts.js",
                            "https://static-cdn.bok.or.kr/static/portal/js/mcp/202603/data.js"] + script_urls
        elif board == "통화신용정책보고서" and "2025년 9월" in report_name:
            script_urls += ["https://static-cdn.bok.or.kr/static/portal/js/mcp-report-charts.js",
                            "https://static-cdn.bok.or.kr/static/portal/js/mcp-report-charts-data.js"]
        seen_names = set()
        for url in script_urls:
            basename = Path(url.split("?", 1)[0]).name
            name = "data.js" if "data" in basename.lower() else "charts.js"
            if name in seen_names:
                continue
            seen_names.add(name)
            fetch(name, url)
    manifest_path.write_text(json.dumps({"report": report_name, "report_id": report_identity(report_name, pub_date),
        "sources": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return results, {Path(item["path"]).name: item for item in records}


def extract_pdf_sources(pdf_files: list[Path], report_name: str, pub_date: str, main_pdf: Path | None):
    rows: list[dict[str, str]] = []
    page_reviews: list[dict[str, str]] = []
    source_stats = []
    for pdf_path in pdf_files:
        try:
            parsed, stats = parse_pdf(pdf_path)
        except Exception as exc:
            page_reviews.append({"보고서": report_name, "발간일": pub_date, "파일": pdf_path.name,
                "PDF쪽": UNKNOWN, "텍스트길이": UNKNOWN,
                "검수사유": f"PDF 파싱 실패: {type(exc).__name__}: {exc}"})
            source_stats.append({"file": pdf_path.name, "error": f"{type(exc).__name__}: {exc}",
                "pdf_pages": 0, "pdf_text_chars": 0, "pdf_caption_candidates": 0,
                "pdf_toc_figures": 0, "pdf_toc_tables": 0, "pdf_body_captions": 0})
            continue
        source_page_reviews = stats.pop("page_reviews", [])
        for row in parsed:
            row["근거"] = f"{pdf_path.name}; {row['근거']}"
            row["_source_file"] = pdf_path.name
            row["_scope"] = "main" if main_pdf and pdf_path == main_pdf else "attachment:" + compact_name(pdf_path.stem)
            row["결과물ID"] = item_id(row["구분"], row["번호"], row["제목"], row["_scope"])
            rows.append(row)
        for item in source_page_reviews:
            page_reviews.append({"보고서": report_name, "발간일": pub_date, "파일": pdf_path.name,
                "PDF쪽": item["page"], "텍스트길이": item["text_length"], "검수사유": item["reason"]})
        for row in parsed:
            if row["구분"] == "표" and "PDF p." in row["근거"]:
                match = re.search(r"PDF p\.(\d+)", row["근거"])
                page_reviews.append({"보고서": report_name, "발간일": pub_date, "파일": pdf_path.name,
                    "PDF쪽": match.group(1) if match else UNKNOWN, "텍스트길이": UNKNOWN,
                    "검수사유": "PDF 표 캡션 감지: 표의 행·열·수치 구조는 원본 페이지와 대조 필요"})
        source_stats.append({"file": pdf_path.name, **stats})
    return rows, page_reviews, source_stats


def merge_archive_records(groups: list[list[dict[str, str]]], chart_js: bytes | None) -> list[dict[str, str]]:
    merged: dict[tuple[str, str], dict[str, str]] = {}
    for group in groups:
        for incoming in group:
            key = row_key(incoming)
            if key not in merged:
                merged[key] = incoming.copy()
                merged[key]["_sources"] = [incoming.get("_source", UNKNOWN)]
                continue
            current = merged[key]
            for field in COMMON_FIELDS:
                if current.get(field, UNKNOWN) == UNKNOWN and incoming.get(field, UNKNOWN) != UNKNOWN:
                    current[field] = incoming[field]
            current["근거"] = join_evidence(current.get("근거", ""), incoming.get("근거", ""))
            current["_sources"] = sorted(set(current.get("_sources", []) + [incoming.get("_source", UNKNOWN)]))
            files = set(current.get("_source_files", []))
            if incoming.get("_source_file"):
                files.add(incoming["_source_file"])
            current["_source_files"] = sorted(files)
            if current.get("설명", UNKNOWN) == UNKNOWN and incoming.get("설명", UNKNOWN) != UNKNOWN:
                current["설명"] = incoming["설명"]
            if current.get("_series", UNKNOWN) == UNKNOWN:
                current["_series"] = incoming.get("_series", UNKNOWN)
    js_map = parse_chart_types(chart_js.decode("utf-8", "replace")) if chart_js else {}
    for record in merged.values():
        record.setdefault("_sources", [record.get("_source", UNKNOWN)])
        record.setdefault("_source_files", [record.get("_source_file", "")])
        if record["구분"] == "그림" and record["종류"] == UNKNOWN:
            chart_id = chart_id_for_number(record["번호"])
            types = js_map.get(chart_id, [])
            if types:
                record["종류"] = "+".join(types)
                record["근거"] = join_evidence(record["근거"], f"charts.js #{chart_id} type")
            elif "HTML" in record["_sources"] and "img" in record.get("근거", "").lower():
                record["종류"] = "이미지/사진"
            else:
                record["근거"] = join_evidence(record["근거"], "차트 종류 선언 확인 불가")
        series = record.get("_series", UNKNOWN)
        combined = " ".join((record.get("제목", ""), series, record.get("설명", "")))
        record["분석 목적"] = purpose(record["구분"], record["제목"], series)
        record["통계기법·지수"] = methods_tags(combined)
        record["결과물ID"] = item_id(record["구분"], record["번호"], record["제목"], record.get("_scope", "main"))
        for field in COMMON_FIELDS:
            if not record.get(field):
                record[field] = UNKNOWN
    return sorted(merged.values(), key=lambda r: (r["구분"] != "그림", number_sort_key(r["번호"]), r["제목"].casefold()))


def write_archive_master(rows: list[dict[str, str]]):
    path = OUT_DIR / "그림표_마스터.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=MASTER_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) or UNKNOWN for field in MASTER_FIELDS})
    return path


def review_evidence_type(field: str, row: dict[str, str]) -> str:
    if row.get(field, UNKNOWN) == UNKNOWN:
        return "불명"
    if field in {"분석 목적", "통계기법·지수"}:
        return "추론"
    if field == "설명":
        return "직접인용"
    if field == "종류" and row.get("구분") == "표":
        return "구조 파싱 또는 PDF 추출"
    return "직접확인 또는 원자료 계산"


def write_archive_review(rows: list[dict[str, str]]):
    path = OUT_DIR / "검수대장.csv"
    existing = {}
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for old in csv.DictReader(stream):
                existing[(old.get("결과물ID"), old.get("필드"))] = old
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        for row in rows:
            for field in COMMON_FIELDS:
                old = existing.get((row["결과물ID"], field), {})
                writer.writerow({"결과물ID": row["결과물ID"], "필드": field,
                    "자동추출값": row.get(field, UNKNOWN), "판단근거유형": review_evidence_type(field, row),
                    "검수상태": old.get("검수상태") or "미검수", "확정값": old.get("확정값", ""),
                    "수정이유": old.get("수정이유", "")})
    return path


def write_page_review(rows: list[dict[str, str]]):
    path = OUT_DIR / "PDF_페이지_검수.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=PAGE_REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_report_markdown(report_name: str, report_dir: Path, rows: list[dict[str, str]], metrics: dict, hashes: dict[str, str], sources: dict):
    board_dir = OUT_DIR / report_dir.parent.name
    board_dir.mkdir(parents=True, exist_ok=True)
    filename = re.sub(r"[\\/:*?\"<>|]", "_", report_name) + ".md"
    path = board_dir / filename
    figures = [row for row in rows if row["구분"] == "그림"]
    tables = [row for row in rows if row["구분"] == "표"]
    unknown_counts = {field: sum(row[field] == UNKNOWN for row in rows) for field in COMMON_FIELDS}
    lines = [f"# {report_name}", "", f"- 발간일: {metrics['pub_date']}",
        f"- 결과물: 그림 {len(figures)}건, 표 {len(tables)}건, 합계 {len(rows)}건",
        f"- 발견된 출처 목록 합집합 {metrics['union_count']}건 중 {len(rows)}건 출력 ({metrics['coverage']}). PDF 전 페이지 시각 검수율을 뜻하지 않습니다.",
        f"- 원본 자료: XLSX {metrics['xlsx_files']}개, PDF {metrics['pdf_files']}개, 웹 HTML {metrics['web_html']}개; 본편 PDF로 대체한 분권 PDF {len(metrics.get('pdf_files_covered_by_combined_book', []))}개; 제외된 동일 해시 파일 {metrics['duplicate_files']}개",
        f"- PDF 캡션 후보 {metrics['pdf_caption_candidates']}건 (차례 {metrics['pdf_toc_captions']}건, 본문 {metrics['pdf_body_captions']}건); 저텍스트·이미지 의심 페이지 {metrics['pdf_review_pages']}개",
        "- 주요 미확인 필드: " + ", ".join(f"{field} {count}건" for field, count in unknown_counts.items() if count) + ".",
        "", "## 그림", ""]
    for row in figures:
        lines += [f"### {row['번호']} · {row['제목']}", "", f"- 결과물ID: `{row['결과물ID']}`"]
        for field in COMMON_FIELDS:
            lines.append(f"- **{field}:** {row.get(field, UNKNOWN)}")
        lines += [f"- **데이터 요약:** {row.get('_series', UNKNOWN)}; {row.get('데이터 형태', UNKNOWN)}", ""]
    lines += ["## 표", ""]
    for row in tables:
        lines += [f"### {row['번호']} · {row['제목']}", "", f"- 결과물ID: `{row['결과물ID']}`"]
        for field in COMMON_FIELDS:
            lines.append(f"- **{field}:** {row.get(field, UNKNOWN)}")
        lines += [f"- **데이터 요약:** {row.get('_series', UNKNOWN)}; {row.get('데이터 형태', UNKNOWN)}", ""]
    lines += ["## 입력 파일 해시", ""]
    lines += [f"- `{name}`: {digest}" for name, digest in sorted(hashes.items())]
    lines += ["", "## 웹 스냅샷", ""]
    if sources:
        lines += [f"- `{name}`: {item['status']}; SHA-256 `{item['sha256']}`; {item['url']}" for name, item in sorted(sources.items())]
    else:
        lines.append("- 확인된 웹보고서 또는 스냅샷이 없습니다.")
    lines += ["", "## 추출 한계", "", "- PDF 표 구조·수치 추출은 저신뢰일 수 있으며 원본 페이지 대조가 필요합니다.",
        "- 자동 목록은 XLSX·웹·PDF에서 발견한 캡션 기준입니다. 이미지에만 포함되어 텍스트로 검출되지 않은 결과물은 PDF 페이지 검수대장에 표시합니다.",
        "- 검수대장 상태는 별도 수동 확인 전까지 `미검수`입니다."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def process_report(report_dir: Path, manifest: dict[str, list[dict[str, str]]], args):
    global REPORT_NAME, PUB_DATE, REPORT_URL
    board, report_name, pub_date = report_metadata(report_dir)
    REPORT_NAME, PUB_DATE = report_name, pub_date
    rel_key = f"{report_dir.parent.name}/{report_dir.name}"
    manifest_files = manifest.get(rel_key, [])
    post_url = next((row.get("게시물URL", "") for row in manifest_files if row.get("게시물URL")), "")
    REPORT_URL = post_url
    all_files = [path for path in report_dir.iterdir() if path.is_file()]
    pdf_candidates = [path for path in all_files if path.suffix.lower() == ".pdf"]
    xlsx_candidates = [path for path in all_files if path.suffix.lower() == ".xlsx"]
    valid_pdfs = [path for path in pdf_candidates if valid_input(path, "pdf")]
    unique_pdfs, pdf_hashes = hash_unique_files(valid_pdfs)
    pdfs, covered_pdf_files, main_pdf = choose_pdf_sources(unique_pdfs, board, report_name)
    xlsx_files, xlsx_hashes = hash_unique_files([path for path in xlsx_candidates if valid_input(path, "xlsx")])
    invalid = [path.name for path in [*pdf_candidates, *xlsx_candidates] if not valid_input(path, path.suffix.lower().lstrip("."))]
    input_hashes = {**pdf_hashes, **xlsx_hashes}
    excluded_names = {name for name, digest in input_hashes.items() if digest.startswith("중복 제외")}
    workbook_rows: list[dict[str, str]] = []
    xlsx_stats = {"workbook_sheets": 0, "toc_figures": 0, "overview_sheets": 0, "appendix_sheets": 0}
    sheet_diagnostics = []
    for xlsx in xlsx_files:
        rows, sheet_data, stats = parse_workbook(xlsx)
        ensure_numbered_workbook_sheets(rows, sheet_data, report_identity(report_name, pub_date))
        for row in rows:
            row["근거"] = f"{xlsx.name}; {row['근거']}"
            row.setdefault("_scope", "main")
            row["결과물ID"] = item_id(row["구분"], row["번호"], row["제목"], row["_scope"])
        workbook_rows.extend(rows)
        for key in xlsx_stats:
            xlsx_stats[key] += stats.get(key, 0)
        sheet_diagnostics.append({"file": xlsx.name, **stats, "sheet_names": list(sheet_data)})
    pdf_rows, page_reviews, pdf_stats = extract_pdf_sources(pdfs, report_name, pub_date, main_pdf)
    web_payloads: dict[str, bytes] = {}
    web_sources: dict[str, dict[str, str]] = {}
    if known_web_report(board, report_name):
        web_payloads, web_sources = snapshot_web(report_name, board, pub_date, post_url, args.refresh_web)
    html_rows, html_stats = parse_html_sources(web_payloads.get("report.html", b""),
        web_payloads.get("charts.js"), web_sources) if web_payloads.get("report.html") else ([], {"figures": 0, "tables": 0, "report_wrap": False})
    for row in html_rows:
        row["_scope"] = "main"
        row["결과물ID"] = item_id(row["구분"], row["번호"], row["제목"], row["_scope"])
    local_sheet_matches = reconcile_local_workbook_rows(workbook_rows, html_rows + pdf_rows)
    groups = [workbook_rows, html_rows, pdf_rows]
    rows = merge_archive_records(groups, web_payloads.get("charts.js"))
    union = union_count(groups)
    metrics = {
        "pub_date": pub_date, "report_id": report_identity(report_name, pub_date),
        "xlsx_files": len(xlsx_files), "pdf_files_available": len(unique_pdfs), "pdf_files": len(pdfs),
        "pdf_files_covered_by_combined_book": covered_pdf_files,
        "web_html": int("report.html" in web_payloads),
        "duplicate_files": len(excluded_names), "invalid_files": invalid,
        **xlsx_stats,
        **local_sheet_matches,
        "html_figures": html_stats.get("figures", 0), "html_tables": html_stats.get("tables", 0),
        "report_wrap": html_stats.get("report_wrap", False),
        "pdf_pages": sum(item["pdf_pages"] for item in pdf_stats),
        "pdf_text_chars": sum(item["pdf_text_chars"] for item in pdf_stats),
        "pdf_caption_candidates": sum(item["pdf_caption_candidates"] for item in pdf_stats),
        "pdf_toc_captions": sum(item["pdf_toc_figures"] + item["pdf_toc_tables"] for item in pdf_stats),
        "pdf_body_captions": sum(item["pdf_body_captions"] for item in pdf_stats),
        "pdf_review_pages": len({(item["파일"], item["PDF쪽"]) for item in page_reviews}), "source_lists_union": union,
        "union_count": union,
        "coverage": f"{len(rows) / union * 100:.1f}%" if union else "0.0%",
        "output_rows": len(rows), "figures": sum(row["구분"] == "그림" for row in rows),
        "tables": sum(row["구분"] == "표" for row in rows),
    }
    md_path = write_report_markdown(report_name, report_dir, rows, metrics, input_hashes, web_sources)
    detail = {"report": report_name, "board": board, "folder": rel_key, "metrics": metrics,
        "input_hashes": input_hashes, "excluded_duplicate_files": sorted(excluded_names),
        "workbooks": sheet_diagnostics, "pdf_sources": pdf_stats, "web_sources": list(web_sources.values()),
        "markdown": str(md_path.relative_to(OUT_DIR)).replace("\\", "/")}
    return rows, page_reviews, detail


def build_all(args):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report_dirs = sorted((path for board in ARCHIVE_DIR.iterdir() if board.is_dir() and board.name[:2].isdigit()
        for path in board.iterdir() if path.is_dir()), key=lambda path: (path.parent.name, path.name))
    if args.report:
        report_dirs = [path for path in report_dirs if args.report in {path.name, f"{path.parent.name}/{path.name}", report_metadata(path)[1]}]
        if not report_dirs:
            raise SystemExit(f"보고서를 찾을 수 없습니다: {args.report}")
    manifest = manifest_rows()
    all_rows: list[dict[str, str]] = []
    page_reviews: list[dict[str, str]] = []
    report_details = []
    for index, report_dir in enumerate(report_dirs, 1):
        board, report_name, pub_date = report_metadata(report_dir)
        print(f"[{index}/{len(report_dirs)}] {report_name}", flush=True)
        try:
            rows, reviews, detail = process_report(report_dir, manifest, args)
            all_rows.extend(rows)
            page_reviews.extend(reviews)
            report_details.append(detail)
        except Exception as exc:
            report_details.append({"report": report_name, "board": board,
                "folder": f"{report_dir.parent.name}/{report_dir.name}", "error": f"{type(exc).__name__}: {exc}",
                "metrics": {"output_rows": 0, "figures": 0, "tables": 0}})
            print(f"  실패: {type(exc).__name__}: {exc}", flush=True)
    all_rows.sort(key=lambda row: (row["보고서"].casefold(), row["구분"] != "그림", number_sort_key(row["번호"]), row["제목"].casefold()))
    write_archive_master(all_rows)
    write_archive_review(all_rows)
    write_page_review(page_reviews)
    summary = {"scope": "manifest에 등록된 현재 아카이브 보고서 디렉터리",
        "report_count": len(report_dirs), "processed_reports": sum("error" not in detail for detail in report_details),
        "failed_reports": [detail for detail in report_details if "error" in detail],
        "output": {"rows": len(all_rows), "figures": sum(row["구분"] == "그림" for row in all_rows),
                   "tables": sum(row["구분"] == "표" for row in all_rows), "blank_common_fields": sum(
                       1 for row in all_rows for field in COMMON_FIELDS if not row.get(field)),
                   "unique_ids": len({row["결과물ID"] for row in all_rows})},
        "reports": report_details,
        "limitations": ["커버리지는 XLSX·HTML·PDF에서 발견된 목록의 합집합 기준이며 전 페이지 시각 검수율이 아님",
                        "PDF 표 구조와 이미지 안의 텍스트는 원본 페이지 검수가 필요할 수 있음",
                        "검수대장 초기 상태는 미검수"]}
    (OUT_DIR / "추출_요약.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary["output"] | {"reports": len(report_dirs), "failed_reports": len(summary["failed_reports"]),
        "pdf_review_pages": len(page_reviews), "master": str(OUT_DIR / "그림표_마스터.csv")}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Extract figure and table catalogs from the BOK report archive.")
    parser.add_argument("--refresh-web", action="store_true", help="알려진 웹보고서 HTML·차트 스크립트 스냅샷을 갱신합니다.")
    parser.add_argument("--report", help="폴더명, 게시판/폴더명 또는 보고서 표기로 단일 판본만 처리합니다.")
    args = parser.parse_args()
    if (OUT_DIR / "보완캐시" / "state.json").exists():
        if args.refresh_web:
            parser.error("보완 결과 보호를 위해 웹 갱신은 별도 스냅샷 검토 후 수행하세요.")
        from enrichment.pipeline import run
        run(report=args.report)
        return
    build_all(args)


if __name__ == "__main__":
    main()
