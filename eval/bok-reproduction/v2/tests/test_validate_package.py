import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))


def make_bundle(path, *, omit=(), tamper=None, unsafe_path=None):
    point = {'period': '202501', 'value': '1'}
    oracle = [{'table_id': 'T', 'item_id': 'I', 'classifications': {}, 'frequency': 'M',
               'unit': '%', 'points': [point]}]
    oracle_hash = hashlib.sha256(json.dumps(oracle, sort_keys=True, ensure_ascii=False,
                                             allow_nan=False).encode()).hexdigest()
    payload = {
        'README.md': b'BOK E2E v2',
        'profiles.json': b'{"baseline":{}}',
        'provider.json': json.dumps({'series': [
            {'table_id': 'T', 'item_id': 'I', 'classifications': {}, 'frequency': 'M',
             'unit': '%', 'points': [point]}]}).encode(),
        'oracles.json': json.dumps({'C1': oracle}).encode(),
        'cases.jsonl': b'',
        'source_register.jsonl': ''.join(
            json.dumps({'id': f'S{i}'}, separators=(',', ':')) + '\n'
            for i in range(1, 47)
        ).encode(),
        'scripts/build.py': b'# build',
        'scripts/core.py': b'# core',
        'scripts/evaluate.py': b'# evaluate',
        'scripts/adapter.py': b'# adapter',
        'scripts/validate_package.py': b'# validate',
        'requirements.txt': b'',
        'attachments/ref.png': b'fixture',
        'build_inputs/source_snapshot.json': b'{}',
    }
    payload['cases.jsonl'] = (
        json.dumps({'id': 'C1', 'source_id': 'S1', 'status': 'runnable',
                    'input': {'query': 'q'}, 'reference_attachments': [{
                        'path': 'attachments/ref.png',
                        'sha256': hashlib.sha256(payload['attachments/ref.png']).hexdigest()}],
                    'expected': {'decision': 'resolved', 'output_kind': 'graph',
                        'series_contracts': [{'table_id': 'T', 'item_id': 'I',
                            'classifications': {}, 'frequency': 'M', 'unit': '%',
                            'periods': ['202501']}], 'oracle_sha256': oracle_hash}},
                   separators=(',', ':')).encode() + b'\n'
    )
    files = {name: hashlib.sha256(data).hexdigest()
             for name, data in payload.items() if name not in omit}
    if tamper:
        payload[tamper] += b'changed'
    manifest = {
        'dataset_version': '2.0',
        'audited_source_count': 46,
        'case_count': 1,
        'product_revision': 'abc123',
        'oracle_role': 'scorer_only',
        'files': files,
    }
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in payload.items():
            if name not in omit:
                archive.writestr(name, data)
        if unsafe_path:
            archive.writestr(unsafe_path, b'unsafe')
        archive.writestr('manifest.json', json.dumps(manifest).encode())


def test_complete_self_contained_bundle_is_ready(tmp_path):
    from validate_package import inspect_bundle

    bundle = tmp_path / 'complete.zip'
    make_bundle(bundle)

    report = inspect_bundle(bundle)

    assert report['ready'] is True
    assert report['errors'] == []
    assert report['case_count'] == 1
    with zipfile.ZipFile(bundle) as archive:
        case = json.loads(archive.read('cases.jsonl'))
    assert case['input'] == {'query': 'q'}
    assert case['reference_attachments'][0]['path'] == 'attachments/ref.png'


@pytest.mark.parametrize('omit', ['provider.json', 'profiles.json', 'scripts/build.py', 'scripts/adapter.py',
                                 'build_inputs/source_snapshot.json'])
def test_missing_runtime_inputs_block_bundle(tmp_path, omit):
    from validate_package import inspect_bundle

    bundle = tmp_path / 'incomplete.zip'
    make_bundle(bundle, omit={omit})

    report = inspect_bundle(bundle)

    assert report['ready'] is False
    assert any((omit if not omit.startswith('build_inputs/') else 'build_inputs/') in error
               for error in report['errors'])


def test_tampered_artifact_and_unsafe_paths_are_rejected(tmp_path):
    from validate_package import inspect_bundle

    bundle = tmp_path / 'tampered.zip'
    make_bundle(bundle, tamper='provider.json', unsafe_path='../outside.txt')

    report = inspect_bundle(bundle)

    assert report['ready'] is False
    assert any('sha256 mismatch' in error for error in report['errors'])
    assert any('unsafe archive path' in error for error in report['errors'])


def test_attachment_hash_and_oracle_role_are_enforced(tmp_path):
    from validate_package import inspect_bundle

    bundle = tmp_path / 'invalid-attachment.zip'
    make_bundle(bundle)
    with zipfile.ZipFile(bundle) as source:
        members = {name: source.read(name) for name in source.namelist()}
    cases = json.loads(members['cases.jsonl'])
    cases['reference_attachments'][0]['sha256'] = '0' * 64
    members['cases.jsonl'] = (json.dumps(cases, separators=(',', ':')) + '\n').encode()
    manifest = json.loads(members['manifest.json'])
    manifest['files']['cases.jsonl'] = hashlib.sha256(members['cases.jsonl']).hexdigest()
    manifest['oracle_role'] = 'runner_visible'
    members['manifest.json'] = json.dumps(manifest).encode()
    with zipfile.ZipFile(bundle, 'w') as target:
        for name, data in members.items():
            target.writestr(name, data)

    report = inspect_bundle(bundle)

    assert report['ready'] is False
    assert any('attachment sha256 mismatch' in error for error in report['errors'])
    assert any('oracle must be scorer_only' in error for error in report['errors'])


def test_reference_attachments_are_rejected_inside_runner_input(tmp_path):
    from validate_package import inspect_bundle

    bundle = tmp_path / 'runner-attachment.zip'
    make_bundle(bundle)
    with zipfile.ZipFile(bundle) as source:
        members = {name: source.read(name) for name in source.namelist()}
    case = json.loads(members['cases.jsonl'])
    case['input']['setup'] = {'attachments': [{'path': 'attachments/ref.png'}]}
    members['cases.jsonl'] = (json.dumps(case, separators=(',', ':')) + '\n').encode()
    manifest = json.loads(members['manifest.json'])
    manifest['files']['cases.jsonl'] = hashlib.sha256(members['cases.jsonl']).hexdigest()
    members['manifest.json'] = json.dumps(manifest).encode()
    with zipfile.ZipFile(bundle, 'w') as target:
        for name, data in members.items():
            target.writestr(name, data)

    report = inspect_bundle(bundle)

    assert report['ready'] is False
    assert any('outside runner input' in error for error in report['errors'])


def test_runnable_case_needs_provider_coverage_and_independent_oracle(tmp_path):
    from validate_package import inspect_bundle

    bundle = tmp_path / 'incomplete-series.zip'
    make_bundle(bundle)
    with zipfile.ZipFile(bundle) as source:
        members = {name: source.read(name) for name in source.namelist()}
    provider = json.loads(members['provider.json'])
    provider['series'][0]['points'] = []
    members['provider.json'] = json.dumps(provider).encode()
    manifest = json.loads(members['manifest.json'])
    manifest['files']['provider.json'] = hashlib.sha256(members['provider.json']).hexdigest()
    members['manifest.json'] = json.dumps(manifest).encode()
    with zipfile.ZipFile(bundle, 'w') as target:
        for name, data in members.items():
            target.writestr(name, data)

    report = inspect_bundle(bundle)

    assert report['ready'] is False
    assert any('provider missing required series or periods' in error for error in report['errors'])


def test_bundle_with_no_runnable_cases_is_not_ready(tmp_path):
    from validate_package import inspect_bundle

    bundle = tmp_path / 'no-runnable.zip'
    make_bundle(bundle)
    with zipfile.ZipFile(bundle) as source:
        members = {name: source.read(name) for name in source.namelist()}
    case = json.loads(members['cases.jsonl'])
    case['status'] = 'blocked'
    members['cases.jsonl'] = (json.dumps(case, separators=(',', ':')) + '\n').encode()
    manifest = json.loads(members['manifest.json'])
    manifest['files']['cases.jsonl'] = hashlib.sha256(members['cases.jsonl']).hexdigest()
    manifest['files']['oracles.json'] = hashlib.sha256(b'{}').hexdigest()
    members['oracles.json'] = b'{}'
    members['manifest.json'] = json.dumps(manifest).encode()
    with zipfile.ZipFile(bundle, 'w') as target:
        for name, data in members.items():
            target.writestr(name, data)

    report = inspect_bundle(bundle)

    assert report['ready'] is False
    assert report['runnable_case_count'] == 0
    assert any('no runnable cases' in error for error in report['errors'])


def test_duplicate_provider_identity_is_rejected(tmp_path):
    from validate_package import inspect_bundle

    bundle = tmp_path / 'duplicate-provider.zip'
    make_bundle(bundle)
    with zipfile.ZipFile(bundle) as source:
        members = {name: source.read(name) for name in source.namelist()}
    provider = json.loads(members['provider.json'])
    provider['series'].append(provider['series'][0])
    members['provider.json'] = json.dumps(provider).encode()
    manifest = json.loads(members['manifest.json'])
    manifest['files']['provider.json'] = hashlib.sha256(members['provider.json']).hexdigest()
    members['manifest.json'] = json.dumps(manifest).encode()
    with zipfile.ZipFile(bundle, 'w') as target:
        for name, data in members.items():
            target.writestr(name, data)

    report = inspect_bundle(bundle)

    assert report['ready'] is False
    assert any('duplicate provider series identity' in error for error in report['errors'])


def test_case_source_id_may_reference_repeated_publication_id(tmp_path):
    from validate_package import inspect_bundle

    bundle = tmp_path / 'publication-source.zip'
    make_bundle(bundle)
    with zipfile.ZipFile(bundle) as source:
        members = {name: source.read(name) for name in source.namelist()}
    sources = [{'id': f'S{i}', 'publication_id': 'PUB1'} for i in range(1, 47)]
    members['source_register.jsonl'] = ''.join(json.dumps(row) + '\n' for row in sources).encode()
    case = json.loads(members['cases.jsonl'])
    case['source_id'] = 'PUB1'
    members['cases.jsonl'] = (json.dumps(case, separators=(',', ':')) + '\n').encode()
    manifest = json.loads(members['manifest.json'])
    manifest['files']['source_register.jsonl'] = hashlib.sha256(members['source_register.jsonl']).hexdigest()
    manifest['files']['cases.jsonl'] = hashlib.sha256(members['cases.jsonl']).hexdigest()
    members['manifest.json'] = json.dumps(manifest).encode()
    with zipfile.ZipFile(bundle, 'w') as target:
        for name, data in members.items():
            target.writestr(name, data)

    report = inspect_bundle(bundle)

    assert report['ready'] is True
