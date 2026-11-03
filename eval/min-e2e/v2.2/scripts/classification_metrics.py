"""Keep function-level classification and actual API routing separate."""
import json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def calculate(cases,observations,scope):
    truth={c['id']:c['expected_query_type'] for c in cases if c['group']=='QT'};pairs=[];unobserved=[];seen=set()
    for o in observations:
        if o.get('classification_scope')!=scope:continue
        cid=o['id'];assert cid in truth and cid not in seen,'Unknown or duplicate classification observation';seen.add(cid)
        label=o.get('predicted_query_type')
        if label in {'general','derived'}:pairs.append((truth[cid],label))
        else:unobserved.append(cid)
    unobserved+=sorted(set(truth)-seen)
    by={}
    for label in ['general','derived']:
        tp=sum(y==p==label for y,p in pairs);fp=sum(p==label and y!=label for y,p in pairs);fn=sum(y==label and p!=label for y,p in pairs)
        by[label]={'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}
    return {'scope':scope,'planned':len(truth),'observed':len(pairs),'unobserved':unobserved,'coverage':len(pairs)/len(truth),'accuracy':sum(y==p for y,p in pairs)/len(pairs) if pairs else None,'per_class':by,'macro_f1':sum(by[k]['f1'] for k in by)/2 if all(by[k]['f1'] is not None for k in by) else None,'not_ragas_faithfulness':True}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--observations',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    if args.output.exists():raise SystemExit('Refuse overwrite')
    cases=[json.loads(l) for l in (ROOT/'oracle/cases.jsonl').read_text(encoding='utf-8').splitlines()]
    obs=[json.loads(l) for l in args.observations.read_text(encoding='utf-8-sig').splitlines() if l.strip()]
    args.output.write_text(json.dumps({s:calculate(cases,obs,s) for s in ['component_function','actual_api_route']},ensure_ascii=False,indent=2),encoding='utf-8')
