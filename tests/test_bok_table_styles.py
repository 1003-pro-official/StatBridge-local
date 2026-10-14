"""User-supplied style pack, synthetic observations; no invented totals or forecasts."""
import copy
import io
import zipfile
import xml.etree.ElementTree as ET

import pytest
from report_table import TableOptions, build_table, render_table_file


def observations():
    return [{'label': name, 'unit': '%', 'frequency': 'M', 'points': [
        {'date': '202412', 'value': 1.234}, {'date': '202501', 'value': 0},
        {'date': '202502', 'value': -2.5}]} for name in ['항목', '조회된 소계']]


@pytest.mark.parametrize('template', [f'BOK-T0{i}' for i in range(1, 7)])
def test_all_templates_preserve_data_and_export(template):
    source = observations(); original = copy.deepcopy(source)
    doc = build_table(source, TableOptions(template=template, emphasized_labels=['조회된 소계'], note='관측값 비교'))
    assert source == original
    assert doc['sections'][0]['rows'][1][1:] == [1.234, 0, -2.5]
    assert doc['sections'][0]['emphasizedRows'] == [1]
    csv = render_table_file(doc, 'csv').decode('utf-8-sig')
    assert '1.2,0.0,-2.5' in csv and '관측값 비교' in csv
    with zipfile.ZipFile(io.BytesIO(render_table_file(doc, 'xlsx'))) as archive:
        sheet = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
        ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        assert [float(x.text) for x in sheet.findall('.//s:v', ns)] == [1.234, 0, -2.5] * 2
        assert bool(sheet.findall('.//s:mergeCell', ns)) == (template in {'BOK-T02', 'BOK-T03'})


def test_grouping_respects_actual_dates_and_transpose():
    doc = build_table(observations(), TableOptions(template='BOK-T02'))
    assert doc['sections'][0]['headerGroups'] == [
        {'label': '2024년', 'start': 1, 'span': 1}, {'label': '2025년', 'start': 2, 'span': 2}]
    doc = build_table(observations(), TableOptions(template='BOK-T02', orientation='periods'))
    assert doc['sections'][0]['headerGroups'] == []
    assert doc['sections'][0]['emphasizedRows'] == []
    assert TableOptions.model_validate({'decimals': 2}).template == 'default'


def test_edit_contract_validates_labels_and_records_readable_description():
    from output_schema import ChartSpec, ChartEditCommand
    from research_chart_editing import apply_research_edit
    from edit_description import describe_edit
    spec = ChartSpec(title='관측값')
    command = ChartEditCommand(operation='set_table', kind='STYLE_EDIT', params={'patch': {'template': 'BOK-T05', 'emphasized_labels': ['조회된 소계']}})
    edited = apply_research_edit(spec, command, ['항목', '조회된 소계'])
    assert edited.report_table.template == 'BOK-T05'
    assert '항목 · 소계 강조표' in describe_edit(command)
    with pytest.raises(ValueError, match='현재 조회된 지표'):
        apply_research_edit(spec, command, ['항목'])


@pytest.mark.parametrize('template', ['BOK-T02', 'BOK-T04', 'BOK-T05', 'BOK-T06'])
def test_visual_exports(template):
    doc = build_table(observations(), TableOptions(template=template, emphasized_labels=['조회된 소계']))
    assert render_table_file(doc, 'png').startswith(b'\x89PNG')
    assert render_table_file(doc, 'pdf').startswith(b'%PDF')
