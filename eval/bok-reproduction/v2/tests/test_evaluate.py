import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from evaluate import evaluate


def test_evaluator_requires_numeric_match_and_visible_product_ui():
    series = [{'table_id': 'T', 'item_id': 'I', 'classifications': {}, 'frequency': 'M',
               'unit': '%', 'points': [{'period': '202501', 'value': '1.25'}]}]
    observed = {'series': series, 'ui_output_visible': True, 'output_kind': 'graph'}

    assert evaluate(series, observed)['passed'] is True
    observed['ui_output_visible'] = False
    assert evaluate(series, observed)['passed'] is False


def test_table_evaluation_requires_xlsx_download():
    series = [{'table_id': 'T', 'item_id': 'I', 'classifications': {}, 'frequency': 'M',
               'unit': '%', 'points': [{'period': '202501', 'value': '1.25'}]}]
    observed = {'series': series, 'ui_output_visible': True, 'output_kind': 'table'}

    report = evaluate(series, observed)

    assert report['passed'] is False
    assert 'table XLSX export was not observed' in report['reasons']


def test_table_evaluation_compares_exported_values_and_periods():
    series = [{'table_id': 'T', 'item_id': 'I', 'classifications': {}, 'frequency': 'M',
               'unit': '%', 'points': [{'period': '202501', 'value': '1.25'}]}]
    observed = {'series': series, 'ui_output_visible': True, 'output_kind': 'table',
                'xlsx_downloaded': True,
                'xlsx_cells': {'A1': {'text': '지표'}, 'B1': {'text': '2025-01'},
                               'A2': {'text': '계열 (%)'}, 'B2': {'value': '1.25'}}}

    assert evaluate(series, observed)['passed'] is True
    observed['xlsx_cells']['B2']['value'] = '9.99'
    assert evaluate(series, observed)['passed'] is False


def test_table_evaluation_rejects_values_assigned_to_the_wrong_period():
    series = [{'table_id': 'T', 'item_id': 'I', 'classifications': {}, 'frequency': 'M',
               'unit': '%', 'points': [{'period': '202501', 'value': '1.25'},
                                       {'period': '202502', 'value': '2.5'}]}]
    observed = {'series': series, 'ui_output_visible': True, 'output_kind': 'table',
                'xlsx_downloaded': True,
                'xlsx_cells': {'B1': {'text': '2025-01'}, 'C1': {'text': '2025-02'},
                               'A2': {'text': '계열 (%)'}, 'B2': {'value': '2.5'},
                               'C2': {'value': '1.25'}}}

    report = evaluate(series, observed)

    assert report['passed'] is False
    assert any('period' in reason for reason in report['reasons'])


def test_table_evaluation_accepts_multiple_series_under_shared_period_headers():
    expected = [
        {'table_id': 'T', 'item_id': item, 'classifications': {}, 'frequency': 'M',
         'unit': '%', 'points': [{'period': '202501', 'value': value}]}
        for item, value in [('I1', '1.25'), ('I2', '2.5')]
    ]
    observed = {'series': expected, 'ui_output_visible': True, 'output_kind': 'table',
                'xlsx_downloaded': True,
                'xlsx_cells': {'B1': {'text': '2025-01'}, 'A2': {'text': 'series 1'},
                               'A3': {'text': 'series 2'}, 'B2': {'value': '1.25'},
                               'B3': {'value': '2.5'}}}

    assert evaluate(expected, observed)['passed'] is True


def test_compare_rejects_duplicate_series_identity():
    from evaluate import compare

    series = {'table_id': 'T', 'item_id': 'I', 'classifications': {}, 'frequency': 'M',
              'unit': '%', 'points': [{'period': '202501', 'value': '1'}]}

    assert compare([series], [series, series])['passed'] is False


def test_compare_rejects_duplicate_observation_period():
    from evaluate import compare

    series = {'table_id': 'T', 'item_id': 'I', 'classifications': {}, 'frequency': 'M',
              'unit': '%', 'points': [{'period': '202501', 'value': '1'}]}
    observed = {**series, 'points': [{'period': '202501', 'value': '999'},
                                    {'period': '202501', 'value': '1'}]}

    assert compare([series], [observed])['passed'] is False


def test_evaluator_selects_case_oracle_from_bundle_mapping():
    from evaluate import select_oracle

    assert select_oracle({'case-a': [{'item_id': 'I'}]}, 'case-a') == [{'item_id': 'I'}]


def test_profile_pins_chart_model_and_single_repeat():
    from core import apply_profile

    env = {'OPENAI_CHART_MODEL': 'wrong-model', 'STATBRIDGE_OUTPUT_PROVIDER': 'ncp'}

    assert apply_profile(env, {'model': 'gpt-5.4', 'repeats': 1}) == 'gpt-5.4'
    assert env['OPENAI_CHART_MODEL'] == 'gpt-5.4'
    assert env['STATBRIDGE_OUTPUT_PROVIDER'] == 'openai'


def test_xlsx_parser_preserves_cell_coordinates(tmp_path):
    import zipfile
    from core import read_xlsx_cells

    workbook_path = tmp_path / 'output.xlsx'
    with zipfile.ZipFile(workbook_path, 'w') as workbook:
        workbook.writestr('xl/worksheets/sheet1.xml',
                          '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                          '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>2025-01</t></is></c>'
                          '<c r="B1"><v>1.25</v></c></row></sheetData></worksheet>')

    assert read_xlsx_cells(workbook_path) == {'A1': {'text': '2025-01'}, 'B1': {'value': '1.25'}}
