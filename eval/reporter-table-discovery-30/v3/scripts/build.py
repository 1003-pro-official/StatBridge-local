"""Reproducible public catalog augmentation; no agent predictions are imported."""
from __future__ import annotations

from collections import Counter, defaultdict
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[4]
DATASET = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'src/agent/stat_dictionary/stat_language_dictionary.json'
BASE = DATASET.parent / 'v2/statbridge-reporter30.jsonl'
SCHEMA = 'reporter349-discovery-3'
FREQUENCY = {'M': '월별', 'Q': '분기별', 'A': '연간', 'Y': '연간', 'S': '반기별'}
spec = importlib.util.spec_from_file_location('v2_metadata_policy', DATASET.parent / 'v2/scripts/validate.py')
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def compact(value):
    return re.sub(r'[^0-9a-z가-힣]', '', str(value).lower())


def representatives(table):
    values = {}
    for dimension in table['dimensions']:
        by_id = {v['value_id']: v for v in dimension['values']}
        chosen = dimension.get('representative_value_id') or dimension['values'][0]['value_id']
        if chosen not in by_id:
            raise ValueError(f"Invalid representative: {table['table_id']} {chosen}")
        values[dimension['api_param']] = by_id[chosen]
    return values


def plan(table, values, label):
    # The v2 validator contains the frozen normative default-period policy.
    # Calling the runtime resolver or build_api_plan here would contaminate gold.
    stub = {'query': '', 'workflow_gold': {'query_interpretation': {'period': None}}}
    frequency = table['api_call_params'].get('prdSe') or table['prd_se']
    start, end = v2.expected_plan_period(stub, table, frequency)
    classes = {p: value['value_id'] for p, value in values.items()}
    labels = {p: value['value_name'] for p, value in values.items()}
    item = table['item_ids'][0]
    params = {'method': 'getList', 'format': 'json', 'jsonVD': 'Y', 'smblChk': 'Y',
              'orgId': str(table['org_id']), 'tblId': table['table_id'], 'itmId': item,
              'prdSe': frequency, 'startPrdDe': start, 'endPrdDe': end, **classes}
    return {'label': label, 'table_id': table['table_id'], 'table_name': table['table_name'],
            'org_id': str(table['org_id']), 'item_id': item, 'frequency': frequency,
            'classifications': classes, 'classification_labels': labels,
            'period_start': start, 'period_end': end, 'exact_params': params}


def make_case(identifier, query, kind, anchors, plans, catalog_hash, **extra):
    ids = sorted({p['table_id'] for p in plans})
    frequencies = sorted({p['frequency'] for p in plans})
    meanings = [{'label': p['label'], 'metric': p['table_name'], 'target': p['classification_labels'],
                 'measure': p['table_name'], 'measurement_basis': None,
                 'qualifiers': {}, 'frequency': p['frequency']} for p in plans]
    return {
        'id': identifier, 'schema_version': SCHEMA, 'split': 'dev', 'query': query,
        'reference_date': '2026-10-08',
        'augmentation': {'kind': kind, 'anchor_table_ids': anchors, **extra},
        'workflow_gold': {
            'query_interpretation': {'user_intent': ['statistical_table_discovery'], 'period': None,
                'frequency': frequencies[0] if len(frequencies) == 1 else None,
                'frequencies': frequencies, 'comparison': {'required': len(plans) > 1,
                'mode': 'series_comparison' if len(plans) > 1 else 'none'}, 'series': meanings,
                'slot_matching': 'semantic_equivalence_allowed_for_names; preserve_metric_and_scope',
                'null_semantics': 'no_explicit_period; catalog_representative_for_unmentioned_dimensions'},
            'table_discovery': {'status': 'matched', 'expected_table_ids': ids, 'selected_table_ids': ids,
                'table_names': {p['table_id']: p['table_name'] for p in plans}, 'unmatched_concepts': []},
            'item_selection': {'item_by_table': {p['table_id']: p['item_id'] for p in plans},
                'matching': 'exact_item_code_by_table'},
            'classification_and_plan': {'series': plans, 'matching': 'exact_series_identity_set_with_period_and_frequency',
                'execution': 'not_run'},
            'resolution': {'agent_status': 'resolved', 'api_status': 'need_period',
                'clarification_required': False, 'table_count': len(ids), 'series_count': len(plans)},
            'post_discovery': {'response_status': 'need_period', 'reason': 'period_missing',
                'period_selection_required': True, 'text_period': None, 'execution': False},
        },
        'evidence': {'catalog_path': str(CATALOG.relative_to(ROOT)).replace('\\', '/'),
            'catalog_sha256': catalog_hash, 'gold_basis': 'public_catalog_codes_and_frozen_v2_metadata_contract'},
        'review': {'ai_assisted': True, 'human_approved': False, 'status': 'draft'},
        'excluded_from_scoring': ['numeric_observations', 'chart_rendering', 'interpretation_text', 'causal_claims'],
    }


def title(table, counts):
    result = f"「{table['table_name']}」"
    if counts[table['table_name']] > 1:
        result += f" [{table['table_id']}]"
    return result


def bounds(table):
    freq = table['prd_se']
    start = v2.normalized_period(table['period_start_observed'], freq)
    end = v2.normalized_period(table['period_end_observed'], freq, end=True)
    if freq in {'A', 'Y'}:
        return start + '01', end + '12'
    if freq == 'Q':
        return start[:4] + f"{(int(start[4:]) - 1) * 3 + 1:02d}", end[:4] + f"{int(end[4:]) * 3:02d}"
    if freq == 'S':
        return start[:4] + f"{(int(start[4:]) - 1) * 6 + 1:02d}", end[:4] + f"{int(end[4:]) * 6:02d}"
    return start, end


def build():
    catalog = json.loads(CATALOG.read_text(encoding='utf-8-sig'))
    tables = sorted(catalog['tables'], key=lambda t: t['table_id'])
    if len(tables) != 349:
        raise ValueError('Expected the frozen 349-table catalog')
    catalog_hash = digest(CATALOG)
    counts = Counter(t['table_name'] for t in tables)
    cases = []
    for original in [json.loads(line) for line in BASE.read_text(encoding='utf8').splitlines()]:
        case = copy.deepcopy(original)
        case['id'] = 'R349-BASE-' + original['id'].rsplit('-', 1)[1]
        case['schema_version'] = SCHEMA
        case['augmentation'] = {'kind': 'v2_original', 'source_id': original['id'],
                                'anchor_table_ids': original['workflow_gold']['table_discovery']['expected_table_ids']}
        cases.append(case)

    for table in tables:
        q = f"{title(table, counts)} 자료를 한 계열로 찾아줘. 조회 기간은 아직 선택하지 않을게."
        p = plan(table, representatives(table), table['table_name'])
        cases.append(make_case('R349-SINGLE-' + table['table_id'], q, 'single_table', [table['table_id']], [p], catalog_hash,
            table_reference='name_plus_id_for_duplicate_title' if counts[table['table_name']] > 1 else 'canonical_name',
            classification_policy='catalog_representative_unmentioned'))

    pairs = set()
    multi_covered = set()
    pairing_exceptions = []
    for index, table in enumerate(tables):
        left_start, left_end = bounds(table)
        partners = []
        for offset in range(1, len(tables)):
            other = tables[(index + offset + 16) % len(tables)]
            if other['table_id'] == table['table_id']:
                continue
            right_start, right_end = bounds(other)
            if max(left_start, right_start) <= min(left_end, right_end):
                partners.append(other)
        partners.sort(key=lambda t: t['prd_se'] != table['prd_se'])
        other = next((t for t in partners if frozenset((table['table_id'], t['table_id'])) not in pairs), None)
        if other is None:
            if table['table_id'] not in multi_covered:
                raise ValueError(f"No overlapping distinct partner: {table['table_id']}")
            pairing_exceptions.append({'table_id': table['table_id'], 'reason': 'all_available_pairs_already_covered'})
            continue
        pairs.add(frozenset((table['table_id'], other['table_id'])))
        multi_covered.update((table['table_id'], other['table_id']))
        q = f"{title(table, counts)} 자료와 {title(other, counts)} 자료를 각각 한 계열로 찾아 비교해줘. 조회 기간은 아직 선택하지 않을게."
        plans = [plan(t, representatives(t), t['table_name'] + ' [' + t['table_id'] + ']') for t in (table, other)]
        cases.append(make_case('R349-MULTI-' + table['table_id'], q, 'multi_table', [table['table_id'], other['table_id']], plans, catalog_hash,
            table_reference='canonical_names_with_ids_only_for_duplicate_titles', pairing='overlapping_observed_period_prefer_same_frequency'))

    classification_exceptions = []
    for table in tables:
        chosen = None
        for dimension in table['dimensions']:
            name_counts = Counter(v['value_name'] for v in dimension['values'])
            values = [v for v in dimension['values'] if name_counts[v['value_name']] == 1]
            if len(values) >= 2:
                chosen = (dimension, values[:2])
                break
        if chosen is None:
            classification_exceptions.append({'table_id': table['table_id'], 'table_name': table['table_name'],
                'reason': 'no_dimension_has_two_distinct_unambiguous_value_names'})
            continue
        dimension, values = chosen
        defaults = representatives(table)
        fixed = {p: v for p, v in defaults.items() if p != dimension['api_param']}
        fixed_parts = []
        for param, value in fixed.items():
            dim = next(d for d in table['dimensions'] if d['api_param'] == param)
            text = f"{dim['level']}번째 분류는 「{value['value_name']}」"
            if sum(v['value_name'] == value['value_name'] for v in dim['values']) > 1:
                text += f" [분류 코드 {value['value_id']}]"
            fixed_parts.append(text)
        fixed_text = ', '.join(fixed_parts)
        q = f"{title(table, counts)}에서 {dimension['level']}번째 분류의 「{values[0]['value_name']}」와 「{values[1]['value_name']}」 자료를 각각 한 계열로 비교해줘."
        if fixed_text:
            q += f" 나머지는 {fixed_text}로 고정해줘."
        q += ' 조회 기간은 아직 선택하지 않을게.'
        plans = [plan(table, {**defaults, dimension['api_param']: v}, table['table_name'] + ' / ' + v['value_name']) for v in values]
        cases.append(make_case('R349-CLASS-' + table['table_id'], q, 'multi_classification', [table['table_id']], plans, catalog_hash,
            varying_dimension=dimension['api_param'], requested_value_ids=[v['value_id'] for v in values],
            fixed_classifications={p: v['value_id'] for p, v in fixed.items()}, table_reference='name_plus_id_for_duplicate_title' if counts[table['table_name']] > 1 else 'canonical_name'))

    duplicates = defaultdict(list)
    for table in tables:
        duplicates[table['table_name']].append(table)
    for index, (name, siblings) in enumerate(sorted(duplicates.items())):
        if len(siblings) < 2:
            continue
        case = make_case('R349-AMBIG-' + siblings[0]['table_id'], f"「{name}」 자료를 찾아줘. 통계표 ID는 아직 선택하지 않았어.",
            'duplicate_title_clarification', [t['table_id'] for t in siblings], [], catalog_hash)
        workflow = case['workflow_gold']
        workflow['table_discovery']['status'] = 'clarification_pending'
        workflow['resolution'] = {'agent_status': 'need_clarification', 'api_status': 'need_clarification',
            'clarification_required': True, 'table_count': 0, 'series_count': 0,
            'clarification': {'id': 'canonical_table:' + compact(name),
                'question': '같은 이름의 통계표가 여러 개입니다. 기준과 통계표 ID를 확인해 선택해 주세요.',
                'options': [{'label': t['table_name'] + ' [' + t['table_id'] + ']', 'value': t['table_id']} for t in siblings]}}
        workflow['post_discovery'] = {'response_status': 'need_clarification', 'reason': 'duplicate_canonical_title', 'execution': False}
        cases.append(case)

    output = DATASET / 'statbridge-reporter349.jsonl'
    output.write_text(''.join(json.dumps(c, ensure_ascii=False, separators=(',', ':')) + '\n' for c in cases), encoding='utf8')
    manifest = {'dataset': 'reporter-table-discovery-349', 'version': 'v3', 'schema_version': SCHEMA,
        'reference_date': '2026-10-08', 'split': 'dev', 'review': {'ai_assisted': True, 'human_approved': False},
        'source_dataset': str(BASE.relative_to(ROOT)).replace('\\', '/'), 'source_dataset_sha256': digest(BASE),
        'catalog_sha256': catalog_hash, 'dataset_sha256': digest(output),
        'counts': {'cases': len(cases), 'by_kind': dict(Counter(c['augmentation']['kind'] for c in cases)),
            'by_status': dict(Counter(c['workflow_gold']['resolution']['agent_status'] for c in cases))},
        'coverage': {'single_table_ids': sorted(t['table_id'] for t in tables), 'multi_table_ids': sorted(multi_covered),
            'multi_classification_ids': sorted(c['augmentation']['anchor_table_ids'][0] for c in cases if c['augmentation']['kind'] == 'multi_classification')},
        'classification_exceptions': classification_exceptions, 'pairing_exceptions': pairing_exceptions,
        'api_frequency_aliases': [{'table_id': t['table_id'], 'catalog_frequency': t['prd_se'],
            'api_frequency': t['api_call_params']['prdSe']} for t in tables
            if t['prd_se'] != t['api_call_params']['prdSe']],
        'period_policy': 'v2 frozen default windows; table-title vintage years are not a user date filter',
        'runtime_prediction_used_to_create_gold': False, 'numeric_execution': False}
    (DATASET / 'dataset_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    lines = ['# 349개 표 증강 골든셋 문항', '', '| ID | 유형 | 질문 | 기대 상태 | 정답 표 | 계열 수 |', '|---|---|---|---|---|---:|']
    for case in cases:
        w = case['workflow_gold']
        lines.append(f"| {case['id']} | {case['augmentation']['kind']} | {case['query'].replace('|', '/')} | {w['resolution']['agent_status']} | {', '.join(w['table_discovery']['expected_table_ids']) or '-'} | {w['resolution']['series_count']} |")
    (DATASET / 'statbridge-reporter349.md').write_text('\n'.join(lines) + '\n', encoding='utf8')
    print(json.dumps(manifest['counts'], ensure_ascii=False))


if __name__ == '__main__':
    build()
