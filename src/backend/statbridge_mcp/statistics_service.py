from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict
from glob import glob
from pathlib import Path
from typing import Any

import pandas as pd

from .config import settings
from .kosis_client import KosisApiError, KosisClient
from .metadata_store import MetadataStore, normalize_frequency, normalize_period


def _norm_map(columns: list[str]) -> dict[str, str]:
    return {c.replace("_", "").lower(): c for c in columns}


def _col(df: pd.DataFrame, *names: str) -> str | None:
    mapping = _norm_map(list(df.columns))
    for name in names:
        key = name.replace("_", "").lower()
        if key in mapping:
            return mapping[key]
    return None


class StatisticsService:
    def __init__(self, store: MetadataStore | None = None, client: KosisClient | None = None) -> None:
        self.store = store or MetadataStore()
        self._client = client
        self.tables_dir = settings.tables_dir
        self._axes_cache: dict[str, OrderedDict[str, list[str]]] = {}
        self._series_options_cache: dict[str, dict[str, Any]] = {}

    @property
    def client(self) -> KosisClient:
        if self._client is None:
            self._client = KosisClient()
        return self._client

    def search_tables(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        from .search_engine import SearchEngine
        if not hasattr(self, "_search_engine"):
            self._search_engine = SearchEngine(self.store)
        return self._search_engine.search(query=query, top_k=top_k)

    def get_series_options(self, table_id: str) -> dict[str, Any]:
        """Read trusted item/class IDs from the bundled rows when processed axes are empty."""
        if table_id in self._series_options_cache:
            return self._series_options_cache[table_id]
        meta = self.store.get(table_id)
        if not meta:
            raise ValueError(f"지원하지 않는 table_id: {table_id}")
        items: list[dict[str, str]] = []
        axes: list[dict[str, Any]] = []
        periods: dict[str, dict[str, str]] = {}
        path = self._find_local_table_csv(table_id)
        if path:
            frame = pd.read_csv(path, dtype=str).fillna("")
            if {"ITM_ID", "ITM_NM"} <= set(frame.columns):
                items = [
                    {"id": item_id, "label": label}
                    for item_id, label in frame[["ITM_ID", "ITM_NM"]].drop_duplicates().itertuples(index=False, name=None)
                    if item_id
                ]
            for index in range(1, 9):
                code, label = f"C{index}", f"C{index}_NM"
                if {code, label} <= set(frame.columns):
                    values = [
                        {"id": value_id, "label": value_name}
                        for value_id, value_name in frame[[code, label]].drop_duplicates().itertuples(index=False, name=None)
                        if value_id
                    ]
                    if values:
                        axes.append({"key": f"objL{index}", "label": str(frame.get(f"C{index}_OBJ_NM", pd.Series([code])).iloc[0]), "values": values})
            if {"PRD_SE", "PRD_DE"} <= set(frame.columns):
                for raw_frequency, rows in frame.groupby("PRD_SE"):
                    values = sorted(set(rows["PRD_DE"]) - {""})
                    if values:
                        normalized = normalize_frequency(raw_frequency)
                        recent_count = {"M": 12, "Q": 8, "Y": 5}.get(normalized, 12)
                        periods[normalized] = {"start": values[0], "end": values[-1],
                                               "recent_start": values[-recent_count]}
        else:
            items = [{"id": item["item_id"], "label": item["item_name"]} for item in meta.items]
            for index, obj_id in enumerate(dict.fromkeys(x["obj_id"] for x in meta.classifications), start=1):
                values = [
                    {"id": value["class_id"], "label": value["class_name"]}
                    for value in meta.classifications if value["obj_id"] == obj_id
                ]
                axes.append({"key": f"objL{index}", "label": obj_id, "values": values})
        result = {"table_id": table_id, "table_name": meta.table_name, "items": items,
                  "axes": axes, "periods": periods, "local_csv_available": bool(path)}
        self._series_options_cache[table_id] = result
        return result

    def get_exact_statistics(
        self, *, table_id: str, item_id: str, classifications: dict[str, str],
        frequency: str, start_period: str, end_period: str, source: str = "kosis",
    ) -> dict[str, Any]:
        """Execute one validated series request without changing IDs or source."""
        if source not in {"kosis", "local"}:
            raise ValueError("source must be kosis or local")
        options = self.get_series_options(table_id)
        if item_id not in {item["id"] for item in options["items"]}:
            raise ValueError(f"지원하지 않는 item_id: {item_id}")
        if set(classifications) != {axis["key"] for axis in options["axes"]}:
            raise ValueError("분류 축을 정확히 지정해야 합니다")
        for axis in options["axes"]:
            if classifications[axis["key"]] not in {value["id"] for value in axis["values"]}:
                raise ValueError(f"지원하지 않는 분류값: {axis['key']}")
        if frequency not in options["periods"] and frequency not in self.store.get(table_id).frequencies:
            raise ValueError(f"지원하지 않는 주기: {frequency}")
        if not start_period or not end_period or start_period > end_period:
            raise ValueError("기간이 올바르지 않습니다")
        import re
        pattern = {"M": r"\d{4}(0[1-9]|1[0-2])", "Q": r"\d{4}0[1-4]",
                   "Y": r"\d{4}", "S": r"\d{4}0[12]", "D": r"\d{8}"}.get(frequency)
        if pattern and (not re.fullmatch(pattern, start_period) or not re.fullmatch(pattern, end_period)):
            raise ValueError("기간 형식이 주기와 맞지 않습니다")
        if source == "local":
            rows = self._filter_local_data(table_id, item_id, classifications, frequency, start_period, end_period)
            result_source = "local_csv"
        else:
            meta = self.store.get(table_id)
            rows = self.client.get_statistics(
                org_id=meta.org_id or "301", table_id=table_id, item_id=item_id,
                frequency="A" if frequency == "Y" else frequency,
                start_period=start_period, end_period=end_period, classifications=classifications,
            )
            result_source = "kosis_api"
        return {"source": result_source, "table_id": table_id,
                "used_params": {"item_id": item_id, "classifications": classifications,
                                "frequency": frequency, "start_period": start_period,
                                "end_period": end_period},
                "row_count": len(rows), "rows": rows}

    def _live_period_metadata(self, table_id: str) -> dict[str, Any]:
        meta = self.store.get(table_id)
        if not meta:
            raise ValueError(f"지원하지 않는 table_id: {table_id}")

        rows = self.client.get_prd_meta(meta.org_id or "301", table_id)
        frequencies: list[str] = []
        periods_by_freq: dict[str, list[str]] = {}
        current_freq = ""

        for row in rows:
            raw_freq = ""
            raw_period = ""
            for k, v in row.items():
                nk = k.replace("_", "").lower()
                if nk == "prdse" and v not in ("", None):
                    raw_freq = str(v).strip()
                elif nk == "prdde" and v not in ("", None):
                    raw_period = str(v).strip()

            if raw_freq:
                current_freq = normalize_frequency(raw_freq)
                if current_freq and current_freq not in frequencies:
                    frequencies.append(current_freq)
                periods_by_freq.setdefault(current_freq, [])

            if raw_period and current_freq:
                periods_by_freq.setdefault(current_freq, []).append(
                    normalize_period(current_freq, raw_period)
                )

        flattened = [
            p for values in periods_by_freq.values() for p in values if p
        ]

        return {
            "frequencies": frequencies,
            "periods_by_freq": {
                f: sorted(set(v)) for f, v in periods_by_freq.items()
            },
            "start_period": min(flattened) if flattened else None,
            "end_period": max(flattened) if flattened else None,
        }

    def get_table_metadata(self, table_id: str, live_period_fallback: bool = True) -> dict[str, Any]:
        meta = self.store.get(table_id)
        if not meta:
            raise ValueError(f"지원하지 않는 table_id: {table_id}")

        result = asdict(meta)
        result["period_source"] = "local"

        if live_period_fallback and (
            not result.get("frequencies")
            or not result.get("start_period")
            or not result.get("end_period")
        ):
            try:
                live = self._live_period_metadata(table_id)
                if not result.get("frequencies") and live["frequencies"]:
                    result["frequencies"] = live["frequencies"]
                if not result.get("start_period") and live["start_period"]:
                    result["start_period"] = live["start_period"]
                if not result.get("end_period") and live["end_period"]:
                    result["end_period"] = live["end_period"]
                result["period_source"] = "kosis_live_prd_fallback"
                result["periods_by_freq"] = live["periods_by_freq"]
            except Exception as e:  # noqa: BLE001 - 라이브 메타 폴백 실패는 기록만 하고 계속
                result["period_fallback_error"] = str(e)

        return result

    def _find_local_table_csv(self, table_id: str) -> Path | None:
        patterns = [
            str(self.tables_dir / f"{table_id}__*.csv"),
            str(self.tables_dir / f"{table_id}.csv"),
        ]
        for pattern in patterns:
            matches = glob(pattern)
            if matches:
                return Path(matches[0]).resolve()
        return None

    def _filter_local_data(
        self,
        table_id: str,
        item_id: str,
        classifications: dict[str, str] | None,
        frequency: str | None,
        start_period: str | None,
        end_period: str | None,
    ) -> list[dict[str, Any]]:
        path = self._find_local_table_csv(table_id)
        if not path or not path.exists():
            return []

        df = pd.read_csv(path, dtype=str).fillna("")
        tbl_col = _col(df, "TBL_ID", "tblId")
        itm_col = _col(df, "ITM_ID", "itmId")
        prd_se_col = _col(df, "PRD_SE", "prdSe")
        prd_de_col = _col(df, "PRD_DE", "prdDe")

        if tbl_col:
            df = df[df[tbl_col] == table_id]
        if itm_col and item_id and item_id != "ALL":
            df = df[df[itm_col] == item_id]
        if prd_se_col and frequency:
            # CSV는 KOSIS 원본 주기코드(예: A), 입력은 정규화 코드(예: Y)일 수 있어 양쪽을 맞춘다.
            df = df[df[prd_se_col].map(normalize_frequency) == frequency]
        if prd_de_col and start_period:
            df = df[df[prd_de_col] >= start_period]
        if prd_de_col and end_period:
            df = df[df[prd_de_col] <= end_period]

        for obj_key, obj_val in (classifications or {}).items():
            if not obj_val or obj_val == "ALL":
                continue
            col = _col(df, obj_key.replace("objL", "C"))
            if col:
                df = df[df[col] == obj_val]

        return df.to_dict(orient="records")

    def _live_classification_axes(self, table_id: str) -> OrderedDict[str, list[str]]:
        """KOSIS getMeta(type=ITM)에서 분류 축(OBJ_ID 순서)과 값(ITM_ID)을 얻는다.

        로컬 bok_classifications 가 비어 있으면 objL 축 수/값을 알 수 없어
        objL1만 보내다 실패하므로, 이 라이브 정보로 축을 복원한다(표별 캐시).
        """
        if table_id in self._axes_cache:
            return self._axes_cache[table_id]

        meta = self.store.get(table_id)
        axes: OrderedDict[str, list[str]] = OrderedDict()
        if meta:
            try:
                for row in self.client.get_itm_meta(meta.org_id or "301", table_id):
                    oid = str(row.get("OBJ_ID") or "").strip()
                    cid = str(row.get("ITM_ID") or "").strip()
                    # OBJ_ID=="ITEM"은 항목축이므로 분류(objL)에서 제외한다.
                    if not oid or oid == "ITEM" or not cid:
                        continue
                    axes.setdefault(oid, [])
                    if cid not in axes[oid]:
                        axes[oid].append(cid)
            except Exception:  # noqa: BLE001 - 축 조회 실패 시 기존 동작으로 폴백
                axes = OrderedDict()

        self._axes_cache[table_id] = axes
        return axes

    def _classification_depth(self, table_id: str) -> int:
        meta = self.store.get(table_id)
        if not meta or not meta.classifications:
            return 1
        obj_ids = []
        for c in meta.classifications:
            oid = c.get("obj_id", "")
            if oid and oid not in obj_ids:
                obj_ids.append(oid)
        return max(1, len(obj_ids))

    def _first_real_classifications(self, table_id: str) -> dict[str, str]:
        meta = self.store.get(table_id)

        obj_ids = []
        values_by_obj: dict[str, list[str]] = {}
        for c in (meta.classifications if meta else []):
            oid = c.get("obj_id", "")
            cid = c.get("class_id", "")
            if not oid or not cid:
                continue
            if oid not in obj_ids:
                obj_ids.append(oid)
            values_by_obj.setdefault(oid, [])
            if cid not in values_by_obj[oid]:
                values_by_obj[oid].append(cid)

        if not obj_ids:
            return {"objL1": "ALL"}

        out = {}
        for i, oid in enumerate(obj_ids, start=1):
            vals = values_by_obj.get(oid, [])
            out[f"objL{i}"] = vals[0] if vals else "ALL"
        return out

    def _api_attempts(
        self,
        table_id: str,
        item_id: str,
        classifications: dict[str, str] | None,
        frequency: str,
        start_period: str,
        end_period: str,
    ) -> list[tuple[str, dict[str, Any]]]:
        meta = self.store.get(table_id)
        if not meta:
            raise ValueError(f"지원하지 않는 table_id: {table_id}")

        org_id = meta.org_id or "301"
        objs = {k: v for k, v in (classifications or {}).items() if v not in ("", None)}
        depth = self._classification_depth(table_id)

        # 로컬 분류 메타가 없으면 라이브 ITM 메타로 축 수/실제값을 복원한다(API 경로에서만 호출).
        if not meta.classifications:
            axes = self._live_classification_axes(table_id)
            if axes:
                depth = max(depth, len(axes))
                first_real = {
                    f"objL{i}": (ids[0] if ids else "ALL")
                    for i, ids in enumerate(axes.values(), start=1)
                }
            else:
                first_real = self._first_real_classifications(table_id)
        else:
            first_real = self._first_real_classifications(table_id)

        all_by_depth = {f"objL{i}": "ALL" for i in range(1, depth + 1)}

        attempts_raw = [
            ("requested", item_id, objs),
            ("requested_item_all_classes", item_id, all_by_depth),
            ("item_all_requested_classes", "ALL", objs),
            ("item_all_all_classes", "ALL", all_by_depth),
            ("requested_item_first_real_classes", item_id, first_real),
            ("item_all_first_real_classes", "ALL", first_real),
        ]

        # 메타데이터의 실제 item id들도 fallback 후보로 추가
        real_item_ids = [i.get("item_id", "") for i in meta.items if i.get("item_id")]
        for rid in real_item_ids[:5]:
            attempts_raw.extend([
                ("real_item_all_classes", rid, all_by_depth),
                ("real_item_first_real_classes", rid, first_real),
            ])

        # 중복 제거
        seen = set()
        attempts = []
        for name, iid, cls in attempts_raw:
            key = (iid, tuple(sorted(cls.items())))
            if key in seen:
                continue
            seen.add(key)
            attempts.append((name, {
                "org_id": org_id,
                "table_id": table_id,
                "item_id": iid,
                "frequency": frequency,
                "start_period": start_period,
                "end_period": end_period,
                "classifications": cls,
            }))
        return attempts

    def get_statistics(
        self,
        table_id: str,
        item_id: str = "ALL",
        classifications: dict[str, str] | None = None,
        frequency: str | None = None,
        start_period: str | None = None,
        end_period: str | None = None,
        prefer_local: bool = True,
    ) -> dict[str, Any]:
        meta = self.store.get(table_id)
        if not meta:
            raise ValueError(f"지원하지 않는 table_id: {table_id}")

        effective_meta = self.get_table_metadata(table_id, live_period_fallback=True)

        frequencies = effective_meta.get("frequencies") or []
        frequency = frequency or (frequencies[0] if frequencies else "Y")
        start_period = start_period or effective_meta.get("start_period") or ""
        end_period = end_period or effective_meta.get("end_period") or ""

        if not classifications:
            classifications = {
                f"objL{i}": "ALL"
                for i in range(1, self._classification_depth(table_id) + 1)
            }

        if prefer_local:
            local_rows = self._filter_local_data(
                table_id=table_id,
                item_id=item_id,
                classifications=classifications,
                frequency=frequency,
                start_period=start_period,
                end_period=end_period,
            )
            if local_rows:
                return {
                    "source": "local_csv",
                    "table_id": table_id,
                    "table_name": meta.table_name,
                    "used_params": {
                        "item_id": item_id,
                        "classifications": classifications,
                        "frequency": frequency,
                        "start_period": start_period,
                        "end_period": end_period,
                    },
                    "row_count": len(local_rows),
                    "rows": local_rows,
                }

        errors = []
        for attempt_name, params in self._api_attempts(
            table_id=table_id,
            item_id=item_id,
            classifications=classifications,
            frequency=frequency,
            start_period=start_period,
            end_period=end_period,
        ):
            try:
                rows = self.client.get_statistics(
                    org_id=params["org_id"],
                    table_id=params["table_id"],
                    item_id=params["item_id"],
                    frequency=params["frequency"],
                    start_period=params["start_period"],
                    end_period=params["end_period"],
                    classifications=params["classifications"],
                )
                if rows:
                    return {
                        "source": "kosis_api",
                        "attempt": attempt_name,
                        "table_id": table_id,
                        "table_name": meta.table_name,
                        "used_params": {
                            "item_id": params["item_id"],
                            "classifications": params["classifications"],
                            "frequency": params["frequency"],
                            "start_period": params["start_period"],
                            "end_period": params["end_period"],
                        },
                        "row_count": len(rows),
                        "rows": rows,
                    }
            except KosisApiError as e:
                errors.append({"attempt": attempt_name, "error": f"{e.code}:{e.msg}"})
            except Exception as e:  # noqa: BLE001 - 시도별 오류를 누적해 계속 진행
                errors.append({"attempt": attempt_name, "error": str(e)})

        return {
            "source": "none",
            "table_id": table_id,
            "table_name": meta.table_name,
            "used_params": {
                "item_id": item_id,
                "classifications": classifications,
                "frequency": frequency,
                "start_period": start_period,
                "end_period": end_period,
            },
            "row_count": 0,
            "rows": [],
            "errors": errors,
        }
