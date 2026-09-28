#!/usr/bin/env python3
from pathlib import Path
from collections import Counter,defaultdict
import json,re,sys
ROOT=Path(__file__).resolve().parents[1]
TARGET_SPLIT={'dev':50,'test':70}
TARGET_TYPE={'single':60,'multi':20,'clarify':20,'no_match':15,'catalog_only':5,'followup':30}
EXPECTED_MATRIX={
 'single':{'dev':20,'test':28,'holdout':12}, 'multi':{'dev':7,'test':9,'holdout':4},
 'clarify':{'dev':7,'test':9,'holdout':4}, 'no_match':{'dev':5,'test':7,'holdout':3},
 'catalog_only':{'dev':2,'test':2,'holdout':1}, 'followup':{'dev':9,'test':15,'holdout':6}}
def load(p): return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
def main(private_answers=None):
 dev=load(ROOT/'dev.jsonl'); test=load(ROOT/'test.jsonl'); hq=load(ROOT/'holdout_queries.jsonl')
 labeled=dev+test
 errors=[]
 if len(dev)!=50: errors.append(f'dev count {len(dev)}')
 if len(test)!=70: errors.append(f'test count {len(test)}')
 if len(hq)!=30: errors.append(f'holdout query count {len(hq)}')
 ids=[r['id'] for r in labeled]+[r['id'] for r in hq]
 if len(ids)!=len(set(ids)): errors.append('duplicate ids across public splits')
 # holdout leakage check
 forbidden={'type','difficulty','language_style','intent','slots','expected_status','table_ids','candidate_table_ids','hard_negative_table_ids','clarification','expected_items','evidence'}
 for r in hq:
  leaked=forbidden & set(r)
  if leaked: errors.append(f"{r['id']} holdout leakage: {sorted(leaked)}")
 # labeled integrity
 for r in labeled:
  typ=r['type']; st=r['expected_status']; tids=r['table_ids']
  if typ=='single' and not(st=='select' and len(tids)==1): errors.append(f"{r['id']} bad single")
  if typ=='multi' and not(st=='select' and len(tids)>=2): errors.append(f"{r['id']} bad multi")
  if typ=='clarify' and not(st=='clarify' and not tids and r['clarification']['required']): errors.append(f"{r['id']} bad clarify")
  if typ=='no_match' and not(st=='no_match' and not tids): errors.append(f"{r['id']} bad no_match")
  if typ=='catalog_only' and not(st=='catalog_only' and len(tids)==1): errors.append(f"{r['id']} bad catalog_only")
  if r.get('review',{}).get('human_approved') is not False: errors.append(f"{r['id']} human_approved must be false")
  if r.get('schema_version')!='4.1': errors.append(f"{r['id']} schema_version")
  # explicit full year must agree with slot period
  ys=re.findall(r'(20\d{2})년',r['query'])
  if ys and typ not in ('followup',):
   p=str(r['slots'].get('period'))
   if ys[-1] not in p: errors.append(f"{r['id']} query year {ys[-1]} != period {p}")
 # ensure style/difficulty not collapsed by type in public labeled data
 for typ in TARGET_TYPE:
  vals=[r for r in labeled if r['type']==typ]
  if vals and typ!='catalog_only' and len({r['language_style'] for r in vals})<2: errors.append(f'{typ} has <2 styles')
 if len({r['difficulty'] for r in labeled})<3: errors.append('difficulty lacks easy/medium/hard')
 if private_answers:
  pa=load(Path(private_answers)); amap={r['id']:r for r in pa};
  if set(amap)!={r['id'] for r in hq}: errors.append('private answer IDs != holdout query IDs')
  # matrix across all data
  full=labeled+pa
  matrix=defaultdict(Counter)
  for r in full: matrix[r['type']][r.get('split','holdout')]+=1
  # private answers do not carry split by design, count them as holdout
  matrix=defaultdict(Counter)
  for r in labeled: matrix[r['type']][r['split']]+=1
  for r in pa: matrix[r['type']]['holdout']+=1
  for typ,exp in EXPECTED_MATRIX.items():
   for sp,n in exp.items():
    if matrix[typ][sp]!=n: errors.append(f'{typ}/{sp}={matrix[typ][sp]} expected {n}')
 if errors:
  print('VALIDATION FAILED')
  for e in errors[:100]: print('-',e)
  return 1
 print('VALIDATION OK')
 print('dev/test/holdout = 50/70/30; public holdout has no gold leakage')
 return 0
if __name__=='__main__': sys.exit(main(sys.argv[1] if len(sys.argv)>1 else None))
