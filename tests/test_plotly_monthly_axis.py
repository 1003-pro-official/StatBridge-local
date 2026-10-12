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


def test_quarterly_ids_are_not_converted_to_months():
    series = [{"label": "분기", "unit": "%", "frequency": "Q", "color": "#4865ff",
               "points": [{"date": "202501", "value": 1}, {"date": "202502", "value": 2}]}]
    figure = render_plotly(series, ChartSpec(chart_type="line"))
    assert figure["data"][0]["x"] == ["202501", "202502"]


def test_monthly_axis_preserves_user_tick_spacing_and_rotation():
    series = [{"label": "월", "unit": "%", "frequency": "M", "color": "#4865ff",
               "points": [{"date": f"2025{month:02d}", "value": month} for month in range(1, 7)]}]
    figure = render_plotly(series, ChartSpec(chart_type="line", axes={"x": {"tick_step": 2, "tick_angle": 30}}))
    assert figure["layout"]["xaxis"]["tickvals"][:3] == ["202501", "202503", "202505"]
    assert figure["layout"]["xaxis"]["ticktext"][:3] == ["2025년 1월", "2025년 3월", "2025년 5월"]
    assert figure["layout"]["xaxis"]["tickangle"] == 30
