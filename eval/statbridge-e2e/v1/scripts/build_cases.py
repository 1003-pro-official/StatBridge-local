"""Generate public cases and the private numeric oracle from the frozen inventory.

No product output, PDF value, or research verdict becomes a gold value here.
Tier A numbers come from data/tables CSV only; other tiers carry no numbers.
"""
from __future__ import annotations

import csv
import glob
import hashlib
import json
import re

from e2e_common import (BASE, CACHE, RESEARCH, TABLES, calculate, digest_file, digest_value,
                    period, read, write, write_rows)

REFERENCE_DATE = '2026-10-21'
BASE_PERIODS = {'M': ('202301', '202512'), 'Q': ('2023Q1', '2025Q4'), 'A': ('2022', '2024')}
VARIANT_PERIODS = {'M': ('202501', '202512'), 'Q': ('2024Q1', '2025Q4'), 'A': ('2020', '2024')}
VARIANT_TEXT = {'M': '{a}년 1월부터 {b}년 12월까지', 'Q': '{a}년 1분기부터 {b}년 4분기까지',
                'A': '{a}년부터 {b}년까지'}
QUALITATIVE = ('facts', 'clarity')


def periods_between(start, end, frequency):
    if frequency == 'M':
        y, m = int(start[:4]), int(start[4:])
        stop = int(end[:4]) * 12 + int(end[4:])
        out = []
        while y * 12 + m <= stop:
            out.append(f'{y:04d}{m:02d}')
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        return out
    if frequency == 'Q':
        y, q = int(start[:4]), int(start[-1])
        out = []
        while f'{y}{q}' <= f'{end[:4]}{end[-1]}':
            out.append(f'{y}Q{q}')
            y, q = (y + 1, 1) if q == 4 else (y, q + 1)
        return out
    return [str(y) for y in range(int(start), int(end) + 1)]


_index = {}


def table_index(table_id):
    if table_id in _index:
        return _index[table_id]
    matches = glob.glob(str(TABLES / f'{table_id}__*.csv'))
    if len(matches) != 1:
        raise ValueError(f'{table_id}: expected one CSV, found {len(matches)}')
    path = matches[0]
    print(f'index {table_id}', flush=True)
    data = {}
    with open(path, encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            if str(row.get('PRD_DE') or '')[:4] < '2019':
                continue
            frequency = {'월': 'M', '분기': 'Q', '년': 'A', 'M': 'M', 'Q': 'Q', 'A': 'A'}.get(row.get('PRD_SE'), 'M')
            classes = {f'objL{index}': row.get(f'C{index}') for index in range(1, 5) if row.get(f'C{index}')}
            key = (row['ITM_ID'], tuple(sorted(classes.items())), frequency)
            slot = data.setdefault(key, {'unit': row.get('UNIT_NM') or '', 'points': {}, 'classes': classes,
                                         'lst': row.get('LST_CHN_DE') or ''})
            try:
                slot['points'][period(row['PRD_DE'], frequency)] = row['DT']
            except ValueError as exc:
                raise ValueError(f'{path}: PRD_SE={row.get("PRD_SE")!r} PRD_DE={row.get("PRD_DE")!r}') from exc
    _index[table_id] = {'path': path, 'sha256': digest_file(path), 'rows': data}
    return _index[table_id]


def label_map():
    result = {}
    for spec in json.loads((RESEARCH / '원본재현명세.json').read_text(encoding='utf-8')):
        for series in spec['series']:
            result[(series['table_id'], series['item_id'], json.dumps(series.get('classifications') or {}, sort_keys=True))] = series['label']
    return result


def series_ref(table_id, item_id, classifications, frequency, labels):
    table = table_index(table_id)
    key = (item_id, tuple(sorted((classifications or {}).items())), frequency)
    if key not in table['rows']:
        raise ValueError(f'{table_id}/{item_id}/{key[1]} not in CSV')
    slot = table['rows'][key]
    ident = (table_id, item_id, json.dumps(classifications or {}, sort_keys=True))
    return {'table_id': table_id, 'item_id': item_id, 'classifications': classifications or {},
            'frequency': frequency, 'unit': slot['unit'], 'label': labels.get(ident, f'{table_id} {item_id}'),
            'lst_chn_de': slot['lst'], 'points': slot['points'], 'file_sha256': table['sha256']}


def oracle_entry(refs, labels):
    return {
        'series': [{k: ref[k] for k in ('table_id', 'item_id', 'classifications', 'frequency', 'unit', 'label')}
                   | {'points': [{'period': p, 'value': ref['points'][p]} for p in sorted(ref['points']) if p in ref['selected']]}
                   for ref in refs],
        'source': {ref['table_id']: {'file_sha256': ref['file_sha256'], 'lst_chn_de': ref['lst_chn_de']} for ref in refs},
    }


def select(refs, wanted):
    for ref in refs:
        ref['selected'] = set(wanted)
        missing = ref['selected'] - set(ref['points'])
        if missing:
            raise ValueError(f'{ref["table_id"]}/{ref["item_id"]}: missing periods {sorted(missing)[:3]}')
    return refs


def rewrite_period(query, frequency, periods):
    a, b = periods[0], periods[-1]
    text = VARIANT_TEXT[frequency].format(a=a[:4], b=b[:4])
    return re.sub(r'^.*?까지\s*', text + ' ', query, count=1)


def main():
    inventory = read(BASE / 'inventory.json')
    labels = label_map()
    types = inventory['types']
    order = sorted(types, key=lambda t: hashlib.sha256(t['type_id'].encode()).hexdigest())
    dev = {t['type_id'] for t in order[:14]}

    cases, oracles, seq = [], {}, 0

    def emit(mode, type_id, split_group, input_, expected, tags, eligible=True):
        nonlocal seq
        seq += 1
        case = {
            'id': f'SBE-{seq:04d}', 'schema_version': '1.0', 'mode': mode,
            'split': 'dev' if split_group in dev else 'test', 'group_id': split_group,
            'tier': split_group_tier(split_group), 'tags': tags,
            'input': input_, 'expected': expected,
            'evidence': evidence_of(split_group),
            'eligible_for_scoring': eligible,
            'qualitative_applicable': list(QUALITATIVE) if mode == 'query_output' else list(QUALITATIVE) + ['completeness', 'source_limits'],
            'review': {'human_approved': False, 'reviewer': None},
        }
        cases.append(case)
        return case

    def split_group_tier(type_id):
        return next(t['tier'] for t in types if t['type_id'] == type_id)

    def evidence_of(type_id):
        item = next(t for t in types if t['type_id'] == type_id)
        return {'research_type_id': type_id, **item['source'], 'scope_note': item['scope_note']}

    # 1) base: 36 types x graph/table = 72
    for item in sorted(types, key=lambda t: t['type_id']):
        type_id, frequency = item['type_id'], item['frequency']
        periods = periods_between(*BASE_PERIODS[frequency], frequency)
        for kind, tag in (('graph', 'graph'), ('table', 'table')):
            query = item['queries'][kind]
            if not query:
                raise ValueError(f'{type_id}: missing {kind} query')
            if item['tier'] == 'C':
                expected = {'decision': 'unresolved_probe', 'output_kind': kind,
                            'series': item['expected_series'], 'periods': periods, 'oracle_sha256': None,
                            'reason': 'research could not confirm this target; not a gold answer'}
                emit('query_output', type_id, type_id,
                     {'query': query, 'reference_date': REFERENCE_DATE, 'prior_turns': [], 'actions': confirm(periods, frequency)},
                     expected, [tag, frequency, 'probe'], eligible=False)
                continue
            refs = [series_ref(s['table_id'], s['item_id'], s['classifications'], s['frequency'], labels)
                    for s in item['expected_series']]
            numeric = item['tier'] == 'A'
            expected = {'decision': 'resolved', 'output_kind': kind,
                        'series': item['expected_series'], 'periods': periods, 'oracle_sha256': None,
                        'numeric_scored': numeric}
            if numeric:
                entry = oracle_entry(select(refs, periods), labels)
                oracles[f'SBE-{seq + 1:04d}'] = entry
                expected['oracle_sha256'] = digest_value(entry)
            emit('query_output', type_id, type_id,
                 {'query': query, 'reference_date': REFERENCE_DATE, 'prior_turns': [], 'actions': []},
                 expected, [tag, frequency])

    # 2) period variants: 12 (M4/Q4/A4)
    by_freq = {}
    for item in sorted(types, key=lambda t: t['type_id']):
        if item['tier'] != 'C':
            by_freq.setdefault(item['frequency'], []).append(item)
    picks = [('M', i) for i in range(4)] + [('Q', i) for i in range(4)] + [('A', i % 2) for i in range(4)]
    seen = {}
    for frequency, offset in picks:
        pool = by_freq[frequency]
        item = pool[(seen.get(frequency, -1) + 1 + offset) % len(pool)]
        seen[frequency] = pool.index(item)
        periods = periods_between(*VARIANT_PERIODS[frequency], frequency)
        refs = [series_ref(s['table_id'], s['item_id'], s['classifications'], s['frequency'], labels)
                for s in item['expected_series']]
        numeric = item['tier'] == 'A'
        expected = {'decision': 'resolved', 'output_kind': 'graph', 'variant_of': f'{item["type_id"]}',
                    'series': item['expected_series'], 'periods': periods, 'oracle_sha256': None,
                    'numeric_scored': numeric}
        if numeric:
            entry = oracle_entry(select(refs, periods), labels)
            oracles[f'SBE-{seq + 1:04d}'] = entry
            expected['oracle_sha256'] = digest_value(entry)
        emit('query_output', item['type_id'], item['type_id'],
             {'query': rewrite_period(item['queries']['graph'], frequency, periods),
              'reference_date': REFERENCE_DATE, 'prior_turns': [], 'actions': confirm(periods, frequency)},
             expected, ['graph', frequency, 'period_variant'])

    # 3) derived: 1 difference + 7 growth/yoy
    rate = next(t for t in types if t['type_id'] == 'RATE-03')
    big, small = rate['expected_series']
    difference_refs = [series_ref(s['table_id'], s['item_id'], s['classifications'], s['frequency'], labels) for s in (big, small)]
    difference_periods = periods_between(*BASE_PERIODS['M'], 'M')
    for ref in difference_refs:
        ref['selected'] = set(difference_periods)
    difference = calculate({p: difference_refs[0]['points'][p] for p in difference_periods}, 'difference', 'M')
    difference_oracle = {
        'sources': [{k: r[k] for k in ('table_id', 'item_id', 'classifications', 'frequency', 'unit', 'label')} for r in difference_refs],
        'operation': 'difference', 'points': [{'period': p, 'value': v} for p, v in difference.items()],
        'source': {r['table_id']: {'file_sha256': r['file_sha256'], 'lst_chn_de': r['lst_chn_de']} for r in difference_refs},
    }
    oracles[f'SBE-{seq + 1:04d}'] = difference_oracle
    emit('derived', 'RATE-03', 'RATE-03',
         {'query': '2023년 1월부터 2025년 12월까지 예금은행 대출금리(신규취급액 기준)에서 대기업대출과 중소기업대출의 금리차를 월별로 계산해 보여줘.',
          'reference_date': REFERENCE_DATE, 'prior_turns': [], 'actions': []},
         {'decision': 'resolved', 'operation': 'difference', 'sources': rate['expected_series'],
          'periods': difference_periods, 'oracle_sha256': digest_value(difference_oracle)},
         ['derived', 'difference', 'M'])

    growth_picks = [('CSI-01', 'growth'), ('PRICE-01', 'yoy'), ('BOP-01', 'growth'),
                    ('GDP-01', 'yoy'), ('CREDIT-01', 'growth'), ('PAY-03', 'yoy'), ('FIRM-01', 'growth')]
    for type_id, operation in growth_picks:
        item = next(t for t in types if t['type_id'] == type_id)
        frequency = item['frequency']
        periods = periods_between(*BASE_PERIODS[frequency], frequency)
        refs = [series_ref(s['table_id'], s['item_id'], s['classifications'], s['frequency'], labels)
                for s in item['expected_series']]
        points = {p: refs[0]['points'][p] for p in periods}
        computed = calculate(points, operation, frequency)
        entry = {'sources': [{k: r[k] for k in ('table_id', 'item_id', 'classifications', 'frequency', 'unit', 'label')} for r in refs],
                 'operation': operation, 'points': [{'period': p, 'value': v} for p, v in computed.items()],
                 'source': {refs[0]['table_id']: {'file_sha256': refs[0]['file_sha256'], 'lst_chn_de': refs[0]['lst_chn_de']}}}
        oracles[f'SBE-{seq + 1:04d}'] = entry
        text = '전년 동기 대비 증감률' if operation == 'yoy' else '전기 대비 증감률'
        emit('derived', type_id, type_id,
             {'query': f'{period_text(periods, frequency)} {topic_of(item)} {text}로 계산해 보여줘.',
              'reference_date': REFERENCE_DATE, 'prior_turns': [], 'actions': []},
             {'decision': 'resolved', 'operation': operation, 'sources': item['expected_series'],
              'periods': periods, 'oracle_sha256': digest_value(entry)},
             ['derived', operation, frequency])

    # 4) report: 12 (chart_brief 6 / interpret 4 / conversation 2)
    resolved = [c for c in cases if c['mode'] == 'query_output' and c['expected']['decision'] == 'resolved'
                and c['expected']['output_kind'] == 'graph' and c['tier'] == 'A']
    if len(resolved) < 12:
        resolved = [c for c in cases if c['mode'] == 'query_output' and c['expected']['decision'] == 'resolved'
                    and c['expected']['output_kind'] == 'graph']
    report_kinds = ['chart_brief'] * 6 + ['interpret'] * 4 + ['conversation'] * 2
    for index, kind in enumerate(report_kinds):
        source = resolved[index % len(resolved)]
        instruction = {
            'chart_brief': '이 그래프를 보도자료에 넣을 짧은 설명 초안으로 정리해줘.',
            'interpret': '이 자료를 근거로 보고서 본문 초안을 작성하고, 인용한 수치와 출처를 함께 표시해줘.',
            'conversation': '이 그래프에서 최근 두 시점의 변화만 짧게 설명해줘.',
        }[kind]
        expected = {'decision': 'resolved', 'base_case_id': source['id'], 'report_kind': kind,
                    'series': source['expected']['series'], 'periods': source['expected']['periods'],
                    'revision': 0, 'require_citations': kind == 'interpret', 'oracle_sha256': None}
        emit('report', source['group_id'], source['group_id'],
             {'query': instruction, 'reference_date': REFERENCE_DATE, 'prior_turns': [],
              'base_case_id': source['id'], 'actions': [{'kind': 'report', 'report_kind': kind}]},
             expected, ['report', kind, source['tier']])

    # 5) follow_up: 8
    follow_pool = [c for c in cases if c['mode'] == 'query_output' and c['expected']['decision'] == 'resolved'
                   and c['expected']['output_kind'] == 'graph' and c['tier'] == 'A']
    for index in range(8):
        source = follow_pool[index % len(follow_pool)]
        frequency = source['tags'][1]
        periods = periods_between(*VARIANT_PERIODS[frequency], frequency)
        expected = {'decision': 'resolved', 'base_case_id': source['id'],
                    'series': source['expected']['series'], 'periods': periods,
                    'preserved': ['table_ids', 'frequency'], 'oracle_sha256': None}
        emit('follow_up', source['group_id'], source['group_id'],
             {'query': '방금 자료를 다른 기간으로 다시 보여줘: ' + period_text(periods, frequency),
              'reference_date': REFERENCE_DATE,
              'prior_turns': [{'role': 'user', 'text': source['input']['query']},
                              {'role': 'assistant', 'text': '요청하신 통계표를 찾아 조회했습니다.'}],
              'base_case_id': source['id'], 'actions': []},
             expected, ['follow_up', frequency])

    # 6) edit: 8 (2 each)
    edit_ops = [('set_title', "제목을 '한국은행 통계'로 바꿔줘.", {'title': '한국은행 통계'}),
                ('set_title', "제목을 '월별 추이'로 바꿔줘.", {'title': '월별 추이'}),
                ('set_legend', '범례를 숨겨줘.', {'legend': False}),
                ('set_legend', '범례를 숨겨줘.', {'legend': False}),
                ('set_transform', '전기 대비 증감률로 바꿔줘.', {'transform': 'growth_rate'}),
                ('set_transform', '전년 동기 대비 증감률로 바꿔줘.', {'transform': 'year_over_year'}),
                ('filter_period', '최근 12개 시점만 남겨줘.', {'recent': 12}),
                ('filter_period', '최근 8개 시점만 남겨줘.', {'recent': 8})]
    for index, (operation, instruction, state) in enumerate(edit_ops):
        source = follow_pool[(index + 3) % len(follow_pool)]
        emit('edit', source['group_id'], source['group_id'],
             {'query': instruction, 'reference_date': REFERENCE_DATE, 'prior_turns': [],
              'base_case_id': source['id'], 'actions': [{'kind': 'edit', 'operation': operation}]},
             {'decision': 'resolved', 'base_case_id': source['id'], 'operation': operation,
              'expected_state': state, 'periods': source['expected']['periods']},
             ['edit', operation])

    for case in cases:
        if case['mode'] in ('report', 'follow_up', 'edit') and case['expected'].get('base_case_id'):
            base_case = next(c for c in cases if c['id'] == case['expected']['base_case_id'])
            case['split'] = base_case['split']
    public = [c for c in cases if c['split'] in ('dev', 'test')]
    dev_cases = [c for c in public if c['split'] == 'dev']
    test_cases = [c for c in public if c['split'] == 'test']
    holdout_window = {'M': ('202201', '202212'), 'Q': ('2022Q1', '2022Q4'), 'A': ('2019', '2021')}
    holdout_types = [t for t in sorted(types, key=lambda t: t['type_id']) if t['tier'] != 'C']
    holdout = []
    for item in holdout_types:
        periods = periods_between(*holdout_window[item['frequency']], item['frequency'])
        holdout.append({'id': f'SBH-{len(holdout) + 1:04d}', 'mode': 'query_output', 'output_kind': 'graph',
                        'query': rewrite_period(item['queries']['graph'], item['frequency'], periods),
                        'prior_turns': [], 'reference_date': REFERENCE_DATE})
    for item in holdout_types[:7]:
        periods = periods_between(*holdout_window[item['frequency']], item['frequency'])
        holdout.append({'id': f'SBH-{len(holdout) + 1:04d}', 'mode': 'query_output', 'output_kind': 'table',
                        'query': rewrite_period(item['queries']['table'], item['frequency'], periods),
                        'prior_turns': [], 'reference_date': REFERENCE_DATE})
    write_rows(BASE / 'cases' / 'dev.jsonl', dev_cases)
    write_rows(BASE / 'cases' / 'test.jsonl', test_cases)
    write_rows(BASE / 'cases' / 'holdout_queries.jsonl', holdout)
    wanted = {}
    for case in public:
        if case['mode'] == 'query_output' and case['eligible_for_scoring']:
            for series in case['expected']['series']:
                wanted.setdefault((series['table_id'], series['item_id'], series['frequency']), set()).update(
                    case['expected']['periods'])
    provider = {}
    for (table_id, item_id, frequency), periods in sorted(wanted.items()):
        table = table_index(table_id)
        low, high = min(periods), max(periods)
        for key, slot in table['rows'].items():
            if key[0] != item_id or key[2] != frequency:
                continue
            classes = slot['classes']
            provider_key = (table_id, item_id, json.dumps(classes, sort_keys=True), frequency)
            provider[provider_key] = {
                'table_id': table_id, 'item_id': item_id, 'classifications': classes,
                'frequency': frequency, 'unit': slot['unit'],
                'label': labels.get((table_id, item_id, json.dumps(classes, sort_keys=True)), f'{table_id} {item_id}'),
                'points': [{'period': p, 'value': v} for p, v in sorted(slot['points'].items()) if low <= p <= high],
            }
    CACHE.mkdir(parents=True, exist_ok=True)
    write(CACHE / 'oracles.json', {'schema_version': '1.0', 'reference_date': REFERENCE_DATE,
                                   'cases': oracles})
    write(CACHE / 'provider.json', {'schema_version': '1.0', 'reference_date': REFERENCE_DATE,
                                    'series': list(provider.values())})
    print(json.dumps({'cases': len(public), 'dev': len(dev_cases), 'test': len(test_cases),
                      'holdout_queries': len(holdout), 'oracles': len(oracles),
                      'modes': {m: sum(c['mode'] == m for c in public) for m in
                                ('query_output', 'derived', 'report', 'follow_up', 'edit')}}, ensure_ascii=False))


def topic_of(item):
    query = item['queries']['graph']
    return re.sub(r'^.*?까지\s*', '', query).split(' 자료를')[0]


def period_text(periods, frequency):
    first, last = periods[0], periods[-1]
    if frequency == 'M':
        return f'{first[:4]}년 {int(first[4:])}월부터 {last[:4]}년 {int(last[4:])}월까지'
    if frequency == 'Q':
        return f'{first[:4]}년 {first[-1]}분기부터 {last[:4]}년 {last[-1]}분기까지'
    return f'{first}년부터 {last}년까지'


def iso_periods(periods, frequency):
    first, last = periods[0], periods[-1]
    if frequency == 'M':
        return f'{first[:4]}-{first[4:]}-01', f'{last[:4]}-{last[4:]}-31'
    if frequency == 'Q':
        months = {'1': ('01', '03'), '2': ('04', '06'), '3': ('07', '09'), '4': ('10', '12')}
        return f'{first[:4]}-{months[first[-1]][0]}-01', f'{last[:4]}-{months[last[-1]][1]}-31'
    return f'{first}-01-01', f'{last}-12-31'


def confirm(periods, frequency):
    start, end = iso_periods(periods, frequency)
    return [{'kind': 'confirm_period', 'start': start, 'end': end}]


if __name__ == '__main__':
    main()
