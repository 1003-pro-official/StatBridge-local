"""Build the private, fixed-data BOK E2E v2 ZIP from local public research inputs."""
import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from core import digest, expand_queries, extract_series, periods, write_json, write_jsonl

HERE = Path(__file__).resolve().parent
REPO = next((parent for parent in HERE.parents
             if (parent / 'research/kosis-bok-reproduction/질의집.jsonl').is_file()), HERE.parent)
CACHE_OUT = REPO / '.venv/cache/kosis-bok-reproduction/evaluation-v2'
METADATA = ('bok_table_master.csv', 'bok_items.csv', 'bok_classifications.csv',
            'bok_periods.csv', 'bok_comments.csv', 'bok_sources.csv')


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def publication_id(source):
    import re
    match = re.search(r'nttId=(\d+)', source.get('url', ''))
    return match.group(1) if match else ''


def make_inputs(root):
    root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / 'research/kosis-bok-reproduction/질의집.jsonl', root / 'queries.jsonl')
    shutil.copy2(REPO / 'research/kosis-bok-reproduction/재현매핑.csv', root / 'mapping.csv')
    shutil.copy2(REPO / 'eval/bok-reproduction/v1/audit.jsonl', root / 'audit.jsonl')
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip() or 'unrecorded'
    (root / 'product_revision.txt').write_text(revision + '\n', encoding='utf-8')
    for name in METADATA:
        (root / 'processed').mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / 'data/processed' / name, root / 'processed' / name)
    table_ids = {series['table_id'] for case in read_jsonl(root / 'queries.jsonl')
                 for series in case.get('expected_parameters', [])}
    for table_id in sorted(table_ids):
        matches = list((REPO / 'data/tables').glob(table_id + '*.csv'))
        if not matches:
            continue
        target = root / 'tables'
        target.mkdir(parents=True, exist_ok=True)
        for path in matches:
            shutil.copy2(path, target / path.name)
    attachment_root = root / 'pdfs'
    attachment_root.mkdir(exist_ok=True)
    for row in read_jsonl(root / 'queries.jsonl'):
        source = row.get('source', {})
        expected = source.get('sha256')
        if not expected or any(sha(path) == expected for path in attachment_root.glob('*.pdf')):
            continue
        release = REPO / '.venv/cache/kosis-bok-reproduction/releases' / row['source_id']
        for path in release.glob('*.pdf'):
            if sha(path) == expected:
                shutil.copy2(path, attachment_root / (expected + '.pdf'))
                break
    return root


def build(output_zip, product_revision, input_root=None):
    output_zip = Path(output_zip).resolve()
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bok-e2e-v2-') as temp:
        stage = Path(temp) / 'bundle'
        stage.mkdir()
        source_inputs = Path(input_root).resolve() if input_root else make_inputs(stage / 'build_inputs')
        if input_root:
            shutil.copytree(source_inputs, stage / 'build_inputs', dirs_exist_ok=True)
        product_revision = (product_revision or
            ((source_inputs / 'product_revision.txt').read_text(encoding='utf-8').strip()
             if (source_inputs / 'product_revision.txt').exists() else 'unrecorded'))
        if product_revision == 'unrecorded' and not input_root:
            product_revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                                               capture_output=True, text=True).stdout.strip() or product_revision
        queries = read_jsonl(source_inputs / 'queries.jsonl')
        audited = read_jsonl(source_inputs / 'audit.jsonl')
        sources = []
        for row in audited:
            source = row.get('source', {})
            sources.append({'id': row['id'], 'publication_id': publication_id(source),
                            'title': row.get('title'), 'kind': row.get('kind'),
                            'url': source.get('url'), 'publication_date': source.get('publication_date'),
                            'sha256': source.get('sha256'), 'page': source.get('pdf_page'),
                            'human_approved': row.get('review', {}).get('human_approved', False)})
        source_ids = {row['publication_id'] for row in sources}
        cases = expand_queries(queries)
        provider_index = {}
        unit_by_code = {}
        with (source_inputs / 'processed/bok_classifications.csv').open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                if row.get('UNIT_NM'):
                    unit_by_code[row['ITM_ID']] = row['UNIT_NM']
        source_tables = {path.stem.split('__')[0]: path for path in (source_inputs / 'tables').glob('*.csv')}
        attachment_by_hash = {sha(path): path for path in (source_inputs / 'pdfs').glob('*.pdf')}
        extracted_by_identity = {}
        query_index = {row['id']: row for row in queries}
        for case in cases:
            original = query_index[case['logical_case_id']]
            why = []
            if case['source_id'] not in source_ids:
                why.append('source not found in 46-object audit register')
            targets = []
            for target in original.get('expected_parameters', []):
                contract = {key: target[key] for key in ('table_id', 'item_id', 'frequency', 'classifications')}
                contract['periods'] = periods(original['frequency'], original['period_text'])
                path = source_tables.get(contract['table_id'])
                if not path:
                    why.append('local CSV missing: ' + contract['table_id'])
                    continue
                identity = (contract['table_id'], contract['item_id'], json.dumps(
                    contract['classifications'], sort_keys=True), contract['frequency'],
                    tuple(contract['periods']))
                try:
                    if identity not in extracted_by_identity:
                        extracted_by_identity[identity] = extract_series(path, contract, unit_by_code)
                    extracted = extracted_by_identity[identity]
                except ValueError as exc:
                    why.append(str(exc))
                    continue
                targets.append(contract)
                contract['unit'] = extracted['unit']
                contract['label'] = extracted['label']
                provider_index[(extracted['table_id'], extracted['item_id'], json.dumps(
                    extracted['classifications'], sort_keys=True), extracted['frequency'])] = extracted
            if len(targets) != len(original.get('expected_parameters', [])):
                why.append('one or more required series failed fixture validation')
            if not targets:
                why.append('no validated series')
            attachment_hash = original.get('source', {}).get('sha256')
            attachment = attachment_by_hash.get(attachment_hash)
            if not attachment:
                why.append('reference PDF is missing or its SHA-256 does not match')
            else:
                rel = 'attachments/' + attachment.name
                (stage / 'attachments').mkdir(exist_ok=True)
                shutil.copy2(attachment, stage / rel)
                case['reference_attachments'] = [{'path': rel, 'sha256': attachment_hash,
                    'page': original.get('source_page'), 'caption': original.get('source_caption')}]
            case['expected'].update(decision='resolved', series_contracts=targets)
            case['status'] = 'runnable' if not why else 'blocked'
            case['blockers'] = sorted(set(why))
            case['review'] = {'human_approved': False, 'reviewer': None}
        oracles = {}
        for case in cases:
            if case['status'] != 'runnable':
                case['expected'].pop('series_contracts', None)
                case['expected']['decision'] = 'blocked'
                continue
            selected = []
            for contract in case['expected']['series_contracts']:
                key = (contract['table_id'], contract['item_id'], json.dumps(
                    contract['classifications'], sort_keys=True), contract['frequency'])
                series = provider_index[key]
                selected.append({key: value for key, value in series.items() if key != 'label'})
            oracles[case['id']] = selected
            case['expected']['oracle_sha256'] = digest(selected)
        write_json(stage / 'provider.json', {'vintage': 'local KOSIS CSV snapshot at build time',
                    'kosis_live_verified': False, 'series': list(provider_index.values())})
        write_json(stage / 'oracles.json', oracles)
        write_jsonl(stage / 'cases.jsonl', cases)
        write_jsonl(stage / 'source_register.jsonl', sources)
        write_json(stage / 'profiles.json', {'baseline': {'model': 'gpt-5.4', 'repeats': 1}})
        (stage / 'scripts').mkdir()
        for name in ('build.py', 'core.py', 'evaluate.py', 'adapter.py', 'validate_package.py'):
            source = HERE / name
            if source.exists():
                shutil.copy2(source, stage / 'scripts' / name)
        shutil.copy2(HERE.parent / 'README.md', stage / 'README.md')
        (stage / 'requirements.txt').write_text('playwright==1.55.0\n', encoding='utf-8')
        payload = sorted(path for path in stage.rglob('*') if path.is_file())
        manifest = {'dataset_version': '2.0', 'built_at': '2026-10-21',
                    'audited_source_count': len(sources), 'logical_query_count': len(queries),
                    'candidate_case_count': len(cases), 'case_count': len(cases),
                    'product_revision': product_revision, 'oracle_role': 'scorer_only',
                    'review_status': 'pending_human_approval',
                    'files': {path.relative_to(stage).as_posix(): sha(path) for path in payload}}
        write_json(stage / 'manifest.json', manifest)
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(stage.rglob('*')):
                if path.is_file():
                    archive.write(path, path.relative_to(stage).as_posix())
    return {'output': str(output_zip), 'cases': len(cases),
            'runnable': sum(c['status'] == 'runnable' for c in cases),
            'blocked': sum(c['status'] == 'blocked' for c in cases)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(CACHE_OUT / 'bok-e2e-v2.zip'))
    parser.add_argument('--product-revision')
    parser.add_argument('--input-root')
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.product_revision, args.input_root), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
