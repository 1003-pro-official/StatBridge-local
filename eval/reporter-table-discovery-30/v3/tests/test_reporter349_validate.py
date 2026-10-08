"""Mutation checks for the full 349-table metadata and query audit."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

DATASET = Path(__file__).resolve().parents[1]
ROOT = DATASET.parents[2]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, DATASET / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load('reporter349_validate', 'validate.py')
builder = load('reporter349_build', 'build.py')


@pytest.fixture(scope='module')
def data():
    cases = [json.loads(line) for line in (DATASET/'statbridge-reporter349.jsonl').read_text(encoding='utf8').splitlines()]
    catalog = json.loads((ROOT/'src/agent/stat_dictionary/stat_language_dictionary.json').read_text(encoding='utf-8-sig'))
    manifest = json.loads((DATASET/'dataset_manifest.json').read_text(encoding='utf8'))
    base = [json.loads(line) for line in (DATASET.parent/'v2/statbridge-reporter30.jsonl').read_text(encoding='utf8').splitlines()]
    return cases, catalog, manifest, base


def test_every_case_and_all_table_lanes_are_audited(data):
    result = validator.audit(*data)
    assert result['valid'], result['errors']
    assert result['checked_cases'] == 1104
    assert result['coverage'] == {'single_table':349, 'multi_table':349, 'multi_classification':348}
    assert result['metadata_summary']['series'] == 1782
    assert [x['table_id'] for x in result['classification_exceptions']] == ['DT_404Y017']
    assert result['warning_count'] == 318


@pytest.mark.parametrize('field,bad', [('item_id','UNKNOWN'),('frequency','D'),('period_end','209912')])
def test_wrong_item_frequency_or_period_is_rejected(data, field, bad):
    cases, catalog, _, _ = data
    case = copy.deepcopy(next(c for c in cases if c['augmentation']['kind']=='single_table'))
    case['workflow_gold']['classification_and_plan']['series'][0][field] = bad
    with pytest.raises(ValueError):
        validator.validate_cases([case], catalog)


def test_classification_code_and_label_cannot_be_forged(data):
    cases, catalog, _, _ = data
    case = copy.deepcopy(next(c for c in cases if c['augmentation']['kind']=='multi_classification'))
    plan = case['workflow_gold']['classification_and_plan']['series'][0]
    param = next(iter(plan['classifications']))
    plan['classifications'][param] = 'NOT_A_CATALOG_CODE'
    with pytest.raises(ValueError, match='invalid classification code'):
        validator.validate_cases([case], catalog)


def test_one_missing_series_cannot_pass(data):
    cases, catalog, _, _ = data
    case = copy.deepcopy(next(c for c in cases if c['augmentation']['kind']=='multi_table'))
    case['workflow_gold']['classification_and_plan']['series'].pop()
    with pytest.raises(ValueError, match='series count'):
        validator.validate_cases([case], catalog)


def test_missing_table_coverage_is_rejected(data):
    cases, catalog, manifest, base = data
    changed = [c for c in cases if c['id'] != 'R349-SINGLE-DT_101Y001']
    result = validator.audit(changed, catalog, manifest, base)
    assert not result['valid']
    assert any('349' in x['error'] for x in result['errors'])


def test_requested_label_removed_from_query_is_rejected(data):
    cases, catalog, manifest, base = data
    changed = copy.deepcopy(cases)
    case = next(c for c in changed if c['augmentation']['kind']=='multi_classification')
    param = case['augmentation']['varying_dimension']
    label = case['workflow_gold']['classification_and_plan']['series'][1]['classification_labels'][param]
    case['query'] = case['query'].replace(label, '알 수 없는 값')
    result = validator.audit(changed, catalog, manifest, base)
    assert not result['valid']
    assert any(x['error']=='Classification label missing from query' for x in result['errors'])


def test_original_v2_gold_cannot_silently_change(data):
    cases, catalog, manifest, base = data
    changed = copy.deepcopy(cases)
    changed[0]['query'] += ' 변형'
    result = validator.audit(changed, catalog, manifest, base)
    assert not result['valid']
    assert any('Original v2' in x['error'] for x in result['errors'])


def test_build_is_reproducible_and_does_not_use_predictions(data, tmp_path, monkeypatch):
    monkeypatch.setattr(builder, 'DATASET', tmp_path)
    builder.build()
    assert (tmp_path/'statbridge-reporter349.jsonl').read_bytes() == (DATASET/'statbridge-reporter349.jsonl').read_bytes()
    manifest = json.loads((tmp_path/'dataset_manifest.json').read_text(encoding='utf8'))
    assert manifest['runtime_prediction_used_to_create_gold'] is False
    source = (DATASET/'scripts/build.py').read_text(encoding='utf8')
    assert 'from agent_runtime import' not in source and 'import bridge_api' not in source


def test_annual_api_code_comes_from_catalog_api_params(data):
    cases, catalog, manifest, _ = data
    assert {x['table_id'] for x in manifest['api_frequency_aliases']} == {'DT_284Y001','DT_284Y002'}
    for tid in ['DT_284Y001','DT_284Y002']:
        case = next(c for c in cases if c['id']=='R349-SINGLE-'+tid)
        assert case['workflow_gold']['classification_and_plan']['series'][0]['exact_params']['prdSe']=='Y'
        validator.validate_cases([case], catalog)


def test_incompatible_catalog_and_api_frequency_is_rejected(data):
    _, catalog, _, _ = data
    changed = copy.deepcopy(catalog)
    changed['tables'][0]['api_call_params']['prdSe'] = 'Q'
    errors, _ = validator.audit_catalog(changed)
    assert any(x['error']=='Incompatible catalog/API frequencies' for x in errors)
