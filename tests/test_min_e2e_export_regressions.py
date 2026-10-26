"""Compare actual document text with the browser figure's time-axis title."""
import io
import xml.etree.ElementTree as ET
import pytest
from pypdf import PdfReader
from output_agent import OutputAgent
from output_schema import ChartSpec
from advanced_chart_spec import ReportOptions
from report_export import render_file
from plotly_renderer import render_plotly
from test_advanced_reports import fixture


@pytest.mark.parametrize('fmt',['pdf','svg'])
@pytest.mark.parametrize('label',['','관측월'])
def test_document_keeps_default_or_explicit_time_axis_title(fmt,label):
    data=fixture();series=OutputAgent()._series(data['execution']['rows'])
    spec=ChartSpec(chart_type='line',x_axis_label=label,report=ReportOptions(svg_text_mode='text'))
    wanted=render_plotly(series,spec)['layout']['xaxis']['title']['text']
    content=render_file(series,spec,data,fmt)
    text='\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(content)).pages) if fmt=='pdf' else ''.join(ET.fromstring(content).itertext())
    assert wanted in text
