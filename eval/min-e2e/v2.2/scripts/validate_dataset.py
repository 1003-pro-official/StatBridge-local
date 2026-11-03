"""Independent offline dataset checks, not a product evaluation run."""
from pathlib import Path
from decimal import Decimal,getcontext
from collections import Counter
from copy import deepcopy
import argparse,json,hashlib,sys,os,re,ast
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from score_predictions import score_case,compare_state,read_cases,source_key
getcontext().prec=45
def numeric_reference(c,fixture):
    # Direct formulas keyed to authored economic definitions, not a plan interpreter.
    a=list(map(Decimal,fixture['a']));b=list(map(Decimal,fixture['b']));g=[y-x for x,y in zip(a,b)];r=[y/x for x,y in zip(a,b)]
    avg=lambda xs:sum(xs)/Decimal(len(xs));n=int(c['id'][1:]);out={}
    expected_months=[v['period'] for v in c['expected']['expected']]
    for month in expected_months:
        t=fixture['months'].index(month)
        if n==21:v=g[t]-g[t-2]
        elif n==22:v=g[t]-g[t-3]
        elif n==23:v=avg(g[t-1:t+1])
        elif n==24:v=avg(g[t-3:t+1])
        elif n==25:v=avg([a[t]-a[t-1],a[t-1]-a[t-2]])
        elif n==26:v=avg([b[i]-b[i-1] for i in range(t-2,t+1)])
        elif n==27:v=avg(a[t-2:t+1])-avg(a[t-3:t])
        elif n==28:v=avg(b[t-2:t+1])-avg(b[t-3:t])
        elif n==29:v=a[t]-a[t-2]
        elif n==30:v=b[t]-b[t-3]
        elif n==31:v=r[t]
        elif n==32:v=avg(r[t-2:t+1])
        elif n==33:v=avg(b[t-2:t+1])/avg(a[t-2:t+1])
        elif n==34:v=r[t]-r[t-1]
        elif n==35:v=a[t]/a[1]*100-b[t]/b[1]*100
        elif n==36:v=g[t]/g[0]*100
        elif n==37:v=(g[t]/g[t-1]-1)*100
        elif n==38:v=(a[t]/a[t-2]-1)*100
        elif n==39:v=avg(g[3:6])
        elif n==40:v=avg(r)
        else:raise AssertionError(n)
        out[month]=v
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--local1',type=Path,required=True);args=ap.parse_args()
    cases=read_cases();inputs=[json.loads(l) for l in (ROOT/'runner/questions.jsonl').read_text(encoding='utf-8').splitlines()];scenarios=json.loads((ROOT/'runner/scenarios.json').read_text(encoding='utf-8'))
    results=[]
    def check(name,condition,detail=None):
        results.append({'check':name,'status':'pass' if condition else 'fail','detail':detail})
        if not condition:print('FAIL',name,detail)
    check('120 unique cases',len(cases)==len({c['id'] for c in cases})==120)
    check('six domains x20',Counter(c['group'] for c in cases)==Counter({g:20 for g in ['QT','CQ','DA','D','E','F']}))
    check('120 unique query texts',len({c['query'] for c in cases})==120)
    check('input gold separation',all(set(q)=={'id','query'} for q in inputs) and inputs==[{'id':c['id'],'query':c['query']} for c in cases])
    check('no fabricated product results',all(c.get('product_evaluation_executed') is False and c['human_review']=='pending' for c in cases))
    original=json.loads((ROOT/'fixtures/v2_source_contract.json').read_text(encoding='utf-8-sig'))
    original_queries={c['id']:c['query'] for c in original['cases']}
    original_queries.update({q['id']:q['query'] for q in [json.loads(l) for l in (ROOT/'fixtures/v21_queries_source.jsonl').read_text(encoding='utf-8-sig').splitlines()]})
    check('original queries unchanged',all(c['query']==original_queries[c['id']] for c in cases))
    query_md=(ROOT/'01_질의전용_120문항.md').read_text(encoding='utf-8-sig')
    gold_md=(ROOT/'02_질의와_정답_120문항.md').read_text(encoding='utf-8-sig')
    review_md=(ROOT/'04_정답_사람검토_120문항.md').read_text(encoding='utf-8-sig')
    check('human query list has 120 IDs',sum(line.startswith('### ') for line in query_md.splitlines())==120 and all(c['query'] in query_md for c in cases))
    check('Notion reference table has 120 rows',sum(bool(re.match(r'^\| (?:QT21-|CQ21-|DA21-|D\d|E\d|F\d)',line)) for line in gold_md.splitlines())==120)
    check('human approval form has 120 pending rows',review_md.count('| 검토 대기 |')==120)
    pilot=json.loads((ROOT/'runner/pilot_ids.json').read_text(encoding='utf-8'))
    check('pilot 12 covers six domains',len(pilot)==len(set(pilot))==12 and Counter(next(c['group'] for c in cases if c['id']==pid) for pid in pilot)=={g:2 for g in ['QT','CQ','DA','D','E','F']})
    excerpt=json.loads((ROOT/'oracle/catalog_excerpt.json').read_text(encoding='utf-8'))
    for c in cases:
        check(c['id']+' complete contract',bool(c['query'] and c['expected'] and c['metrics']))
        if c['group']=='DA':
            s=c['expected']['sources'][0];tid=s['table_id'];catalog_ok=tid in excerpt['tables'] and any(i['TBL_ID']==tid and i['ITM_ID']==s['item_id'] for i in excerpt['items'])
            catalog_ok &= all(any(r['TBL_ID']==tid and 'objL'+r['OBJ_ID_SN']==k and r['ITM_ID']==v for r in excerpt['classifications']) for k,v in s['classifications'].items())
            check(c['id']+' catalog identity',catalog_ok)
            p=ROOT/c['expected']['snapshot_file'];d=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
            ok=d.get('status')=='fetched' and Counter(r['period'] for r in d.get('rows',[]))==Counter(c['expected']['periods'])
            if ok:
                ok=all(source_key(r)==source_key(s) for r in d['rows'])
                ok &= all(Decimal(r['value']).is_finite() and r['unit'] for r in d['rows'])
                ok &= d['response_sha256']==hashlib.sha256(json.dumps(d['response'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            check(c['id']+' direct API oracle',ok,{'rows':len(d.get('rows',[]))})
            if c['expected'].get('equivalence_snapshot_file'):
                from score_predictions import compare_rows
                alt=ROOT/c['expected']['equivalence_snapshot_file'];ad=json.loads(alt.read_text(encoding='utf-8')) if alt.exists() else {}
                check(c['id']+' equivalent GDP source verified',ad.get('status')=='fetched' and compare_rows(ad.get('rows'),d.get('rows')))
        if c['group']=='CQ':
            e=c['expected'];check(c['id']+' ambiguity contract',bool(e['missing_slots'])==e['clarification_required'] and bool(e['preserve_conditions']))
        if c['group'] in {'E','F'}:
            check(c['id']+' ordered checkpoints',len(c['expected']['checkpoints'])==len(scenarios[c['id']]['ordered_steps']))
            check(c['id']+' preserves 12 source values',all(cp['expected_state']['series'][a]['values']==dict(zip(original['fixture']['months'],original['fixture'][a])) for cp in c['expected']['checkpoints'] for a in ['a','b']))
            if c['group']=='F':check(c['id']+' export contracts',len(c['expected']['downloads'])>=2 and all(d['step']<=len(c['expected']['checkpoints']) and d['format'] in ['png','pdf','svg','csv','xlsx'] for d in c['expected']['downloads']))
        if c['group']=='D':
            ref=numeric_reference(c,original['fixture']);check(c['id']+' independent Decimal formula',all(abs(ref[r['period']]-Decimal(r['value']))<=Decimal('0.000001') for r in c['expected']['expected']))
    qt=[c for c in cases if c['group']=='QT'];cq=[c for c in cases if c['group']=='CQ']
    check('QT balanced 10/10',Counter(c['expected']['label'] for c in qt)=={'general':10,'derived':10})
    check('CQ balanced 10/10',Counter(c['expected']['clarification_required'] for c in cq)=={True:10,False:10})
    # Meaningful corner cases in the reference model.
    by={c['id']:c for c in cases}
    check('E24 undo2 redo1 removes B dash',by['E24']['expected']['final_state']['series']['b']['dash']=='solid' and by['E24']['expected']['final_state']['series']['a']['color']=='#E53935')
    check('E33 ambiguity preserves initial revision',by['E33']['expected']['checkpoints'][0]['clarification']['revision_unchanged'])
    check('E37 removes residual segment style',by['E37']['expected']['final_state']['series']['a']['segments']==[])
    check('E40 restores initial snapshot',by['E40']['expected']['final_state']==json.loads((ROOT/'fixtures/baseline.json').read_text(encoding='utf-8')))
    check('F23 preserves two export revisions',by['F23']['expected']['downloads'][0]['expected_state']['legend_visible'] is False and by['F23']['expected']['downloads'][1]['expected_state']['legend_visible'] is True)
    check('F39 preserves old title export',by['F39']['expected']['downloads'][0]['expected_state']['title']=='1차 검토' and by['F39']['expected']['downloads'][1]['expected_state']['title']=='2차 검토')
    check('D32 differs from D33',by['D32']['expected']['expected']!=by['D33']['expected']['expected'])
    # Offline integration with the designated local1 expression engine, not natural-language/UI execution.
    os.environ['PYTHONDONTWRITEBYTECODE']='1';os.environ['LANGFUSE_TRACING_ENABLED']='false'
    os.environ['STATBRIDGE_DATA_DIR']=str(args.local1/'data/processed')
    sys.path[:0]=[str(args.local1/'src/agent'),str(args.local1/'src/backend')]
    try:
        from expression_tree_schema import ExpressionPlan
        from expression_tree_validator import validate_plan
        from dynamic_expression_executor import DynamicExpressionExecutor,Series
        from derived_catalog_tools import DerivedCatalogTools
        from statbridge_mcp.metadata_store import MetadataStore
        catalog=DerivedCatalogTools(MetadataStore())
        for c in cases:
            if c['group']!='D':continue
            try:
                plan=ExpressionPlan.model_validate(c['expected']['plan']);bounds=validate_plan(plan,catalog)
                sources={a:Series(dict(zip(original['fixture']['months'],map(float,original['fixture'][a]))),'연리%','M',[a]) for a in ['a','b']}
                actual=DynamicExpressionExecutor().execute(plan,sources)['rows'];ref=numeric_reference(c,original['fixture'])
                ok=len(actual)==len(ref) and all(r['PRD_DE'] in ref and r['UNIT_NM']==c['expected']['unit'] and abs(Decimal(str(r['DT']))-ref[r['PRD_DE']])<=Decimal('0.000001') for r in actual) and bounds==c['expected']['history']
                check(c['id']+' local1 engine offline',ok)
            except Exception as exc:check(c['id']+' local1 engine offline',False,type(exc).__name__)
    except Exception as exc:check('local1 engine available',False,type(exc).__name__)
    # Scorer mutation checks use synthetic observations, never counted as product scores.
    mutations=0
    for c in cases:
        g=c['group'];e=c['expected'];p={'id':c['id'],'run_status':'completed'}
        if g=='QT':p['label']=e['label'];bad=deepcopy(p);bad['label']='derived' if p['label']=='general' else 'general'
        elif g=='DA':
            d=json.loads((ROOT/e['snapshot_file']).read_text(encoding='utf-8'));p.update(sources=e['sources'],rows=[{k:r[k] for k in ['period','value','unit']} for r in d.get('rows',[])])
            p['table_rows']=deepcopy(p['rows']);bad=deepcopy(p)
            if bad['rows']:bad['rows'][0]['value']=str(Decimal(bad['rows'][0]['value'])+1)
        elif g=='D':
            p.update(sources=[{'org_id':'301',**s} for s in e['plan']['sources']],rows=[{'period':r['period'],'value':r['value'],'unit':e['unit']} for r in e['expected']],observed_source_rows={a:dict(zip(original['fixture']['months'],original['fixture'][a])) for a in ['a','b']})
            bad=deepcopy(p);bad['rows'][0]['unit']='WRONG_UNIT'
        elif g=='E':
            p['checkpoints']=[{'step':cp['step'],'state':deepcopy(cp['expected_state']),**({'clarification_slots':cp['clarification']['slots'],'revision_unchanged':True} if cp['clarification'] else {})} for cp in e['checkpoints']]
            bad=deepcopy(p);bad['checkpoints'][-1]['state']['series']['a']['color']='#000000'
        elif g=='CQ':
            p.update(clarification_required=e['clarification_required'],executed=not e['clarification_required'],query_resolved=True,response_text='synthetic scorer self-test, not product output')
            p['semantic_review']={'response_sha256':hashlib.sha256(p['response_text'].encode()).hexdigest(),'target_correct':True,'conditions_preserved':True,'human_reviewed':True,'reason':'synthetic test only'}
            bad=deepcopy(p);bad['semantic_review']['target_correct']=False
        elif g=='F':
            p['checkpoints']=[{'step':cp['step'],'state':deepcopy(cp['expected_state'])} for cp in e['checkpoints']]
            good=score_case(c,p);bad=deepcopy(p);bad['checkpoints'][-1]['state']['series']['a']['width']=99
            negative=score_case(c,bad)
            check(c['id']+' scorer observes checkpoint match',good['checks']['edit_contract'] is True)
            check(c['id']+' scorer rejects checkpoint mutation',negative['checks']['edit_contract'] is False)
            check(c['id']+' missing file evidence not pass',good['status']!='pass');mutations+=1
            continue
        else:continue
        good=score_case(c,p);negative=score_case(c,bad)
        check(c['id']+' scorer accepts fixture observation',good['status']=='pass')
        check(c['id']+' scorer rejects mutation',negative['status']=='fail');mutations+=1
    # Missing evidence must not be silently marked successful.
    check('CQ missing semantic review stays pending',score_case(by['CQ21-01'],{'run_status':'completed','clarification_required':True,'executed':False})['status']=='pending')
    check('F missing artifacts cannot pass',score_case(by['F21'],{'run_status':'completed','checkpoints':[{'step':cp['step'],'state':cp['expected_state']} for cp in by['F21']['expected']['checkpoints']]})['status']!='pass')
    check('provider error not semantic failure',score_case(by['DA21-01'],{'run_status':'provider_error'})['status']=='provider_error')
    check('metadata wait not semantic failure',score_case(by['CQ21-01'],{'run_status':'metadata_verifying'})['status']=='metadata_verifying')
    check('not executed remains not executed',score_case(by['QT21-01'],None)['status']=='not_executed')
    from export_ragas import export_record
    synthetic={'run_status':'completed','response_text':'synthetic statement','evidence_contexts':[{'origin':'official_api_response','capture_id':'self-test-only','text':'synthetic evidence'}]}
    exported,reason=export_record(by['DA21-01'],synthetic)
    check('RAGAS export preserves query and observed evidence',exported is not None and exported['user_input']==by['DA21-01']['query'] and exported['retrieved_contexts']==['synthetic evidence'])
    bad=deepcopy(synthetic);bad['evidence_contexts'][0]['origin']='gold_answer'
    check('RAGAS export rejects oracle as evidence',export_record(by['DA21-01'],bad)[0] is None)
    bad=deepcopy(synthetic);bad['evidence_contexts']=[]
    check('RAGAS export does not invent missing context',export_record(by['DA21-01'],bad)[0] is None)
    empty_guard=ROOT/'validation/empty_run_score_guard.json'
    if empty_guard.exists():
        guard=json.loads(empty_guard.read_text(encoding='utf-8'))
        check('empty actual run never becomes a product pass',all(r['status']=='not_executed' for r in guard['results']) and len(guard['results'])==120)
    for p in (ROOT/'scripts').glob('*.py'):
        try:ast.parse(p.read_text(encoding='utf-8'));ok=True
        except SyntaxError:ok=False
        check(p.name+' syntax',ok)
    failures=[r for r in results if r['status']=='fail']
    summary={'status':'pass' if not failures else 'fail','checks':len(results),'passed':len(results)-len(failures),'failed':len(failures),'cases':120,'groups':dict(Counter(c['group'] for c in cases)),'scorer_mutation_pairs':mutations,'human_review':'pending','product_evaluation_executed':False,'browser_e2e_executed':False,'ragas_judge_executed':False,'live_oracle_retrieval_is_not_product_test':True,'results':results}
    (ROOT/'validation/dataset_validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='results'},ensure_ascii=False))
    return bool(failures)
if __name__=='__main__':raise SystemExit('Use validate_reviewed.py; v1 validation assumptions do not apply to dynamic initial snapshots.')
