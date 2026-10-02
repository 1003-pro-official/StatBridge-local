from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "agent"))

from output_agent import OutputAgent  # noqa: E402
from output_schema import ChartSpec  # noqa: E402
from plotly_renderer import render_plotly  # noqa: E402


class FakeHCX:
    configured = True
    settings = SimpleNamespace(main_model="HCX-007")

    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)

    def chat_main(self, *_args: object, **_kwargs: object) -> tuple[str, dict]:
        return next(self.responses), {}

    @staticmethod
    def _json_object(value: str) -> dict:
        return json.loads(value)


rows = [
    {"_SOURCE_SERIES_ID": source, "_SERIES_LABEL": "대출금리", "_FREQUENCY": "M",
     "UNIT_NM": "%", "PRD_DE": period, "DT": str(value)}
    for source, values in (("table-a", (4.2, 4.3)), ("table-b", (4.5, 4.6)))
    for period, value in zip(("202401", "202402"), values)
]
result = {"execution": {"status": "success", "rows": rows}}
client = FakeHCX([
    json.dumps({"chart_type": "line", "title": "금리 비교"}),
    "두 금리 모두 마지막 관측값이 첫 관측값보다 높습니다.",
    json.dumps({"operation": "set_title", "kind": "STYLE_EDIT", "value": "수정한 제목"}),
    "두 금리 모두 마지막 관측값이 첫 관측값보다 높습니다.",
    json.dumps({"operation": "filter_period", "kind": "DATA_EDIT", "start": "202402", "end": "202402"}),
    "2024년 2월 값만 표시합니다.",
])
agent = OutputAgent(client)
output = agent.prepare(result, {"chart_type": "auto", "natural_language": "두 금리 비교"})
assert len(output["visualization"]["series"]) == 2
assert output["chartState"]["title"] == "금리 비교"
assert output["explanation"]["source"] == "HCX-007"

edited = agent.edit(result, output, "제목을 수정한 제목으로 바꿔줘")
assert edited["chartState"]["title"] == "수정한 제목"
assert edited["visualization"]["series"] == output["visualization"]["series"]

filtered = agent.edit(result, edited, "2024년 2월만 보여줘")
assert all(len(item["points"]) == 1 for item in filtered["visualization"]["series"])
assert [item["kind"] for item in filtered["editHistory"]] == ["STYLE_EDIT", "DATA_EDIT"]

for chart_type in (
    "line", "bar", "stacked_bar", "area", "scatter", "bubble", "pie", "donut",
    "histogram", "box", "heatmap", "treemap", "waterfall",
):
    series = output["visualization"]["series"]
    if chart_type == "bubble":
        series = [*series, {**series[0], "label": "크기"}]
    if chart_type == "waterfall":
        series = series[:1]
    assert render_plotly(series, ChartSpec(chart_type=chart_type))["data"]

mixed = render_plotly([
    {**output["visualization"]["series"][0], "label": "수출액", "unit": "억 원"},
    {**output["visualization"]["series"][1], "label": "증가율", "unit": "%"},
], ChartSpec(chart_type="line", series_chart_types={"수출액": "bar", "증가율": "line"},
             secondary_axis_series=["증가율"]))
assert [trace["type"] for trace in mixed["data"]] == ["bar", "scatter"]
assert mixed["data"][1]["yaxis"] == "y2"

print("OUTPUT AGENT V2 OK: HCX spec/explanation, safe edits, 13 Plotly chart types and mixed axes")
