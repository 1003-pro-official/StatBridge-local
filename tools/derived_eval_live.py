"""Real providers only. No gold answer is included in model messages.

Structural scores are provisional author-specification agreement, not expert
economic judgement. Synthetic/error-injection cases are offline-only.
"""
import copy
import hashlib
import json
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]


class RecordedClient:
    def __init__(self,client):self.client=client;self.calls=[]
    @property
    def configured(self):return self.client.configured
    def request(self,system,user,**kwargs):
        tick=time.perf_counter();entry={'stage':'semantic_review' if '경제학적 의미 검토자' in system else 'planning',
            'input_chars':len(system)+len(user),'input_sha256':hashlib.sha256((system+user).encode()).hexdigest()}
        try:
            raw,meta=self.client.request(system,user,**kwargs)
            entry.update(raw_response=raw,model=meta.get('model'),usage=meta.get('usage',{}))
            try:entry['action']=json.loads(raw).get('action')
            except (ValueError,AttributeError):pass
            return raw,meta
        except Exception as exc:entry['error']=str(exc);raise
        finally:entry['seconds']=time.perf_counter()-tick;self.calls.append(entry)


def chosen(cases,limit):
    # Eligible before any model calls: genuine natural requests; synthetic
    # defects and adversarial adapter inputs cannot be passed off as live data.
    eligible=[c for c in cases if c['category'] in {'single','multiple','nested','ambiguous'} or
              c['category']=='unavailable' and c['scenario'] in {'catalog_missing','outside_scope'}]
    buckets={k:[] for k in sorted({c['category'] for c in eligible})}
    for c in eligible:buckets[c['category']].append(c)
    for group in buckets.values():group.sort(key=lambda c:hashlib.sha256(c['id'].encode()).hexdigest())
    selected=[]
    while len(selected)<limit and any(buckets.values()):
        for group in buckets.values():
            if group and len(selected)<limit:selected.append(group.pop(0))
    return selected


def score(case,result):
    from derived_eval_reference import canonical_formula
    state=result.get('status');want=case['expected_result']
    detail={'actual_result':state,'expected_result':want,'search_count':len(result.get('searches',[])),
            'metrics':{},'review':'draft author labels, not human approved'}
    if want=='clarify':
        okay=state=='need_details' and bool(result.get('question'))
        detail['metrics']['Clarification Appropriateness']=int(okay)
    elif want=='unavailable':
        okay=state=='unavailable' and bool(result.get('missing'))
        detail['metrics']['Safe Refusal Rate']=int(okay)
    else:
        okay=state=='planned';detail['metrics']['DAG Validity Rate']=int(okay)
        detail['metrics']['Unnecessary Clarification']=int(state=='need_details')
        if okay:
            got=result['plan'].model_dump();expected=case['expected_plan']
            tables={s['table_id'] for s in got['sources']};gold={s['table_id'] for s in expected['sources']}
            detail['metrics']['Table Selection Precision']=len(tables&gold)/len(tables)
            detail['metrics']['Table Selection Recall']=len(tables&gold)/len(gold)
            identities=lambda p:{(s['table_id'],s['item_id'],tuple(sorted(s['classifications'].items())),s['frequency']) for s in p['sources']}
            exact=identities(got)==identities(expected)
            detail['metrics']['Item Selection Accuracy']=int(exact)
            formula=canonical_formula(got)==canonical_formula(expected)
            period=(got['start_period'],got['end_period'])==(expected['start_period'],expected['end_period'])
            detail.update(exact_source_selection=exact,canonical_formula_agreement=formula,period_agreement=period)
            # Different symbolic trees require expert review, not an invented
            # definitive semantic error. Keep the raw output for adjudication.
            detail['metrics']['Formula Structural Agreement']=int(formula)
            okay=exact and formula and period
    detail['metrics']['Intent Result Agreement']=int(okay)
    return ('PASS' if okay else 'FAIL'),detail


def run_live(args,implementation):
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env',override=False)
    from run_derived_eval import dump,metric
    from statbridge_mcp.metadata_store import MetadataStore
    from derived_catalog_tools import DerivedCatalogTools
    from derived_indicator_planner import DerivedIndicatorPlanner
    from openai_chart_client import OpenAIChartClient
    cases=[json.loads(x) for x in (ROOT/'eval/derived_goldset_300.jsonl').read_text(encoding='utf-8').splitlines()]
    if args.split!='all':cases=[c for c in cases if c['split']==args.split]
    if args.ids:selected=[c for c in cases if c['id'] in args.ids.split(',')]
    else:selected=chosen(cases,args.limit)
    destination=args.output or ROOT/f'eval/derived_{args.phase}_{args.mode}_{args.split}.json'
    prior=json.loads(destination.read_text(encoding='utf8')) if args.resume and destination.exists() else {}
    records={r['id']:r for r in prior.get('records',[]) if r['status']!='SKIPPED'}
    store=MetadataStore();catalog=DerivedCatalogTools(store);started=time.perf_counter()
    def one(case):
        tick=time.perf_counter();client=RecordedClient(OpenAIChartClient(model='gpt-5.4'))
        row={'id':case['id'],'category':case['category'],'split':case['split'],'query':case['query'],
             'observation_origin':'real_provider' if args.mode=='live' else 'actual_KOSIS_API',
             'calls':client.calls,'status':'SKIPPED'}
        if not client.configured:row['reason']='OPENAI_API_KEY absent';return row
        try:
            if args.mode=='kosis':
                from statbridge_mcp.config import settings
                if not settings.kosis_api_key:row['reason']='KOSIS_API_KEY absent';return row
            result=DerivedIndicatorPlanner(client,catalog).plan(case['query'])
            row['planning']={k:v.model_dump() if hasattr(v,'model_dump') else v for k,v in result.items()}
            row['status'],row['detail']=score(case,result)
            if args.mode=='kosis':
                if result['status']!='planned':row['status']='FAIL';row['failure_type']='analysis_failure';return row
                from statbridge_mcp.statistics_service import StatisticsService
                from mcp_gateway import McpToolGateway
                from derived_indicator_runtime import DerivedIndicatorRuntime
                from derived_eval_reference import evaluate,compare
                runtime=DerivedIndicatorRuntime(McpToolGateway(StatisticsService(store)),client,ROOT/'.venv/cache/derived-independent-20261019/live-evidence')
                tick_fetch=time.perf_counter()
                try:responses=runtime.fetch(result['plan'],result['bounds'])
                except Exception as exc:
                    row.update(status='FAIL',failure_type=getattr(exc,'failure_kind','source_api_error'),error=str(exc));return row
                row['fetch_seconds']=time.perf_counter()-tick_fetch
                # Preserve sanitized actual observations, not only derived values.
                actual=runtime.calculate(case['query'],result,responses)
                row['receipt']=actual['derivedEvidence'];row['raw_sources']=actual['_derived']['responses']
                raw={}
                for s in result['plan'].sources:
                    rows=responses[s.alias]['rows']
                    def decimal_observation(v):
                        return None if v is None or str(v).strip() in {'','-','..','...','NA','N/A'} else Decimal(str(v).replace(',',''))
                    raw[s.alias]={'values':{str(r['PRD_DE']):decimal_observation(r.get('DT')) for r in rows},
                        'unit':str(rows[0]['UNIT_NM']).strip(),'frequency':s.frequency,'source_ids':[s.alias]}
                expected=evaluate(result['plan'].model_dump(),raw)
                got={'series':{name:SimpleNamespace(**v) for name,v in actual['_derived']['series'].items()}}
                numerical=compare(expected,got);row['numerical_check']=numerical
                row['detail']['metrics']['Numerical Accuracy']=int(numerical['passed'])
                row['status']='PASS' if row['status']=='PASS' and numerical['passed'] else 'FAIL'
                row['failure_type']=None if row['status']=='PASS' else 'analysis_or_numerical_disagreement'
            elif row['status']=='FAIL':row['failure_type']='planner_author_specification_disagreement'
        except Exception as exc:
            row.update(status='FAIL',error_type=type(exc).__name__,error=str(exc),
                       failure_type='provider_failure' if not client.calls or client.calls[-1].get('error') else 'analysis_failure')
        finally:
            row['latency_seconds']=time.perf_counter()-tick
            row['gpt_calls']=len(client.calls)
            row['tokens']={k:sum((c.get('usage') or {}).get(k,0) for c in client.calls) for k in ('input_tokens','output_tokens','total_tokens')}
        return row
    def report():
        rows=sorted(records.values(),key=lambda r:r['id']);counts=Counter(r['status'] for r in rows)
        names=sorted({k for r in rows for k in r.get('detail',{}).get('metrics',{})})
        return {'phase':args.phase,'mode':args.mode,'implementation_path':str(implementation),'human_review':'PENDING',
            'goldset_sha256':hashlib.sha256((ROOT/'eval/derived_goldset_300.jsonl').read_bytes()).hexdigest(),
            'selection_policy':'fixed SHA id ordering, round robin categories; synthetic attacks excluded',
            'elapsed_seconds':time.perf_counter()-started,'summary':{'selected':len(selected),'executed':len(rows)-counts['SKIPPED'],
                'passed':counts['PASS'],'failed':counts['FAIL'],'skipped_selected':counts['SKIPPED'],
                'unexecuted_of_300':300-(len(rows)-counts['SKIPPED']),
                'metrics':{name:metric([r['detail']['metrics'][name] for r in rows if name in r.get('detail',{}).get('metrics',{})]) for name in names}},'records':rows}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs={pool.submit(one,c):c for c in selected if c['id'] not in records}
        for future in as_completed(jobs):
            row=future.result();records[row['id']]=row;dump(destination,report())
            print(json.dumps({'id':row['id'],'status':row['status'],'calls':row.get('gpt_calls',0),'done':len(records),'selected':len(selected)}),flush=True)
    dump(destination,report());print(json.dumps(report()['summary'],ensure_ascii=False,indent=2))
    return 0
