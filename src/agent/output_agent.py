from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import json

from output_schema import ChartEditCommand, ChartSpec, Highlight, Annotation
from plotly_renderer import render_plotly


SUPPORTED_CHART_TYPES = {"auto", "line", "bar", "stacked_bar", "area", "scatter", "bubble", "pie", "donut", "histogram", "box", "heatmap", "treemap", "waterfall"}
SUPPORTED_LAYOUTS = {"combined", "separate"}


@dataclass(slots=True)
class OutputRequest:
    """User-controlled presentation request consumed only by OutputAgent."""

    chart_type: str = "auto"
    layout: str = "combined"
    title: str | None = None
    show_legend: bool = True
    x_axis_label: str | None = None
    y_axis_label: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "OutputRequest":
        raw = value or {}
        chart_type = str(raw.get("chart_type") or "auto").lower()
        layout = str(raw.get("layout") or "combined").lower()
        return cls(
            chart_type=chart_type if chart_type in SUPPORTED_CHART_TYPES else "auto",
            layout=layout if layout in SUPPORTED_LAYOUTS else "combined",
            title=str(raw.get("title") or "").strip() or None,
            show_legend=bool(raw.get("show_legend", True)),
            x_axis_label=str(raw.get("x_axis_label") or "").strip() or None,
            y_axis_label=str(raw.get("y_axis_label") or "").strip() or None,
        )


class OutputAgent:
    """Turn MCP rows into an editable, renderer-independent output specification.

    This skeleton deliberately does not draw pixels. It owns chart selection,
    data shaping and edit options; the frontend only renders the returned spec.
    """

    palette = ["#4568ff", "#ff805e", "#24a47c", "#9a62df", "#e3a52b", "#2aa7c9"]

    def __init__(self, ncp_client: Any | None = None) -> None:
        self.ncp_client = ncp_client

    @staticmethod
    def _series_key(row: dict[str, Any]) -> tuple[str, str, str]:
        source_id = str(row.get("_SOURCE_SERIES_ID") or "")
        explicit = str(row.get("_SERIES_LABEL") or "").strip()
        dimensions = [str(row.get(f"C{index}_NM") or "").strip() for index in range(1, 9)]
        dimensions = [name for name in dimensions if name and name not in {"전체", "계", "합계"}]
        if explicit:
            label = " · ".join([explicit, *(name for name in dimensions if name not in explicit)])
            return source_id, label, str(row.get("UNIT_NM") or "")
        labels = [str(row.get("ITM_NM") or "").strip()]
        labels.extend(dimensions)
        return source_id, " · ".join(x for x in labels if x) or "통계값", str(row.get("UNIT_NM") or "")

    def _series(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        frequencies: dict[tuple[str, str, str], str] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                value = float(str(row.get("DT", "")).replace(",", ""))
            except (TypeError, ValueError):
                continue
            period = str(row.get("PRD_DE") or "").strip()
            if period:
                key = self._series_key(row)
                grouped.setdefault(key, []).append({"date": period, "value": value})
                frequencies[key] = str(row.get("_FREQUENCY") or "")
        result = []
        for index, ((source_id, label, unit), points) in enumerate(grouped.items()):
            unique: dict[str, dict[str, Any]] = {}
            for point in points:
                previous = unique.get(point["date"])
                if previous is not None and previous["value"] != point["value"]:
                    raise ValueError(f"{label}의 {point['date']} 값이 여러 개라 계열을 안전하게 합칠 수 없습니다.")
                unique[point["date"]] = point
            result.append({
                "id": f"series-{index + 1}",
                "label": label,
                "unit": unit,
                "sourceId": source_id,
                "frequency": frequencies[(source_id, label, unit)],
                "color": self.palette[index % len(self.palette)],
                "points": [unique[key] for key in sorted(unique)],
            })
        return result

    @staticmethod
    def _select_chart_type(requested: str, series: list[dict[str, Any]]) -> str:
        if requested != "auto":
            return requested
        point_count = max((len(item.get("points") or []) for item in series), default=0)
        return "bar" if point_count <= 6 else "line"

    @staticmethod
    def _summary(series: list[dict[str, Any]]) -> str:
        if not series:
            return "선택한 기간에 그래프로 표시할 수치 데이터가 없습니다."
        item = series[0]
        points = item.get("points") or []
        if not points:
            return "그래프를 생성했습니다."
        first, last = points[0], points[-1]
        delta = last["value"] - first["value"]
        direction = "증가" if delta > 0 else "감소" if delta < 0 else "같은 수준을 유지"
        extra = f" 함께 표시된 계열은 총 {len(series)}개입니다." if len(series) > 1 else ""
        label = str(item.get("label") or "통계값")
        last_char = label[-1]
        has_batchim = "가" <= last_char <= "힣" and (ord(last_char) - ord("가")) % 28 != 0
        subject = label + ("은" if has_batchim else "는")
        return (
            f"{subject} {first['date']} {first['value']:,.1f}에서 "
            f"{last['date']} {last['value']:,.1f}{item.get('unit') or ''}로 {direction}했습니다.{extra}"
        )

    @staticmethod
    def _table(series: list[dict[str, Any]]) -> dict[str, Any]:
        """Expose the plotted values as a table without changing their meaning."""
        return {
            "columns": ["series", "period", "value", "unit"],
            "rows": [
                {
                    "series": item["label"],
                    "period": point["date"],
                    "value": point["value"],
                    "unit": item["unit"],
                }
                for item in series
                for point in item["points"]
            ],
        }

    @staticmethod
    def _evidence(result: dict[str, Any]) -> list[dict[str, Any]]:
        """Report only source identifiers and query bounds supplied by execution."""
        execution = result.get("execution") or {}
        plans = result.get("api_plans") or [result.get("api_plan")]
        sources = execution.get("sources") or []
        evidence = []
        for plan in plans:
            if not isinstance(plan, dict):
                continue
            table_id = str(plan.get("table_id") or "")
            source = next((item for item in sources if isinstance(item, dict) and str(item.get("table_id") or "") == table_id), {})
            evidence.append({
                "tableId": table_id,
                "tableName": str(plan.get("table_name") or ""),
                "organizationId": str(plan.get("org_id") or ""),
                "itemId": str(plan.get("item_id") or ""),
                "frequency": str(plan.get("frequency") or ""),
                "requestedPeriod": {
                    "start": str(plan.get("start_period") or ""),
                    "end": str(plan.get("end_period") or ""),
                },
                "rowCount": source.get("row_count"),
                "source": str(source.get("source") or ""),
            })
        return evidence

    @staticmethod
    def _model_data(series: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{
            "label": s["label"], "unit": s["unit"], "pointCount": len(s["points"]),
            "first": s["points"][0] if s["points"] else None,
            "last": s["points"][-1] if s["points"] else None,
            "minimum": min(s["points"], key=lambda p: p["value"]) if s["points"] else None,
            "maximum": max(s["points"], key=lambda p: p["value"]) if s["points"] else None,
        } for s in series]

    def _explain(self, series: list[dict[str, Any]], spec: ChartSpec, fallback: str) -> dict[str, Any]:
        if not series or not self.ncp_client or not self.ncp_client.configured:
            return {"text": fallback, "source": "rules", "method": "첫 번째 계열의 시작값과 끝값 비교"}
        system = (
            "너는 통계 그래프 설명자다. 제공된 숫자와 시점만 근거로 한국어 2~3문장으로 설명한다. "
            "원인, 예측, 정책 효과를 추측하지 마라. 다른 단위를 직접 크기 비교하지 마라. "
            "원자료의 모든 점을 받은 것은 아니므로 중간 구간의 세부 추세를 단정하지 마라."
        )
        user = json.dumps({"chart_type": spec.chart_type, "title": spec.title,
                           "series": self._model_data(series)}, ensure_ascii=False)
        try:
            text, _ = self.ncp_client.chat_main(system, user, max_tokens=320, thinking_effort="none")
            if text.strip():
                return {"text": text.strip(), "source": self.ncp_client.settings.main_model,
                        "method": "그래프 계열의 시작·끝·최솟값·최댓값을 근거로 생성"}
        except Exception:
            pass
        return {"text": fallback, "source": "rules", "method": "첫 번째 계열의 시작값과 끝값 비교"}

    def _propose_spec(self, series: list[dict[str, Any]], request: dict[str, Any]) -> dict[str, Any]:
        if not self.ncp_client or not self.ncp_client.configured:
            return {}
        system = (
            "너는 통계 그래프 명세 생성기다. 사용자 요청과 실제 데이터 구조만 사용한다. "
            "허용된 유형은 line, bar, stacked_bar, area, scatter, bubble, pie, donut, "
            "histogram, box, heatmap, treemap, waterfall이다. JSON 객체 하나만 반환하라. "
            "필드는 chart_type, title, subtitle, x_axis_label, y_axis_label, legend_position, "
            "highlights([{start,end,label}]), series_chart_types(계열 이름별 line/bar/area), secondary_axis_series만 허용한다. "
            "막대와 선을 함께 요청하면 각 계열의 유형을 series_chart_types에 넣고, 단위가 다른 보조 계열을 secondary_axis_series에 넣어라. "
            "데이터에 필요한 차원이 없으면 line 또는 bar를 선택하라. "
            "통계 수치나 데이터 계열을 새로 만들지 마라."
        )
        user = json.dumps({"request": request.get("natural_language") or "", "series": self._model_data(series)}, ensure_ascii=False)
        try:
            text, _ = self.ncp_client.chat_main(system, user, max_tokens=380, thinking_effort="none")
            proposed = self.ncp_client._json_object(text)
            allowed = {"chart_type", "title", "subtitle", "x_axis_label", "y_axis_label", "legend_position", "highlights", "series_chart_types", "secondary_axis_series"}
            return {key: value for key, value in proposed.items() if key in allowed}
        except Exception:
            return {}

    @staticmethod
    def _apply_data_edits(series: list[dict[str, Any]], spec: ChartSpec) -> list[dict[str, Any]]:
        shaped = []
        for item in series:
            if item["label"] in spec.hidden_series:
                continue
            points = [p for p in item["points"] if
                      (not spec.period_start or p["date"] >= spec.period_start) and
                      (not spec.period_end or p["date"] <= spec.period_end)]
            if spec.transform == "cumulative":
                total = 0.0
                points = [{"date": p["date"], "value": (total := total + p["value"])} for p in points]
            elif spec.transform == "average" and points:
                points = [{"date": points[-1]["date"], "value": sum(x["value"] for x in points) / len(points)}]
            elif spec.transform in {"growth_rate", "year_over_year"}:
                if spec.transform == "year_over_year":
                    if all(len(p["date"]) == 6 and p["date"].isdigit() for p in points): lag = 12
                    elif all("Q" in p["date"].upper() for p in points): lag = 4
                    elif all(len(p["date"]) == 4 and p["date"].isdigit() for p in points): lag = 1
                    else: raise ValueError("이 시점 형식의 전년 대비 계산은 지원하지 않습니다.")
                else:
                    lag = 1
                points = [{"date": points[i]["date"], "value": (points[i]["value"] / points[i-lag]["value"] - 1) * 100}
                          for i in range(lag, len(points)) if points[i-lag]["value"] != 0]
            unit = "%" if spec.transform in {"growth_rate", "year_over_year"} else item["unit"]
            shaped.append({**item, "points": points, "unit": unit})
        if spec.top_n:
            shaped = sorted(shaped, key=lambda s: abs(s["points"][-1]["value"]) if s["points"] else -1, reverse=True)[:spec.top_n]
        return shaped

    def _build(self, result: dict[str, Any], spec: ChartSpec) -> dict[str, Any]:
        source_series = self._series((result.get("execution") or {}).get("rows") or [])
        series = self._apply_data_edits(source_series, spec)
        labels = {s["label"] for s in series}
        if any(label not in labels for label in [*spec.series_chart_types, *spec.secondary_axis_series]):
            raise ValueError("그래프 명세에 조회되지 않은 계열이 포함되어 있습니다.")
        if spec.secondary_axis_series and spec.chart_type not in {"line", "bar", "stacked_bar", "area"}:
            raise ValueError("보조축은 선·막대·영역 그래프에서만 사용할 수 있습니다.")
        mixed_units = len({s["unit"] for s in series}) > 1
        mixed_frequency = len({s["frequency"] for s in series if s["frequency"]}) > 1
        if (mixed_frequency or (mixed_units and not spec.secondary_axis_series)) and spec.layout == "combined":
            spec = ChartSpec.model_validate({**spec.model_dump(), "layout": "separate"})
        summary = self._summary(series)
        explanation = self._explain(series, spec, summary)
        figure = render_plotly(series, spec)
        return {
            "status": "ready" if any(s["points"] for s in series) else "empty",
            "agent": "output-agent-chartspec-v2",
            "summary": explanation["text"],
            "table": self._table(series),
            "explanation": explanation,
            "evidence": self._evidence(result),
            "chartState": spec.model_dump(),
            "plotlyFigure": figure,
            "visualization": {
                "chartType": spec.chart_type, "layout": spec.layout, "series": series, "editable": True,
                "editOptions": {
                    "title": spec.title, "showLegend": spec.show_legend,
                    "xAxisLabel": spec.x_axis_label, "yAxisLabel": spec.y_axis_label,
                    "supportedChartTypes": sorted(SUPPORTED_CHART_TYPES - {"auto"}),
                    "supportedLayouts": sorted(SUPPORTED_LAYOUTS),
                },
            },
        }

    def prepare(self, result: dict[str, Any], request: dict[str, Any] | None = None) -> dict[str, Any]:
        raw = request or {}
        series = self._series((result.get("execution") or {}).get("rows") or [])
        proposed = self._propose_spec(series, raw)
        requested_type = str(raw.get("chart_type") or "auto")
        if requested_type not in SUPPORTED_CHART_TYPES:
            raise ValueError("지원하지 않는 그래프 종류입니다.")
        if requested_type != "auto": proposed["chart_type"] = requested_type
        elif proposed.get("chart_type") not in SUPPORTED_CHART_TYPES - {"auto"}:
            proposed["chart_type"] = self._select_chart_type("auto", series)
        proposed.update(layout=raw.get("layout") or "combined", show_legend=raw.get("show_legend", True))
        for field in ("title", "subtitle", "x_axis_label", "y_axis_label"):
            if raw.get(field): proposed[field] = raw[field]
        try:
            spec = ChartSpec.model_validate(proposed)
        except ValueError:
            spec = ChartSpec(chart_type=self._select_chart_type(requested_type, series), layout=raw.get("layout") or "combined",
                             title=raw.get("title") or "", x_axis_label=raw.get("x_axis_label") or "",
                             y_axis_label=raw.get("y_axis_label") or "", show_legend=raw.get("show_legend", True))
        try:
            return self._build(result, spec)
        except ValueError:
            if requested_type != "auto" or spec.chart_type in {"line", "bar"}:
                raise
            safe = ChartSpec.model_validate({**spec.model_dump(), "chart_type": self._select_chart_type("auto", series)})
            return self._build(result, safe)

    def edit(self, result: dict[str, Any], current_output: dict[str, Any], instruction: str) -> dict[str, Any]:
        """Interpret a natural-language edit as one validated operation on saved chart state."""
        if not self.ncp_client or not self.ncp_client.configured:
            raise ValueError("자연어 그래프 수정에는 NCP_CLOVA_API_KEY가 필요합니다.")
        current = ChartSpec.model_validate(current_output["chartState"])
        labels = [s["label"] for s in self._series((result.get("execution") or {}).get("rows") or [])]
        system = (
            "너는 그래프 수정 명령 분류기다. Python 코드를 만들거나 통계 숫자를 계산하지 마라. "
            "JSON 객체 하나만 출력하라. 필드: operation, kind, value, start, end, label, x_axis_label, y_axis_label. "
            "operation은 set_title,set_subtitle,set_axis_labels,set_chart_type,set_layout,set_legend,set_line_width,"
            "highlight_period,highlight_series,add_annotation,add_reference_line,hide_series,filter_period,set_top_n,set_transform,set_series_chart_type,set_secondary_axis 중 하나. "
            "set_series_chart_type은 label=계열 이름, value=line/bar/area. set_secondary_axis는 value=계열 이름. "
            "hide_series,filter_period,set_top_n,set_transform은 DATA_EDIT이고 나머지는 STYLE_EDIT이다. "
            "명시되지 않은 값은 추측하지 마라."
        )
        user = json.dumps({"instruction": instruction, "chartState": current.model_dump(), "seriesLabels": labels}, ensure_ascii=False)
        text, _ = self.ncp_client.chat_main(system, user, max_tokens=320, thinking_effort="none")
        raw_command = self.ncp_client._json_object(text)
        operation = str(raw_command.get("operation") or "").strip().lower()
        raw_command["operation"] = operation
        data_operations = {"hide_series", "filter_period", "set_top_n", "set_transform"}
        raw_command["kind"] = "DATA_EDIT" if operation in data_operations else "STYLE_EDIT"
        for field in ("start", "end"):
            if raw_command.get(field) is not None:
                raw_command[field] = str(raw_command[field])
        command = ChartEditCommand.model_validate(raw_command)
        updates: dict[str, Any] = {}
        value = command.value
        if command.operation == "set_title": updates["title"] = str(value or "")
        elif command.operation == "set_subtitle": updates["subtitle"] = str(value or "")
        elif command.operation == "set_axis_labels": updates.update(x_axis_label=command.x_axis_label or current.x_axis_label, y_axis_label=command.y_axis_label or current.y_axis_label)
        elif command.operation == "set_chart_type": updates["chart_type"] = value
        elif command.operation == "set_layout": updates["layout"] = value
        elif command.operation == "set_legend":
            if isinstance(value, bool): updates["show_legend"] = value
            else: updates["legend_position"] = value
        elif command.operation == "set_line_width": updates["line_width"] = value
        elif command.operation == "highlight_period": updates["highlights"] = [*current.highlights, Highlight(start=command.start or "", end=command.end or "", label=command.label or "")]
        elif command.operation == "highlight_series":
            if value not in labels: raise ValueError("선택한 계열이 조회 결과에 없습니다.")
            updates["highlighted_series"] = str(value)
        elif command.operation == "add_annotation": updates["annotations"] = [*current.annotations, Annotation(period=command.start or "", text=str(value or ""))]
        elif command.operation == "add_reference_line": updates["reference_lines"] = [*current.reference_lines, float(value)]
        elif command.operation == "hide_series":
            if value not in labels: raise ValueError("제외할 계열이 조회 결과에 없습니다.")
            updates["hidden_series"] = [*current.hidden_series, str(value)]
        elif command.operation == "filter_period": updates.update(period_start=command.start, period_end=command.end)
        elif command.operation == "set_top_n": updates["top_n"] = value
        elif command.operation == "set_transform": updates["transform"] = value
        elif command.operation == "set_series_chart_type":
            if command.label not in labels: raise ValueError("선택한 계열이 조회 결과에 없습니다.")
            updates["series_chart_types"] = {**current.series_chart_types, command.label: value}
        elif command.operation == "set_secondary_axis":
            if value not in labels: raise ValueError("보조축에 표시할 계열이 조회 결과에 없습니다.")
            updates["secondary_axis_series"] = list(dict.fromkeys([*current.secondary_axis_series, str(value)]))
            updates["layout"] = "combined"
        edited_spec = current.model_copy(update=updates)
        edited_spec = ChartSpec.model_validate(edited_spec.model_dump())
        edited = self._build(result, edited_spec)
        edited["lastEdit"] = command.model_dump()
        edited["editHistory"] = [*(current_output.get("editHistory") or []), command.model_dump()]
        return edited

    def inspect(self, result: dict[str, Any]) -> dict[str, Any]:
        """Describe available output choices without producing a render spec."""
        series = self._series((result.get("execution") or {}).get("rows") or [])
        return {
            "seriesCount": len(series),
            "pointCount": sum(len(item.get("points") or []) for item in series),
            "recommendedChartType": self._select_chart_type("auto", series),
            "supportedChartTypes": sorted(SUPPORTED_CHART_TYPES - {"auto"}),
            "supportedLayouts": sorted(SUPPORTED_LAYOUTS),
            "editableFields": ["title", "show_legend", "x_axis_label", "y_axis_label"],
        }
