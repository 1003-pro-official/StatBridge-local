from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .config import settings
from .utils import unique_join

FREQ_MAP = {
    "일": "D",
    "월": "M",
    "분기": "Q",
    "반기": "S",
    "년": "Y",
    "연": "Y",
    "연간": "Y",
    "부정기": "IR",
    "A": "Y",
    "D": "D",
    "M": "M",
    "Q": "Q",
    "S": "S",
    "Y": "Y",
    "IR": "IR",
}


def normalize_frequency(value: str) -> str:
    value = str(value or "").strip()
    return FREQ_MAP.get(value, value)


def normalize_period(freq: str, value: str) -> str:
    s = str(value or "").strip()
    if not s:
        return ""

    freq = normalize_frequency(freq)

    if freq == "Y":
        m = re.search(r"(\d{4})", s)
        return m.group(1) if m else s

    if freq == "M":
        m = re.search(r"(\d{4})\D*([01]?\d)", s)
        if m:
            return f"{m.group(1)}{int(m.group(2)):02d}"

    if freq == "Q":
        m = re.search(r"(\d{4}).*?([1-4])(?:/4|분기|Q)?", s, re.IGNORECASE)
        if m:
            return f"{m.group(1)}{int(m.group(2)):02d}"

    if freq == "S":
        m = re.search(r"(\d{4}).*?([1-2])(?:/2|반기)?", s)
        if m:
            return f"{m.group(1)}{int(m.group(2)):02d}"

    if freq == "D":
        digits = re.sub(r"\D", "", s)
        return digits if len(digits) == 8 else s

    return s


@dataclass(slots=True)
class TableMetadata:
    table_id: str
    org_id: str
    table_name: str
    path_text: str
    frequencies: list[str]
    start_period: str | None
    end_period: str | None
    items: list[dict[str, Any]]
    classifications: list[dict[str, Any]]
    comments: list[str]
    sources: list[str]
    search_text: str


class MetadataStore:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = (data_dir or settings.data_dir).resolve()
        self.table_master = self._read_csv("bok_table_master.csv")
        self.items = self._read_csv("bok_items.csv")
        self.classifications = self._read_csv("bok_classifications.csv")
        self.periods = self._read_csv("bok_periods.csv", required=False)
        self.comments = self._read_csv("bok_comments.csv", required=False)
        self.sources = self._read_csv("bok_sources.csv", required=False)

        self._index = self._build_index()

    def _read_csv(self, name: str, required: bool = True) -> pd.DataFrame:
        path = self.data_dir / name
        if not path.exists():
            if required:
                raise FileNotFoundError(f"필수 파일이 없습니다: {path}")
            return pd.DataFrame()
        return pd.read_csv(path, dtype=str).fillna("")

    def _col(self, df: pd.DataFrame, *names: str) -> str | None:
        if df.empty:
            return None
        mapping = {c.replace("_", "").lower(): c for c in df.columns}
        for name in names:
            c = mapping.get(name.replace("_", "").lower())
            if c:
                return c
        return None

    @staticmethod
    def _split_multi(value: str) -> list[str]:
        s = str(value or "").strip()
        if not s:
            return []
        parts = re.split(r"[|,;/]+", s)
        out = []
        for part in parts:
            part = part.strip()
            if part and part not in out:
                out.append(part)
        return out

    def _build_index(self) -> dict[str, TableMetadata]:
        idx: dict[str, TableMetadata] = {}
        if self.table_master.empty:
            return idx

        tbl_id_col = self._col(self.table_master, "TBL_ID", "tblId")
        tbl_nm_col = self._col(self.table_master, "TBL_NM", "tblNm", "STAT_NAME")
        org_col = self._col(self.table_master, "ORG_ID", "orgId")

        # table_master 자체에 이미 요약된 기간/주기 정보가 있으므로 반드시 fallback에 사용한다.
        master_freq_col = self._col(self.table_master, "FREQUENCIES", "FREQUENCY", "PRD_SE")
        master_start_col = self._col(self.table_master, "START_PERIOD", "START_PRD_DE", "STARTPRDDE")
        master_end_col = self._col(self.table_master, "END_PERIOD", "END_PRD_DE", "ENDPRDDE")
        master_comments_col = self._col(self.table_master, "COMMENTS", "COMMENT")
        master_source_col = self._col(self.table_master, "SOURCE", "SOURCES", "JOSA_NM")

        path_cols = [
            c for c in self.table_master.columns
            if "list" in c.lower() or "path" in c.lower() or "lvl" in c.lower()
        ]

        item_tbl_col = self._col(self.items, "TBL_ID", "tblId")
        item_id_col = self._col(self.items, "ITM_ID", "itmId")
        item_nm_col = self._col(self.items, "ITM_NM", "itmNm")

        cls_tbl_col = self._col(self.classifications, "TBL_ID", "tblId")
        cls_obj_col = self._col(self.classifications, "OBJ_ID", "objId")
        cls_id_col = self._col(self.classifications, "CLS_ID", "ITM_ID", "itmId")
        cls_nm_col = self._col(self.classifications, "CLS_NM", "ITM_NM", "itmNm")
        cls_obj_nm_col = self._col(self.classifications, "OBJ_NM", "objNm")

        prd_tbl_col = self._col(self.periods, "TBL_ID", "tblId")
        prd_se_col = self._col(self.periods, "PRD_SE", "prdSe")
        prd_de_col = self._col(self.periods, "PRD_DE", "prdDe")

        cmt_tbl_col = self._col(self.comments, "TBL_ID", "tblId")
        cmt_text_col = self._col(self.comments, "CMT_NM", "CMMT_NM", "comment", "NOTE")

        src_tbl_col = self._col(self.sources, "TBL_ID", "tblId")
        src_text_col = self._col(self.sources, "SRC_NM", "source", "SRC", "JOSA_NM")

        for _, row in self.table_master.iterrows():
            table_id = str(row[tbl_id_col]).strip()
            if not table_id:
                continue

            table_name = str(row[tbl_nm_col]).strip() if tbl_nm_col else table_id
            org_id = str(row[org_col]).strip() if org_col else "301"
            path_text = unique_join(
                [str(row[c]) for c in path_cols if str(row[c]).strip()]
            )

            items: list[dict[str, Any]] = []
            if item_tbl_col and item_id_col and item_nm_col:
                sub = self.items[self.items[item_tbl_col] == table_id]
                items = [
                    {
                        "item_id": str(r[item_id_col]).strip(),
                        "item_name": str(r[item_nm_col]).strip(),
                    }
                    for _, r in sub.iterrows()
                    if str(r[item_id_col]).strip()
                ]

            classifications: list[dict[str, Any]] = []
            if cls_tbl_col and cls_obj_col and cls_id_col:
                sub = self.classifications[self.classifications[cls_tbl_col] == table_id]
                classifications = [
                    {
                        "obj_id": str(r[cls_obj_col]).strip(),
                        "obj_name": str(r[cls_obj_nm_col]).strip() if cls_obj_nm_col else "",
                        "class_id": str(r[cls_id_col]).strip(),
                        "class_name": str(r[cls_nm_col]).strip() if cls_nm_col else "",
                    }
                    for _, r in sub.iterrows()
                    if str(r[cls_id_col]).strip()
                ]

            # 1) bok_periods.csv 상세행 우선
            frequencies: list[str] = []
            periods_by_freq: dict[str, list[str]] = {}

            if prd_tbl_col and not self.periods.empty:
                sub = self.periods[self.periods[prd_tbl_col] == table_id]
                current_freq = ""

                # PRD_SE / PRD_DE가 서로 다른 행일 수 있으므로 stateful하게 처리한다.
                for _, pr in sub.iterrows():
                    raw_freq = str(pr[prd_se_col]).strip() if prd_se_col else ""
                    if raw_freq:
                        current_freq = normalize_frequency(raw_freq)
                        if current_freq and current_freq not in frequencies:
                            frequencies.append(current_freq)
                        periods_by_freq.setdefault(current_freq, [])

                    raw_period = str(pr[prd_de_col]).strip() if prd_de_col else ""
                    if raw_period and current_freq:
                        periods_by_freq.setdefault(current_freq, []).append(
                            normalize_period(current_freq, raw_period)
                        )

            # 2) 상세기간 행이 없거나 주기를 얻지 못하면 table_master 요약값 fallback
            if not frequencies and master_freq_col:
                for raw in self._split_multi(str(row[master_freq_col])):
                    f = normalize_frequency(raw)
                    if f and f not in frequencies:
                        frequencies.append(f)

            flattened_periods = [
                p
                for plist in periods_by_freq.values()
                for p in plist
                if p
            ]

            start_period = min(flattened_periods) if flattened_periods else None
            end_period = max(flattened_periods) if flattened_periods else None

            # master의 START/END 값 fallback
            primary_freq = frequencies[0] if frequencies else ""

            if not start_period and master_start_col:
                raw = str(row[master_start_col]).strip()
                if raw:
                    start_period = normalize_period(primary_freq, raw)

            if not end_period and master_end_col:
                raw = str(row[master_end_col]).strip()
                if raw:
                    end_period = normalize_period(primary_freq, raw)

            comments: list[str] = []
            if cmt_tbl_col and cmt_text_col:
                sub = self.comments[self.comments[cmt_tbl_col] == table_id]
                comments = [
                    str(x).strip()
                    for x in sub[cmt_text_col].tolist()
                    if str(x).strip()
                ]

            if not comments and master_comments_col:
                raw = str(row[master_comments_col]).strip()
                if raw:
                    comments = [raw]

            sources: list[str] = []
            if src_tbl_col and src_text_col:
                sub = self.sources[self.sources[src_tbl_col] == table_id]
                sources = [
                    str(x).strip()
                    for x in sub[src_text_col].tolist()
                    if str(x).strip()
                ]

            if not sources and master_source_col:
                raw = str(row[master_source_col]).strip()
                if raw:
                    sources = [raw]

            search_text = unique_join(
                [
                    table_name,
                    path_text,
                    " ".join(i["item_name"] for i in items),
                    " ".join(c["class_name"] for c in classifications),
                    " ".join(frequencies),
                    " ".join(comments[:10]),
                    " ".join(sources[:5]),
                ],
                sep=" ",
            )

            idx[table_id] = TableMetadata(
                table_id=table_id,
                org_id=org_id,
                table_name=table_name,
                path_text=path_text,
                frequencies=frequencies,
                start_period=start_period,
                end_period=end_period,
                items=items,
                classifications=classifications,
                comments=comments,
                sources=sources,
                search_text=search_text,
            )

        return idx

    def table_ids(self) -> list[str]:
        return list(self._index.keys())

    def get(self, table_id: str) -> TableMetadata | None:
        return self._index.get(table_id)

    def all(self) -> list[TableMetadata]:
        return list(self._index.values())

    def is_supported(self, table_id: str) -> bool:
        return table_id in self._index

    def available_supported_tables(self) -> list[TableMetadata]:
        return [
            m
            for m in self._index.values()
            if m.items or m.classifications or m.frequencies
        ]
