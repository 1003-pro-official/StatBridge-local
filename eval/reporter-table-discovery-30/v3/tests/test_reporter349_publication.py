import importlib.util
from pathlib import Path


def test_failed_run_keeps_diagnostics_without_publishing_markdown(tmp_path):
    path=Path(__file__).resolve().parents[1]/'scripts/evaluate_runtime.py'
    spec=importlib.util.spec_from_file_location('reporter349_runtime',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.save_result(tmp_path,{'summary':{'cases':1104,'passed':1103,'failed':1},'cases':[],'environment':{}},{})
    assert (tmp_path/'diagnostic_scores.json').exists()
    assert not (tmp_path/'REPORT.md').exists()
    assert not (tmp_path/'scores.json').exists()
