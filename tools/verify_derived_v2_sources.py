"""Actual KOSIS source availability, separate from GPT plan/fixture scores."""
import argparse,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/agent'),str(ROOT/'src/backend'),str(ROOT/'tools')]
from dotenv import load_dotenv
load_dotenv(ROOT/'.env',override=False)
from expression_tree_schema import ExpressionPlan
from expression_tree_validator import validate_plan
from dynamic_expression_executor import source_series
from derived_catalog_tools import DerivedCatalogTools
from statbridge_mcp.metadata_store import MetadataStore
from statbridge_mcp.statistics_service import StatisticsService
from statbridge_mcp.config import settings
from mcp_gateway import McpToolGateway
from run_derived_eval import dump

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--resume',action='store_true');parser.add_argument('--retry-failed',action='store_true');args=parser.parse_args()
    cases=[json.loads(x) for x in (ROOT/'eval/derived_goldset_v2_300.jsonl').read_text(encoding='utf8').splitlines()]
    store=MetadataStore();catalog=DerivedCatalogTools(store);sources={}
    for c in cases:
        for p in [c.get('expected_plan'),c.get('previous_plan')]:
            if not p:continue
            parsed=ExpressionPlan.model_validate(p);bounds=validate_plan(parsed,catalog)
            for s in parsed.sources:
                identity=json.dumps(s.model_dump(exclude={'alias','required_data'}),sort_keys=True)
                uid=hashlib.sha256(identity.encode()).hexdigest()[:20]
                entry=sources.setdefault(uid,{'source':s.model_dump(),'first':bounds['fetch_start'],'last':bounds['fetch_end'],'cases':[]})
                entry['first']=min(entry['first'],bounds['fetch_start']);entry['last']=max(entry['last'],bounds['fetch_end']);entry['cases'].append(c['id'])
    destination=ROOT/'eval/derived_v2_kosis_source_verification.json'
    old=json.loads(destination.read_text(encoding='utf8')) if args.resume and destination.exists() else {}
    records={r['id']:r for r in old.get('records',[]) if r['status']!='SKIPPED' and not (args.retry_failed and r['status']=='FAIL')}
    gateway=McpToolGateway(StatisticsService(store));tick=time.perf_counter()
    for uid,e in sources.items():
        if uid in records:continue
        s=ExpressionPlan.model_validate({'plan_version':'1.0','indicator_name':'source verification','economic_definition':'source verification',
            'sources':[e['source']],'nodes':[{'id':'check','operator':'lag','inputs':[e['source']['alias']],'lag':1}],
            'outputs':[{'node':'check','label':'source verification'}],'start_period':e['first'],'end_period':e['last']}).sources[0]
        row={'id':uid,**e,'origin':'actual_KOSIS_API_only','status':'SKIPPED'};started=time.perf_counter()
        if not settings.kosis_api_key:row['reason']='KOSIS_API_KEY absent'
        else:
            try:
                catalog.validate_source_selection(s)
                response=gateway.get_statistics(table_id=s.table_id,item_id=s.item_id,classifications=s.classifications,
                    frequency=s.frequency,start_period=e['first'],end_period=e['last'],prefer_local=False,allow_fallback=False)
                row['response_status']=response.get('status');row['response_source']=response.get('source')
                row['source_error']=str(response.get('error') or response.get('message') or response.get('reason') or '')[:1500].replace(settings.kosis_api_key,'[REDACTED]')
                row['observed_unit_set']=sorted({str(r.get('UNIT_NM')) for r in response.get('rows',[])})
                row['raw_preview']=[{k:r.get(k) for k in ['ORG_ID','TBL_ID','ITM_ID','PRD_DE','PRD_SE','DT','UNIT_NM']} for r in response.get('rows',[])[:2]]
                series=source_series(s,response)
                row.update(status='PASS',observations=len(series.values),valid_values=sum(v is not None for v in series.values.values()),
                    actual_unit=series.unit,actual_frequency=series.frequency,observed_first=min(series.values),observed_last=max(series.values),
                    raw_preview=[{k:r.get(k) for k in ['ORG_ID','TBL_ID','ITM_ID','PRD_DE','PRD_SE','DT','UNIT_NM']} for r in response['rows'][:2]])
            except Exception as exc:row.update(status='FAIL',failure_kind=getattr(exc,'failure_kind','source_api_error'),error=str(exc))
        row['seconds']=time.perf_counter()-started;records[uid]=row
        result={'catalog_version':catalog.version,'requested_source_count':len(sources),'table_count':len({e['source']['table_id'] for e in sources.values()}),
            'status':'COMPLETE' if len(records)==len(sources) else 'RUNNING','elapsed_seconds':time.perf_counter()-tick,
            'summary':{'executed':sum(r['status']!='SKIPPED' for r in records.values()),'passed':sum(r['status']=='PASS' for r in records.values()),
                       'failed':sum(r['status']=='FAIL' for r in records.values()),'skipped':sum(r['status']=='SKIPPED' for r in records.values())},'records':list(records.values())}
        dump(destination,result);print(json.dumps({'source':uid,'table':s.table_id,'status':row['status'],'done':len(records),'total':len(sources)}),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
