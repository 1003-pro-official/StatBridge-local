"""Freeze file and dataset hashes. Approvals are never changed here."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from e2e_common import BASE, CACHE, ROOT, digest_file, digest_value, read, write, rows


def git_output(*args):
    try:
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unknown'


def main():
    files = {}
    for path in sorted(BASE.rglob('*')):
        if path.is_dir() or path.name == 'manifest.json' or '__pycache__' in path.parts or 'results' in path.parts:
            continue
        files[str(path.relative_to(BASE))] = digest_file(path)
    dev = rows(BASE / 'cases' / 'dev.jsonl')
    test = rows(BASE / 'cases' / 'test.jsonl')
    holdout = rows(BASE / 'cases' / 'holdout_queries.jsonl')
    inventory = read(BASE / 'inventory.json')
    oracles = read(CACHE / 'oracles.json')['cases'] if (CACHE / 'oracles.json').is_file() else {}
    manifest = {
        'schema_version': '1.0',
        'dataset_version': '1.0',
        'name': 'StatBridge E2E workflow evaluation',
        'status': 'ready_for_review',
        'official_performance': False,
        'ai_assisted': True,
        'product_revision': git_output('log', '-1', '--format=%H', '--', 'src'),
        'reference_date': '2026-10-21',
        'counts': {'dev': len(dev), 'test': len(test), 'holdout_queries': len(holdout),
                   'oracle_cases': len(oracles),
                   'modes': {mode: sum(c['mode'] == mode for c in dev + test) for mode in
                             ('query_output', 'derived', 'report', 'follow_up', 'edit')}},
        'research': inventory['research'],
        'catalog': inventory['catalog'],
        'oracle_sha256': digest_value(oracles),
        'files': files,
        'limitations': [
            'Only tier A cases carry independent numeric oracles.',
            'Tier B cases score series identity and periods, not values.',
            'derived/report/follow_up/edit need a model-backed adapter and stay not_executed offline.',
            'No human gold approval or response review exists yet.',
        ],
    }
    write(BASE / 'manifest.json', manifest)
    print(json.dumps({'files': len(files), 'counts': manifest['counts'],
                      'product_revision': manifest['product_revision']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
