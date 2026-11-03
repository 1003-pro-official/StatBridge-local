"""Retry only infrastructure-verifying responses, unchanged questions, no gold."""
import run,shutil
from run import HERE,json,time,hashlib,concurrent,api
run.PREDICTIONS=HERE/'final-predictions'
run.PREDICTIONS.mkdir(exist_ok=True)
targets=[]
for q in run.questions:
 p=HERE/'predictions'/f"{q['id']}.json"
 d=json.loads(p.read_text(encoding='utf8'))
 if d.get('response',{}).get('availability',{}).get('status')=='verifying':targets.append(q)
 else:shutil.copy2(p,run.PREDICTIONS/p.name)
run.write(HERE/'retry-policy.json',{'reason':'only actual metadata verification pending; no semantic-failure retries','ids':[q['id'] for q in targets]})
inventory=api.agent.workflow.derived_runtime.api_inventory
start=time.monotonic()
while inventory.snapshot() is None and time.monotonic()-start<2100:
 print('Waiting for existing live metadata refresh:',len(list(inventory.directory.glob('DT_*.json'))),'/349',flush=True)
 time.sleep(30)
if inventory.snapshot() is None:raise RuntimeError('Metadata refresh did not complete within 35 minutes')
print('Live metadata inventory ready; retrying unchanged requests.',flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(run.run,targets))
files=sorted(run.PREDICTIONS.glob('*.json'));assert len(files)==60
run.write(HERE/'final-prediction-freeze.json',{'frozen_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}})
