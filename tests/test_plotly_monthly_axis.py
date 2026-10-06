from output_schema import ChartSpec
from plotly_renderer import render_plotly


def test_monthly_line_places_each_month_on_distinct_date():
    months = [f"2025{month:02d}" for month in range(1, 13)]
    series = [{
        "label": "경상수지", "unit": "백만달러", "frequency": "M", "color": "#4865ff",
        "points": [{"date": month, "value": 8000 + index * 100} for index, month in enumerate(months)],
    }]

    figure = render_plotly(series, ChartSpec(chart_type="line"))

    assert figure["data"][0]["x"] == [f"2025-{month:02d}-01" for month in range(1, 13)]
    assert figure["layout"]["xaxis"]["type"] == "date"
    assert figure["layout"]["xaxis"]["tickvals"][0] == "2025-01-01"
    assert figure["layout"]["xaxis"]["tickvals"][-1] == "2025-12-01"
    assert figure["layout"]["xaxis"]["ticktext"][0] == "2025-01"
    assert figure["layout"]["xaxis"]["ticktext"][-1] == "2025-12"


def test_quarterly_ids_are_not_converted_to_months():
    series = [{"label": "분기", "unit": "%", "frequency": "Q", "color": "#4865ff",
               "points": [{"date": "202501", "value": 1}, {"date": "202502", "value": 2}]}]
    figure = render_plotly(series, ChartSpec(chart_type="line"))
    assert figure["data"][0]["x"] == ["202501", "202502"]


def test_monthly_axis_preserves_user_tick_spacing_and_rotation():
    series = [{"label": "월", "unit": "%", "frequency": "M", "color": "#4865ff",
               "points": [{"date": f"2025{month:02d}", "value": month} for month in range(1, 7)]}]
    figure = render_plotly(series, ChartSpec(chart_type="line", axes={"x": {"tick_step": 2, "tick_angle": 30}}))
    assert figure["layout"]["xaxis"]["tickvals"][:3] == ["2025-01-01", "2025-03-01", "2025-05-01"]
    assert figure["layout"]["xaxis"]["tickangle"] == 30
