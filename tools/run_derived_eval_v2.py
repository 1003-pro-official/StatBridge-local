"""All 300 reviewed questions through REAL GPT-5.4, resumable, no gold prompts.

v1 is immutable. Data corruption probes are synthetic component checks and never
reported as actual KOSIS. Questions and answers are sealed BEFORE model calls.
"""
import argparse,copy,hashlib,json,os,sys,time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/agent'),str(ROOT/'src/backend'),str(ROOT/'tools'),str(ROOT/'tests')]
from dotenv import load_dotenv
load_dotenv(ROOT/'.env',override=False)
from derived_eval_live import RecordedClient
from derived_eval_reference import canonical_formula,synthetic_data,evaluate
from derived_indicator_planner import DerivedIndicatorPlanner
from derived_catalog_tools import DerivedCatalogTools
from expression_tree_validator import validate_plan
from statbridge_mcp.metadata_store import MetadataStore
from openai_chart_client import OpenAIChartClient
from run_derived_eval import dump,Evaluation


def identity(s):return (s['table_id'],s['item_id'],tuple(sorted(s['classifications'].items())),s['frequency'])


def equivalent(gold,got,case):
    """Independent Decimal probes for alternate DAGs; not an economic proof."""
    exact=canonical_formula(gold)==canonical_formula(got)
    if exact:return {'equivalent':True,'method':'canonical_structure','expert_semantics':'NOT_APPROVED'}
    # Do not accept extra/different inputs via a merely coincident numeric result.
    if {identity(s) for s in gold['sources']}!={identity(s) for s in got['sources']}:return {'equivalent':False,'method':'different_source_identity'}
    if (gold['start_period'],gold['end_period'])!=(got['start_period'],got['end_period']):return {'equivalent':False,'method':'different_period'}
    try:
        for seed in [19,43,107]:
            probe=copy.deepcopy(case);probe['fixture']={'seed':seed};probe['scenario']='numerical'
            raw=synthetic_data(probe,gold);mapped={}
            for s in got['sources']:
                alias=next(t['alias'] for t in gold['sources'] if identity(t)==identity(s));mapped[s['alias']]=raw[alias]
            a=list(evaluate(gold,raw).values());b=list(evaluate(got,mapped).values())
            if len(a)!=len(b):return {'equivalent':False,'method':'different_output_count'}
            for x,y in zip(a,b):
                if x['unit']!=y['unit']:return {'equivalent':False,'method':'different_output_unit','gold_unit':x['unit'],'actual_unit':y['unit']}
                for t,want in x['values'].items():
                    actual=y['values'].get(t)
                    if want is None and actual is None:continue
                    if want is None or actual is None or abs(want-actual)>Decimal('1e-9')+Decimal('1e-11')*abs(want):return {'equivalent':False,'method':'different_decimal_probe'}
        return {'equivalent':True,'method':'three_independent_Decimal_probes','expert_semantics':'REVIEW_REQUIRED_NOT_SYMBOLIC_PROOF'}
    except (ValueError,KeyError,TypeError,ArithmeticError) as exc:return {'equivalent':False,'method':'probe_error','error':str(exc)}


def score(case,result):
    want=case['accepted_statuses'];actual=result.get('status');detail={'expected_statuses':want,'actual_status':actual,'metrics':{}}
    okay=actual in want
    if actual=='need_details':okay &= isinstance(result.get('question'),str) and bool(result['question'].strip())
    if actual=='unavailable':okay &= bool(result.get('missing')) and bool(result.get('searches'))
    if case.get('observed_blocker'):
        message=str(result.get('question') or '')+json.dumps(result.get('missing',[]),ensure_ascii=False)
        blocker=case['observed_blocker']['kind']
        okay &= any(word in message for word in (['단위','UNIT_NM'] if blocker=='verified_unit_absence' else ['조회','원자료','API','응답','분류']))
        detail['specific_blocker_explained']=bool(okay)
    if case['expected_result']=='clarify':detail['metrics']['Clarification Appropriateness']=int(okay)
    if case['expected_result'] in {'unavailable','safe_stop'}:detail['metrics']['Safe Refusal Rate']=int(okay)
    if case['expected_result']=='compute':
        detail['metrics']['DAG Validity Rate']=int(actual=='planned')
        detail['metrics']['Unnecessary Clarification Rate']=int(actual=='need_details')
        if actual=='planned':
            got=result['plan'].model_dump();gold=case['expected_plan'];a={s['table_id'] for s in got['sources']};b={s['table_id'] for s in gold['sources']}
            detail['metrics']['Table Selection Precision']=len(a&b)/len(a)
            detail['metrics']['Table Selection Recall']=len(a&b)/len(b)
            selections={identity(s) for s in got['sources']}=={identity(s) for s in gold['sources']}
            period=(got['start_period'],got['end_period'])==(gold['start_period'],gold['end_period'])
            formula=equivalent(gold,got,case)
            detail.update(source_identity_match=selections,period_match=period,formula_check=formula)
            detail['metrics']['Item Selection Accuracy']=int(selections)
            detail['metrics']['Formula Agreement']=int(formula['equivalent'])
            okay &= selections and period and formula['equivalent']
    detail['metrics']['Request Contract Accuracy']=int(okay)
    return bool(okay),detail


def summary(rows):
    counts=Counter(r['status'] for r in rows);names=sorted({n for r in rows for n in r.get('detail',{}).get('metrics',{})})
    return {'total':len(rows),'attempted_actual_GPT':sum(bool(r.get('calls')) for r in rows),
        'passed':counts['PASS'],'failed':counts['FAIL'],'skipped':counts['SKIPPED'],'unexecuted':300-len(rows),
        'by_category':{c:dict(Counter(r['status'] for r in rows if r['category']==c)) for c in sorted({r['category'] for r in rows})},
        'by_split':{c:dict(Counter(r['status'] for r in rows if r['split']==c)) for c in sorted({r['split'] for r in rows})},
        'metrics':{n:{'n':len(v:=[r['detail']['metrics'][n] for r in rows if n in r.get('detail',{}).get('metrics',{})]),'value':sum(v)/len(v)} for n in names},
        'failure_types':dict(Counter(r.get('failure_type') for r in rows if r['status']=='FAIL')),
        'gpt_calls':sum(len(r.get('calls',[])) for r in rows),'total_tokens':sum(r.get('tokens',{}).get('total_tokens',0) for r in rows),
        'score_status':'AI_ASSISTED_AUTHOR_LABELS_NOT_EXPERT_APPROVED'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=5);parser.add_argument('--resume',action='store_true');parser.add_argument('--live-metadata',action='store_true')
    parser.add_argument('--goldset',type=Path,default=ROOT/'eval/derived_goldset_v2_300.jsonl')
    parser.add_argument('--validation',type=Path,default=ROOT/'eval/derived_goldset_v2_validation.json')
    parser.add_argument('--reuse-run',type=Path)
    parser.add_argument('--reuse-goldset',type=Path)
    parser.add_argument('--ids',default='');parser.add_argument('--output',type=Path,default=ROOT/'eval/derived_v2_live_300.json');args=parser.parse_args()
    goldfile=args.goldset;validation=json.loads(args.validation.read_text(encoding='utf8'))
    digest=hashlib.sha256(goldfile.read_bytes()).hexdigest()
    assert digest==validation['v'+validation['version'].split('.')[0]+'_sha256'] and not validation['pre_evaluation_validation_errors'],'Question/catalog review must pass before live evaluation'
    cases=[json.loads(x) for x in goldfile.read_text(encoding='utf8').splitlines()]
    assert len(cases)==300
    if args.ids:cases=[c for c in cases if c['id'] in args.ids.split(',')]
    old=json.loads(args.output.read_text(encoding='utf8')) if args.resume and args.output.exists() else {}
    if old:assert old['goldset_sha256']==digest,'Do not resume across different answers'
    records={r['id']:r for r in old.get('records',[]) if r['status']!='SKIPPED'}
    case_directory=args.output.parent/(args.output.stem+'_cases')
    if args.resume and case_directory.exists():
        for checkpoint in case_directory.glob('*.json'):
            saved=json.loads(checkpoint.read_text(encoding='utf8'))
            if saved.get('goldset_sha256')==digest and saved['status']!='SKIPPED':records[saved['id']]=saved
    store=MetadataStore();catalog=DerivedCatalogTools(store);started=time.perf_counter()
    if args.live_metadata:
        from live_derived_catalog import LiveDerivedCatalog
        from statbridge_mcp.kosis_client import KosisClient
        catalog=LiveDerivedCatalog(store,KosisClient())
    implementation_snapshot={name:hashlib.sha256((ROOT/'src/agent'/name).read_bytes()).hexdigest() for name in
        ['derived_indicator_planner.py','derived_request_period.py','derived_catalog_tools.py','live_derived_catalog.py','derived_indicator_runtime.py','expression_tree_schema.py','expression_tree_validator.py','dynamic_expression_executor.py']}
    assert catalog.version==validation['catalog_version']
    if old:assert old['implementation_sha256']==implementation_snapshot,'Cannot resume across implementation changes'
    reused=[]
    if args.reuse_run:
        assert args.reuse_goldset,'Provide the exact sealed input corpus for reused real-model records'
        source_run=json.loads(args.reuse_run.read_text(encoding='utf8'))
        assert source_run['summary']['total']==300,'Finish the preceding run before selecting reusable records'
        assert source_run['goldset_sha256']==hashlib.sha256(args.reuse_goldset.read_bytes()).hexdigest()
        assert source_run['implementation_sha256']==implementation_snapshot,'Different code requires fresh model evaluation'
        source_cases={c['id']:c for c in map(json.loads,args.reuse_goldset.read_text(encoding='utf8').splitlines())}
        source_rows={r['id']:r for r in source_run['records']}
        meaningful=['query','previous_plan','expected_plan','allowed_sources','expected_result','accepted_statuses','post_plan_probe']
        for c in cases:
            prior=source_cases.get(c['id']);r=source_rows.get(c['id'])
            # Reuse BOTH successes and failures. Never selectively rerun failures
            # or count an offline fixture as an actual provider result.
            if c['id'] not in records and prior and r and r.get('calls') and all(c.get(k)==prior.get(k) for k in meaningful):
                row=copy.deepcopy(r);row.update(goldset_sha256=digest,goldset_version=c['goldset_version'],
                    reused_actual_record_from=str(args.reuse_run),original_goldset_sha256=source_run['goldset_sha256'])
                records[c['id']]=row;reused.append(c['id'])
    def one(case):
        client=RecordedClient(OpenAIChartClient(model='gpt-5.4'));tick=time.perf_counter()
        row={'id':case['id'],'category':case['category'],'split':case['split'],'query':case['query'],'calls':client.calls,
             'goldset_version':case['goldset_version'],'expected_result':case['expected_result'],'goldset_sha256':digest,
             'observation_origin':'actual_GPT_planning; no actual KOSIS observations in this run',
             'question_style':case.get('question_style','natural_language'),'status':'SKIPPED'}
        if not client.configured:row['reason']='OPENAI_API_KEY absent';return row
        try:
            result=DerivedIndicatorPlanner(client,catalog).plan(case['query'],previous=case.get('previous_plan'),allow_deterministic=False)
            if result.get('plan'):validate_plan(result['plan'],catalog)
            row['planning']={k:v.model_dump() if hasattr(v,'model_dump') else v for k,v in result.items()}
            passed,detail=score(case,result);row['detail']=detail
            if case.get('post_plan_probe'):
                # A separate adapter fault test, after a genuine GPT request.
                # Its scripted fake response is never labelled live KOSIS/GPT.
                probe=copy.deepcopy(case);probe['expected_plan']=case['boundary_fixture_plan']
                evaluator=Evaluation();probe_result=evaluator.security(probe)
                row['injected_component_probe']={'scope':'synthetic_only','detail':probe_result}
                passed &= probe_result.get('passed',False)
            row['status']='PASS' if passed else 'FAIL'
            row['failure_type']=None if passed else 'planner_or_boundary_contract_disagreement'
            assert client.calls,'Every question requires actual GPT, not just a deterministic shortcut'
        except Exception as exc:
            guard_blocked=case['expected_result']=='safe_stop' and type(exc).__name__=='DerivedValidationError' and getattr(exc,'failure_kind',None)=='validation_error'
            row.update(status='PASS' if guard_blocked else 'FAIL',failure_type=None if guard_blocked else getattr(exc,'failure_kind','analysis_error'),
                       error_type=type(exc).__name__,error=str(exc),planner_trace=getattr(exc,'evidence',None))
            if guard_blocked:row['detail']={'actual_status':'server_validation_blocked','metrics':{'Safe Refusal Rate':1,'Request Contract Accuracy':1},'scope':'unsafe model proposal rejected by server, not model-only refusal'}
        finally:
            row['latency_seconds']=time.perf_counter()-tick
            row['tokens']={k:sum(c.get('usage',{}).get(k,0) for c in client.calls) for k in ['input_tokens','output_tokens','total_tokens']}
            dump(case_directory/(case['id']+'.json'),row)
        return row
    def report():
        rows=sorted(records.values(),key=lambda r:r['id'])
        return {'schema_version':validation['version'],'goldset_sha256':digest,'catalog_version':catalog.version,'implementation_sha256':implementation_snapshot,'metadata_origin':'actual_KOSIS_metadata_API' if args.live_metadata else 'local_catalog',
            'elapsed_seconds':time.perf_counter()-started,'previous_elapsed_seconds':old.get('elapsed_seconds',0),
            'pre_evaluation_question_review':str(args.validation.relative_to(ROOT)) if args.validation.is_absolute() else str(args.validation),'all_cases_selected':len(cases)==300,
            'reused_identical_actual_questions':reused,'reuse_policy':'exact same question, prior graph, independent answer and implementation SHA; reuse both PASS and FAIL',
            'human_expert_review':'PENDING','holdout':'retrospective, not blind; never tune from individual holdout failures',
            'summary':summary(rows),'records':rows}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs=[pool.submit(one,c) for c in cases if c['id'] not in records]
        for future in as_completed(jobs):
            row=future.result();records[row['id']]=row;dump(args.output,report())
            print(json.dumps({'id':row['id'],'status':row['status'],'calls':len(row.get('calls',[])),'completed':len(records),'selected':len(cases)}),flush=True)
    dump(args.output,report());print(json.dumps(report()['summary'],ensure_ascii=False,indent=2))
    return int(any(r['status']=='FAIL' for r in records.values()))

if __name__=='__main__':raise SystemExit(main())
