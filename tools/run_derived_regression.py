"""Reproducible offline regression with provider keys disabled in child only."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--full',action='store_true');args=parser.parse_args()
    env=dict(os.environ)
    for key in ('OPENAI_API_KEY','KOSIS_API_KEY','NCP_CLOVA_API_KEY','NCP_API_KEY','CLOVA_STUDIO_API_KEY','JEV_API_KEY','TYPESAFE_API_KEY'):env[key]=''
    env['STATBRIDGE_HYBRID_RETRIEVAL']='0';env['PYTHONIOENCODING']='utf-8'
    env['PYTHONPATH']=os.pathsep.join(str(ROOT/p) for p in ('src/backend','src/agent','tests'))
    env['STATBRIDGE_AUTH_DB']=str(ROOT/'.venv/cache/derived-independent-20261019/regression-accounts.sqlite3')
    targets=['tests','eval/table-discovery/v4.1/tests'] if args.full else ['tests/test_dynamic_derived_indicators.py','tests/test_derived_independent_audit_regressions.py','tests/test_derived_followup_quality.py','tests/test_derived_private_inputs.py','tests/test_derived_support_policy.py','tests/test_derived_natural_period.py','tests/test_derived_request_routing.py','tests/test_derived_supplement.py','tests/test_live_derived_catalog.py','tests/test_derived_file_inputs.py','tests/test_derived_twelve_daily.py','tests/test_derived_json_response.py','tests/test_derived_availability.py','tests/test_derived_period_comparison.py']
    if not args.full:
        targets += ['tests/test_query_api.py','tests/test_workflow_simplification.py','tests/test_workflow_conflict_recovery.py','tests/test_workflow_combination_matrix.py','tests/test_complex_query_flow.py','tests/test_measure_intent.py','tests/test_edit_request_safety.py','tests/test_chart_edit_agent.py','tests/test_request_match_period.py','tests/test_period_selection_provenance.py','tests/test_chart_edit_period_and_box.py','tests/test_quick_period_and_sync.py']
    output=ROOT/'eval'/('derived_regression_full.txt' if args.full else 'derived_regression_targeted.txt')
    command=[sys.executable,'-m','pytest','-q',*targets,'--junitxml='+str(output.with_suffix('.xml'))]
    tick=time.perf_counter()
    with output.open('w',encoding='utf8') as log:
        run=subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    report={'command':command,'returncode':run.returncode,'seconds':time.perf_counter()-tick,'log':str(output),'scope':'offline providers disabled'}
    output.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False));return run.returncode

if __name__=='__main__':raise SystemExit(main())
