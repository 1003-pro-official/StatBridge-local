"""Validate public frozen records offline without reading private or runtime data."""
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def ids(rows, count):
    result = [row['id'] for row in rows]
    require(len(result) == count and len(set(result)) == count, f'Expected {count} unique case IDs')
    return set(result)


def validate():
    manifest = load(BASE / 'publication-20261028.json')
    seen = set()
    source_hashes = {}
    for record in manifest['files']:
        relative = PurePosixPath(record['path'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe publication path')
        require(relative.parts[:2] == ('eval', 'min-e2e') or relative.as_posix() == 'tests/test_min_e2e_v21_dataset.py', 'Unexpected publication scope')
        require(not any('private' in part.lower() or part.lower().startswith('holdout') for part in relative.parts), 'Nonpublic path')
        require(record['path'] not in seen, 'Duplicate publication path')
        seen.add(record['path'])
        source_hashes[record['path']] = record['source_sha256']
        blob = ROOT.joinpath(*relative.parts).read_bytes()
        require(len(blob) == record['bytes'], f'Size mismatch: {relative}')
        require(b'\r\n' not in blob, f'Expected LF publication: {relative}')
        require(hashlib.sha256(blob).hexdigest() == record['sha256'], f'SHA-256 mismatch: {relative}')

    # v2 original and operational revision are separate, each with 60 questions.
    for name in ['original', 'dataset']:
        folder = BASE / 'v2' / name
        cases = load(folder / 'cases.json')['cases']
        questions = jsonl(folder / 'questions.jsonl')
        expected = ids(cases, 60)
        require(ids(questions, 60) == expected, 'v2 question/case mismatch')
        require(Counter(row['group'] for row in cases) == {'edit': 20, 'screen_file': 20, 'derived': 20}, 'v2 category counts')
        for row, question in zip(cases, questions):
            require(row['id'] == question['id'] and row['query'] == question['query'], 'v2 query drift')
            require(set(question) <= {'id', 'group', 'query', 'steps'}, 'v2 question contains scoring data')
            require(bool(row['answer']), 'v2 missing answer')
    for run in ['initial-20261027', 'patched-20261027']:
        require(ids(load(BASE / 'v2/records' / run / 'scores.json')['cases'], 60) == expected, 'v2 score IDs')

    cases = jsonl(BASE / 'v2.1/cases.jsonl')
    expected = ids(cases, 60)
    for run in ['initial-20261027', 'patched-20261027']:
        folder = BASE / 'v2.1/records' / run
        require(ids(load(folder / 'scores.json')['results'], 60) == expected, 'v2.1 score IDs')
        require(jsonl(folder / 'questions.jsonl') == jsonl(BASE / 'v2.1/questions.jsonl'), 'v2.1 execution query drift')

    folder = BASE / 'v1.4'
    questions = jsonl(folder / 'questions.jsonl')
    expected = ids(questions, 50)
    require(all(set(row) == {'id', 'query'} for row in questions), 'v1.4 question contains scoring data')
    for name in ['questions.md', 'answers.md']:
        found = set(re.findall(r'ME14-\d{2}', (folder / name).read_text(encoding='utf-8')))
        require(found == expected, f'v1.4 IDs in {name}')
    for name, digest in load(folder / 'manifest.json')['sha256'].items():
        require(Path(name).name == name, 'Unsafe v1.4 manifest path')
        require(source_hashes[f'eval/min-e2e/v1.4/{name}'] == digest, f'v1.4 original source hash: {name}')
    require(ids(load(folder / 'records/initial-20261027/scores.json')['results'], 50) == expected, 'v1.4 initial score IDs')
    require(ids(load(folder / 'records/patched-20261027/latest-results.json')['results'], 50) == expected, 'v1.4 patched score IDs')
    require(ids(load(folder / 'records/ME14-41-20261028/scores-v2.json')['results'], 1) == {'ME14-41'}, 'Clarified case scope')

    folder = BASE / 'v1.1/records/query-type-20261027'
    expected = ids(jsonl(folder / 'input/questions.jsonl'), 20)
    predictions = jsonl(folder / 'output/predictions.jsonl')
    require(ids(predictions, 20) == expected, 'v1.1 prediction IDs')
    summary = load(folder / 'output/summary.json')
    require(summary['total'] == 20 and summary['passed'] + summary['failed'] == 20, 'v1.1 summary counts')
    require(hashlib.sha256((folder / 'output/predictions.jsonl').read_bytes()).hexdigest() == summary['predictions_sha256'], 'v1.1 frozen predictions')
    print(f'PUBLICATION OK: {len(seen)} frozen source files; v1.1=20, v2=60+60, v2.1=60, v1.4=50+1')


if __name__ == '__main__':
    validate()
