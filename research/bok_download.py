#!/usr/bin/env python3
"""한국은행 핵심 법정 보고서 3년치 첨부자료 다운로더.

- 대상: 통화신용정책보고서 / 금융안정보고서 / 경제전망보고서 / 지급결제보고서 / 연차보고서
- 목록: /portal/singl/newsData/listCont.do (depth=200699 간행물, depth2=<게시판 menuNo>)
- 첨부: fileDown.do (다운로드) + /fileSrc/... (인라인 PDF) 모두 수집
- 출력: research/bok-archive/<게시판>/<날짜>_<제목>/<파일> + manifest.csv
"""
import os, re, csv, time, html, hashlib
from urllib.parse import unquote, quote
from datetime import date, timedelta
import requests

BASE = "https://www.bok.or.kr"
LIST = BASE + "/portal/singl/newsData/listCont.do"
PARENT_DEPTH = "200699"  # 뉴스/자료 > 간행물
YEARS = 3
BOARDS = [
    ("01-통화신용정책보고서", "200067"),
    ("02-금융안정보고서", "200068"),
    ("03-경제전망보고서", "200066"),
    ("04-지급결제보고서", "200072"),
    ("05-연차보고서", "200071"),
]
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "bok-archive")
CUT = date.today() - timedelta(days=365 * YEARS)

S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0"})


def clean(s):
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def safe(name, maxlen=80):
    name = re.sub(r'[\\/:*?"<>|\n\r\t]+', "_", name).strip(" ._")
    return name[:maxlen] or "item"


def list_items(menu):
    items, page = [], 1
    while page <= 60:
        r = S.get(LIST, params={
            "pageIndex": page, "targetDepth": "3", "menuNo": menu,
            "depth": PARENT_DEPTH, "depth2": menu, "sort": "1",
            "pageUnit": "100", "searchCnd": "1",
        }, timeout=40)
        blocks = re.split(r'<li class="bbsRowCls">', r.text)[1:]
        if not blocks:
            break
        stop = False
        for b in blocks:
            m = re.search(r'<a href="([^"]+)"[^>]*class="title">(.*?)</a>', b, re.S)
            md = re.search(r'class="date">.*?(\d{4})\.(\d{2})\.(\d{2})', b, re.S)
            if not m or not md:
                continue
            d = date(int(md.group(1)), int(md.group(2)), int(md.group(3)))
            if d < CUT:
                stop = True
                continue
            href = m.group(1)
            dept = re.search(r'class="depart">.*?</span>([^<]*)</span>', b, re.S)
            items.append({
                "title": clean(m.group(2)),
                "date": d.isoformat(),
                "dept": clean(dept.group(1)) if dept else "",
                "url": BASE + href if href.startswith("/") else href,
            })
        if stop:
            break
        page += 1
        time.sleep(0.3)
    return items


def attachments(view_url):
    t = S.get(view_url, timeout=60).text
    files, seen = [], set()

    def add(kind, u):
        if u not in seen:
            seen.add(u); files.append((kind, u))

    for m in re.finditer(r'fileDown\.do\?atchFileId=([0-9a-zA-Z]+)&(?:amp;)?fileSn=(\d+)', t):
        add("down", f"{BASE}/portal/cmmn/file/fileDown.do?atchFileId={m.group(1)}&fileSn={m.group(2)}")
    for m in re.finditer(r'(/fileSrc/[^"&#]+)', t):
        add("src", BASE + quote(unquote(m.group(1)).split("#")[0], safe="/"))
    for m in re.finditer(r'file=([^"&]+)', t):
        p = unquote(m.group(1)).split("#")[0]
        if p.startswith("/fileSrc/"):
            add("src", BASE + quote(p, safe="/"))
    return files


def fix_name(s):
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def filename(resp, u):
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
    if m:
        n = fix_name(os.path.basename(unquote(m.group(1).strip())))
        if "." in n:
            return n
    return fix_name(unquote(os.path.basename(u.split("?")[0]))) or "file.bin"


def download(kind, u, dest_dir, seen_hashes):
    r = S.get(u, timeout=180, stream=True, allow_redirects=True)
    r.raise_for_status()
    name = safe(filename(r, u), 120)
    path = os.path.join(dest_dir, name)
    clen = r.headers.get("Content-Length")
    if os.path.exists(path) and os.path.getsize(path) > 0 and clen == str(os.path.getsize(path)):
        return path, os.path.getsize(path), "skip"
    if os.path.exists(path):
        stem, ext = os.path.splitext(name)
        i = 2
        while os.path.exists(os.path.join(dest_dir, f"{stem}_{i}{ext}")):
            i += 1
        name = f"{stem}_{i}{ext}"
        path = os.path.join(dest_dir, name)
    tmp = path + ".part"
    h = hashlib.sha256(); n = 0
    with open(tmp, "wb") as f:
        for chunk in r.iter_content(65536):
            f.write(chunk); h.update(chunk); n += len(chunk)
    with open(tmp, "rb") as f:
        head = f.read(64)
    if head[:9] == b"<!DOCTYPE" or head[:5] == b"<html":
        os.remove(tmp)
        return path, n, "err"
    if h.hexdigest() in seen_hashes:
        os.remove(tmp)
        return path, n, "dup"
    seen_hashes.add(h.hexdigest())
    os.replace(tmp, path)
    return path, n, "ok"


def main():
    os.makedirs(OUT, exist_ok=True)
    mf = os.path.join(OUT, "manifest.csv")
    new = not os.path.exists(mf)
    f = open(mf, "a", newline="", encoding="utf-8-sig")
    w = csv.writer(f)
    if new:
        w.writerow(["게시판", "제목", "등록일", "담당부서", "파일명", "파일URL", "저장경로", "바이트", "게시물URL"])
    total_files = 0
    for label, menu in BOARDS:
        print(f"\n### {label}")
        items = list_items(menu)
        print(f"  기간 내 게시물 {len(items)}건")
        for it in items:
            dest = os.path.join(OUT, label, f"{it['date']}_{safe(it['title'], 60)}")
            os.makedirs(dest, exist_ok=True)
            try:
                atts = attachments(it["url"])
            except Exception as e:
                print(f"  ! {it['title']}: 목록 오류 {e}")
                continue
            got = 0
            seen_hashes = set()
            for kind, u in atts:
                try:
                    path, size, st = download(kind, u, dest, seen_hashes)
                    if st == "dup":
                        print(f"  [dup] {os.path.basename(path)}")
                        continue
                    if st == "err":
                        print(f"  [err] {os.path.basename(path)} (오류 응답, 제외)")
                        continue
                    got += 1; total_files += 1
                    print(f"  [{st}] {it['date']} {it['title'][:28]} -> {os.path.basename(path)} ({size//1024}KB)")
                    w.writerow([label, it["title"], it["date"], it["dept"],
                                os.path.basename(path), u, os.path.relpath(path, OUT), size, it["url"]])
                    f.flush()
                except Exception as e:
                    print(f"  ! 다운로드 실패 {u}: {e}")
                time.sleep(0.2)
            if got == 0:
                print(f"  - {it['date']} {it['title'][:40]} (첨부 없음)")
    f.close()
    print(f"\n완료: 총 {total_files}개 파일 -> {OUT}")


if __name__ == "__main__":
    main()
