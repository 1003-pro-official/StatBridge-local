"""Score normalized observations; no product calls, no inferred missing evidence."""
import argparse,csv,hashlib,json,re,math
from pathlib import Path
from decimal import Decimal,InvalidOperation
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
TOL=Decimal('0.000001')
def normalized_unit(x):return str(x or '').replace('＝','=').replace(' ','')
def source_key(s):
    return (str(s.get('org_id')),s.get('table_id'),s.get('item_id'),tuple(sorted(s.get('classifications',{}).items())),'Y' if s.get('frequency')=='A' else s.get('frequency'))
def close(a,b):
    try:return abs(Decimal(str(a))-Decimal(str(b)))<=TOL
    except (InvalidOperation,TypeError,ValueError):return False
def compare_state(actual,expected,path='state'):
    errors=[]
    if isinstance(expected,dict):
        if not isinstance(actual,dict):return [path+': missing object']
        if set(actual)!=set(expected):errors.append(path+': keys missing/extra')
        for k,v in expected.items():
            if k in actual:errors+=compare_state(actual[k],v,path+'.'+k)
    elif isinstance(expected,list):
        if not isinstance(actual,list) or len(actual)!=len(expected):return [path+': list length']
        for i,(a,b) in enumerate(zip(actual,expected)):errors+=compare_state(a,b,path+f'[{i}]')
    elif path.endswith(('.x','.y')) and isinstance(expected,(int,float)):
        if not isinstance(actual,(int,float)) or abs(actual-expected)>0.03:errors.append(path+': annotation position')
    elif '.values.' in path:
        if not close(actual,expected):errors.append(path+': numeric value')
    elif path.endswith('.color'):
        if str(actual).lower()!=str(expected).lower():errors.append(path+': color')
    elif actual!=expected:errors.append(path+': mismatch')
    return errors
def compare_rows(actual,expected):
    if not isinstance(actual,list) or len(actual)!=len(expected):return False
    key=lambda r:(str(r.get('period')),str(r.get('alias','')))
    if Counter(map(key,actual))!=Counter(map(key,expected)):return False
    aa=sorted(actual,key=key);ee=sorted(expected,key=key)
    return all(close(a.get('value'),b['value']) and normalized_unit(a.get('unit'))==normalized_unit(b.get('unit')) for a,b in zip(aa,ee))
def read_cases():return [json.loads(l) for l in (ROOT/'oracle/cases.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
def score_case(c,p,artifact_root=None):
    cid=c['id'];g=c['group'];e=c['expected'];checks={};notes=[]
    if p is None:return {'id':cid,'group':g,'status':'not_executed','checks':{}}
    if p.get('run_status') in {'provider_error','metadata_verifying','not_executed','evaluator_error'}:
        return {'id':cid,'group':g,'status':p['run_status'],'checks':{},'note':'Not a semantic failure; report coverage separately.'}
    if p.get('run_status')=='product_failure':return {'id':cid,'group':g,'status':'fail','checks':{'product_completed':False}}
    if p.get('run_status')!='completed':return {'id':cid,'group':g,'status':'unobserved','checks':{}}
    if g=='QT':checks['intent_accuracy']=p.get('label')==e['label'] if p.get('label') in {'general','derived'} else None
    elif g=='CQ':
        checks['clarification_decision']=p.get('clarification_required')==e['clarification_required'] if isinstance(p.get('clarification_required'),bool) else None
        checks['no_premature_execution']=not p.get('executed',False) if e['clarification_required'] and 'executed' in p else (None if e['clarification_required'] else True)
        # Semantic observations must be grounded in response and independently reviewed.
        judged=p.get('semantic_review',{})
        fingerprint=hashlib.sha256(str(p.get('response_text','')).encode()).hexdigest()
        valid=judged.get('response_sha256')==fingerprint and judged.get('evidence_reviewed') is True and bool(judged.get('reason'))
        checks['clarification_target']=judged.get('target_correct') if valid and isinstance(judged.get('target_correct'),bool) else None
        checks['condition_preservation']=judged.get('conditions_preserved') if valid and isinstance(judged.get('conditions_preserved'),bool) else None
        if e['clarification_required'] is False:checks['query_resolved']=p.get('query_resolved') if isinstance(p.get('query_resolved'),bool) else None
    elif g in {'DA','D'}:
        expected_sources=e['sources'] if g=='DA' else e['plan']['sources']
        expected_sources=[{'org_id':'301',**s} for s in expected_sources]
        allowed=[expected_sources]
        if g=='DA' and e.get('allowed_source_sets'):
            alt=ROOT/e['equivalence_snapshot_file'];primary=ROOT/e['snapshot_file']
            if alt.exists() and primary.exists():
                ad=json.loads(alt.read_text(encoding='utf-8'));pd=json.loads(primary.read_text(encoding='utf-8'))
                if ad.get('status')==pd.get('status')=='fetched' and compare_rows(ad['rows'],pd['rows']):allowed=e['allowed_source_sets']
        checks['source_exact_match']=any(Counter(map(source_key,p['sources']))==Counter(map(source_key,sset)) for sset in allowed) if isinstance(p.get('sources'),list) else None
        if g=='DA':
            snap=ROOT/e['snapshot_file'];oracle=json.loads(snap.read_text(encoding='utf-8')) if snap.exists() else {}
            rr=oracle.get('rows',[]) if oracle.get('status')=='fetched' else []
            target=[{'period':r['period'],'value':r['value'],'unit':r['unit']} for r in rr]
        else:target=[{'period':r['period'],'value':r['value'],'unit':e['unit']} for r in e['expected']]
        if not target:checks['numeric_unit_match']=None;notes.append('Oracle unavailable; not a product failure.')
        else:
            checks['numeric_unit_match']=compare_rows(p['rows'],target) if isinstance(p.get('rows'),list) else None
        periods=[r['period'] for r in target]
        checks['period_frequency_match']=Counter(str(r.get('period')) for r in p['rows'])==Counter(periods) if periods and isinstance(p.get('rows'),list) else None
        if g=='DA':checks['required_table']=compare_rows(p['table_rows'],target) if target and isinstance(p.get('table_rows'),list) else None
        else:
            h=e['history'];inputs=p.get('observed_source_rows')
            if isinstance(inputs,dict):
                from datetime import date
                def months(start,end):
                    y,m=int(start[:4]),int(start[4:]);out=[]
                    while f'{y:04}{m:02}'<=end:
                        out.append(f'{y:04}{m:02}');m+=1
                        if m==13:y+=1;m=1
                    return out
                required=set(months(h['fetch_start'],h['fetch_end']))
                checks['lookback_coverage']=all(required<=set(inputs.get(s['alias'],{})) for s in e['plan']['sources'])
            else:checks['lookback_coverage']=None
    else:
        actual=p.get('checkpoints',[]);by_step={a.get('step'):a for a in actual if isinstance(a,dict)}
        checks['checkpoint_coverage']=len(actual)==len(e['checkpoints']) and set(by_step)=={a['step'] for a in e['checkpoints']}
        differences=[]
        for cp in e['checkpoints']:
            obs=by_step.get(cp['step'])
            if obs is None:continue
            differences+=compare_state(obs.get('state'),cp['expected_state'],f'step{cp["step"]}')
            if cp['clarification']:
                if obs.get('clarification_slots')!=cp['clarification']['slots'] or obs.get('revision_unchanged') is not True:differences.append('clarification or revision changed')
        checks['edit_contract']=not differences if checks['checkpoint_coverage'] else None
        notes+=differences[:12]
        if g=='F':
            files=p.get('downloads',[]);checks['download_coverage']=len(files)==len(e['downloads'])
            structural=[];semantic=[]
            for wanted,actual_file in zip(e['downloads'],files):
                valid=False
                if artifact_root is not None:
                    path=(Path(artifact_root)/actual_file.get('path','')).resolve();root=Path(artifact_root).resolve()
                    if path.is_relative_to(root) and path.is_file():
                        b=path.read_bytes();fmt=wanted['format']
                        signature={'png':lambda b:b.startswith(b'\x89PNG\r\n\x1a\n'),'pdf':lambda b:b.startswith(b'%PDF-'),'xlsx':lambda b:b.startswith(b'PK'),'svg':lambda b:b'<svg' in b[:2000],'csv':lambda b:bool(b)}[fmt]
                        valid=bool(b) and signature(b) and hashlib.sha256(b).hexdigest()==actual_file.get('sha256')
                        if valid:
                            review=actual_file.get('independent_artifact_review',{})
                            expected_sha=hashlib.sha256(json.dumps(wanted['expected_state'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
                            semantic.append(review.get('matches') if review.get('artifact_sha256')==actual_file.get('sha256') and review.get('reference_state_sha256')==expected_sha and review.get('method') in ['decoded_numeric_compare','svg_attribute_and_render_review','rendered_image_human_review'] and review.get('reviewer') and review.get('reason') else None)
                structural.append(valid and actual_file.get('step')==wanted['step'] and actual_file.get('format')==wanted['format'])
            checks['file_integrity']=all(structural) if checks['download_coverage'] else None
            checks['screen_file_consistency']=(all(semantic) if semantic and all(isinstance(s,bool) for s in semantic) and len(semantic)==len(e['downloads']) else None)
            notes.append('File signature/hash alone never establishes rendered/numeric agreement; independent review is required.')
    status='fail' if any(v is False for v in checks.values()) else ('pending' if not checks or any(v is None for v in checks.values()) else 'pass')
    return {'id':cid,'group':g,'status':status,'checks':checks,'notes':notes,'human_oracle_review':c['human_review'],'scope':'specified rule checks only; RAGAS and optional claims reported separately'}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--predictions',type=Path,required=True);ap.add_argument('--artifacts',type=Path);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    ps=[json.loads(l) for l in args.predictions.read_text(encoding='utf-8-sig').splitlines() if l.strip()];assert len({p['id'] for p in ps})==len(ps),'Duplicate predictions'
    obs={p['id']:p for p in ps};cases=read_cases();assert not set(obs)-{c['id'] for c in cases},'Unknown IDs'
    results=[score_case(c,obs.get(c['id']),args.artifacts) for c in cases]
    summary={g:dict(Counter(r['status'] for r in results if r['group']==g)) for g in ['QT','CQ','DA','D','E','F']}
    rates={}
    for g,counts in summary.items():
        passed=counts.get('pass',0);failed=counts.get('fail',0);judged=passed+failed
        rates[g]={'planned':20,'judged':judged,'judgment_coverage':judged/20,'pass_rate_among_judged':passed/judged if judged else None,'pass_fraction_of_planned':passed/20,'unjudged':20-judged}
    def binary_stats(rows,positive):
        if not rows:return {'n':0,'precision':None,'recall':None,'f1':None}
        tp=sum(y==positive and p==positive for y,p in rows);fp=sum(y!=positive and p==positive for y,p in rows);fn=sum(y==positive and p!=positive for y,p in rows)
        return {'n':len(rows),'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}
    intent_rows=[(c['expected']['label'],obs[c['id']]['label']) for c in cases if c['group']=='QT' and c['id'] in obs and obs[c['id']].get('run_status')=='completed' and obs[c['id']].get('label') in {'general','derived'}]
    intent={label:binary_stats(intent_rows,label) for label in ['general','derived']}
    intent['macro_f1']=sum(intent[label]['f1'] for label in ['general','derived'])/2 if all(intent[label]['f1'] is not None for label in ['general','derived']) else None
    intent['accuracy']=sum(y==p for y,p in intent_rows)/len(intent_rows) if intent_rows else None
    cq_rows=[(c['expected']['clarification_required'],obs[c['id']]['clarification_required']) for c in cases if c['group']=='CQ' and c['id'] in obs and obs[c['id']].get('run_status')=='completed' and isinstance(obs[c['id']].get('clarification_required'),bool)]
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps({'summary':summary,'group_rates':rates,'intent_metrics':intent,'clarification_decision_metrics':binary_stats(cq_rows,True),'results':results,'warning':'Oracle human review pending; no combined 100-point score.'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
