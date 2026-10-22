"""Score captured UI output against private v2 oracles."""
import argparse
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from collections import defaultdict


def compare(expected, observed, tolerance=Decimal('0.000001')):
    report = {'passed': False, 'expected_cells': 0, 'matched_cells': 0, 'reasons': []}
    key = lambda row: (row.get('table_id'), row.get('item_id'),
                       json.dumps(row.get('classifications', {}), sort_keys=True), row.get('frequency'))
    try:
        gold = {key(series): series for series in expected}
        actual = {key(series): series for series in observed}
        if len(gold)!=len(expected) or len(actual)!=len(observed):
            raise ValueError('duplicate series identity')
        if not gold or gold.keys() != actual.keys():
            raise ValueError('series identity mismatch')
        for identity, series in gold.items():
            other = actual[identity]
            if series.get('unit') != other.get('unit') or not series.get('unit'):
                raise ValueError('unit mismatch')
            points = {str(p['period']): p.get('value') for p in series['points']}
            values = {str(p['period']): p.get('value') for p in other['points']}
            if len(points)!=len(series['points']) or len(values)!=len(other['points']):
                raise ValueError('duplicate observation period')
            if points.keys() != values.keys():
                raise ValueError('period mismatch')
            report['expected_cells'] += len(points)
            for period, value in points.items():
                if value is None and values[period] is None:
                    report['matched_cells'] += 1
                elif value is not None and values[period] is not None and abs(Decimal(str(value))-Decimal(str(values[period]))) <= tolerance:
                    report['matched_cells'] += 1
                else:
                    report['reasons'].append('numeric mismatch at ' + period)
        report['passed'] = report['expected_cells'] > 0 and not report['reasons']
    except (ValueError, KeyError, TypeError, InvalidOperation) as exc:
        report['reasons'].append(str(exc))
    return report


def evaluate(expected, observed):
    report = compare(expected, observed.get('series', []))
    if not observed.get('ui_output_visible'):
        report['reasons'].append('product UI output was not observed')
    if observed.get('output_kind') == 'table' and not observed.get('xlsx_downloaded'):
        report['reasons'].append('table XLSX export was not observed')
    if observed.get('output_kind') == 'table' and observed.get('xlsx_downloaded'):
        try:
            _check_xlsx_cells(expected, observed.get('xlsx_cells', {}))
        except (InvalidOperation, ValueError) as exc:
            report['reasons'].append(str(exc))
    report['passed'] = report['passed'] and not report['reasons']
    return report


def _cell_position(address):
    match = re.fullmatch(r'([A-Z]+)(\d+)', address)
    if not match:
        raise ValueError('invalid XLSX cell address: ' + address)
    column = 0
    for char in match[1]:
        column = column * 26 + ord(char) - ord('A') + 1
    return int(match[2]), column


def _period_matches(text, period, frequency):
    if frequency == 'M':
        match = re.fullmatch(r'\s*(\d{4})\s*[-./년]?\s*(0?[1-9]|1[0-2])\s*월?\s*', text)
        return bool(match and match[1] + match[2].zfill(2) == str(period))
    if frequency == 'Q':
        match = re.fullmatch(r'\s*(\d{4})\s*(?:년\s*)?(?:Q\s*([1-4])|([1-4])\s*분기)\s*', text, re.IGNORECASE)
        return bool(match and match[1] + 'Q' + (match[2] or match[3]) == str(period))
    return bool(re.fullmatch(r'\s*' + re.escape(str(period)) + r'\s*년?\s*', text))


def _check_xlsx_cells(expected, cells):
    grid = defaultdict(dict)
    periods = defaultdict(list)
    for address, cell in cells.items():
        row, column = _cell_position(address)
        if 'value' in cell:
            grid[row][column] = Decimal(str(cell['value']))
        if 'text' in cell:
            for series in expected:
                for point in series['points']:
                    if _period_matches(str(cell['text']), point['period'], series['frequency']):
                        periods[(series['frequency'], str(point['period']))].append((row, column))
    expected_by_period = defaultdict(list)
    for series in expected:
        for point in series['points']:
            expected_by_period[(series['frequency'], str(point['period']))].append(Decimal(str(point['value'])))
    if not expected_by_period:
        raise ValueError('oracle has no XLSX observations')
    if any(not periods[key] for key in expected_by_period):
        raise ValueError('XLSX period headers are missing or ambiguous')

    for axis in ('row', 'column'):
        passed = True
        for key, expected_values in expected_by_period.items():
            coordinates=set()
            for row,column in periods[key]:
                coordinates.update(((row,col) for col in grid[row] if col!=column)
                                   if axis=='row' else
                                   ((other_row,column) for other_row,values in grid.items()
                                    if column in values and other_row!=row))
            actual_values=[grid[row][column] for row,column in sorted(coordinates)]
            remaining = list(actual_values)
            for value in expected_values:
                match = next((index for index, actual in enumerate(remaining)
                              if abs(value - actual) <= Decimal('0.000001')), None)
                if match is None:
                    passed = False
                    break
                remaining.pop(match)
            if remaining:
                passed = False
            if not passed:
                break
        if passed:
            return
    raise ValueError('XLSX numeric values do not match the oracle by period')


def select_oracle(value, case_id=None):
    if isinstance(value, dict):
        if not case_id:
            raise ValueError('a case ID is required when the oracle is a case mapping')
        if case_id not in value:
            raise ValueError('oracle has no case ID: ' + case_id)
        return value[case_id]
    if case_id:
        raise ValueError('case ID can only select from an oracle case mapping')
    if not isinstance(value, list):
        raise ValueError('oracle must be a series list or case mapping')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('oracle')
    parser.add_argument('observed')
    parser.add_argument('--case-id')
    parser.add_argument('--output')
    args = parser.parse_args()
    oracle = select_oracle(json.loads(Path(args.oracle).read_text(encoding='utf-8')), args.case_id)
    report = evaluate(oracle,
                      json.loads(Path(args.observed).read_text(encoding='utf-8')))
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + '\n', encoding='utf-8')
    print(rendered)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
