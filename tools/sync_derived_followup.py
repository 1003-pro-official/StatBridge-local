"""Explicit two-checkout synchronization; excludes configs/accounts/raw data."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=ROOT.parent if ROOT.name=='StatBridge-local1' else ROOT.parent.parent
SOURCE=WORKSPACE/'StatBridge-local1'
TARGET=WORKSPACE/'StatBridge1/StatBridge-official'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    code=['src/agent/'+p for p in ['derived_indicator_planner.py','derived_request_period.py','derived_indicator_runtime.py','bridge_api.py']]
    code+=['src/agent/frontend/'+p for p in ['src/WorkspaceData.tsx','src/periodDraft.ts','test-period-draft.mjs']]
    code+=['tests/'+p for p in ['test_derived_independent_audit_regressions.py','test_derived_followup_quality.py']]
    code+=['tools/'+p for p in ['run_derived_eval.py','run_derived_eval_v2.py','run_derived_regression.py','run_derived_v3_offline.py','prepare_derived_eval_v2.py','review_derived_eval_final.py','finalize_derived_questions.py','prepare_derived_goldset_v5.py','verify_derived_v2_sources.py','verify_derived_followup_evidence.py','report_derived_eval.py','report_derived_followup.py','sync_derived_followup.py']]
    files=set(code+['docs/derived_agent_audit.md'])
    names=['derived_goldset_review.md','derived_evaluation_results.json','derived_failure_analysis.md','derived_patch_report.md','derived_before_after_comparison.md','derived_live_evidence.json','derived_performance_report.md','derived_quality_summary.md','derived_date_widget_followup_e2e.json','derived_v1_final_recheck_30.json','derived_v1_followup_live_30.json']
    files.update('eval/'+n for n in names)
    for path in (SOURCE/'eval').glob('derived_*'):
        if path.is_file() and (path.name.startswith(('derived_goldset_v2_','derived_goldset_v3_','derived_goldset_v4_','derived_goldset_v5_','derived_v2_','derived_v3_','derived_v4_','derived_v5_'))):
            if path.name=='derived_v5_offline_300.json':continue # Keep each checkout's own run.
            files.add(path.relative_to(SOURCE).as_posix())
    for directory in ['derived_v2_live_300_cases','derived_v4_live_300_cases','derived_v5_live_300_cases','derived_v1_reports_20261019','derived_followup_e2e_records']:
        files.update(p.relative_to(SOURCE).as_posix() for p in (SOURCE/'eval'/directory).rglob('*') if p.is_file())
    env_hashes={str(tree/'.env'):sha(tree/'.env') for tree in [SOURCE,TARGET] if (tree/'.env').exists()}
    # Exact configured key values are checked without printing their contents.
    secrets=[]
    for tree in [SOURCE,TARGET]:
        p=tree/'.env'
        if p.exists():
            for line in p.read_text(encoding='utf-8-sig').splitlines():
                if '=' not in line or line.lstrip().startswith('#'):continue
                key,value=line.split('=',1);value=value.strip().strip('\"\'')
                if any(token in key.upper() for token in ['KEY','SECRET','TOKEN']) and len(value)>=16:secrets.append(value.encode())
    leaks=[]
    for relative in sorted(files):
        path=SOURCE/relative
        if any(secret in path.read_bytes() for secret in secrets):leaks.append(relative)
    assert not leaks, 'Configured secret detected in selected artifacts: '+str(leaks)
    manifest=[]
    for relative in sorted(files):
        source=SOURCE/relative;target=TARGET/relative
        prior=sha(target) if target.exists() else None
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        assert sha(source)==sha(target)
        manifest.append({'path':relative,'sha256':sha(source),'target_previous_sha256':prior})
    for path,digest in env_hashes.items():assert sha(Path(path))==digest
    core=['derived_catalog_tools.py','expression_tree_schema.py','expression_tree_validator.py','dynamic_expression_executor.py','derived_indicator_evidence.py','derived_intent_router.py','langgraph_workflow.py','output_agent.py']
    core_equal={f:sha(SOURCE/'src/agent'/f)==sha(TARGET/'src/agent'/f) for f in core}
    assert all(core_equal.values()),core_equal
    for suffix in ['json','txt','xml']:
        shutil.copy2(SOURCE/f'eval/derived_regression_full.{suffix}',TARGET/f'eval/derived_regression_full_main.{suffix}')
    result={'source':str(SOURCE),'target':str(TARGET),'shared_files':len(manifest),'files':manifest,'unmodified_core_equal':core_equal,
            'env_hashes_unchanged_during_sync':True,'configured_secret_scan':'PASS','local_offline_and_targeted_logs_preserved':True,
            'e2e_screenshots':'Each checkout retains its independently captured derived_date_widget_v5_proof.jpg',
            'excluded':['.env','.venv','original account databases','original source data','saved analyses','runtime_data'],'full_main_logs_in_target':'derived_regression_full_main.*'}
    for tree in [SOURCE,TARGET]:(tree/'eval/derived_followup_sync_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'shared_files':len(manifest),'equal_core':core_equal,'secret_scan':'PASS','env_preserved':True},ensure_ascii=False))

if __name__=='__main__':main()
