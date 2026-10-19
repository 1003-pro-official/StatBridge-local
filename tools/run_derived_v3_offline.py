"""Independent Decimal and genuine previous->edited snapshot checks, no providers."""
import argparse,copy,hashlib,json,os,sys,time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/agent'),str(ROOT/'src/backend'),str(ROOT/'tools'),str(ROOT/'tests')]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--goldset',type=Path,default=ROOT/'eval/derived_goldset_v3_300.jsonl');parser.add_argument('--output',type=Path,default=ROOT/'eval/derived_v3_offline_300.json');args=parser.parse_args()
    for key in ['OPENAI_API_KEY','KOSIS_API_KEY','NCP_CLOVA_API_KEY','NCP_API_KEY','CLOVA_STUDIO_API_KEY','JEV_API_KEY','TYPESAFE_API_KEY']:os.environ[key]=''
    from run_derived_eval import Evaluation,dump
    from expression_tree_schema import ExpressionPlan
    from derived_eval_reference import synthetic_data,evaluate,compare,canonical_formula
    evaluator=Evaluation();records=[];tick=time.perf_counter()
    path=args.goldset;cases=[json.loads(x) for x in path.read_text(encoding='utf8').splitlines()]
    for case in cases:
        started=time.perf_counter()
        try:
            if case.get('observed_blocker'):
                from expression_tree_schema import SourceSelection
                from dynamic_expression_executor import source_series
                blocker=case['observed_blocker'];source=SourceSelection.model_validate(blocker['source']);evaluator.catalog.validate_source_selection(source)
                if blocker['kind']=='verified_unit_absence':
                    row={'ORG_ID':'301','TBL_ID':source.table_id,'ITM_ID':source.item_id,'PRD_SE':source.frequency,'PRD_DE':'2023' if source.frequency=='Y' else '202301','DT':'100','UNIT_NM':None,
                         **{k.replace('objL','C'):v for k,v in source.classifications.items()}}
                    response={'status':'success','source':'kosis_api','table_id':source.table_id,'rows':[row]}
                else:response={'status':'failed','source':'none','table_id':source.table_id,'rows':[]}
                try:source_series(source,response);detail={'passed':False,'reason':'Unverified source executed'}
                except ValueError as exc:detail={'passed':True,'safe_block':True,'failure_kind':getattr(exc,'failure_kind','validation_error'),
                    'scope':'synthetic reproduction of a separately recorded actual API blocker; not a successful KOSIS query'}
            elif case['category']=='edit':
                fixture=copy.deepcopy(case);fixture['expected_plan']=case['previous_plan']
                runtime,_=evaluator.runtime(fixture);prior=ExpressionPlan.model_validate(case['previous_plan'])
                original=runtime.calculate('synthetic',{'plan':prior,'bounds':runtime.validate(prior)},runtime.fetch(prior,runtime.validate(prior)));saved=copy.deepcopy(original)
                mode=case['scenario'];kw={'lag_patch':{'node_patch':{'id':'r','lag':3}},'window_patch':{'node_patch':{'id':'r','window':5}},
                    'base_patch':{'node_patch':{'id':'r','base_period':'202306'}},'period_shrink':{'start':'202307','end':'202406'},
                    'period_expand':{'start':'202201','end':'202512'},'failed_edit_preserves':{'node_patch':{'id':'r','operator':'exec'}}}[mode]
                if mode=='failed_edit_preserves':
                    try:runtime.revise(original,**kw);detail={'passed':False,'reason':'unsupported edit accepted'}
                    except ValueError:detail={'passed':original==saved,'safe_block':True,'original_preserved':original==saved}
                else:
                    revised=runtime.revise(original,**kw);gold=case['expected_plan'];actual=revised['derivedEvidence']['plan']
                    wanted=evaluate(gold,synthetic_data(fixture,fixture['expected_plan']))
                    detail=compare(wanted,{'series':{k:SimpleNamespace(**v) for k,v in revised['_derived']['series'].items()}})
                    detail['plan_matches_independent_answer']=canonical_formula(gold)==canonical_formula(actual) and (gold['start_period'],gold['end_period'])==(actual['start_period'],actual['end_period'])
                    detail['original_preserved']=original==saved
                    detail['new_immutable_receipt']=revised['derivedEvidence']['calculationId']!=original['derivedEvidence']['calculationId'] and revised['_derived']['record']['previous']==original['derivedEvidence']['calculationId']
                    detail['passed'] &= detail['plan_matches_independent_answer'] and detail['original_preserved'] and detail['new_immutable_receipt']
            elif case['category']=='security':
                fixture=copy.deepcopy(case);fixture['expected_plan']=case['boundary_fixture_plan'];detail=evaluator.security(fixture)
            else:detail=evaluator.offline(case)
            records.append({'id':case['id'],'category':case['category'],'split':case['split'],'status':'PASS' if detail.get('passed') else 'FAIL','detail':detail,'seconds':time.perf_counter()-started})
        except Exception as exc:records.append({'id':case['id'],'category':case['category'],'split':case['split'],'status':'FAIL','error':str(exc),'error_type':type(exc).__name__})
    result={'goldset_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'implementation_root':str(ROOT),'scope':'synthetic numerical/boundary contracts only, not live GPT or live KOSIS',
        'summary':{'total':len(records),'passed':sum(r['status']=='PASS' for r in records),'failed':sum(r['status']=='FAIL' for r in records),'skipped':0,
            'checked_points':sum(r.get('detail',{}).get('checked_points',0) for r in records),'categories':{c:dict(Counter(r['status'] for r in records if r['category']==c)) for c in sorted({r['category'] for r in records})}},'seconds':time.perf_counter()-tick,'records':records}
    dump(args.output,result);print(json.dumps(result['summary'],ensure_ascii=False));return int(result['summary']['failed']>0)

if __name__=='__main__':raise SystemExit(main())
