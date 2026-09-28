"""Validated series selection and chart data for the HTTP UI."""

from __future__ import annotations

import math
from typing import Any

from statbridge_mcp.search_engine import SearchEngine
from statbridge_mcp.statistics_service import StatisticsService


def _number(value: Any) -> float | None:
    try:
        number = float(str(value).replace(",", ""))
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


class AnalysisService:
    def __init__(self, service: StatisticsService) -> None:
        self.service = service
        self.searcher = SearchEngine(service.store)

    def analyze(self, request: dict[str, Any]) -> dict[str, Any]:
        query = str(request.get("query") or "").strip()
        if not query:
            raise ValueError("query must be a nonempty string")
        if request.get("source", "kosis") not in ("kosis", "local"):
            raise ValueError("source must be kosis or local")
        selected = request.get("series") or []
        if not isinstance(selected, list) or len(selected) > 5:
            raise ValueError("series must contain at most five entries")
        if not selected:
            broad = self._broad_candidates(query)
            if broad:
                ids = [item["table_id"] for item in broad]
                return {"status": "need_clarification", "query": query, "reason": "table",
                        "question": "어떤 통계를 보시겠어요?", "candidates": broad,
                        "resolution": self._resolution("ambiguous", "semantic", ids)}
            groups = self.searcher.search_groups(query, top_k=5)
            candidates = self.searcher.search(query, top_k=5)
            if not candidates:
                return {"status": "no_match", "query": query, "candidates": [],
                        "resolution": self._resolution("unsupported", "none", [])}
            proposed = list(dict.fromkeys(group[0]["table_id"] for group in groups if group))
            return {"status": "need_clarification", "query": query, "reason": "table",
                    "candidates": candidates,
                    "resolution": self._resolution("resolved", "none", proposed)}

        # Resolve all missing selections before any numeric request.
        for choice in selected:
            if not isinstance(choice, dict) or not isinstance(choice.get("table_id"), str):
                raise ValueError("each series needs a table_id")
            options = self.service.get_series_options(choice["table_id"])
            if not choice.get("item_id") or choice.get("classifications") is None or not choice.get("frequency"):
                return {"status": "need_clarification", "query": query, "reason": "series",
                        "options": options, "series": selected,
                        "resolution": self._resolution(
                            "resolved", "series_parameters", [item["table_id"] for item in selected]
                        )}
            if (not isinstance(choice["item_id"], str) or not isinstance(choice["frequency"], str)
                    or not isinstance(choice["classifications"], dict)
                    or any(not isinstance(key, str) or not isinstance(value, str)
                           for key, value in choice["classifications"].items())):
                raise ValueError("series IDs and frequency must be strings")

        charts = []
        for choice in selected:
            if not isinstance(choice, dict) or not isinstance(choice.get("table_id"), str):
                raise ValueError("each series needs a table_id")
            table_id = choice["table_id"]
            options = self.service.get_series_options(table_id)
            if not options["items"]:
                return {"status": "data_unavailable", "query": query, "table_id": table_id,
                        "message": "검증 가능한 항목 ID가 없습니다."}
            item_id = choice.get("item_id")
            classifications = choice.get("classifications")
            frequency = choice.get("frequency")
            available = options["periods"].get(frequency)
            if not available:
                return {"status": "data_unavailable", "query": query, "table_id": table_id,
                        "message": "고정 데이터에서 제공 기간을 확인할 수 없습니다."}
            start = str(choice.get("start_period") or request.get("start_period") or available["start"])
            end = str(choice.get("end_period") or request.get("end_period") or available["end"])
            if request.get("source", "kosis") == "local" and (start < available["start"] or end > available["end"]):
                raise ValueError("requested period exceeds the known available period")
            try:
                data = self.service.get_exact_statistics(
                    table_id=table_id, item_id=item_id, classifications=classifications,
                    frequency=frequency, start_period=start, end_period=end,
                    source=request.get("source", "kosis"),
                )
            except ValueError:
                raise
            except Exception:
                return {"status": "data_unavailable", "query": query, "table_id": table_id,
                        "message": "선택한 계열의 수치를 조회하지 못했습니다.",
                        "local_csv_available": options["local_csv_available"]}
            points: dict[str, float] = {}
            units: set[str] = set()
            for row in data["rows"]:
                if row.get("ITM_ID") and str(row["ITM_ID"]) != item_id:
                    return {"status": "data_unavailable", "query": query, "table_id": table_id,
                            "message": "응답의 통계 항목 ID가 선택값과 다릅니다."}
                if any(row.get(f"C{axis[4:]}") and str(row[f"C{axis[4:]}"]) != value
                       for axis, value in classifications.items()):
                    return {"status": "data_unavailable", "query": query, "table_id": table_id,
                            "message": "응답의 분류 ID가 선택값과 다릅니다."}
                period = str(row.get("PRD_DE") or "")
                value = _number(row.get("DT"))
                if period and value is not None:
                    if period in points and points[period] != value:
                        return {"status": "data_unavailable", "query": query, "table_id": table_id,
                                "message": "같은 시점에 서로 다른 값이 있습니다."}
                    points[period] = value
                    units.add(str(row.get("UNIT_NM") or ""))
            if not points or len(units) > 1:
                return {"status": "data_unavailable", "query": query, "table_id": table_id,
                        "message": "선택한 계열에 유효한 단일 단위의 관측값이 없습니다.",
                        "local_csv_available": options["local_csv_available"]}
            item_name = next(item["label"] for item in options["items"] if item["id"] == item_id)
            labels = [next(value["label"] for value in axis["values"]
                           if value["id"] == classifications[axis["key"]]) for axis in options["axes"]]
            charts.append({"table_id": table_id, "table_name": options["table_name"],
                           "label": " · ".join([item_name, *labels]), "unit": units.pop(),
                           "frequency": frequency, "source": data["source"],
                           "used_params": data["used_params"],
                           "points": [{"period": period, "value": value}
                                      for period, value in sorted(points.items())]})
        compatible = len({(chart["unit"], chart["frequency"]) for chart in charts}) == 1
        return {"status": "resolved", "query": query, "chart": charts,
                "layout": "combined" if compatible else "separate",
                "resolution": self._resolution(
                    "resolved", "none", [chart["table_id"] for chart in charts]
                )}

    @staticmethod
    def _resolution(intent: str, clarification_kind: str, table_ids: list[str]) -> dict[str, Any]:
        return {"intent": intent, "clarification_kind": clarification_kind,
                "proposed_table_ids": list(dict.fromkeys(table_ids))}

    def _broad_candidates(self, query: str) -> list[dict[str, Any]]:
        """Offer real catalog choices for common underspecified economic words."""
        from statbridge_mcp.search_engine import compact
        q = compact(query)
        if any(word in q for word in ("예측", "전망치", "추천", "상담")):
            return []
        groups = [
            ("지역별대출", ["DT_141Y003", "DT_151Y003"]),
            ("기업경기전망", ["DT_512Y014", "DT_512Y020"]),
            ("지역경기", ["DT_512Y019", "DT_511Y004"]),
            ("전자지급", ["DT_633Y002", "DT_633Y004"]),
            ("기업재무상태", ["DT_501Y001", "DT_501Y002"]),
            ("기업실적", ["DT_501Y005", "DT_501Y006"]),
            ("가계빚", ["DT_151Y001", "DT_151Y002"]),
            ("경기전망", ["DT_512Y014", "DT_512Y020"]),
            ("물가", ["DT_401Y015", "DT_404Y014"]),
            ("결제", ["DT_601Y003", "DT_603Y010"]),
            ("대출", ["DT_104Y016", "DT_151Y001"]),
            ("금리", ["DT_121Y002", "DT_121Y006"]),
        ]
        for term, ids in groups:
            if term in q and not any(word in q for word in ("신규취급액", "잔액기준", "수신금리", "대출금리", "수입물가", "생산자물가")):
                choices = [self.searcher.search(table_id, top_k=1) for table_id in ids]
                return [choice[0] for choice in choices if choice and choice[0]["table_id"] in ids]
        return []
