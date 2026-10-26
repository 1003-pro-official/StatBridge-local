"""Join the research artifacts into one frozen inventory. Reads only; never calls the product or network."""
from __future__ import annotations

import csv
import json

from e2e_common import BASE, PROCESSED, RESEARCH, TABLES, digest_file, write

RESEARCH_FILES = ('재현매핑.csv', '질의집.jsonl', '원본재현명세.json', '원본목록.csv')


def identity(table_id, item_id, classifications):
    return (table_id, item_id, json.dumps(classifications or {}, sort_keys=True))


def load_specs():
    specs = json.loads((RESEARCH / '원본재현명세.json').read_text(encoding='utf-8'))
    covered = {}
    for spec in specs:
        for series in spec['series']:
            covered[identity(series['table_id'], series['item_id'], series.get('classifications'))] = spec['id']
    return specs, covered


def load_periods():
    result = {}
    with (PROCESSED / 'bok_periods.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            frequency = {'월': 'M', '분기': 'Q', '년': 'A'}.get(row['PRD_SE'])
            if frequency:
                result[(row['TBL_ID_BASE'], frequency)] = [row['STRT_PRD_DE'], row['END_PRD_DE']]
    return result


def load_attachments():
    result = {}
    with (RESEARCH / '원본목록.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            key = row.get('게시물ID') or row.get('source_id') or ''
            sha = row.get('SHA-256') or row.get('sha256') or ''
            if key and sha:
                result[key] = {'sha256': sha, 'filename': row.get('파일명') or row.get('filename') or ''}
    return result


def main():
    mapping = list(csv.DictReader((RESEARCH / '재현매핑.csv').open(encoding='utf-8-sig', newline='')))
    queries = {row['id']: row for row in (json.loads(line) for line in
                                          (RESEARCH / '질의집.jsonl').read_text(encoding='utf-8').splitlines() if line.strip())}
    specs, covered = load_specs()
    periods = load_periods()
    attachments = load_attachments()

    types = []
    for row in mapping:
        type_id = row['유형ID']
        query = queries.get(type_id, {})
        expected = query.get('expected_parameters') or json.loads(row['기대조회조건'])
        keys = [identity(s['table_id'], s['item_id'], s.get('classifications')) for s in expected]
        frequencies = {s.get('frequency') for s in expected}
        frequency = frequencies.pop() if len(frequencies) == 1 else (query.get('frequency') or '')
        full_specs = sorted({covered[key] for key in keys if key in covered})
        tier = 'A' if keys and all(key in covered for key in keys) else 'B'
        if row['실행판정'] != '출력 확인':
            tier = 'C'
        table_ids = sorted({s['table_id'] for s in expected})
        period_key = (table_ids[0], frequency) if table_ids else None
        types.append({
            'type_id': type_id,
            'tier': tier,
            'eligible_for_scoring': tier != 'C',
            'source': {
                'title': row['원본'],
                'url': row['원본URL'],
                'pdf_page': int(row['PDF물리페이지']) if row['PDF물리페이지'].strip() else None,
                'caption': row['원본캡션'],
                'attachment_sha256': query.get('source', {}).get('sha256') or attachments.get(query.get('source_id'), {}).get('sha256'),
            },
            'execution_verdict': row['실행판정'],
            'scope_note': row['제약'],
            'frequency': frequency,
            'period_range': periods.get(period_key) if period_key else None,
            'expected_series': [
                {'table_id': s['table_id'], 'item_id': s['item_id'],
                 'classifications': s.get('classifications') or {}, 'frequency': s.get('frequency')}
                for s in expected
            ],
            'full_specs': full_specs,
            'queries': {
                'graph': (query.get('queries') or {}).get('업무형', {}).get('그래프'),
                'table': (query.get('queries') or {}).get('업무형', {}).get('표'),
            },
        })

    inventory = {
        'schema_version': '1.0',
        'name': 'StatBridge E2E evaluation inventory',
        'research': {
            'path': str(RESEARCH.relative_to(RESEARCH.parents[1])),
            'files': {name: digest_file(RESEARCH / name) for name in RESEARCH_FILES},
            'full_specs': [spec['id'] for spec in specs],
        },
        'catalog': {
            'tables_dir': str(TABLES.relative_to(TABLES.parents[1])),
            'periods_sha256': digest_file(PROCESSED / 'bok_periods.csv'),
        },
        'counts': {
            'types': len(types),
            'tier_a': sum(t['tier'] == 'A' for t in types),
            'tier_b': sum(t['tier'] == 'B' for t in types),
            'tier_c': sum(t['tier'] == 'C' for t in types),
        },
        'types': types,
    }
    write(BASE / 'inventory.json', inventory)
    print(json.dumps(inventory['counts'], ensure_ascii=False))
    for item in types:
        print(item['type_id'], item['tier'], item['frequency'], item['period_range'], item['full_specs'])


if __name__ == '__main__':
    main()
