import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from core import expand_queries, extract_series


def sample_case():
    return {
        'id': 'T-01', 'source_id': 'PUB1', 'frequency': 'M',
        'expected_parameters': [{'table_id': 'T', 'item_id': 'I', 'frequency': 'M',
                                 'classifications': {'objL1': 'C'}}],
        'expected': [{'table_id': 'T', 'values': ['series']}],
        'queries': {'업무형': {'그래프': '업무 그래프', '표': '업무 표'},
                    '정확형': {'그래프': '정확 그래프', '표': '정확 표'}},
    }


def test_expand_queries_preserves_all_four_exact_prompts_and_source_mapping():
    cases = expand_queries([sample_case()])

    assert len(cases) == 4
    assert [case['input']['query'] for case in cases] == [
        '업무 그래프', '업무 표', '정확 그래프', '정확 표']
    assert {case['source_id'] for case in cases} == {'PUB1'}
    assert {case['expected']['output_kind'] for case in cases} == {'graph', 'table'}


def test_extract_series_reads_only_requested_identity_periods_and_unit(tmp_path):
    source = tmp_path / 'T.csv'
    source.write_text(
        'TBL_ID,ITM_ID,PRD_SE,PRD_DE,DT,C1,UNIT_NM,C1_NM\n'
        'T,I,M,199901,0.50,C,%,Series\n'
        'T,I,M,202301,1.25,C,%,Series\n'
        'T,I,M,202302,2.50,C,%,Series\n'
        'T,I,M,202303,999,OTHER,%,Wrong classification\n', encoding='utf-8')

    series = extract_series(source, {
        'table_id': 'T', 'item_id': 'I', 'frequency': 'M',
        'classifications': {'objL1': 'C'}, 'periods': ['202301', '202302']})

    assert series['unit'] == '%'
    assert series['points'] == [
        {'period': '202301', 'value': '1.25'}, {'period': '202302', 'value': '2.50'}]


@pytest.mark.parametrize('rows, message', [
    ('T,I,M,202301,1,C,%,S\nT,I,M,202301,2,C,%,S\n', 'duplicate'),
    ('T,I,M,202301,1,C,,S\n', 'unit'),
    ('T,I,M,202301,NaN,C,%,S\n', 'finite'),
])
def test_extract_series_rejects_duplicate_missing_unit_and_nonfinite_values(tmp_path, rows, message):
    source = tmp_path / 'T.csv'
    source.write_text('TBL_ID,ITM_ID,PRD_SE,PRD_DE,DT,C1,UNIT_NM,C1_NM\n' + rows, encoding='utf-8')

    with pytest.raises(ValueError, match=message):
        extract_series(source, {'table_id': 'T', 'item_id': 'I', 'frequency': 'M',
                                'classifications': {'objL1': 'C'}, 'periods': ['202301']})


def test_extract_series_uses_item_id_for_metadata_unit_fallback(tmp_path):
    source = tmp_path / 'T.csv'
    source.write_text('TBL_ID,ITM_ID,PRD_SE,PRD_DE,DT,C1,UNIT_NM,C1_NM\n'
                      'T,I,M,202301,1.25,C,,Series\n', encoding='utf-8')

    series = extract_series(source, {'table_id': 'T', 'item_id': 'I', 'frequency': 'M',
                                     'classifications': {'objL1': 'C'}, 'periods': ['202301']},
                            {'I': '%'})

    assert series['unit'] == '%'
