"""Emit a human oracle-check sheet. Values stay in the private cache."""
from __future__ import annotations

import argparse
import json

from e2e_common import BASE, CACHE, read, rows, write, write_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(CACHE / 'oracle-review.jsonl'))
    args = parser.parse_args()
    cases = rows(BASE / 'cases' / 'dev.jsonl') + rows(BASE / 'cases' / 'test.jsonl')
    oracles = read(CACHE / 'oracles.json')['cases']
    sheet = []
    for case in cases:
        digest = case['expected'].get('oracle_sha256')
        if not digest or case['id'] not in oracles:
            continue
        entry = oracles[case['id']]
        series = entry.get('series') or [{
            'table_id': source['table_id'], 'item_id': source['item_id'],
            'classifications': source['classifications'], 'frequency': source['frequency'],
            'unit': source['unit'], 'label': source['label']}
            for source in entry.get('sources', [])]
        sheet.append({
            'id': case['id'], 'group_id': case['group_id'], 'mode': case['mode'],
            'series': [{**{k: s[k] for k in ('table_id', 'item_id', 'classifications', 'frequency', 'unit', 'label')},
                        'points': entry.get('points') if 'points' in entry else s.get('points')}
                       for s in series],
            'source': entry.get('source'),
            'checker': None, 'checked_at': None, 'checked': False, 'note': None,
        })
    write_rows(args.output, sheet)
    lines = ['# Tier A 숫자 오라클 검산표', '',
             'CSV 행과 대조한 뒤 `checked`를 true로 바꾸고 검산자 이름을 적습니다. 값은 비공개 캐시에만 있습니다.', '',
             '| 사례 | 그룹 | 계열 | 기간 수 | 근거 파일 해시 |', '|---|---|---|---:|---|']
    for row in sheet:
        for series in row['series']:
            points = series.get('points') or []
            source = (row.get('source') or {}).get(series['table_id']) or {}
            lines.append(f"| {row['id']} | {row['group_id']} | {series['label']} | {len(points)} | "
                         f"{str(source.get('file_sha256'))[:12]} |")
    write(CACHE / 'oracle-review.md', '\n'.join(lines) + '\n')
    print(json.dumps({'cases': len(sheet), 'output': args.output}, ensure_ascii=False))


if __name__ == '__main__':
    main()
