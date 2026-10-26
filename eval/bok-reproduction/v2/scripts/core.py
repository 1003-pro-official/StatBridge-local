"""Pure helpers for the BOK E2E v2 builder."""
import csv
import hashlib
import json
import math
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_jsonl(path, rows):
    Path(path).write_text(''.join(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n' for row in rows), encoding='utf-8')


def apply_profile(env, profile):
    model = profile.get('model')
    if not isinstance(model, str) or not model.strip() or profile.get('repeats') != 1:
        raise ValueError('adapter requires a model profile with exactly one repeat')
    env['OPENAI_CHART_MODEL'] = model.strip()
    env['STATBRIDGE_OUTPUT_PROVIDER'] = 'openai'
    return model.strip()


def read_xlsx_cells(workbook_path):
    import zipfile
    from xml.etree import ElementTree as ET

    with zipfile.ZipFile(workbook_path) as workbook:
        sheet = next((name for name in workbook.namelist()
                      if name.startswith('xl/worksheets/sheet') and name.endswith('.xml')), None)
        if not sheet:
            raise ValueError('XLSX workbook has no readable worksheet')
        shared = []
        if 'xl/sharedStrings.xml' in workbook.namelist():
            strings = ET.fromstring(workbook.read('xl/sharedStrings.xml'))
            shared = [''.join(node.text or '' for node in item.findall('.//{*}t'))
                      for item in strings.findall('.//{*}si')]
        root = ET.fromstring(workbook.read(sheet))
    cells = {}
    for cell in root.findall('.//{*}c'):
        address = cell.get('r')
        if not address:
            continue
        kind = cell.get('t')
        if kind == 'inlineStr':
            cells[address] = {'text': ''.join(node.text or '' for node in cell.findall('.//{*}t'))}
            continue
        value = cell.find('{*}v')
        if value is None or value.text is None:
            continue
        if kind == 's':
            index = int(value.text)
            if index >= len(shared):
                raise ValueError('XLSX shared-string index is invalid')
            cells[address] = {'text': shared[index]}
        elif kind in ('str', 'b', 'e'):
            cells[address] = {'text': value.text}
        else:
            cells[address] = {'value': value.text}
    return cells


def periods(frequency, text):
    years = re.findall(r'(20\d{2})년', text)
    if len(years) < 2:
        raise ValueError('period range is not explicit')
    first, last = int(years[0]), int(years[-1])
    if frequency == 'M':
        return [f'{year}{month:02d}' for year in range(first, last + 1) for month in range(1, 13)]
    if frequency == 'Q':
        return [f'{year}Q{quarter}' for year in range(first, last + 1) for quarter in range(1, 5)]
    if frequency in ('A', 'Y'):
        return [str(year) for year in range(first, last + 1)]
    raise ValueError('unsupported frequency: ' + frequency)


def expand_queries(query_rows):
    result = []
    for row in query_rows:
        for wording, outputs in row['queries'].items():
            for display, query in outputs.items():
                output_kind = {'그래프': 'graph', '표': 'table'}.get(display)
                if output_kind is None:
                    raise ValueError('unsupported output variant: ' + display)
                result.append({'id': f"{row['id']}__{wording}__{output_kind}",
                               'source_id': row['source_id'], 'logical_case_id': row['id'],
                               'wording': wording, 'input': {'query': query},
                               'expected': {'output_kind': output_kind}})
    if len({case['id'] for case in result}) != len(result):
        raise ValueError('duplicate generated case id')
    return result


def _period(value, frequency):
    value = str(value).strip()
    if frequency == 'Q' and re.fullmatch(r'\d{4}0[1-4]', value):
        return value[:4] + 'Q' + value[-1]
    if frequency == 'Q' and re.fullmatch(r'\d{4}Q[1-4]', value):
        return value
    if frequency == 'M' and re.fullmatch(r'\d{6}', value) and 1 <= int(value[-2:]) <= 12:
        return value
    if frequency in ('Y', 'A') and re.fullmatch(r'\d{4}', value):
        return value
    raise ValueError('invalid period: ' + value)


def _number(value):
    try:
        number = Decimal(str(value).replace(',', '').strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('invalid numeric observation') from exc
    if not number.is_finite():
        raise ValueError('non-finite numeric observation')
    return str(number)


def extract_series(path, contract, unit_by_code=None):
    wanted = {_period(period, contract['frequency']) for period in contract['periods']}
    values = {}
    units = set()
    labels = set()
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            if row.get('TBL_ID') != contract['table_id'] or row.get('ITM_ID') != contract['item_id']:
                continue
            freq = row.get('PRD_SE', '')
            if freq not in (contract['frequency'], 'Y' if contract['frequency'] == 'A' else contract['frequency']):
                continue
            if any(row.get('C' + key.removeprefix('objL'), '') != value
                   for key, value in contract['classifications'].items()):
                continue
            period = _period(row.get('PRD_DE', ''), contract['frequency'])
            if period not in wanted:
                continue
            if period in values:
                raise ValueError('duplicate source period: ' + period)
            raw_unit = (row.get('UNIT_NM') or '').strip()
            if not raw_unit and unit_by_code:
                raw_unit = unit_by_code.get(contract['item_id'], '')
            units.add(raw_unit)
            labels.add((row.get('C1_NM') or row.get('ITM_NM') or contract['item_id']).strip())
            values[period] = _number(row.get('DT', ''))
    missing = wanted - values.keys()
    if missing:
        raise ValueError('missing periods: ' + ', '.join(sorted(missing)))
    if len(units) != 1 or not next(iter(units)):
        raise ValueError('missing or conflicting unit')
    if len(labels) != 1:
        raise ValueError('conflicting series labels')
    return {key: contract[key] for key in ('table_id', 'item_id', 'classifications', 'frequency')} | {
        'unit': next(iter(units)), 'label': next(iter(labels)),
        'points': [{'period': period, 'value': values[period]} for period in sorted(values)]}
