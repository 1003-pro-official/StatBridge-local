"""Sync only reviewed implementation/evaluation artifacts; preserve local state."""
import hashlib, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent if ROOT.name == 'StatBridge-local1' else ROOT.parent.parent
SOURCE = WORKSPACE / 'StatBridge-local1'
TARGET = WORKSPACE / 'StatBridge1/StatBridge-official'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    agent = ['derived_indicator_planner.py', 'derived_request_period.py', 'derived_indicator_runtime.py', 'live_derived_catalog.py', 'derived_supplement.py',
             'derived_supplement_schema.py', 'bridge_api.py', 'openai_chart_client.py', 'output_agent.py', 'advanced_chart_render.py']
    frontend = ['src/DerivedSupplementPanel.tsx', 'src/App.tsx', 'src/api/types.ts']
    tests = ['test_derived_supplement.py', 'test_live_derived_catalog.py', 'test_derived_followup_quality.py']
    tools = ['run_derived_eval_v2.py', 'run_derived_regression.py', 'verify_live_kosis_metadata_349.py', 'check_derived_gold_against_api.py',
             'verify_derived_v6_evidence.py', 'report_derived_v6.py', 'report_derived_v7.py', 'report_derived_eval.py', 'sync_derived_v6.py', 'serve_derived_supplement_e2e.py']
    files = {'README.md', 'docs/derived_agent_audit.md', 'docs/derived_api_and_file_inputs.md'}
    files.update('src/agent/' + f for f in agent)
    files.update('src/agent/frontend/' + f for f in frontend)
    files.update('tests/' + f for f in tests)
    files.update('tools/' + f for f in tools)
    for name in ['derived_goldset_review.md', 'derived_evaluation_results.json', 'derived_failure_analysis.md', 'derived_patch_report.md',
                 'derived_before_after_comparison.md', 'derived_live_evidence.json', 'derived_performance_report.md', 'derived_quality_summary.md',
                 'derived_api_metadata_349.json']:
        files.add('eval/' + name)
    # Target-owned test runs must remain attributable to their own checkout.
    own_suffixes = ['offline_300.json', 'frontend_tests.txt', 'frontend_build.txt', 'frontend_typecheck.txt', 'validator.txt']
    for p in [*(SOURCE / 'eval').glob('derived_v6*'), *(SOURCE / 'eval').glob('derived_v7*')]:
        if p.name.endswith('_sync_manifest.json'): continue
        if p.is_file() and not any(p.name == 'derived_v6_' + suffix for suffix in own_suffixes):
            files.add(p.relative_to(SOURCE).as_posix())
    for folder in ['derived_api_metadata_349_records', 'derived_v6_live_api_300_cases', 'derived_v6_failed_10_live_cases',
                   'derived_v6_failed_10_live_api_cases', 'derived_v6_ui_records', 'derived_v5_reports_20261019', 'derived_v6_reports_20261019',
                   'derived_v7_failed_8_live_cases', 'derived_v7_failed_8_final_live_cases', 'derived_v7_failed_8_verified_live_cases',
                   'derived_v7_related_holdout_150_live_cases']:
        files.update(p.relative_to(SOURCE).as_posix() for p in (SOURCE / 'eval' / folder).rglob('*') if p.is_file())
    environment = {str(t / '.env'): sha(t / '.env') for t in [SOURCE, TARGET] if (t / '.env').exists()}
    secrets = []
    for path in environment:
        for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
            if '=' not in line or line.lstrip().startswith('#'): continue
            k,v = line.split('=', 1); v = v.strip().strip('"\'')
            if any(s in k.upper() for s in ['KEY', 'TOKEN', 'SECRET']) and len(v) >= 16: secrets.append(v.encode())
    assert not [p for p in files if any(s in (SOURCE / p).read_bytes() for s in secrets)], 'Configured secret in selected artifact'
    manifest = []
    for relative in sorted(files):
        source = SOURCE / relative; target = TARGET / relative
        before = sha(target) if target.exists() else None
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
        assert sha(source) == sha(target)
        manifest.append({'path': relative, 'sha256': sha(source), 'target_previous_sha256': before})
    for suffix in ['json', 'txt', 'xml']:
        shutil.copy2(SOURCE / f'eval/derived_regression_full.{suffix}', TARGET / f'eval/derived_regression_full_main.{suffix}')
    core = ['derived_catalog_tools.py', 'expression_tree_schema.py', 'expression_tree_validator.py', 'dynamic_expression_executor.py',
            'derived_indicator_evidence.py', 'derived_intent_router.py', 'langgraph_workflow.py', 'derived_request_period.py']
    equal = {n: sha(SOURCE / 'src/agent' / n) == sha(TARGET / 'src/agent' / n) for n in core}
    assert all(equal.values()), equal
    assert all(sha(Path(p)) == s for p,s in environment.items())
    result = {'source': str(SOURCE), 'target': str(TARGET), 'shared_files': len(manifest), 'files': manifest,
              'unchanged_core_equal': equal, 'configured_secret_scan': 'PASS', 'env_hashes_unchanged': True,
              'target_owned_test_logs_preserved': True, 'actual_provider_results': 'shared evidence, not separately executed on target',
              'excluded': ['.env', '.venv', 'runtime_data', 'account databases', 'saved analyses', 'source data']}
    version='v7' if (SOURCE/'eval/derived_v7_summary.json').exists() else 'v6'
    for tree in [SOURCE, TARGET]:
        (tree / f'eval/derived_{version}_sync_manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'shared_files': len(manifest), 'core_equal': equal, 'configured_secret_scan': 'PASS', 'env_preserved': True}))

if __name__ == '__main__': main()
