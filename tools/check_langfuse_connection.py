"""Explicit, key-safe Langfuse authentication/export/readback check; no LLM calls."""
from pathlib import Path
import sys,os,json,time
from datetime import datetime,timezone,timedelta
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
sys.path[:0]=[str(ROOT/'src/backend'),str(ROOT/'src/agent')]

def main():
    missing=[k for k in ['LANGFUSE_PUBLIC_KEY','LANGFUSE_SECRET_KEY','LANGFUSE_BASE_URL'] if not os.getenv(k,'').strip()]
    if missing:
        print(json.dumps({'status':'SKIPPED','reason':'missing_configuration','missing':missing}));return 2
    from statbridge_mcp.observability import Trace,CURRENT,exporter
    client,state=exporter()
    if client is None:
        print(json.dumps({'status':'FAIL','reason':state}));return 1
    try:
        if not client.auth_check():
            print(json.dumps({'status':'FAIL','reason':'authentication_failed'}));return 1
        trace=Trace('statbridge.connection_check');token=CURRENT.set(trace)
        try:
            with trace.span('statbridge.connection_check'):
                with trace.span('local.validation'):pass
        finally:CURRENT.reset(token)
        client.flush()
        verified=False
        for attempt in range(20):
            try:
                now=datetime.now(timezone.utc)
                remote=client.api.observations.get_many(trace_id=trace.id,from_start_time=now-timedelta(minutes=10),to_start_time=now+timedelta(minutes=1),limit=20)
                if any(row.trace_id==trace.id and row.name=='statbridge.connection_check' for row in remote.data):verified=True;break
            except Exception:pass
            if attempt<19:time.sleep(2)
        result={'status':'PASS' if verified else 'LIMITATION','authenticated':True,'dashboard_readback':verified,'traceId':trace.id,'model_calls':0}
        if verified:
            try:result['traceUrl']=client.get_trace_url(trace_id=trace.id)
            except Exception:pass
        print(json.dumps(result));return 0 if verified else 3
    except Exception as exc:
        print(json.dumps({'status':'FAIL','reason':'connection_or_export_failed','errorType':type(exc).__name__}));return 1
    finally:
        try:client.shutdown()
        except Exception:pass

if __name__=='__main__':raise SystemExit(main())
