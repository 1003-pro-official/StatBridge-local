"""Explicit file-input patch synchronization without original app state."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=ROOT.parent if ROOT.name=='StatBridge-local1' else ROOT.parent.parent
SOURCE=WORKSPACE/'StatBridge-local1';TARGET=WORKSPACE/'StatBridge1/StatBridge-official'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    paths=['README.md','docs/derived_file_formats_and_sources.md','docs/derived_api_and_file_inputs.md','src/backend/requirements.txt',
           'src/agent/derived_file_inputs.py','src/agent/derived_input_guidance.py','src/agent/derived_supplement.py','src/agent/derived_indicator_planner.py','src/agent/bridge_api.py',
           'src/agent/frontend/src/DerivedSupplementPanel.tsx','src/agent/frontend/src/DerivedSupplementPanel.css','src/agent/frontend/src/App.tsx','src/agent/frontend/src/api/types.ts',
           'tests/test_derived_file_inputs.py','tools/run_derived_regression.py','tools/report_derived_files.py','tools/sync_derived_files.py']
    owned=['derived_files_v8_final.txt','derived_files_v8_final.xml','derived_files_v8_build.txt','derived_files_v8_frontend_tests.txt','derived_files_v8_validator.txt',
           'derived_files_v8_targeted.txt','derived_files_v8_targeted.xml']
    paths += [p.relative_to(SOURCE).as_posix() for p in (SOURCE/'eval').glob('derived_files_v8*') if p.is_file() and p.name not in owned and 'sync_manifest' not in p.name]
    paths += [p.relative_to(SOURCE).as_posix() for p in (SOURCE/'eval/derived_files_v8_evidence').rglob('*') if p.is_file()]
    envs={str(t/'.env'):sha(t/'.env') for t in [SOURCE,TARGET] if (t/'.env').exists()}
    secrets=[]
    for p in envs:
        for line in Path(p).read_text(encoding='utf-8-sig').splitlines():
            if '=' not in line or line.lstrip().startswith('#'):continue
            k,v=line.split('=',1);v=v.strip().strip('"\'')
            if any(t in k.upper() for t in ['KEY','TOKEN','SECRET']) and len(v)>=16:secrets.append(v.encode())
    assert not [p for p in paths if any(v in (SOURCE/p).read_bytes() for v in secrets)],'Configured secret in selected artifacts'
    records=[]
    for relative in sorted(set(paths)):
        source=SOURCE/relative;target=TARGET/relative;previous=sha(target) if target.exists() else None
        target.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(source,target)
        assert sha(source)==sha(target);records.append({'path':relative,'sha256':sha(source),'target_previous_sha256':previous})
    for suffix in ['txt','json','xml']:
        for t in [SOURCE,TARGET]:shutil.copy2(SOURCE/f'eval/derived_regression_full.{suffix}',t/f'eval/derived_files_v8_full_main.{suffix}')
    assert all(sha(Path(p))==v for p,v in envs.items())
    result={'source':str(SOURCE),'target':str(TARGET),'files':records,'shared_files':len(records),'configured_secret_scan':'PASS','env_hashes_unchanged':True,
            'own_test_logs_preserved':True,'real_provider_evidence':'Executed on local1, shared evidence labelled as such',
            'excluded':['.env','account databases','runtime_data','saved analyses','original data','virtual environments']}
    for t in [SOURCE,TARGET]:(t/'eval/derived_files_v8_sync_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'shared_files':len(records),'secret_scan':'PASS','env_preserved':True}))

if __name__=='__main__':main()
