"""Question-only product evaluation. No scoring code or gold input is present."""
import sys, os, json, time, hashlib, threading
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl

import argparse
parser = argparse.ArgumentParser(description='Fresh question-only model run. Never overwrites saved evidence.')
parser.add_argument('--run-dir', type=Path, required=True)
args = parser.parse_args()
ARCHIVE = Path(__file__).resolve().parents[1]
ROOT = ARCHIVE.parent
RUN = args.run_dir.resolve()
RUN.mkdir(parents=True, exist_ok=False)
(RUN/'input').mkdir()
(RUN/'output').mkdir()
(RUN/'output/raw_responses').mkdir()
(RUN/'input/questions.jsonl').write_bytes((ARCHIVE/'questions.jsonl').read_bytes())
os.chdir(RUN)
sys.path[:0] = [str(ROOT/'src/backend'), str(ROOT/'src/agent')]
os.environ['STATBRIDGE_DATA_DIR'] = str(ROOT/'data/processed')
os.environ['STATBRIDGE_TABLES_DIR'] = str(ROOT/'data/tables')
os.environ['LANGFUSE_ENABLED'] = 'false'
blocked = []
archive_dir = str(ARCHIVE.resolve()).lower().replace('\\','/')
def audit(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        name = os.fsdecode(args[0]).lower().replace('\\','/')
        if archive_dir in name or any(s in name for s in ('evaluation_drafts','answer_key','golden-data','holdout','evaluation-private','데이터 조회 평가 수정본')):
            blocked.append(name)
            raise PermissionError('gold and restricted evaluation data are unavailable to runner')
sys.addaudithook(audit)

questions = [json.loads(s) for s in (RUN/'input/questions.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(questions)==20 and all(set(q)=={'id','query'} for q in questions)
assert sorted(p.name for p in (RUN/'input').iterdir())==['questions.jsonl']
# Test the denial before importing or invoking any model code. No content is read.
try:
    (RUN/'input/answer_key.jsonl').read_text()
except PermissionError:
    pass
else:
    raise AssertionError('read isolation is not active')
(RUN/'output/preflight.json').write_text(json.dumps({'checks':[{'check':'input schema contains only id and query; 20 cases','passed':True},{'check':'input directory contains questions.jsonl only','passed':True},{'check':'gold read denial self-test before model execution','passed':True}],'questions_sha256':hashlib.sha256((RUN/'input/questions.jsonl').read_bytes()).hexdigest(),'no_gold_opened':True},indent=2),encoding='utf-8',newline='\n')
print('PREFLIGHT 3/3 PASSED; gold read guard active',flush=True)

from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
import requests
secrets = [v for k,v in os.environ.items() if ('KEY' in k or 'TOKEN' in k or 'SECRET' in k) and len(v)>8]
def clean(value):
    if isinstance(value,dict):return {k:('[REDACTED]' if any(t in k.lower() for t in ('apikey','api_key','authorization','token','secret')) and not any(t in k.lower() for t in ('tokens','token_count')) else clean(v)) for k,v in value.items()}
    if isinstance(value,list):return [clean(v) for v in value]
    if isinstance(value,str):
        for s in secrets:value=value.replace(s,'[REDACTED]')
    return value
lock=threading.Lock()
current={'id':None}
counts={'model':0,'kosis_data':0,'other':0}
def append(name,data):
    with lock:
        with (RUN/'output'/name).open('ab') as f:f.write((json.dumps(clean(data),ensure_ascii=False,default=str)+'\n').encode('utf8'))
send=requests.Session.send
model_pace_lock=threading.Lock()
last_model_started=[0.0]
def traced_send(self,request,**kwargs):
    url=urlsplit(request.url)
    kind='kosis_data' if url.hostname=='kosis.kr' and 'statisticsParameterData.do' in url.path else 'model' if any(s in (url.hostname or '') for s in ('openai','ntruss','typesafe')) else 'other'
    body=None
    if request.body:
        try:body=json.loads(request.body)
        except Exception:body={'unparsed_body':True}
    if kind=='model':
        with model_pace_lock:
            pause=max(0,15-(time.monotonic()-last_model_started[0]))
            if pause:time.sleep(pause)
            last_model_started[0]=time.monotonic()
        text=json.dumps(body,ensure_ascii=False)
        assert not any(x in text for x in ('answer_key.jsonl','golden-data-accuracy','DA3-')), 'blocked evaluation marker in model payload'
    record={'case_id':current['id'],'kind':kind,'host':url.hostname,'path':url.path,'params':dict(parse_qsl(url.query)),'body':body,'started':time.time()}
    with lock:
        counts[kind]+=1
        record['request_id']=f'{current["id"]}-{kind}-{counts[kind]:04d}'
    try:
        response=send(self,request,**kwargs)
        record['http_status']=response.status_code
        raw=response.content
        assert not any(s.encode('utf8') in raw for s in secrets), 'response contains credential; cannot persist'
        relative='raw_responses/'+record['request_id']+'.bin'
        (RUN/'output'/relative).write_bytes(raw)
        record['response_file']=relative
        record['response_sha256']=hashlib.sha256(raw).hexdigest()
        record['response_bytes']=len(raw)
        record['received_at_unix']=time.time()
        record['response_content_type']=response.headers.get('Content-Type')
        record['server_date']=response.headers.get('Date')
        if kind=='kosis_data':
            try:
                data=response.json()
                record['provider_result']=({'row_count':len(data)} if isinstance(data,list) else {k:data.get(k) for k in ('err','errMsg')})
            except Exception:record['provider_parse_error']=True
        if kind=='model':
            try:record['response']=response.json()
            except Exception:record['response_parse_error']=True
        return response
    except Exception as exc:
        record['error_type']=type(exc).__name__
        raise
    finally:
        record['elapsed_seconds']=round(time.time()-record['started'],3)
        append('http.jsonl',record)
requests.Session.send=traced_send

from statbridge_mcp.statistics_service import StatisticsService
from mcp_gateway import McpToolGateway
from agent_runtime import StatBridgeAgent
from openai_chart_client import OpenAIChartClient
from derived_indicator_runtime import DerivedIndicatorRuntime
from live_derived_catalog import LiveDerivedCatalog
from derived_api_inventory import DerivedApiInventory

service=StatisticsService()
gateway=McpToolGateway(service)
agent=StatBridgeAgent(gateway)
runtime=DerivedIndicatorRuntime(gateway,OpenAIChartClient(),RUN/'output/derived_evidence')
live=LiveDerivedCatalog(service.store,service.client)
runtime.catalog=runtime.planner.catalog=live
runtime.api_inventory=DerivedApiInventory(live,RUN/'output/derived_inventory')
agent.workflow.derived_runtime=runtime
assert os.getenv('KOSIS_API_KEY','').strip(), 'live KOSIS key required'
configuration={'ncp_configured':agent.ncp.configured,'ncp_classifier':agent.ncp.settings.classifier_model,'ncp_main':agent.ncp.settings.main_model,'openai_model':runtime.planner.client.settings.main_model if hasattr(runtime.planner,'client') else None,'hybrid_enabled':agent.hybrid.enabled,'mode':'StatBridge Agent->MCP->live KOSIS; no browser/HTTP authentication evaluation; no answer-informed clarifications or retries'}
(RUN/'output/configuration.json').write_text(json.dumps(configuration,ensure_ascii=False,default=str,indent=2),encoding='utf-8',newline='\n')
for q in questions:
    current['id']=q['id'];start=time.time()
    try:
        # Independent sessions; only the natural-language question is passed.
        result=agent.run(query=q['query'],execute=True,generate_answer=True)
        append('observations.jsonl',{'id':q['id'],'query':q['query'],'result':result,'elapsed_seconds':round(time.time()-start,3)})
        print(q['id'],result.get('status'),(result.get('execution') or {}).get('status'),round(time.time()-start,1),flush=True)
    except Exception as exc:
        append('observations.jsonl',{'id':q['id'],'query':q['query'],'error_type':type(exc).__name__,'elapsed_seconds':round(time.time()-start,3)})
        print(q['id'],'ERROR',type(exc).__name__,flush=True)
(RUN/'output/completion.json').write_text(json.dumps({'completed':True,'cases':20,'http_calls':counts,'gold_access_attempts_after_selftest':len(blocked)-1,'model_payload_guard_active':True},indent=2),encoding='utf-8',newline='\n')
print('COMPLETE',counts,flush=True)

# All case files and completion marker have been closed; stop optional background inventory work.
sys.stdout.flush()
os._exit(0)
