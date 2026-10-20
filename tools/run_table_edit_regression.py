"""Run the public regression files in isolated processes without model keys."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,choices=[1,2,3],default=3);parser.add_argument('--out');args=parser.parse_args()
    out=Path(args.out) if args.out else ROOT/'.venv/cache/table-editor-20261019/regression-final';out.mkdir(parents=True,exist_ok=True)
    files=[p for base in [ROOT/'tests',ROOT/'eval/table-discovery/v4.1/tests'] for p in base.rglob('test*.py')]
    weights={};previous=out.parent/'full-regression.xml'
    if previous.exists():
        for c in ET.parse(previous).iter('testcase'):
            name=c.get('classname','');weights[name]=weights.get(name,0)+float(c.get('time','0'))
    groups=[[] for _ in range(args.workers)];loads=[0.0]*args.workers
    def weight(p):return weights.get('.'.join(p.relative_to(ROOT).with_suffix('').parts),max(1,p.stat().st_size/20000))
    for p in sorted(files,key=weight,reverse=True):
        i=loads.index(min(loads));groups[i].append(p);loads[i]+=weight(p)
    tracked=[*files,*list((ROOT/'src/agent').glob('*.py'))]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}
    def run(i):
        env=os.environ.copy();env['PYTHONPATH']=os.pathsep.join([str(ROOT/'src/backend'),str(ROOT/'src/agent')]);env['STATBRIDGE_HYBRID_RETRIEVAL']='0';env['LANGFUSE_ENABLED']='false';env['STATBRIDGE_AUTH_DB']=str(out/f'test-accounts-{i}.sqlite3')
        for key in ['OPENAI_API_KEY','NCP_CLOVA_API_KEY','NCP_API_KEY','CLOVA_STUDIO_API_KEY','JEV_API_KEY','TYPESAFE_API_KEY']:env[key]=''
        start=time.perf_counter()
        with (out/f'shard-{i}.txt').open('w',encoding='utf8') as log:
            result=subprocess.run([sys.executable,'-m','pytest','-q',*[str(p.relative_to(ROOT)) for p in groups[i]],'--disable-warnings','--tb=short',f'--junitxml={out/f"shard-{i}.xml"}'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        text=(out/f'shard-{i}.txt').read_text(encoding='utf8',errors='replace');summary=text.splitlines()[-1] if text.splitlines() else ''
        return {'shard':i,'return_code':result.returncode,'files':len(groups[i]),'seconds':round(time.perf_counter()-start,2),'summary':summary,'passed':sum(map(int,re.findall(r'(\d+) passed',summary))),'failed':sum(map(int,re.findall(r'(\d+) failed',summary))),'skipped':sum(map(int,re.findall(r'(\d+) skipped',summary))),'subtests_passed':sum(map(int,re.findall(r'(\d+) subtests passed',summary)))}
    start=time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:results=list(pool.map(run,range(args.workers)))
    unchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    report={'elapsed_seconds':round(time.perf_counter()-start,2),'files':len(files),'source_unchanged_during_run':unchanged,'model_keys_disabled':True,'shards':results,**{key:sum(r[key] for r in results) for key in ['passed','failed','skipped','subtests_passed']}}
    report['passed_all']=unchanged and all(r['return_code']==0 for r in results)
    (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False));return 0 if report['passed_all'] else 1

if __name__=='__main__':raise SystemExit(main())
