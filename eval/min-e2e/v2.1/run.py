"""ai-assisted query-only evaluation. Never opens cases/gold files."""
import os,sys,json,time,hashlib,concurrent.futures,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PREDICTIONS=HERE/'predictions'
sys.path[:0]=[str(ROOT/'src/agent'),str(ROOT/'src/backend')]
from dotenv import load_dotenv
load_dotenv(ROOT/'.env',override=False)
os.environ['STATBRIDGE_AUTH_DB']=str(HERE/'accounts.sqlite3')
os.environ['STATBRIDGE_DERIVED_SUPPLEMENT_DIR']=str(HERE/'supplements')
os.environ['LANGFUSE_TRACING_ENABLED']='false'
import bridge_api as api
from derived_indicator_evidence import DerivedIndicatorEvidence
api.agent.workflow.derived_runtime.evidence=DerivedIndicatorEvidence(HERE/'evidence')
from fastapi.testclient import TestClient
from derived_indicator_planner import is_derived_request
def write(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),encoding='utf8')
source=ROOT/'eval/min-e2e/v2.1/questions.jsonl'
questions=[json.loads(s) for s in source.read_text(encoding='utf8').splitlines()]
assert len(questions)==60 and all(set(q)=={'id','query'} for q in questions)
(HERE/'questions.jsonl').write_bytes(source.read_bytes())
if not (HERE/'environment.json').exists():
 write(HERE/'environment.json',{'mode':'DA/CQ real API first response; QT production local routing function','input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'started':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'kosis_configured':bool(os.getenv('KOSIS_API_KEY')),'raw_data':'live service; no fixtures or gold injected','fresh_request_state':True})
lock=threading.Lock()
def run(q):
 path=PREDICTIONS/f"{q['id']}.json"
 if path.exists():return
 start=time.monotonic()
 out={'id':q['id'],'query':q['query']}
 try:
  if q['id'].startswith('QT'):
   out.update(mode='local_branch',label='derived' if is_derived_request(q['query']) else 'general')
  else:
   client=TestClient(api.app,raise_server_exceptions=False)
   login=client.post('/api/auth/login',json={'username':'test1','password':'1234'})
   assert login.status_code==200,'isolated test login failed'
   response=client.post('/api/query',json={'query':q['query'],'execute':True})
   out['http_status']=response.status_code
   try:out['response']=response.json()
   except ValueError:out['response']={'status':'invalid_response'}
   sid=out['response'].get('outputSessionId')
   if sid and sid in api.OUTPUT_SESSIONS:
    out['resolved_result']=api.OUTPUT_SESSIONS[sid]['result']
   client.close()
 except Exception as exc:
  out['error_type']=type(exc).__name__
 out['elapsed_seconds']=round(time.monotonic()-start,2)
 write(path,out)
 with lock:print(json.dumps({'id':q['id'],'status':out.get('response',{}).get('status',out.get('label',out.get('error_type'))),'seconds':out['elapsed_seconds']},ensure_ascii=False),flush=True)
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  list(pool.map(run,questions))
 files=sorted(PREDICTIONS.glob('*.json'))
 assert len(files)==60
 write(HERE/'prediction-freeze.json',{'frozen_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}})
 print('FROZEN 60 predictions; scoring may now read gold.',flush=True)
