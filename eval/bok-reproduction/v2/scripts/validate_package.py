"""Validate a portable BOK E2E evaluation bundle without extracting it."""
import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import PurePosixPath


REQUIRED_FILES = {
    'README.md', 'manifest.json', 'profiles.json', 'provider.json', 'oracles.json',
    'cases.jsonl', 'source_register.jsonl', 'requirements.txt',
    'scripts/build.py', 'scripts/core.py', 'scripts/evaluate.py', 'scripts/adapter.py', 'scripts/validate_package.py',
}


def _json(data, path):
    try:
        return json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'invalid JSON in {path}: {exc}') from exc


def _jsonl(data, path):
    rows = []
    for line_no, line in enumerate(data.decode('utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f'invalid JSONL in {path}:{line_no}: {exc}') from exc
    return rows


def _safe_path(name):
    path = PurePosixPath(name)
    return bool(name) and '\\' not in name and '\x00' not in name and ':' not in path.parts[0] and not path.is_absolute() and all(
        part not in ('', '.', '..') for part in path.parts
    )


def _sha256(archive, info):
    digest = hashlib.sha256()
    with archive.open(info) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _attachments(case):
    return case.get('reference_attachments', [])


def _has_runner_attachment(value):
    if isinstance(value, dict):
        return any(key in {'attachment', 'attachments', 'reference_attachments'} or
                   _has_runner_attachment(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_has_runner_attachment(child) for child in value)
    return False


def _identity(series):
    return (
        series.get('table_id'), series.get('item_id'),
        json.dumps(series.get('classifications', {}), sort_keys=True), series.get('frequency'),
    )


def _contains_gold(value):
    if isinstance(value, dict):
        if set(value) & {'expected', 'oracle', 'oracle_sha256', 'answer_key'}:
            return True
        return any(_contains_gold(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_gold(child) for child in value)
    return False


def inspect_bundle(bundle_path):
    errors = []
    try:
        archive = zipfile.ZipFile(bundle_path)
    except (OSError, zipfile.BadZipFile) as exc:
        return {'ready': False, 'errors': [f'invalid ZIP: {exc}']}

    with archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            errors.append('duplicate archive paths')
        folded = [name.casefold() for name in names]
        if len(folded) != len(set(folded)):
            errors.append('case-insensitive duplicate archive paths')
        for info in infos:
            if not _safe_path(info.filename):
                errors.append(f'unsafe archive path: {info.filename}')
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                errors.append(f'symlink is not allowed: {info.filename}')

        by_name = {info.filename: info for info in infos if _safe_path(info.filename)}
        missing = sorted(REQUIRED_FILES - by_name.keys())
        if missing:
            errors.append('missing required files: ' + ', '.join(missing))
        if 'manifest.json' not in by_name:
            return {'ready': False, 'errors': errors}

        try:
            manifest = _json(archive.read(by_name['manifest.json']), 'manifest.json')
            files = manifest['files']
            if manifest.get('dataset_version') != '2.0':
                errors.append('dataset_version must be 2.0')
            if not isinstance(manifest.get('product_revision'), str) or not manifest['product_revision'].strip():
                errors.append('product_revision is required')
            if manifest.get('oracle_role') != 'scorer_only':
                errors.append('oracle must be scorer_only')
            payload_names = set(by_name) - {'manifest.json'}
            if set(files) != payload_names:
                errors.append('manifest files must list every payload file exactly once')
            if not any(name.startswith('build_inputs/') for name in payload_names):
                errors.append('build_inputs/ must contain the builder source data')
            for name, expected in files.items():
                if name not in by_name:
                    errors.append(f'manifest file is missing from ZIP: {name}')
                    continue
                if not _safe_path(name):
                    errors.append(f'unsafe manifest path: {name}')
                    continue
                if _sha256(archive, by_name[name]) != expected:
                    errors.append(f'sha256 mismatch: {name}')

            sources = _jsonl(archive.read(by_name['source_register.jsonl']), 'source_register.jsonl')
            source_ids = [row.get('id') for row in sources]
            if len(source_ids) != 46 or len(set(source_ids)) != 46 or not all(source_ids):
                errors.append('source_register.jsonl must contain 46 unique source IDs')
            case_source_ids = {row.get('publication_id') for row in sources if row.get('publication_id')}
            if not case_source_ids:
                case_source_ids = set(source_ids)
            if manifest.get('audited_source_count') != 46:
                errors.append('audited_source_count must be 46')

            cases = _jsonl(archive.read(by_name['cases.jsonl']), 'cases.jsonl')
            case_ids = [case.get('id') for case in cases]
            if len(case_ids) != len(set(case_ids)) or not all(case_ids):
                errors.append('cases.jsonl must contain unique non-empty case IDs')
            if manifest.get('case_count') != len(cases):
                errors.append('case_count does not match cases.jsonl')
            provider = _json(archive.read(by_name['provider.json']), 'provider.json')
            profiles = _json(archive.read(by_name['profiles.json']), 'profiles.json')
            oracles = _json(archive.read(by_name['oracles.json']), 'oracles.json')
            provider_series = provider.get('series', [])
            provider_identities = [_identity(series) for series in provider_series]
            if len(provider_identities) != len(set(provider_identities)):
                errors.append('duplicate provider series identity')
            provider_by_identity = dict(zip(provider_identities, provider_series))
            for series in provider_series:
                periods = [str(point.get('period')) for point in series.get('points', [])]
                if len(periods) != len(set(periods)):
                    errors.append(f"duplicate provider period: {series.get('table_id')}/{series.get('item_id')}")
            if not isinstance(profiles, dict) or not profiles:
                errors.append('profiles.json must contain at least one profile')
            if not isinstance(oracles, dict):
                errors.append('oracles.json must be an object keyed by case ID')
                oracles = {}
            runnable_ids = {case.get('id') for case in cases if case.get('status') == 'runnable'}
            if not runnable_ids:
                errors.append('no runnable cases')
            if set(oracles) != runnable_ids:
                errors.append('oracles.json keys must match runnable case IDs exactly')
            for case in cases:
                if case.get('source_id') not in case_source_ids:
                    errors.append(f"unknown source_id in case {case.get('id')}")
                if case.get('status') not in ('runnable', 'blocked'):
                    errors.append(f"invalid case status in {case.get('id')}")
                if not isinstance(case.get('input'), dict) or not isinstance(case.get('expected'), dict):
                    errors.append(f"case {case.get('id')} needs input and expected objects")
                if _contains_gold(case.get('input')):
                    errors.append(f"gold data must not be in runner input: {case.get('id')}")
                if _has_runner_attachment(case.get('input')):
                    errors.append(f"reference attachments must be outside runner input: {case.get('id')}")
                if case.get('status') == 'runnable':
                    expected = case['expected']
                    contracts = expected.get('series_contracts', [])
                    if expected.get('decision') != 'resolved' or expected.get('output_kind') not in ('table', 'graph') or not contracts:
                        errors.append(f"runnable case needs decision, output_kind, and series_contracts: {case.get('id')}")
                    oracle = oracles.get(case.get('id'))
                    if oracle is not None:
                        oracle_hash = hashlib.sha256(json.dumps(
                            oracle, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()
                        if expected.get('oracle_sha256') != oracle_hash:
                            errors.append(f"oracle sha256 mismatch: {case.get('id')}")
                        oracle_by_identity = {_identity(series): series for series in oracle}
                    else:
                        oracle_by_identity = {}
                    for contract in contracts:
                        identity = _identity(contract)
                        periods = contract.get('periods')
                        if (not contract.get('table_id') or not contract.get('item_id') or
                                not contract.get('unit') or not isinstance(periods, list) or not periods):
                            errors.append(f"incomplete series contract in case {case.get('id')}")
                            continue
                        provider = provider_by_identity.get(identity)
                        available_periods = {str(point.get('period')) for point in provider.get('points', [])} if provider else set()
                        if not provider or provider.get('unit') != contract.get('unit') or not set(map(str, periods)) <= available_periods:
                            errors.append(f"provider missing required series or periods: {case.get('id')}")
                        oracle_series = oracle_by_identity.get(identity)
                        oracle_periods = {str(point.get('period')) for point in oracle_series.get('points', [])} if oracle_series else set()
                        if not oracle_series or oracle_series.get('unit') != contract.get('unit') or oracle_periods != set(map(str, periods)):
                            errors.append(f"oracle series differs from contract: {case.get('id')}")
                for attachment in _attachments(case):
                    name = attachment.get('path')
                    if not isinstance(name, str) or name not in by_name:
                        errors.append(f"missing attachment in case {case.get('id')}: {name}")
                    elif _sha256(archive, by_name[name]) != attachment.get('sha256'):
                        errors.append(f"attachment sha256 mismatch in case {case.get('id')}: {name}")
        except (AttributeError, KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
            errors.append(str(exc))
            cases = []
            sources = []

    return {
        'ready': not errors and bool(cases),
        'errors': errors,
        'source_count': len(sources),
        'case_count': len(cases),
        'runnable_case_count': sum(case.get('status') == 'runnable' for case in cases),
        'blocked_case_count': sum(case.get('status') == 'blocked' for case in cases),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle')
    args = parser.parse_args()
    report = inspect_bundle(args.bundle)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
