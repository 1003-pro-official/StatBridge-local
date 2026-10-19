"""Unverified publication candidates are search hints, never executable recipes."""
import csv,re
from functools import lru_cache
from pathlib import Path

PATH=Path(__file__).resolve().parents[2]/'data/processed/derived_publication_candidates_20261019.csv'

@lru_cache(maxsize=1)
def candidates():
    if not PATH.exists():return ()
    with PATH.open(encoding='utf-8-sig',newline='') as f:
        return tuple({'id':r['ID'],'name':r['파생지표_그래프표'],
            'table_ids':tuple(dict.fromkeys(re.findall(r'DT_[A-Za-z0-9]+',r['원자료표코드'])))} for r in csv.DictReader(f))


def search_hints(query, approved, limit=3):
    normalized=re.sub(r'\s+','',query)
    tokens=set(re.findall(r'[가-힣A-Za-z]{2,}',query))
    ranked=[]
    for row in candidates():
        name=re.sub(r'\s+','',row['name'])
        score=(100 if name in normalized else 0)+sum(len(t) for t in tokens if t in name)
        if score<6:continue
        ids=[t for t in row['table_ids'] if t in approved]
        ranked.append((score,row['id'],{'candidate_id':row['id'],'name':row['name'],'table_ids':ids,
            'verification':'분석 후보이며 보고서 개별 도표 및 실제 항목·주기·기간·수식 미검증. 검색 힌트만 사용.'}))
    ranked.sort(key=lambda r:(-r[0],r[1]))
    return [r[2] for r in ranked[:limit]]
