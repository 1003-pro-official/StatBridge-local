"""Validated local snapshot replacement and observation fingerprints."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

IDENTITY = ('TBL_ID', 'PRD_SE', 'PRD_DE', 'ITM_ID', *(f'C{i}' for i in range(1, 9)))


def observation_version(rows):
    """Hash requested observations, including source revision dates, in stable order."""
    records = [json.dumps({k: str(v) for k, v in row.items() if not k.startswith('_')},
                          ensure_ascii=False, sort_keys=True) for row in rows]
    return hashlib.sha256('\n'.join(sorted(records)).encode()).hexdigest()


def _index(rows, table_id):
    result = {}
    for row in rows:
        key = tuple(str(row.get(k, '')) for k in IDENTITY)
        if row.get('TBL_ID') != table_id or not all(row.get(k) for k in IDENTITY[:4]) or key in result:
            raise ValueError('통계표·관측치 식별자가 잘못되었거나 중복되었습니다.')
        try:
            value = Decimal(str(row.get('DT', '')).replace(',', ''))
        except InvalidOperation:
            raise ValueError('수치가 아닌 관측치가 있습니다.') from None
        if not value.is_finite():
            raise ValueError('유한하지 않은 관측치가 있습니다.')
        result[key] = row
    if not result:
        raise ValueError('빈 자료로 교체할 수 없습니다.')
    return result


def replace_snapshot(path, rows, table_id, versions_dir):
    """Replace the same observation domain only; never infer an incomplete refresh."""
    path, versions_dir = Path(path), Path(versions_dir)
    original = path.read_bytes()
    with path.open(encoding='utf-8-sig', newline='') as stream:
        previous = list(csv.DictReader(stream))
    old, new = _index(previous, table_id), _index(rows, table_id)
    if old.keys() != new.keys():
        raise ValueError('조회 범위가 기존 관측치 전체와 일치하지 않습니다.')
    if any(old[k].get('UNIT_NM', '') != new[k].get('UNIT_NM', '') for k in old):
        raise ValueError('단위가 달라 자동 교체할 수 없습니다.')
    before = hashlib.sha256(original).hexdigest()
    versions_dir.mkdir(parents=True, exist_ok=True)
    backup = versions_dir / f'{table_id}-{before}.csv'
    if backup.exists():
        if backup.read_bytes() != original:
            raise ValueError('기존 백업의 무결성이 손상되었습니다.')
    else:
        with backup.open('xb') as stream:
            stream.write(original)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', newline='', dir=path.parent,
                                         prefix=f'.{table_id}-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            columns = list(dict.fromkeys(k for row in rows for k in row))
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n')
            writer.writeheader(); writer.writerows(rows)
            stream.flush(); os.fsync(stream.fileno())
        after = hashlib.sha256(temporary.read_bytes()).hexdigest()
        manifest = versions_dir / f'{table_id}-{after}.json'
        record = dict(table_id=table_id, source='kosis_api', retrieved_at=datetime.now(timezone.utc).isoformat(),
                      sha256_before=before, sha256_after=after, backup=str(backup), manifest=str(manifest),
                      row_count=len(rows), changed_values=sum(old[k]['DT'] != new[k]['DT'] for k in old),
                      source_last_changed=sorted({r.get('LST_CHN_DE', '') for r in rows}))
        # Persist recovery evidence before replacing the only active copy.
        manifest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        if path.read_bytes() != original:
            raise ValueError('검증 도중 원본 파일이 변경되어 교체를 중단했습니다.')
        os.replace(temporary, path)
        return record
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
