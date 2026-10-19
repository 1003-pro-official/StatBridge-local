"""Refresh the existing observation domain without replacing historical backups.

Network use is explicit (--live); mutation requires --apply. Raw backups and
manifests belong outside Git (default: .venv/cache/kosis-snapshots).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/backend'))
from statbridge_mcp.data_snapshot import _index, replace_snapshot
from statbridge_mcp.statistics_service import StatisticsService


def fetch_existing_domain(service, table_id):
    path = service._find_local_table_csv(table_id)
    if path is None:
        raise ValueError('기존 로컬 통계표가 없습니다.')
    with path.open(encoding='utf-8-sig', newline='') as stream:
        previous = list(csv.DictReader(stream))
    _index(previous, table_id)
    rows = []
    # Bound requests by year to avoid KOSIS response-size truncation.
    for frequency, year in sorted({(r['PRD_SE'], r['PRD_DE'][:4]) for r in previous}):
        subset = [r for r in previous if r['PRD_SE'] == frequency and r['PRD_DE'].startswith(year)]
        organizations = {r['ORG_ID'] for r in subset}
        if organizations != {'301'}:
            raise ValueError('한국은행 자료만 갱신할 수 있습니다.')
        classes = {f'objL{i}': 'ALL' for i in range(1, 9) if any(r.get(f'C{i}') for r in subset)}
        rows.extend(service.client.get_statistics('301', table_id, 'ALL', frequency,
                    min(r['PRD_DE'] for r in subset), max(r['PRD_DE'] for r in subset), classes))
    old, new = _index(previous, table_id), _index(rows, table_id)
    if old.keys() != new.keys() or any(old[k].get('UNIT_NM', '') != new[k].get('UNIT_NM', '') for k in old):
        raise ValueError('전체 관측치 범위 또는 단위가 일치하지 않습니다. 기존 파일을 유지합니다.')
    return path, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('table_ids', nargs='+')
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    service = StatisticsService()
    if service.client is None:
        parser.error('KOSIS 키가 필요합니다.')
    fetched = []
    for table_id in args.table_ids:
        try:
            path, rows = fetch_existing_domain(service, table_id)
            fetched.append((table_id, path, rows))
        except Exception as exc:
            print(json.dumps(dict(table_id=table_id, status='failed', error_type=type(exc).__name__)), flush=True)
            return 1
    for table_id, path, rows in fetched:
        try:
            if args.apply:
                result = replace_snapshot(path, rows, table_id, ROOT / '.venv/cache/kosis-snapshots')
                print(json.dumps(result, ensure_ascii=False), flush=True)
            else:
                print(json.dumps(dict(table_id=table_id, validated_rows=len(rows), applied=False)), flush=True)
        except Exception as exc:
            # Request exceptions can contain API keys in their URLs.
            print(json.dumps(dict(table_id=table_id, status='failed', error_type=type(exc).__name__)), flush=True)
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
