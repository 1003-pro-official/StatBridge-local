"""Evidence-bounded RAGAS inputs; never rescores without actual artifacts."""
from pathlib import Path
import argparse,json,hashlib
from reviewed_evidence import capture,lookup,canonical,sha
ROOT=Path(__file__).resolve().parents[1]
ORIGINS={'retrieval_trace','official_api_response','executed_calculation_evidence','official_metadata_snapshot'}
def export(case,p,artifact_root):
    run_id=p.get('run_id');cid=case['id'];status=p.get('run_status')
    reason={'metadata_verifying':'METADATA_PENDING','provider_error':'PROVIDER_FAILURE','product_failure':'CALCULATION_OR_PRODUCT_INCOMPLETE','evaluator_error':'HARNESS_ERROR','not_executed':'NOT_EXECUTED'}.get(status)
    if reason:return None,reason
    if status!='completed':return None,'COMPLETION_UNOBSERVED'
    if p.get('response_kind')=='clarification':return None,'EXPECTED_CLARIFICATION' if case.get('clarification_required') else 'UNEXPECTED_CLARIFICATION_REVIEW'
    if p.get('assertion_count')==0:return None,'NO_FACTUAL_ASSERTIONS'
    response=p.get('response_text')
    if not isinstance(response,str) or not response.strip():return None,'FINAL_RESPONSE_MISSING'
    doc,error=capture(p.get('response_capture'),cid,run_id,artifact_root,{'product_response'})
    if not doc or doc['payload'].get('response_text')!=response:return None,'RESPONSE_BINDING_GAP:'+str(error)
    contexts=p.get('evidence_contexts',[])
    if not contexts:return None,'EVIDENCE_GAP'
    texts=[];proofs=[]
    for c in contexts:
        evidence,error=capture(c.get('capture'),cid,run_id,artifact_root,ORIGINS)
        if not evidence:return None,'EVIDENCE_BINDING_GAP:'+str(error)
        try:selected=lookup(evidence,c.get('selector',''))
        except (ValueError,KeyError,IndexError,TypeError):return None,'INVALID_OR_GENERATED_EVIDENCE_SELECTOR'
        text=selected if isinstance(selected,str) else canonical(selected)
        if c.get('text')!=text:return None,'EVIDENCE_TEXT_NOT_FROM_CAPTURE'
        texts.append(text);proofs.append({'origin':evidence['origin'],'capture':c['capture'],'selector':c['selector'],'selected_text_sha256':sha(text.encode())})
    return {'case_id':cid,'run_id':run_id,'user_input':case['query'],'response':response,'retrieved_contexts':texts,'evidence_proofs':proofs,'response_sha256':sha(response.encode()),'input_sha256':sha(canonical({'query':case['query'],'response':response,'contexts':texts}).encode()),'new_evaluation_input':True,'original_judge_score_preserved':True,'ragas_judge_executed':False},None
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--predictions',type=Path,required=True);ap.add_argument('--artifacts',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    if args.output.exists():raise SystemExit('Refuse overwrite')
    cases={c['id']:c for c in [json.loads(l) for l in (ROOT/'oracle/cases.jsonl').read_text(encoding='utf-8').splitlines()]}
    records=[];applicability=[];seen=set()
    for line in args.predictions.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip():continue
        p=json.loads(line);assert p['id'] in cases and p['id'] not in seen;seen.add(p['id'])
        record,reason=export(cases[p['id']],p,args.artifacts)
        applicability.append({'id':p['id'],'run_id':p.get('run_id'),'execution_status':p.get('run_status'),'applicable':record is not None,'applicability_reason':reason})
        if record:records.append(record)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records),encoding='utf-8')
    args.output.with_suffix('.applicability.json').write_text(json.dumps({'records':applicability,'ragas_judge_executed':False},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
