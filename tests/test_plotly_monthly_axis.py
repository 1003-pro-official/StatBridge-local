from output_schema import ChartSpec
from plotly_renderer import render_plotly


def test_monthly_line_places_each_month_on_distinct_category():
    months = [f"2025{month:02d}" for month in range(1, 13)]
    series = [{
        "label": "경상수지", "unit": "백만달러", "frequency": "M", "color": "#4865ff",
        "points": [{"date": month, "value": 8000 + index * 100} for index, month in enumerate(months)],
    }]

    figure = render_plotly(series, ChartSpec(chart_type="line"))

    assert figure["data"][0]["x"] == months
    assert figure["layout"]["xaxis"]["type"] == "category"
    assert figure["layout"]["xaxis"]["categoryarray"] == months
    assert figure["layout"]["xaxis"]["ticktext"][0] == "2025-01"
    assert figure["layout"]["xaxis"]["ticktext"][-1] == "2025-12"
