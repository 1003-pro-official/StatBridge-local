"""Validate the public paired dataset without running or importing the product."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

DATASET = Path(__file__).resolve().parents[1]
ROOT = DATASET.parents[2]
SOURCE_NAMES = (
    'eval/min-e2e/v1.1/질의와_정답_40문항.md',
    'eval/min-e2e/v1.1/질의_유형_분류_정확도_20문항.md',
)
CATEGORY = {'DA': 'data_accuracy', 'CQ': 'clarification', 'QT': 'query_type'}
SLOTS = {
    1: ['loan_rate_basis'], 2: ['m2_balance_basis'], 3: ['m2_adjustment'],
    4: ['gdp_price_basis'], 5: ['gdp_adjustment'], 6: ['currency_basis'],
    7: ['esi_series'], 8: ['start_month', 'end_month'],
    9: ['change_comparison_basis'], 10: ['annual_aggregation_method'],
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def load_baseline():
    result = {}
    for name in SOURCE_NAMES:
        for line in (ROOT / name).read_text(encoding='utf-8').splitlines():
            match = re.match(r'\| ((?:DA3|CQ1|QT1)-\d{2}) ', line)
            if match:
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                result[match[1]] = {'query': cells[1], 'answer': cells[2]}
    require(len(result) == 60, 'baseline must have 60 distinct IDs')
    return result


def validate_content(cases, questions, baseline, document):
    require(len(cases) == 60, 'expected 60 cases')
    ids = {f'{group}21-{n:02}' for group in CATEGORY for n in range(1, 21)}
    require({c['id'] for c in cases} == ids, 'case IDs must be complete and unique')
    require(len({re.sub(r'\s+', '', c['query']) for c in cases}) == 60, 'duplicate query')
    require(Counter(c['category'] for c in cases) == dict.fromkeys(CATEGORY.values(), 20), 'category counts')
    require({c['baseline_id'] for c in cases} == set(baseline), 'baseline mapping must be one-to-one')
    for case in cases:
        cid = case['id']
        group, number = cid[:2], int(cid[-2:])
        prefix = {'DA': 'DA3', 'CQ': 'CQ1', 'QT': 'QT1'}[group]
        require(case['baseline_id'] == f'{prefix}-{number:02}', f'{cid}: paired ID')
        old = baseline[case['baseline_id']]
        require(case['category'] == CATEGORY[group], f'{cid}: category')
        require(case['difficulty'] == 'hard' and case['evaluation_status'] == 'not_run', f'{cid}: status')
        require(case['review'] == {'ai_assisted': True, 'human_approved': False}, f'{cid}: review')
        require(case['query'].strip() and case['query'] != old['query'], f'{cid}: query must be rewritten')
        require('\n' not in case['query'] and '|' not in case['query'], f'{cid}: query formatting')
        require(case['difficulty_rationale'].strip(), f'{cid}: missing rationale')
        factors = case['difficulty_factors']
        codes = {factor['code'] for factor in factors}
        require(len(codes) >= 2 and len(codes) == len(factors) and codes <= set('PDNQIM'), f'{cid}: difficulty factors')
        for factor in factors:
            require(factor['evidence'].strip() and factor['evidence'] in case['query'], f'{cid}: evidence must occur in query')
        expected = case['expected']
        if cid != 'CQ21-16':
            require(expected['answer'] == old['answer'], f'{cid}: baseline answer changed')
        if group == 'DA':
            require(expected['numeric_reference'] == 'v1.1_public_snapshot', f'{cid}: numeric provenance')
        elif group == 'CQ':
            require(expected['clarification_required'] is (number <= 10), f'{cid}: clarification label')
            require(expected['required_slots'] == SLOTS.get(number, []), f'{cid}: required slots')
            if number == 16:
                require(expected['latest_period_policy'] == 'resolve_from_actual_series_at_execution_time', 'latest period policy')
                require(set(re.findall(r'202[0-9]{3}', expected['answer'])) <= {'202401'}, 'latest month must not be hard-coded')
        else:
            label = re.search(r'`(general|derived)`', old['answer'])[1]
            require(expected['label'] == label, f'{cid}: query type label changed')
    require(Counter(c['expected']['label'] for c in cases if c['category'] == 'query_type') == {'general': 10, 'derived': 10}, 'query type balance')
    require(len(questions) == 60 and {q['id'] for q in questions} == ids, 'question IDs must be complete and unique')
    by_id = {c['id']: c for c in cases}
    for question in questions:
        require(set(question) == {'id', 'query'}, 'question input contains extra fields / answer leakage')
        require(question['query'] == by_id[question['id']]['query'], 'question copy differs')
    doc_rows = {}
    mapping_rows = {}
    for line in document.splitlines():
        match = re.match(r'\| ((?:DA|CQ|QT)21-\d{2}) ', line)
        if not match:
            continue
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        if ' · ' in cells[0]:
            require(len(cells) == 3 and match[1] not in doc_rows, 'document case formatting')
            doc_rows[match[1]] = cells
        else:
            require(len(cells) == 4 and match[1] not in mapping_rows, 'document mapping formatting')
            mapping_rows[match[1]] = cells
    require(set(doc_rows) == ids and set(mapping_rows) == ids, 'document must contain 60 cases and 60 mappings')
    for case in cases:
        require(doc_rows[case['id']][1:] == [case['query'], case['expected']['answer']], 'document differs from cases')
        require(mapping_rows[case['id']][1] == case['baseline_id'], 'document baseline mapping differs')
        require(mapping_rows[case['id']][3] == case['difficulty_rationale'], 'document rationale differs')


def main():
    cases = load_jsonl(DATASET / 'cases.jsonl')
    questions = load_jsonl(DATASET / 'questions.jsonl')
    validate_content(cases, questions, load_baseline(), (DATASET / '질의와_정답_60문항.md').read_text(encoding='utf-8'))
    manifest = json.loads((DATASET / 'manifest.json').read_text(encoding='utf-8'))
    require(manifest['version'] == '2.1' and manifest['family'] == 'min-e2e' and manifest['total'] == 60, 'manifest identity')
    require(manifest['counts'] == dict.fromkeys(CATEGORY.values(), 20), 'manifest counts')
    require(manifest['evaluation_status'] == 'not_run' and manifest['review_status'] == 'human_review_pending', 'manifest status')
    require(set(manifest['baseline_sha256']) == set(SOURCE_NAMES), 'baseline hash paths')
    require(set(manifest['sha256']) == {'cases.jsonl', 'questions.jsonl', '질의와_정답_60문항.md'}, 'dataset hash paths')
    for name, digest in manifest['baseline_sha256'].items():
        require(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, f'baseline hash mismatch: {name}')
    for name, digest in manifest['sha256'].items():
        require(hashlib.sha256((DATASET / name).read_bytes()).hexdigest() == digest, f'dataset hash mismatch: {name}')
    print('VALIDATION OK: 60 cases; 20/20/20; 10:10 clarification and query-type labels; 60 baseline pairs; question-only input; document and SHA-256 integrity')
    print('Design validation only; product evaluation not run; human review pending.')


if __name__ == '__main__':
    main()
