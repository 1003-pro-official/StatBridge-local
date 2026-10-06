"""Fail-closed request/catalog matching. Retrieval scores are not authorization."""
from __future__ import annotations

import re
import unicodedata


def compact(value):
    return re.sub(r"[^0-9a-z가-힣]", "", unicodedata.normalize("NFKC", str(value or "")).lower())


def catalog_mentions(query, tables):
    """Longest canonical-name spans. A suffix-free name retains ALL basis variants."""
    q = compact(query)
    spans = {}
    for table in tables:
        title = str(table.get("table_name") or "")
        names = {compact(title)}
        base = compact(title.split("(", 1)[0])
        if len(base) >= 4:
            names.add(base)
        for name in names:
            if len(name) < 3:
                continue
            start = q.find(name)
            while start >= 0:
                key = (start, start + len(name))
                spans.setdefault(key, set()).add(str(table["table_id"]))
                start = q.find(name, start + 1)
    kept = []
    for (start, end), ids in sorted(spans.items(), key=lambda item: -(item[0][1]-item[0][0])):
        if any(start < m["end"] and end > m["start"] for m in kept):
            continue
        kept.append({"start": start, "end": end, "text": q[start:end], "table_ids": sorted(ids)})
    return sorted(kept, key=lambda m: m["start"])


def scoped_catalog_query(query, table_id, mentions):
    """Other named tables own their embedded qualifiers; do not apply them here."""
    if not mentions:
        return str(query)
    q = compact(query)
    for mention in reversed(mentions):
        if str(table_id) not in mention["table_ids"]:
            q = q[:mention["start"]] + " " + q[mention["end"]:]
    ids=re.findall(r"\bDT_[0-9A-Za-z]+\b",str(query),re.I)
    return q + (' ' + ' '.join(ids) if ids else '')


def residual_catalog_query(query, mentions):
    q = compact(query)
    for mention in reversed(mentions):
        q = q[:mention["start"]] + " " + q[mention["end"]:]
    return q


def scoped_metric_query(query, table, mentions):
    """Split only grounded clauses; protect conjunctions INSIDE catalog titles."""
    if structure_request(query)['explicit_ids']:
        return scoped_catalog_query(query,table['table_id'],mentions)
    masked=compact(query)
    for index in range(len(mentions)-1,-1,-1):
        m=mentions[index]
        masked=masked[:m['start']]+f'@{index}@'+masked[m['end']:]
    parts=re.split(r'그리고|및|와|과',masked)
    restored=[]
    for part in parts:
        for index,m in enumerate(mentions):
            part=part.replace(f'@{index}@',m['text'])
        restored.append(part)
    # Do not discard unknown requested clauses or guess a split inside a noun.
    if len(restored)>1 and all(structure_request(p)['metrics'] or any(m['text'] in p for m in mentions) for p in restored):
        own_names=[m['text'] for m in mentions if str(table['table_id']) in m['table_ids']]
        own=[p for p in restored if any(name in p for name in own_names)] if own_names else [p for p in restored if table_evidence(p,table)[0]]
        if own:
            return ' '.join(own)
    return scoped_catalog_query(query,table['table_id'],mentions)


def unsupported_quantity_terms(query, tables):
    """Unsupported explicitly named quantities must not disappear in a multi-query."""
    catalog=' '.join(compact(value) for t in tables for value in
                     [t.get('table_name',''),*t.get('aliases',[]),*t.get('public_query_terms',[])])
    unknown=[]
    for word in re.findall(r'[가-힣a-zA-Z]+',str(query)):
        term=re.sub(r'(?:으로|까지|부터|에서|을|를|은|는|의|와|과)$','',word)
        if len(term)>=3 and term.endswith(('지수','금리','물가','사용량','발전량','생산량','소비량')) and compact(term) not in catalog:
            unknown.append(term)
    return list(dict.fromkeys(unknown))


# These map measured concepts, not merely related concepts or embedding neighbors.
FAMILIES = [
    ("수출물가", ("수출물가",), ("수출물가",)),
    ("수입물가", ("수입물가",), ("수입물가",)),
    ("수출물량", ("수출물량",), ("수출물량",)),
    ("수입물량", ("수입물량",), ("수입물량",)),
    ("수출금액", ("수출금액",), ("수출금액",)),
    ("수입금액", ("수입금액",), ("수입금액",)),
    ("대출금리", ("대출금리", "대출이자"), ("대출금리",)),
    ("수신금리", ("수신금리", "예금금리", "예금이자"), ("수신금리", "예금금리")),
    ("생산자물가", ("생산자물가",), ("생산자물가",)),
    ("소비자물가", ("소비자물가",), ("소비자물가",)),
    ("경제심리", ("경제심리", "경제분위기", "경기분위기"), ("경제심리",)),
    ("기업경기", ("기업경기", "기업체감", "기업들이", "회사들이"), ("기업경기",)),
    ("소비자심리", ("소비자심리", "소비심리"), ("소비자동향", "소비자심리")),
    ("GDP", ("gdp", "국내총생산", "경제성장", "경제규모"), ("gdp", "국내총생산")),
    ("GNI", ("gni", "국민총소득"), ("gni", "국민총소득")),
    ("국민소득", ("국민소득",), ("국민소득", "gni", "국민총소득")),
    ("수출", ("수출",), ("수출",)),
    ("수입", ("수입",), ("수입",)),
    ("통화", ("통화", "m1", "m2", "시중에돈", "돈이얼마나풀"), ("통화", "m1", "m2")),
    ("대출", ("대출", "주담대", "빌린돈", "빚"), ("대출", "가계신용")),
    ("금리", ("금리", "이자"), ("금리",)),
    ("물가", ("물가", "물건값"), ("물가",)),
    ("채권", ("채권",), ("채권",)),
    ("수신", ("수신", "예금"), ("수신", "예금")),
    ("신용카드", ("신용카드", "카드결제"), ("카드",)),
    ("자금순환", ("자금순환",), ("자금순환", "금융거래", "잔액표", "거래표")),
]
QUALIFIERS = ("지역별", "국가별", "나라별", "산업별", "기관별", "상품별", "용도별", "기업규모별",
              "예금은행", "비은행금융기관", "분기별", "월별", "연간", "자료", "통계", "추이", "그래프")


def structure_request(query):
    q=compact(query)
    # Institution names are qualifiers, not requests for deposit statistics.
    metric_q=q.replace("예금은행", "은행").replace("비은행예금취급기관", "기관")
    matches=[(name,triggers,terms) for name,triggers,terms in FAMILIES if any(compact(t) in metric_q for t in triggers)]
    # Specific quantities win over their broad substring families.
    specific={"수출물가":("수출","물가"),"수입물가":("수입","물가"),"수출물량":("수출",),
        "수입물량":("수입",),"수출금액":("수출",),"수입금액":("수입",),
        "대출금리":("대출","금리"),"수신금리":("수신","금리"),"생산자물가":("물가",),"소비자물가":("물가",)}
    removed={broad for name,_,_ in matches for broad in specific.get(name,())}
    metrics=[name for name,_,_ in matches if name not in removed]
    return {"original_query":query,"metrics":metrics,
            "qualifiers":[term for term in QUALIFIERS if term in q],
            "years":re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)",str(query)),
            "explicit_ids":re.findall(r"\bDT_[0-9A-Za-z]+\b",str(query),re.I),
            "comparison":bool(re.search(r"비교|같이|함께|나란히|그리고|및|와|과|,",str(query)))}


def table_evidence(query, table):
    request=structure_request(query); q=compact(query)
    name=compact(table.get("table_name")); tid=str(table.get("table_id") or "")
    # Only canonical table/item names establish measured-concept evidence.
    measured=" ".join([name,*[compact(x) for x in table.get("item_names",[])]])
    hits=[metric for metric in request["metrics"] if any(compact(term) in measured for n,_,terms in FAMILIES if n==metric for term in terms)]
    exact=bool(request["explicit_ids"] and tid.lower() in {x.lower() for x in request["explicit_ids"]})
    if request["explicit_ids"] and not exact:return False,hits,request
    if request["metrics"]:
        valid=bool(hits) if request["comparison"] else len(hits)==len(request["metrics"])
        if not valid:return False,hits,request
    elif not exact:
        phrases=[table.get("table_name", ""),*table.get("aliases",[]),*table.get("public_query_terms",[])]
        # A region/dimension match cannot stand in for the measured quantity.
        valid=bool(len(name)>=3 and name in q)
        for phrase in phrases:
            core=compact(phrase)
            for term in QUALIFIERS:core=core.replace(compact(term),"")
            core=re.sub(r"(?:평잔|말잔|원계열|계절조정계열|계절조정|지수|통계|표)$","",core)
            if len(core)>=3 and core in q:
                valid=True;break
        if not valid:return False,hits,request
    # Geographic breakdown is a hard table capability, not a soft similarity hint.
    if "지역별" in request["qualifiers"] and "지역" not in name:return False,hits,request
    if any(x in request["qualifiers"] for x in ("국가별","나라별")) and "국가" not in name:return False,hits,request
    return True,hits,request
