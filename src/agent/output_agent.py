from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import json
import math

from output_schema import ChartEditCommand, ChartSpec, Highlight, Annotation
from plotly_renderer import render_plotly
from chart_availability import inspect_charts, combined_layout_reason


SUPPORTED_CHART_TYPES = {"auto", "line", "bar", "stacked_bar", "area", "scatter", "bubble", "pie", "donut", "histogram", "box", "heatmap", "treemap", "waterfall"}
SUPPORTED_LAYOUTS = {"combined", "separate", "horizontal", "grid"}


def edit_change_description(command: ChartEditCommand) -> str:
    names = {"set_title":"제목", "set_subtitle":"부제목", "set_axis_labels":"축 이름",
        "set_axis_style":"축 표시", "set_legend":"범례", "set_presentation":"글꼴·배치",
        "set_segment_style":"선택 구간 스타일", "set_point_style":"선택 관측점 스타일",
        "set_series_color":"계열 색상", "set_series_dash":"선 모양", "set_series_style":"계열 스타일",
        "set_line_width":"선 두께", "highlight_period":"기간 강조", "filter_period":"표시 기간",
        "set_chart_type":"그래프 종류", "set_layout":"그래프 배치", "rename_series":"계열 표시 이름",
        "set_transform":"표시값 변환", "hide_series":"계열 숨기기", "show_series":"계열 다시 표시",
        "add_note":"메모 추가", "add_annotation":"주석 추가", "reset_styles":"스타일 초기화"}
    fields = {"tick_step":"눈금 간격", "tick_angle":"글자 각도", "color":"색상", "dash":"선 모양",
        "width":"선 두께", "marker_size":"점 크기", "show_grid":"격자 표시", "minimum":"최솟값",
        "maximum":"최댓값", "title":"축 제목", "font_size":"글자 크기", "title_size":"제목 크기"}
    detail = ", ".join(f"{fields.get(k,k)} {v}" for k,v in command.params.items()) if command.params else str(
        command.value if command.value is not None else command.x_axis_label or command.y_axis_label or "")
    label = {"x":"가로축", "y":"세로축", "y2":"보조 세로축"}.get(command.label, command.label) if command.operation == "set_axis_style" else command.label
    period = f" · {command.start} ~ {command.end or command.start}" if command.start else ""
    return f"{names.get(command.operation, '그래프 설정 변경')}{' · ' + label if label else ''}{period}: {detail}"


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
            if not math.isfinite(value):
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
            "label": s["label"], "unit": s["unit"], "frequency": s.get("frequency"), "pointCount": len(s["points"]),
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
            "frequency=Q의 YYYY01~YYYY04는 1~4분기이며 월이 아니다. frequency=M일 때만 YYYYMM을 월로 설명한다. "
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
            "frequency=Q의 YYYY01~YYYY04는 1~4분기이며 월이 아니다. 실제 주기를 제목과 부제에 반영한다. "
            "통계 수치나 데이터 계열을 새로 만들지 마라."
            "series_chart_types의 키와 secondary_axis_series 값은 제공된 series.label을 띄어쓰기와 구분 기호까지 그대로 복사하라. "
            "주택담보대출처럼 줄인 지표명으로 바꾸지 마라. 원·도넛 등에는 계열별 선/막대 유형이나 보조축을 넣지 마라."
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
        if spec.series_order:
            shaped.sort(key=lambda s: spec.series_order.index(s["label"]))
        return shaped

    def _build(self, result: dict[str, Any], spec: ChartSpec, generate_explanation: bool = True) -> dict[str, Any]:
        validation = result.get("request_validation")
        if validation is not None and validation.get("valid") is not True:
            raise ValueError("요청과 통계표가 일치하지 않아 그래프 출력을 중단했습니다.")
        plans = result.get("api_plans") or ([result["api_plan"]] if result.get("api_plan") else [])
        planned_ids = {str(p["table_id"]) for p in plans}
        if validation and set(str(t) for t in validation.get("table_ids", [])) != planned_ids:
            raise ValueError("검증 이후 출력 통계표가 변경되었습니다.")
        for row in (result.get("execution") or {}).get("rows") or []:
            source = row.get("_SOURCE_SERIES_ID") or row.get("TBL_ID")
            if planned_ids and source and str(source) not in planned_ids:
                raise ValueError("출력 자료의 출처가 요청한 통계표와 다릅니다.")
        source_series = self._series((result.get("execution") or {}).get("rows") or [])
        series = self._apply_data_edits(source_series, spec)
        series = [{**s, "color": spec.series_colors.get(s["label"], s["color"])} for s in series]
        labels = {s["label"] for s in source_series}
        if any(label not in labels for label in [*spec.series_chart_types, *spec.secondary_axis_series, *spec.series_colors, *spec.series_dashes, *spec.series_styles, *spec.display_names, *(r.label for r in spec.range_styles)]):
            raise ValueError("그래프 명세에 조회되지 않은 계열이 포함되어 있습니다.")
        from research_chart_editing import validate_research_spec
        validate_research_spec(series, spec)
        if spec.secondary_axis_series and spec.chart_type not in {"line", "bar", "stacked_bar", "area"}:
            raise ValueError("보조축은 선·막대·영역 그래프에서만 사용할 수 있습니다.")
        mixed_units = len({s["unit"] for s in series}) > 1
        mixed_frequency = len({s["frequency"] for s in series if s["frequency"]}) > 1
        if (mixed_frequency or (mixed_units and not spec.secondary_axis_series)) and spec.layout == "combined" and spec.chart_type not in {"scatter", "bubble"}:
            raise ValueError(combined_layout_reason(series))
        summary = self._summary(series)
        figure = render_plotly(series, spec)
        explanation = self._explain(series, spec, summary) if generate_explanation else {"text": summary, "source": "rules", "method": "기존 조회 자료로 편집 상태 복원"}
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
                    "supportedChartTypes": inspect_charts(series)[0],
                    "supportedLayouts": sorted(SUPPORTED_LAYOUTS),
                },
            },
        }

    def prepare(self, result: dict[str, Any], request: dict[str, Any] | None = None) -> dict[str, Any]:
        raw = request or {}
        series = self._series((result.get("execution") or {}).get("rows") or [])
        proposed = self._propose_spec(series, raw)
        # Initial output is neutral. Background highlights are user edits,
        # not decorations that the presentation model may invent.
        proposed.pop("highlights", None)
        labels={s['label'] for s in series}
        references=[]
        mapping=proposed.get('series_chart_types')
        if isinstance(mapping,dict):references.extend(mapping)
        axes=proposed.get('secondary_axis_series')
        if isinstance(axes,list):references.extend(axes)
        unknown=[label for label in references if not isinstance(label,str) or label not in labels]
        rejected_proposal=bool(unknown)
        if rejected_proposal:
            # Discard untrusted styling, never remap a guessed name to another series.
            # User-selected type/layout and original observations remain authoritative.
            proposed={}
        requested_type = str(raw.get("chart_type") or "auto")
        if requested_type not in SUPPORTED_CHART_TYPES:
            raise ValueError("지원하지 않는 그래프 종류입니다.")
        if requested_type != "auto":
            proposed["chart_type"] = requested_type
            # A model's per-series suggestion must not override the explicit
            # chart type selected by the user. Mixed types remain available via
            # explicit follow-up edits and automatic output planning.
            proposed.pop("series_chart_types", None)
        elif proposed.get("chart_type") not in SUPPORTED_CHART_TYPES - {"auto"}:
            proposed["chart_type"] = self._select_chart_type("auto", series)
        if proposed.get('chart_type') not in {'line','bar','stacked_bar','area'}:
            proposed.pop('series_chart_types',None)
            proposed.pop('secondary_axis_series',None)
        elif raw.get('layout') and raw['layout']!='combined':
            proposed.pop('secondary_axis_series',None)
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
            output=self._build(result, spec)
        except ValueError:
            if requested_type != "auto" or spec.chart_type in {"line", "bar"}:
                raise
            safe = ChartSpec.model_validate({**spec.model_dump(), "chart_type": self._select_chart_type("auto", series)})
            output=self._build(result, safe)
        if rejected_proposal:
            output['warnings']=['자동 스타일 제안의 항목명이 조회 결과와 달라 적용하지 않았습니다. 선택한 그래프 종류로 실제 조회된 계열을 표시했습니다.']
        return output

    def edit(self, result: dict[str, Any], current_output: dict[str, Any], instruction: str) -> dict[str, Any]:
        """Compatibility entry point; interpretation lives exclusively in ChartEditAgent."""
        from chart_edit_agent import ChartEditAgent, Hcx007EditModel
        from ncp_clova_client import NcpClovaClient
        if isinstance(self.ncp_client, NcpClovaClient):
            model = Hcx007EditModel(self.ncp_client)
        else:
            # Explicit injected clients are used by existing offline regression tests.
            client = self.ncp_client
            class InjectedModel:
                model_name = "injected-test-model"
                supports_images = False
                def interpret(self, system: str, context: dict[str, Any]) -> dict[str, Any]:
                    if not client or not client.configured:
                        raise ValueError("자연어 그래프 수정에는 NCP_CLOVA_API_KEY가 필요합니다.")
                    text, _ = client.chat_main(system, json.dumps(context, ensure_ascii=False), max_tokens=1400, thinking_effort="none")
                    return client._json_object(text)
            model = InjectedModel()
        return ChartEditAgent(model, self).edit(result, current_output, instruction)

    def apply_edits(self, result: dict[str, Any], current_output: dict[str, Any], commands: list[ChartEditCommand]) -> dict[str, Any]:
        """Apply a validated batch atomically, then render exactly once."""
        labels = [s["label"] for s in self._series((result.get("execution") or {}).get("rows") or [])]
        spec = ChartSpec.model_validate(current_output["chartState"])
        before = spec.model_dump()
        effective = []
        for command in commands:
            changed = self._apply_edit_spec(spec, command, labels)
            if changed.model_dump() != spec.model_dump():
                effective.append(command)
            spec = changed
        if spec.model_dump() == before:
            raise ValueError("요청한 설정이 이미 적용되어 있어 변경된 내용이 없습니다. 다른 수정 내용을 입력해 주세요.")
        edited = self._build(result, spec)
        if edited.get("plotlyFigure") == current_output.get("plotlyFigure"):
            raise ValueError("표시되는 그래프가 바뀌지 않았습니다. 수정할 요소와 설정을 구체적으로 입력해 주세요.")
        edited["editChanges"] = [edit_change_description(c) for c in effective]
        if any(c.operation == 'set_chart_type' for c in effective) and (
                before['range_styles'] or before['series_styles'] or before['series_chart_types'] or before['guides']):
            edited['editChanges'].append('그래프 종류를 변경해 이전 그래프 전용 부분 스타일·혼합 종류를 정리했습니다. 원자료와 표시 기간은 유지됩니다.')
        edited["lastEdit"] = effective[-1].model_dump()
        edited["editHistory"] = [*(current_output.get("editHistory") or []), *(c.model_dump() for c in effective)][-120:]
        return edited

    @staticmethod
    def _apply_edit_spec(current: ChartSpec, command: ChartEditCommand, labels: list[str]) -> ChartSpec:
        from research_chart_editing import apply_research_edit
        extended = apply_research_edit(current, command, labels)
        if extended is not None:
            return extended
        updates: dict[str, Any] = {}
        if command.params and (command.operation != "highlight_period" or set(command.params) - {"color", "opacity"}):
            raise ValueError(f"{command.operation} 명령에 적용할 수 없는 설정이 있습니다: {', '.join(command.params)}. 설정을 확인해 주세요.")
        value = command.value
        if command.operation == "remove_annotation":
            text=str(value or "")
            if not text: raise ValueError("삭제할 주석 텍스트를 지정해 주세요.")
            updates.update(annotations=[a for a in current.annotations if a.text != text],
                notes=[n for n in current.notes if n.text != text],
                highlights=[h.model_copy(update={"label":""}) if h.label == text else h for h in current.highlights])
        elif command.operation == "set_title": updates["title"] = str(value or "")
        elif command.operation == "set_subtitle": updates["subtitle"] = str(value or "")
        elif command.operation == "set_axis_labels":
            if command.x_axis_label is None and command.y_axis_label is None:
                raise ValueError("축 이름 수정 명령에 새 축 이름이 없습니다. 눈금 수정은 축 표시 명령으로 요청해 주세요.")
            updates.update(x_axis_label=current.x_axis_label if command.x_axis_label is None else command.x_axis_label,
                           y_axis_label=current.y_axis_label if command.y_axis_label is None else command.y_axis_label)
        elif command.operation == "set_chart_type":
            # A global kind change must not retain per-series overrides from
            # the previous mixed chart, otherwise "bar" can still draw lines.
            updates.update(chart_type=value, series_chart_types={})
            if value != current.chart_type:
                updates.update(range_styles=[], series_styles={
                    label: style.model_copy(update={key:None for key in style.model_dump(exclude_none=True) if key not in {'color','opacity'}})
                    for label,style in current.series_styles.items()
                    if value != 'heatmap' and (value not in {'scatter','bubble'} or label == labels[0])})
                if value not in {'bar','stacked_bar'}:
                    updates['presentation'] = current.presentation.model_copy(update={'bar_orientation':'vertical'})
                if value not in {'line','bar','stacked_bar','area'}:
                    updates.update(guides=[], notes=[note for note in current.notes if not note.label])
            if value not in {"line", "bar", "stacked_bar", "area"}:
                updates["secondary_axis_series"] = []
        elif command.operation == "set_layout": updates["layout"] = value
        elif command.operation == "set_legend":
            if isinstance(value, bool): updates["show_legend"] = value
            else: updates["legend_position"] = value
        elif command.operation == "set_line_width": updates["line_width"] = value
        elif command.operation == "highlight_period": updates["highlights"] = [*current.highlights, Highlight(start=command.start or "", end=command.end or "", label=command.label or "", **{k:v for k,v in command.params.items() if k in {"color","opacity"}})]
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
        elif command.operation in {"set_series_color", "set_series_dash"}:
            if command.label not in labels:
                raise ValueError("수정할 계열이 조회 결과에 없습니다.")
            field = "series_colors" if command.operation == "set_series_color" else "series_dashes"
            updates[field] = {**getattr(current, field), command.label: value}
        edited_spec = current.model_copy(update=updates)
        return ChartSpec.model_validate(edited_spec.model_dump())

    def inspect(self, result: dict[str, Any]) -> dict[str, Any]:
        """Describe available output choices without producing a render spec."""
        series = self._series((result.get("execution") or {}).get("rows") or [])
        allowed, unavailable = inspect_charts(series)
        return {
            "seriesCount": len(series),
            "pointCount": sum(len(item.get("points") or []) for item in series),
            "recommendedChartType": self._select_chart_type("auto", series),
            "supportedChartTypes": allowed,
            "unavailableChartTypes": unavailable,
            "combinedLayoutReason": combined_layout_reason(series),
            "supportedLayouts": sorted(SUPPORTED_LAYOUTS),
            "editableFields": ["title", "show_legend", "x_axis_label", "y_axis_label"],
        }
