"""Collect official BOK release evidence into an ignored local cache.

No statistical observations or credentials are written to the public catalog.
Run with --fetch explicitly; build.py only reads this cache.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))
from bok_download import clean, filename

CACHE = ROOT / ".venv/cache/kosis-bok-reproduction"
BASE = "https://www.bok.or.kr"
START, END = "2023-10-01", "2026-10-19"
FAMILIES = {
    "통화유동성": r"통화 및 유동성",
    "금리": r"금융기관 가중평균금리",
    "국제수지": r"국제수지.*잠정",
    "자금순환": r"자금순환",
    "기업경기심리": r"기업경기.*(?:조사|실사)",
    "소비자동향": r"소비자동향조사",
    "생산자물가": r"생산자물가지수",
    "수출입물가무역": r"수출입물가지수|무역지수 및 교역조건",
    "기업경영분석": r"기업경영분석",
    "국민소득": r"국민소득|국내총생산",
    "산업별대출": r"산업별\s*대출금",
    "국제투자": r"국제투자대조표",
    "가계신용": r"가계신용",
    "대출행태": r"대출행태서베이",
    "지급결제": r"지급결제동향|지급결제 동향|지급수단.*이용|전자지급서비스.*이용",
}


def parse_listing(text):
    rows = []
    for block in re.split(r'<li class="bbsRowCls">', text)[1:]:
        link = re.search(r'<a href="([^"]+)"[^>]*class="title">(.*?)</a>', block, re.S)
        date = re.search(r'class="date">.*?(\d{4})\.(\d{2})\.(\d{2})', block, re.S)
        if not link or not date:
            continue
        url = urljoin(BASE, html.unescape(link[1]))
        identifier = parse_qs(urlparse(url).query).get("nttId", [None])[0]
        if identifier:
            menu = parse_qs(urlparse(url).query).get("menuNo", ["201264"])[0]
            rows.append({"id": identifier, "date": "-".join(date.groups()),
                         "title": clean(link[2]),
                         "url": f"{BASE}{urlparse(url).path}?nttId={identifier}&menuNo={menu}"})
    return rows


def fetch(url, path):
    if path.exists():
        return path.read_bytes()
    response = requests.get(url, timeout=60, headers={"User-Agent": "StatBridge-public-research/1.0"})
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return response.content


def attachment_links(text):
    links = {}
    for href, title in re.findall(r'<a[^>]+href="([^"]+)"[^>]*title="([^"]+)"', text):
        if href.startswith('/fileSrc/') and href.lower().endswith(('.pdf', '.xlsx')):
            links[urljoin(BASE, html.unescape(href))] = html.unescape(title)
    for atch, serial in re.findall(r'fileDown\.do\?atchFileId=([\w]+)&(?:amp;)?fileSn=(\d+)', text):
        links.setdefault(f"{BASE}/portal/cmmn/file/fileDown.do?atchFileId={atch}&fileSn={serial}", '')
    return links


def collect_release(row):
    row = dict(row)
    try:
        folder = CACHE / "releases" / row["id"]
        text = fetch(row["url"], folder / "page.html").decode("utf-8")
        links = attachment_links(text)
        files = []
        for url, title in links.items():
            # Fetch each attachment once, retaining only PDF/XLSX evidence.
            metadata = folder / f"attachment-{hashlib.sha256(url.encode()).hexdigest()[:12]}.json"
            if metadata.exists():
                files.append(json.loads(metadata.read_text()))
                continue
            response = requests.get(url, timeout=90)
            response.raise_for_status()
            name = title or filename(response, url)
            if not name.lower().endswith((".pdf", ".xlsx")):
                continue
            if name.lower().endswith(".pdf") and not response.content.startswith(b"%PDF"):
                raise ValueError("attachment is not a PDF")
            path = folder / Path(name).name
            path.write_bytes(response.content)
            info = {"name": path.name, "url": url, "path": str(path.relative_to(ROOT)),
                    "sha256": hashlib.sha256(response.content).hexdigest()}
            metadata.write_text(json.dumps(info, ensure_ascii=False, indent=2))
            files.append(info)
        row.update(files=files, status="collected" if files else "no_pdf_xlsx")
    except (requests.RequestException, ValueError, OSError) as exc:
        row.update(status="failed", error=type(exc).__name__)
    print(row["id"], row["title"], row["status"], flush=True)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", required=True)
    args = parser.parse_args()
    rows = {}
    pages = []
    for menu, depth in [('201264', '201264'), ('201265', '201265'), ('200455', '200699')]:
        for page in range(1, 31):
            url = (f"{BASE}/portal/singl/newsData/listCont.do?menuNo={menu}"
                   f"&depth={depth}&depth2={menu}&pageUnit=100&pageIndex={page}&sort=1")
            content = fetch(url, CACHE / f"listing-{menu}-{page}.html")
            found = parse_listing(content.decode("utf-8"))
            if not found:
                raise RuntimeError(f"empty/unparseable listing {menu} page {page}")
            pages.append({"menu": menu, "page": page, "url": url, "rows": len(found),
                          "sha256": hashlib.sha256(content).hexdigest()})
            rows.update({r["id"]: r for r in found if START <= r["date"] <= END})
            if min(r["date"] for r in found) < START:
                break
        else:
            raise RuntimeError("listing limit reached before start date")
    rows = sorted(rows.values(), key=lambda r: (r["date"], r["id"]), reverse=True)
    selected = {}
    seen = set()
    for row in rows:
        family = next((f for f, pattern in FAMILIES.items() if re.search(pattern, row["title"])), None)
        row["family"] = family or "범위외"
        # Annual enterprise books and quarterly sample releases are different populations.
        edition = 'book' if 'P0000599' in row['url'] else 'release'
        if '전자지급' in row['title']:
            edition = 'electronic'
        key = (family, edition, row["date"][:4])
        if family and key not in seen:
            selected[row["id"]] = row | {"selection": "자료군별 연도 내 최신판"}
            seen.add(key)
    # Definition changes are inspected even if not the year's last release.
    for row in rows:
        if re.search(r"기준년.*개편|통계.*개편|분류.*개편", row["title"]):
            selected.setdefault(row["id"], row | {"selection": "통계 정의 변경 후보"})
    with ThreadPoolExecutor(max_workers=5) as pool:
        releases = list(pool.map(collect_release, selected.values()))
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "collection.json").write_text(json.dumps(
        {"period": [START, END], "pages": pages, "listings": rows, "releases": releases},
        ensure_ascii=False, indent=2) + "\n")
    print("listings", len(rows), "releases", len(releases))


if __name__ == "__main__":
    main()
