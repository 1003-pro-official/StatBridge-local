"""Reviewed scoring. Original scores stay untouched; unknown evidence never passes."""
from pathlib import Path
from copy import deepcopy
import argparse,json,hashlib,math
from collections import Counter
from legacy_score_core import score_case as legacy_score,compare_state,source_key,close
from reviewed_evidence import capture,contract_sha,finite_positive,canonical,sha
ROOT=Path(__file__).resolve().parents[1]
def evidence_refs_valid(review,p,root):
    if root is None or not review.get('evidence_refs'):return False
    root=Path(root).resolve();cid=p['id']
    for ref in review['evidence_refs']:
        f=(root/ref.get('path','')).resolve()
        if not f.is_relative_to(root) or not f.is_file() or f.parent.name!=cid or sha(f.read_bytes())!=ref.get('sha256'):return False
    if cid.startswith('CQ'):
        try:
            packet={'query_response':json.loads((root/cid/'query.json').read_text(encoding='utf-8'))['response'],'output_response':json.loads((root/cid/'output.json').read_text(encoding='utf-8'))['response'] if (root/cid/'output.json').exists() else None}
            if p.get('response_text')!=json.dumps(packet,ensure_ascii=False,sort_keys=True):return False
        except (ValueError,KeyError,OSError):return False
    return True

def approved(c):
    a=c.get('approval',{})
    return a.get('status')=='APPROVED' and a.get('actor_type')=='human' and bool(a.get('reviewer')) and bool(a.get('approved_at')) and a.get('approved_contract_sha256')==contract_sha(c)
def unavailable(cid,g,reason,classification='EVIDENCE_GAP'):
    return {'id':cid,'group':g,'status':classification,'rule_status':'pending','classification':classification,'reason':reason}
def score(c,p,artifact_root=None):
    cid=c['id'];g=c['group'];original=deepcopy(c)
    if p is None:return {'id':cid,'group':g,'status':'NOT_EXECUTED','rule_status':'not_executed'}
    if p.get('id',cid)!=cid:return unavailable(cid,g,'observation case binding mismatch','HARNESS_ERROR')
    if p.get('run_status') in {'provider_error','metadata_verifying','evaluator_error','not_executed'}:
        return {'id':cid,'group':g,'status':p['run_status'].upper(),'rule_status':'pending','classification':'HARNESS_ERROR' if p['run_status']=='evaluator_error' else 'EVIDENCE_GAP'}
    if p.get('run_status')=='product_failure':
        failure,error=capture(p.get('failure_capture'),cid,p.get('run_id'),artifact_root,{'product_failure_observation'})
        if not failure or failure['payload'].get('run_status')!='product_failure':return unavailable(cid,g,'Product failure claim has no bound execution capture: '+str(error))
        return {'id':cid,'group':g,'status':'FAIL','rule_status':'fail','classification':'PRODUCT_DEFECT','confirmation':'bound product failure observation; root cause still requires review'}
    if p.get('run_status')!='completed':return unavailable(cid,g,'No observed completed response')
    if not p.get('run_id'):return unavailable(cid,g,'Run ID required before combining score or evidence')
    def nonfinite(value):
        if isinstance(value,float):return not math.isfinite(value)
        if isinstance(value,dict):return any(nonfinite(v) for v in value.values())
        if isinstance(value,list):return any(nonfinite(v) for v in value)
        return False
    if nonfinite(p):return unavailable(cid,g,'Non-finite observation number','HARNESS_ERROR')
    q=deepcopy(p);case=deepcopy(c);extra={};reasons=[]
    if g=='D':
        used=p.get('calculation_input_series');display=p.get('display_only_series')
        if not isinstance(used,list) or not isinstance(display,list):return unavailable(cid,g,'Calculation inputs and display-only series are not observed separately')
        extra['calculation_input_roles']=set(used)==set(c['calculation_input_series'])
        extra['display_roles']=set(display)==set(c['display_only_series'])
        sources=p.get('calculation_sources')
        if not isinstance(sources,list):return unavailable(cid,g,'Need actual computation sources; retrieved sources are not automatically computation inputs')
        q['sources']=sources
        fixture=json.loads((ROOT/'fixtures/v2_source_contract.json').read_text(encoding='utf-8'))['fixture']
        raw=p.get('observed_source_rows',{})
        for alias in c['calculation_input_series']:
            observed=raw.get(alias)
            expected_values=dict(zip(fixture['months'],fixture[alias]))
            extra['raw_input_values_'+alias]=None if not isinstance(observed,dict) or not observed else all(period in expected_values and close(value,expected_values[period]) for period,value in observed.items())
        # Preserve evidence of unrelated fetched series as diagnostic, not a missing-calculation-input penalty.
    if g in {'E','F'}:
        snapshots=p.get('snapshots',{})
        initial,ie=capture(snapshots.get('initial_query'),cid,p['run_id'],artifact_root,{'initial_query_snapshot'})
        ready,re=capture(snapshots.get('fixture_ready'),cid,p['run_id'],artifact_root,{'fixture_ready_snapshot'})
        expected_baseline=json.loads((ROOT/'fixtures/baseline.json').read_text(encoding='utf-8'))
        if not initial or not ready:
            return unavailable(cid,g,'Initial query and fixture-ready snapshots must be captured separately: '+str(ie or re))
        if not isinstance(initial.get('sequence'),int) or not isinstance(ready.get('sequence'),int) or initial['sequence']>=ready['sequence']:
            return unavailable(cid,g,'Snapshot order is missing or invalid','HARNESS_ERROR')
        if compare_state(ready['payload'].get('state'),expected_baseline):return unavailable(cid,g,'Fixture preparation does not match declared baseline','HARNESS_ERROR')
        observations=p.get('checkpoints',[])
        if len(observations)!=len(case['expected']['checkpoints']) or len({o.get('step') for o in observations})!=len(observations):return unavailable(cid,g,'Missing or duplicate UI checkpoints','HARNESS_ERROR')
        by={o['step']:o for o in observations}
        for cp in case['expected']['checkpoints']:
            o=by.get(cp['step'],{});doc,error=capture(o.get('capture'),cid,p['run_id'],artifact_root,{'ui_checkpoint'})
            if not doc or doc.get('step')!=cp['step'] or doc['payload'].get('state')!=o.get('state'):return unavailable(cid,g,'Checkpoint capture mismatch: '+str(error),'HARNESS_ERROR')
            if cp.get('expected_state_ref')=='initial_query_snapshot':cp['expected_state']=deepcopy(initial['payload']['state'])
        for d in case['expected']['downloads']:
            if d.get('expected_state_ref')=='initial_query_snapshot':d['expected_state']=deepcopy(initial['payload']['state'])
        if case['expected'].get('table_graph_independence'):
            required=case['expected']['table_graph_independence']['table_series']
            extra['graph_hide_does_not_change_table_selection']=all(o['state'].get('table_series')==required for o in observations)
        for i,req in enumerate(case['expected'].get('visible_point_requirements',[])):
            matches=[r for r in p.get('rendered_points',[]) if (r.get('step'),r.get('alias'),r.get('period'))==(req['step'],req['alias'],req['period'])]
            key=f'visible_point_{i+1}'
            if len(matches)!=1:extra[key]=None;continue
            r=matches[0];doc,error=capture(r.get('capture'),cid,p['run_id'],artifact_root,{'rendered_point_observation'})
            observed={k:v for k,v in r.items() if k!='capture'}
            if not doc or doc['payload']!=observed:extra[key]=None;continue
            extra[key]=r.get('visible') is True and finite_positive(r.get('marker_size_px')) and str(r.get('color')).lower()==req['color'].lower() and r.get('position_matches') is True and r.get('within_plot') is True and r.get('occluded') is False
    if g=='CQ':
        review=p.get('semantic_review',{})
        valid_review=review.get('actor_type') in {'human','ai_model'} and bool(review.get('reviewer')) and bool(review.get('reviewed_at') or review.get('approved_at')) and evidence_refs_valid(review,p,artifact_root)
        if not valid_review:q['semantic_review']={}
        else:
            q['semantic_review']=deepcopy(review)
            q['semantic_review']['evidence_reviewed']=True
    result=legacy_score(case,q,artifact_root)
    checks=result.get('checks',{});checks.update(extra)
    if g=='F':
        wanted=case['expected']['downloads'];downloads=q.get('downloads',[])
        any_confirmed_failure=False;all_reviewed=len(downloads)==len(wanted)
        for i,(w,a) in enumerate(zip(wanted,downloads)):
            root=Path(artifact_root).resolve() if artifact_root else None
            path=(root/a.get('path','')).resolve() if root else None
            valid=bool(path and path.is_relative_to(root) and path.is_file() and sha(path.read_bytes())==a.get('sha256'))
            review=a.get('independent_artifact_review',{});refhash=sha(canonical(w['expected_state']).encode())
            binding=valid and review.get('artifact_sha256')==a.get('sha256') and review.get('reference_state_sha256')==refhash and a.get('step')==w['step'] and a.get('format')==w['format']
            if w['format'] in {'png','pdf'}:
                human=binding and review.get('actor_type')=='human' and review.get('approval')=='APPROVED' and bool(review.get('reviewer')) and bool(review.get('approved_at'))
                checks[f'file_{i+1}_human_visual_approval']=True if human and review.get('matches') is True else False if human and review.get('matches') is False else None
                all_reviewed &= human and isinstance(review.get('matches'),bool)
                if human and review.get('matches') is False:any_confirmed_failure=True
            elif w['format']=='svg':
                components=review.get('component_results',{})
                required=c['expected'].get('svg_components_required',['base_line_color','line_width','line_dash','legend','period_and_coordinates'])
                inspected=binding and review.get('method')=='svg_attribute_and_render_review' and review.get('actor_type') in {'independent_parser','human'} and all(isinstance(components.get(k),bool) for k in required)
                checks[f'file_{i+1}_svg_components']=all(components[k] for k in required) if inspected else None
                all_reviewed &= inspected
                if inspected and (review.get('matches') is False or any(components[k] is False for k in required)):any_confirmed_failure=True
            else:
                inspected=binding and review.get('method')=='decoded_numeric_compare' and review.get('actor_type') in {'independent_parser','human'} and isinstance(review.get('matches'),bool)
                all_reviewed &= inspected
                if inspected and review['matches'] is False:any_confirmed_failure=True
        checks['screen_file_consistency']=False if any_confirmed_failure else (True if all_reviewed else None)
        if len(downloads)!=len(wanted) and not p.get('download_failures_captured'):checks['download_coverage']=None;checks['file_integrity']=None
        # Ordinal, revision and capture bindings are required independently of filenames/hashes.
        checks['download_revision_binding']=all(a.get('ordinal')==w['ordinal'] and a.get('actual_revision') is not None and a.get('screen_revision')==a.get('actual_revision') and bool(a.get('capture_id')) for w,a in zip(wanted,downloads)) if len(downloads)==len(wanted) else None
    if g=='CQ' and 'latest_reference_pre_prediction' in p:
        checks['latest_reference_pre_prediction']=p['latest_reference_pre_prediction']
    if g=='D' and p.get('summary_review'):
        r=p['summary_review']
        checks['summary_semantics']=r.get('summary_semantics_correct') if evidence_refs_valid(r,p,artifact_root) and r.get('actor_type') in {'ai_model','human'} and r.get('reviewer') and r.get('reviewed_at') else None
    rule_status='fail' if any(v is False for v in checks.values()) else 'pending' if any(v is None for v in checks.values()) else 'pass'
    result.update(rule_status=rule_status,status='FAIL' if rule_status=='fail' else 'PASS' if rule_status=='pass' else 'EVIDENCE_GAP',classification='PRODUCT_DEFECT' if rule_status=='fail' else 'RULE_PASS' if rule_status=='pass' else 'EVIDENCE_GAP',oracle_approval_verified=False,final_human_approval_required=False,checks=checks)
    return result
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--predictions',type=Path,required=True);ap.add_argument('--artifacts',type=Path);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    if args.output.exists():raise SystemExit('Refuse overwrite; use a new run ID/output path')
    cases=[json.loads(l) for l in (ROOT/'oracle/cases.jsonl').read_text(encoding='utf-8').splitlines()]
    rows=[json.loads(l) for l in args.predictions.read_text(encoding='utf-8-sig').splitlines() if l.strip()];assert len({r['id'] for r in rows})==len(rows)
    obs={r['id']:r for r in rows};assert not set(obs)-{c['id'] for c in cases}
    results=[score(c,obs.get(c['id']),args.artifacts) for c in cases]
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps({'run_scope':'reviewed rule checks; separate from RAGAS','summary':{g:dict(Counter(r['status'] for r in results if r['group']==g)) for g in ['QT','CQ','DA','D','E','F']},'results':results},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
