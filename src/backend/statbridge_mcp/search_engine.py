from __future__ import annotations

import re
from typing import Any

from .config import settings
from .metadata_store import MetadataStore, TableMetadata
from .utils import normalize_text


# Colloquial phrases point to official catalog concepts, never to fabricated IDs.
ALIASES = {
    "경제분위기": "경제심리지수",
    "경제심리": "경제심리지수",
    "체감상어떤지경제심리": "경제심리지수",
    "기업체감경기": "기업경기조사",
    "bsi": "기업경기조사",
    "가계빚": "가계신용",
    "시중에풀린돈": "m2",
    "수출물건양": "수출물량지수",
    "수입물가": "수입물가지수",
    "생산자물가": "생산자물가지수",
    "대출이자": "대출금리",
    "달러가격": "환율",
    "집값": "주택가격",
    "은행에서빌린돈총액": "예금은행대출금",
    "지역별은행대출잔액": "지역별대출금",
    "앞으로물가가얼마나오를": "기대인플레이션율",
    "가계빚을어느금융권": "가계대출업권별",
    "집살때빌린가계빚": "가계대출용도별",
    "은행이돈빌려주기에얼마나적극": "대출태도",
    "은행이보는대출자의위험": "신용위험",
    "사람들이대출을얼마나원": "대출수요",
    "나라전체저축과투자": "총저축과총투자",
    "수출로받은돈을지수": "수출금액지수",
    "국내에공급되는물건의가격": "국내공급물가지수",
    "기업몸집이얼마나커": "성장성지표",
    "기업이장사해서남긴이익": "손익지표",
    "기업재무건전성": "자산자본지표",
    "기업현금유입과유출": "현금흐름표",
    "카드로결제한규모": "신용카드",
    "국내총생산지출": "국내총생산에대한지출",
    "가계목적별소비지출": "가계의목적별최종소비지출",
}

CONTRASTS = (
    ("대출금리", "수신금리"),
    ("수입", "수출"),
    ("신규취급액", "잔액"),
    ("실적", "전망"),
    ("실질", "명목"),
)
COMMON_MODIFIERS = ("예금은행", "원화기준", "차주당가계대출", "차주당주택담보대출", "지역별기업경기", "지역별")


def compact(value: str) -> str:
    return normalize_text(value).replace(" ", "")


class SearchEngine:
    def __init__(self, store: MetadataStore) -> None:
        self.docs = store.all()
        self.fields = {
            meta.table_id: (
                compact(meta.table_name),
                [compact(item["item_name"]) for item in meta.items],
                [compact(value["class_name"]) for value in meta.classifications],
            )
            for meta in self.docs
        }

    def _score(self, query: str, meta: TableMetadata) -> float:
        name, items, classes = self.fields[meta.table_id]
        q = compact(query)
        q = q.replace("명목이아닌실질", "실질").replace("실질이아닌명목", "명목")
        if not q:
            return 0.0
        score = 0.0
        if meta.table_id.lower() in query.lower():
            score += 12
        if name and name in q:
            score += 7
        for token in re.findall(r"[가-힣A-Za-z0-9]+", normalize_text(meta.table_name)):
            term = compact(token)
            if len(term) >= 2 and term in q:
                score += max(3, min(len(term), 8) / 2)
        for item in set(items):
            if len(item) >= 4 and item in q:
                score += 2
        class_hits = sum(len(value) >= 3 and value in q for value in set(classes))
        score += min(class_hits, 4) * 1.5
        for phrase, official in ALIASES.items():
            if phrase in q and compact(official) in name:
                score += 5
        if "m2" in q and "잔액" in q and "말잔" in name:
            score += 4
        for positive, negative in CONTRASTS:
            if "전망이아니라실적" in q and {positive, negative} == {"실적", "전망"}:
                continue
            if positive in q and negative in name and positive not in name:
                score -= 4
            if negative in q and positive in name and negative not in name:
                score -= 4
        if "전망이아니라실적" in q and "전망" in name:
            score -= 8
        from_year = re.search(r"(\d{4})년이후", q)
        if from_year and meta.end_period and meta.end_period[:4] < from_year.group(1):
            score -= 8
        return score

    def _search_one(self, query: str, top_k: int) -> list[dict[str, Any]]:
        scored = [(self._score(query, meta), meta) for meta in self.docs]
        scored = [(score, meta) for score, meta in scored if score >= 2.5]
        scored.sort(key=lambda pair: (-pair[0], pair[1].table_id))
        out = []
        for score, meta in scored[:top_k]:
            out.append({
                "table_id": meta.table_id,
                "table_name": meta.table_name,
                "score": round(score, 4),
                "path": meta.path_text,
                "frequencies": meta.frequencies,
                "start_period": meta.start_period,
                "end_period": meta.end_period,
                "local_csv_available": (
                    (settings.tables_dir / f"{meta.table_id}.csv").is_file()
                    or any(settings.tables_dir.glob(f"{meta.table_id}__*.csv"))
                ),
            })
        return out

    def search_groups(self, query: str, top_k: int = 5) -> list[list[dict[str, Any]]]:
        if not 1 <= top_k <= 20:
            raise ValueError("top_k must be between 1 and 20")
        if any(term in compact(query) for term in ("예측해", "예측치", "전망치를실제", "전망치를실측", "종목을추천", "재무상담")):
            return [[]]
        segments = [part.strip() for part in re.split(r"(?:와|과|및)\s+", query) if part.strip()]
        if len(segments) < 2:
            return [self._search_one(query, top_k)]
        modifiers = [value for value in COMMON_MODIFIERS if value in compact(segments[0])]
        groups = [self._search_one(segment + " " + " ".join(modifiers), top_k) for segment in segments]
        return groups if all(groups) else [self._search_one(query, top_k)]

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        lists = self.search_groups(query, top_k)
        if len(lists) == 1:
            return lists[0]
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index in range(top_k):
            for candidates in lists:
                if index < len(candidates) and candidates[index]["table_id"] not in seen:
                    candidate = candidates[index]
                    seen.add(candidate["table_id"])
                    merged.append(candidate)
                    if len(merged) == top_k:
                        return merged
        return merged
