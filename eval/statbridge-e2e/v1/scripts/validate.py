"""Structural, leakage, period and oracle checks. Standard library only."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from e2e_common import BASE, CACHE, PROCESSED, RESEARCH, RUBRIC, digest_file, digest_value, read, rows

MODES = {'query_output', 'derived', 'report', 'follow_up', 'edit'}
TARGET = {'dev': 48, 'test': 72, 'holdout': 40}


def to_key(value, frequency):
    text = str(value).replace('.', '').replace(' ', '')
    if frequency == 'Q':
        if '/4' in text:
            year, quarter = text.split('/4')[0], text.split('/')[-1]
            return f'{year}Q{quarter}'
        return text[:4] + 'Q' + text[-1]
    return text[:6] if frequency == 'M' else text[:4]


def catalog_ids():
    tables, items = set(), set()
    with (PROCESSED / 'bok_items.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            tables.add(row['TBL_ID'])
            items.add((row['TBL_ID'], row['ITM_ID']))
    return tables, items


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-oracles', action='store_true',
                        help='skip private numeric oracle checks when the local cache is absent (CI)')
    args = parser.parse_args(argv)
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    inventory = read(BASE / 'inventory.json')
    for name, digest in inventory['research']['files'].items():
        check(digest_file(RESEARCH / name) == digest, f'research file changed: {name}')
    types = {t['type_id']: t for t in inventory['types']}
    check(len(types) == 36, 'inventory must hold 36 research types')

    cases = {'dev': rows(BASE / 'cases' / 'dev.jsonl'), 'test': rows(BASE / 'cases' / 'test.jsonl')}
    holdout = rows(BASE / 'cases' / 'holdout_queries.jsonl')
    all_cases = cases['dev'] + cases['test']

    check(len(cases['dev']) == TARGET['dev'], f"dev count {len(cases['dev'])}")
    check(len(cases['test']) == TARGET['test'], f"test count {len(cases['test'])}")
    check(len(holdout) == TARGET['holdout'], f"holdout count {len(holdout)}")
    ids = [c['id'] for c in all_cases] + [h['id'] for h in holdout]
    check(len(ids) == len(set(ids)), 'duplicate case ID')
    check(not any(set(h) & {'expected', 'oracle_sha256', 'review'} for h in holdout), 'holdout leaked gold')

    tables, items = catalog_ids()
    groups = {}
    for case in all_cases:
        card = f"{case['id']}"
        check(case.get('schema_version') == '1.0', f'{card}: schema_version')
        check(case.get('mode') in MODES, f'{card}: mode')
        check(case.get('split') in ('dev', 'test'), f'{card}: split')
        check(case['group_id'] in types, f'{card}: unknown group {case["group_id"]}')
        groups.setdefault(case['group_id'], set()).add(case['split'])
        check(not set(case['input']) & {'expected', 'oracle', 'answer_key'}, f'{card}: gold in input')
        query = case['input']['query']
        check('DT_' not in query and '[' not in query, f'{card}: query leaks a table ID')
        check(all('DT_' not in turn['text'] for turn in case['input'].get('prior_turns', [])), f'{card}: prior turn leaks ID')
        check(set(case['qualitative_applicable']) <= set(RUBRIC), f'{card}: rubric name')
        check('facts' in case['qualitative_applicable'], f'{card}: facts must stay in the rubric')
        check(case['review'] == {'human_approved': False, 'reviewer': None}, f'{card}: approval must stay empty')

        item = types[case['group_id']]
        expected = case['expected']
        check(expected.get('decision') in ('resolved', 'unresolved_probe'), f'{card}: decision')
        if item['tier'] == 'C':
            check(case['eligible_for_scoring'] is False, f'{card}: tier C must not be scoreable')
            check(expected['decision'] == 'unresolved_probe', f'{card}: tier C decision')
        else:
            check(case['eligible_for_scoring'] is True, f'{card}: tier A/B must be scoreable')
            check(expected['decision'] == 'resolved', f'{card}: tier A/B decision')

        frequency = item['frequency']
        low, high = to_key(item['period_range'][0], frequency), to_key(item['period_range'][1], frequency)
        for series in expected.get('series', []) or []:
            check((series['table_id'], series['item_id']) in items, f'{card}: unknown series {series["table_id"]}')
            check(series['table_id'] in tables, f'{card}: unknown table {series["table_id"]}')
        for point in expected.get('periods', []):
            key = to_key(point, frequency)
            check(low <= key <= high, f'{card}: period {point} outside {low}..{high}')

        if expected.get('base_case_id'):
            base = next((c for c in all_cases if c['id'] == expected['base_case_id']), None)
            check(base is not None, f'{card}: missing base case')
            if base:
                check(base['split'] == case['split'], f'{card}: base split differs')
                check(base['group_id'] == case['group_id'], f'{card}: base group differs')

    for group, splits in groups.items():
        check(len(splits) == 1, f'group {group} spans splits: {sorted(splits)}')

    counts = {mode: sum(c['mode'] == mode for c in all_cases) for mode in MODES}
    check(sum(counts.values()) == 120, f'mode total {sum(counts.values())}')
    check(counts['query_output'] == 84, f"query_output {counts['query_output']}")

    oracles = read(CACHE / 'oracles.json')['cases'] if (CACHE / 'oracles.json').is_file() else {}
    for case in all_cases:
        if args.no_oracles:
            continue
        digest = case['expected'].get('oracle_sha256')
        if digest:
            check(case['id'] in oracles, f"{case['id']}: oracle missing")
            if case['id'] in oracles:
                check(digest_value(oracles[case['id']]) == digest, f"{case['id']}: oracle hash mismatch")
        numeric = case['mode'] == 'query_output' and case.get('tier') == 'A' and case['expected']['decision'] == 'resolved'
        if numeric:
            check(bool(digest), f"{case['id']}: tier A needs an oracle")
        if case.get('tier') == 'B' and case['mode'] == 'query_output':
            check(not digest, f"{case['id']}: tier B must not carry numbers")

    if errors:
        print('VALIDATION FAILED')
        for error in errors[:40]:
            print(' -', error)
        return 1
    print(f"VALIDATION OK: dev={len(cases['dev'])} test={len(cases['test'])} holdout={len(holdout)} "
          f"oracles={len(oracles)} modes={json.dumps(counts, ensure_ascii=False)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
