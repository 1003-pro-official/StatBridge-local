"""Current policy regression tests; requires extracted live evidence, never API calls."""
from pathlib import Path
from copy import deepcopy
import json,sys,argparse,hashlib
from score_reviewed import score
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--evidence-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
read=lambda p:json.loads(p.read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cs=list(map(json.loads,(ROOT/'oracle/cases.jsonl').read_text(encoding='utf-8').splitlines()));by={c['id']:c for c in cs};old={c['id']:c for c in map(json.loads,(ROOT/'baseline_reference/pre_v22.cases.jsonl').read_text(encoding='utf-8').splitlines())};obs=read(ROOT/'results/ai_adjudication_20261030/all_observations.json');ob={p['id']:p for p in obs};checks=[]
def check(name,value):checks.append({'check':name,'pass':bool(value)})
def evaluate(cid,p=None):
 p=deepcopy(p or ob[cid]);return score(by[cid],p,a.evidence_root/'runs'/p['run_id'])
check('120 unique cases and observations',len(by)==len(ob)==len(cs)==len(obs)==120)
for c in cs:
 check(c['id']+' unchanged question',c['query']==old[c['id']]['query'])
 check(c['id']+' unchanged expected values/semantics',c['expected']==old[c['id']]['expected'])
 check(c['id']+' final approval gate removed',not c.get('approval') and c['evaluation_policy']['final_human_approval_required'] is False)
check('rule-pass is PASS without human oracle approval',evaluate('QT21-01')['status']=='PASS')
check('AI CQ semantic review accepted',evaluate('CQ21-01')['status']=='PASS')
for n in range(1,21):
 cid=f'CQ21-{n:02}';v=evaluate(cid);check(cid+' semantic target evaluated',v['checks']['clarification_target'] is True);check(cid+' conditions evaluated',v['checks']['condition_preservation'] is True)
check('CQ08 early execution is fail',evaluate('CQ21-08')['checks']['no_premature_execution'] is False)
check('CQ16 missing pre-prediction reference remains unknown',evaluate('CQ21-16')['checks']['latest_reference_pre_prediction'] is None)
for mutation in ['actor','hash','response','reviewer','ref_removed']:
 p=deepcopy(ob['CQ21-01'])
 if mutation=='actor':p['semantic_review']['actor_type']='unverified'
 if mutation=='hash':p['semantic_review']['evidence_refs'][0]['sha256']='0'*64
 if mutation=='response':
  p['response_text']='fabricated response';p['semantic_review']['response_sha256']=hashlib.sha256(p['response_text'].encode()).hexdigest()
 if mutation=='reviewer':p['semantic_review']['reviewer']=''
 if mutation=='ref_removed':p['semantic_review']['evidence_refs']=[]
 check('invalid semantic review rejected '+mutation,evaluate('CQ21-01',p)['checks']['clarification_target'] is None)
p=deepcopy(ob['CQ21-01']);p['semantic_review']['target_correct']=False
check('negative AI target judgment causes fail',evaluate('CQ21-01',p)['status']=='FAIL')
check('D23 arithmetic checks retained',all(v is True for k,v in evaluate('D23')['checks'].items() if k!='summary_semantics'))
check('D23 mislabeled summary fails',evaluate('D23')['checks']['summary_semantics'] is False)
for cid in ['F22','F27','F34']:check(cid+' independent negative check persists',evaluate(cid)['status']=='FAIL')
check('F21 human image review preserved',evaluate('F21')['status']=='PASS')
p=deepcopy(ob['F21'])
for d in p['downloads']:
 if d['format']=='png':d['independent_artifact_review']['actor_type']='AI_precheck_only'
check('unreviewed image not fabricated human approval',evaluate('F21',p)['status']=='EVIDENCE_GAP')
check('original RAGAS 0.25 preserved',read(a.evidence_root/'runs/full_warm_80_01/ragas_standard_full_01/D23-score.json')['score']==0.25)
result={'scope':'v2.2 policy and evidence binding regression; not new product runtime performance','checks':len(checks),'passed':sum(c['pass'] for c in checks),'failed':sum(not c['pass'] for c in checks),'records':checks}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='records'}));raise SystemExit(bool(result['failed']))
