"""Compare official PDF samples and (with --live) KOSIS against local CSVs.

Raw observations remain in memory. Persist only conditions, counts and verdicts.
All request exceptions are reduced to their class to avoid exposing request URLs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = ROOT / '.venv/cache/kosis-bok-reproduction'
sys.path[:0] = [str(HERE), str(ROOT / 'src/backend')]


def number(value):
    try:
        n = Decimal(str(value).replace(',', '').strip())
        return n if n.is_finite() else None
    except InvalidOperation:
        return None


def same_rows(local, live):
    def index(rows):
        return {(str(r.get('PRD_DE')), str(r.get('ITM_ID')), *(str(r.get(f'C{i}', '')) for i in range(1, 5))):
                (number(r.get('DT')), r.get('UNIT_NM', '')) for r in rows}
    a, b = index(local), index(live)
    return bool(a) and a == b and len(a) == len(local) == len(live) and all(v[0] is not None for v in a.values())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--live', action='store_true', help='Explicitly allow credentialed KOSIS requests')
    args = p.parse_args()
    if not args.live:
        os.environ['PYTHON_DOTENV_DISABLED'] = '1'
        os.environ['KOSIS_API_KEY'] = ''
    from statbridge_mcp.statistics_service import StatisticsService
    from statbridge_mcp.config import settings
    service = StatisticsService()
    cases = [json.loads(s) for s in (HERE / '질의집.jsonl').read_text().splitlines()]
    result = []
    for case in cases:
        for index, plan in enumerate(case['expected_parameters']):
            end = '2024' if case['frequency'] == 'A' else '202504' if case['frequency'] == 'Q' else '202512'
            params = {k: v for k, v in plan.items() if k != 'org_id'} | {'start_period': end, 'end_period': end}
            record = {'id': case['id'], 'series': index, 'period': end, 'conditions': plan}
            try:
                local = service.get_statistics(**params, prefer_local=True)
                record['local_source'] = local.get('source')
                record['local_rows'] = len(local['rows'])
                if local.get('source') != 'local_csv':
                    record.update(kosis_live_verified=False, reason='local CSV sample unavailable; comparison not performed')
                    result.append(record)
                    (CACHE / 'value-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
                    continue
                if args.live and settings.kosis_api_key:
                    live = service.get_statistics(**params, prefer_local=False)
                    record.update(live_source=live.get('source'), live_rows=len(live['rows']),
                                  matched=same_rows(local['rows'], live['rows']),
                                  local_units=sorted({r.get('UNIT_NM', '') for r in local['rows']}),
                                  live_units=sorted({r.get('UNIT_NM', '') for r in live['rows']}),
                                  returned_params=live.get('used_params'),
                                  kosis_live_verified=live.get('source') == 'kosis_api')
                    if len(local['rows']) == len(live['rows']) == 1:
                        a, b = local['rows'][0], live['rows'][0]
                        record['identity_match'] = all(str(a.get(k, '')) == str(b.get(k, '')) for k in ['PRD_DE', 'ITM_ID', 'C1', 'C2', 'C3', 'C4'])
                        record['numeric_match'] = number(a.get('DT')) == number(b.get('DT'))
                else:
                    record.update(kosis_live_verified=False, reason='live not requested or key unavailable')
            except Exception as exc:
                record.update(kosis_live_verified=False, error=type(exc).__name__)
            result.append(record)
            print(case['id'], index, record.get('matched'), record.get('error', ''), flush=True)
            (CACHE / 'value-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')

    # Independent original-PDF sample: two visible year-end columns, not a reconstructed series.
    import pdfplumber
    collection = json.loads((CACHE / 'collection.json').read_text())
    release = next(r for r in collection['releases'] if r['id'] == '11065098')
    file = next(f for f in release['files'] if f['name'].endswith('.pdf'))
    with pdfplumber.open(ROOT / file['path']) as pdf:
        tables = pdf.pages[2].extract_tables()
    samples = []
    # (case ID, series index, source table row, line within a merged cell)
    cells = [('RATE-01', 0, 1, 0), ('RATE-02', 0, 4, 3),
             ('RATE-03', 0, 4, 1), ('RATE-03', 1, 4, 2), ('RATE-04', 0, 6, 1)]
    for ident, series_index, row, line in cells:
        case = next(c for c in cases if c['id'] == ident)
        for period, column in [('202412', 2), ('202512', 3)]:
            record = {'id': ident, 'series': series_index, 'period': period, 'source_id': release['id'],
                      'pdf_page': 3, 'pdf_sha256': file['sha256'], 'tolerance': '0.005',
                      'review': 'agent PDF table-cell extraction; human review pending'}
            try:
                assert len(tables) == 1 and '2024.12' in tables[0][0] and '2025.12' in tables[0][0]
                value = number(tables[0][row][column].splitlines()[line])
                params = {k: v for k, v in case['expected_parameters'][series_index].items() if k != 'org_id'}
                fetched = service.get_statistics(**params, start_period=period, end_period=period, prefer_local=True)
                record['local_source'] = fetched.get('source')
                assert fetched.get('source') == 'local_csv', 'local CSV sample unavailable'
                observed = fetched['rows']
                numeric = [number(r.get('DT')) for r in observed]
                record.update(source_cell_parsed=value is not None, local_rows=len(observed),
                              matched=len(numeric) == 1 and value is not None and numeric[0] is not None
                              and abs(numeric[0] - value) <= Decimal('0.005'))
            except Exception as exc:
                record.update(matched=False, error=type(exc).__name__)
            samples.append(record)
    (CACHE / 'pdf-value-audit.json').write_text(json.dumps(samples, ensure_ascii=False, indent=2) + '\n')
    print('PDF samples', len(samples), 'matched', sum(r['matched'] for r in samples))


if __name__ == '__main__':
    main()
