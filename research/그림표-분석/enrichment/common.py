from __future__ import annotations
import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parents[1]
ARCHIVE = ROOT / 'research' / 'bok-archive'
CACHE = OUT / '보완캐시'
BACKUP = OUT / '백업' / '보완전_20261002'
UNKNOWN = '불명'
FIELDS = ['보고서','발간일','구분','번호','제목','사용 데이터·출처','단위','데이터 형태','종류','분석 목적','통계기법·지수','설명','근거']
MASTER_FIELDS = ['결과물ID', *FIELDS, '필드별신뢰도']
KINDS = ['선그래프','막대','산점도','영역','pie','혼합','사진·이미지','불명']
BLACKLIST = re.compile(r'이\s*문서는|한국은행의\s*자산|저작권|무단\s*(?:전재|복제)|copyright|all\s+rights\s+reserved|면책|참고문헌|참고\s*문헌|그림\s*차례|통계표\s*차례|목\s*차', re.I)

def normalize(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', str(text))).strip()

def compact(text):
    return re.sub(r'[^0-9a-z가-힣]', '', normalize(text).lower())

def number(text):
    return re.sub(r'\s*[-‐‑‒–—.]\s*', '-', normalize(text).upper())

def digest(value):
    data = value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False,sort_keys=True).encode('utf-8')
    return hashlib.sha256(data).hexdigest()

def load_json(path, default=None):
    if not path.exists(): return default
    return json.loads(path.read_text(encoding='utf-8'))

def save_json(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))

def write_csv(path, rows, fields):
    temp = path.with_suffix(path.suffix+'.tmp')
    with temp.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    temp.replace(path)

def append_evidence(row, text):
    if text and text not in row['근거']:
        row['근거'] += '; ' + text

def ref_pattern(kind, num):
    if num == UNKNOWN: return None
    normalized = number(num)
    # Printed reference numbering must match in full, never I-1 inside I-1-12.
    parts = re.split(r'([- ])',normalized)
    body=''.join(r'\s*[-.‐‑‒–—]\s*' if p=='-' else r'\s*' if p==' ' else re.escape(p) for p in parts)
    return re.compile(re.escape(kind)+r'\s*[\[<(]?\s*'+body+r'(?!\s*[-.‐‑‒–—]\s*\d)(?!\d)',re.I)

def sentence_key(text):
    return re.sub(r'\s+','', normalize(text))

def bad_sentence(text):
    # A block can start halfway through a word at a PDF column/page boundary.
    # Retain complete quotations; do not promote these fragments to sentences.
    start=re.sub(r'^[\s•·\-]+','',text)
    fragment=re.match(r'^(?:며,|어서야|률과|준을|히\s|신\d+\)|회하는|로\s다시|소\s완화|름을|서\s안정|심으로|폭의|서\d+\s|둔화\d|어\s다시|질\s것으로|로\s예상|크가|등에\s영향|게\s개선|로\s전망|원을\s넘어|률이|향받을|될\s가능성|으로\s(?:상승|하락|양호)|다\(그림|등으로\s)',start)
    return bool(BLACKLIST.search(text) or fragment) or len(text)<18 or len(text)>1600
