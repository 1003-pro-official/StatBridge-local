"""Run the public reporter benchmark against this checkout without changing its catalog.

Classification codes are rebased only by unique canonical name at the same table/level.
The original frozen score is retained separately. Numeric and chart execution are blocked.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--goldset-root',type=Path,required=True)
    parser.add_argument('--source-catalog',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--offline',action='store_true',help='Disable language-model and hybrid providers; actual API remains in use')
    parser.add_argument('--local-copy',action='store_true',help='Record file hashes instead of Git provenance for a non-Git backup copy')
    args=parser.parse_args()
    dataset=args.goldset_root.resolve();out=args.output_dir.resolve()
    os.chdir(ROOT)
    if args.offline:
        for key in ['NCP_CLOVA_API_KEY','NCP_API_KEY','CLOVA_STUDIO_API_KEY','JEV_API_KEY','TYPESAFE_API_KEY','OPENAI_API_KEY']:os.environ[key]=''
        os.environ['STATBRIDGE_HYBRID_RETRIEVAL']='0'
    sys.path[:0]=[str(ROOT/'src/agent'),str(ROOT/'src/backend'),str(ROOT/'tests')]
    module_path=dataset/'scripts/evaluate_runtime.py'
    spec=importlib.util.spec_from_file_location('public_reporter_scorer',module_path)
    scorer=importlib.util.module_from_spec(spec);spec.loader.exec_module(scorer);scorer.ROOT=ROOT
    if args.local_copy:
        from datetime import datetime,timezone
        def copy_environment(gold_path):
            files=['src/agent/agent_runtime.py','src/agent/catalog_request_planner.py','src/agent/bridge_api.py',
                   'src/agent/stat_dictionary/stat_language_resolver.py','src/agent/langgraph_workflow.py',
                   'src/agent/output_agent.py','src/agent/mcp_gateway.py']
            return {'source_sha256':{name:digest(ROOT/name) for name in files},
                    'catalog_sha256':digest(ROOT/'src/agent/stat_dictionary/stat_language_dictionary.json'),
                    'dataset_sha256':digest(gold_path),'policy_sha256':scorer.policy_sha256(),
                    'python':sys.executable,'commit':None,'dirty':None,'checkout_kind':'local-copy',
                    'endpoint':'POST /api/query (in-process TestClient, actual application)',
                    'execution':False,'case_timeout_seconds':scorer.POLICY['case_timeout_seconds'],
                    'started_at':datetime.now(timezone.utc).isoformat()}
        scorer.run_environment=copy_environment
    manifest=json.loads((dataset/'dataset_manifest.json').read_text(encoding='utf-8'))
    assert digest(scorer.GOLD)==manifest['dataset_sha256']
    assert scorer.policy_sha256()==manifest['scoring_policy_sha256']
    import bridge_api as api
    from authenticated_client import TestClient
    assert Path(api.__file__).resolve()==ROOT/'src/agent/bridge_api.py'
    original=scorer.load_cases();assert len(original)==200
    aligned=copy.deepcopy(original)
    source={t['table_id']:t for t in json.loads(args.source_catalog.read_text(encoding='utf-8-sig'))['tables']}
    normalize=lambda value:re.sub('[^a-z0-9가-힣]','',str(value).lower())
    mapping=[]
    for case in aligned:
        for plan in case['workflow_gold']['classification_and_plan']['series']:
            for key,code in list(plan['classifications'].items()):
                old=[v for d in source[plan['table_id']]['dimensions'] if d['api_param']==key for v in d['values'] if v['value_id']==code]
                assert len(old)==1,(case['id'],key,code)
                current=[v for d in api.agent.tables_by_id[plan['table_id']]['dimensions'] if d['api_param']==key for v in d['values'] if normalize(v['value_name'])==normalize(old[0]['value_name'])]
                if len(current)>1:current=[v for v in current if v['value_id']==code]
                assert len(current)==1,('ambiguous name mapping',case['id'],key,old[0]['value_name'])
                new=current[0]
                if new['value_id']!=code:mapping.append({'id':case['id'],'table_id':plan['table_id'],'level':key,'canonical_name':old[0]['value_name'],'old_id':code,'local_id':new['value_id']})
                plan['classifications'][key]=new['value_id'];plan['exact_params'][key]=new['value_id']
    sources=[p for area in ['src/agent','src/backend'] for p in (ROOT/area).rglob('*.py') if '__pycache__' not in p.parts]
    sources += [ROOT/'src/agent/stat_dictionary/stat_language_dictionary.json',ROOT/'data/processed/bok_table_master.csv']
    hashes={str(p.relative_to(ROOT)):digest(p) for p in sources}
    provider={'calls':0,'ok':0,'error':0}
    original_post=api.agent.ncp._post
    def observed_post(*a,**kw):
        provider['calls']+=1
        try:
            result=original_post(*a,**kw);provider['ok']+=1;return result
        except Exception:
            provider['error']+=1;raise
    api.agent.ncp._post=observed_post
    started=time.monotonic()
    def progress(index,total,record):
        if index%10==0 or record['http_status']!=200:print(f"{index}/{total} {record['agent_status']} {time.monotonic()-started:.1f}s",flush=True)
    with TestClient(api.app) as client:
        result=scorer.run_suite(api,client,aligned,out/'aligned',gold_suspect=['REPORTER30-V2.1-194'],progress=progress)
    raw={r['id']:json.loads((out/'aligned'/(r['id']+'.json')).read_text(encoding='utf-8')) for r in original}
    frozen=[scorer.score_case(c,raw[c['id']]) for c in original]
    context={'target':str(ROOT),'mode':'offline' if args.offline else 'configured_providers','provider':provider,'ncp_configured':api.agent.ncp.configured,'source_hashes':hashes,'source_unchanged':all(digest(ROOT/path)==value for path,value in hashes.items()),'source_catalog_sha256':digest(args.source_catalog),'gold_human_approved':manifest['review']['human_approved'],'gold_ai_assisted':manifest['review']['ai_assisted'],'aligned_score':result['summary'],'frozen_pass':sum(c['passed'] for c in frozen),'elapsed_seconds':round(time.monotonic()-started,2),'classification_mapping':mapping}
    (out/'context.json').write_text(json.dumps(context,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'aligned_cases.json').write_text(json.dumps(result['cases'],ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'frozen_cases.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in context.items() if k not in {'source_hashes','classification_mapping','aligned_score'}},ensure_ascii=False),flush=True)
    print('ALIGNED',sum(c['passed'] for c in result['cases']),'/200',flush=True)


if __name__=='__main__':main()
