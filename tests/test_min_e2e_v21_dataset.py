"""Public evaluation integrity: reject leakage and accidental label/reference drift."""
import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('min_e2e_v21_validator', ROOT / 'eval/min-e2e/v2.1/scripts/validate.py')
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


@pytest.fixture
def bundle():
    directory = VALIDATOR.DATASET
    return [VALIDATOR.load_jsonl(directory / 'cases.jsonl'),
            VALIDATOR.load_jsonl(directory / 'questions.jsonl'),
            VALIDATOR.load_baseline(),
            (directory / '질의와_정답_60문항.md').read_text(encoding='utf-8')]


def test_public_dataset_and_hashes_are_consistent():
    VALIDATOR.main()


@pytest.mark.parametrize('fault', ['answer_leak', 'label_flip', 'numeric_drift', 'duplicate_id',
                                  'duplicate_factor', 'missing_evidence', 'question_drift', 'slot_drift', 'doc_drift'])
def test_integrity_failures_are_rejected(bundle, fault):
    cases, questions, baseline, document = copy.deepcopy(bundle)
    if fault == 'answer_leak':
        questions[0]['expected'] = {'label': 'general'}
    elif fault == 'label_flip':
        row = next(c for c in cases if c['category'] == 'query_type')
        row['expected']['label'] = 'derived' if row['expected']['label'] == 'general' else 'general'
    elif fault == 'numeric_drift':
        cases[0]['expected']['answer'] += ' altered numeric reference'
    elif fault == 'duplicate_id':
        cases[1]['id'] = cases[0]['id']
    elif fault == 'duplicate_factor':
        cases[0]['difficulty_factors'][1] = copy.deepcopy(cases[0]['difficulty_factors'][0])
    elif fault == 'missing_evidence':
        cases[0]['difficulty_factors'][0]['evidence'] = 'not present in the question'
    elif fault == 'question_drift':
        questions[0]['query'] += ' changed'
    elif fault == 'slot_drift':
        next(c for c in cases if c['id'] == 'CQ21-01')['expected']['required_slots'] = []
    else:
        document = document.replace(cases[0]['query'], 'changed question', 1)
    with pytest.raises(ValueError):
        VALIDATOR.validate_content(cases, questions, baseline, document)
