"""Offline verification of run-time HTTP bodies, final rows and file hashes."""
import hashlib,json,collections,sys
from pathlib import Path
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def lines(p):return [json.loads(s) for s in p.read_text(encoding='utf8').splitlines()]
def main():
 def guard(event,args):
  if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('offline verifier')
 sys.addaudithook(guard)
 m=json.loads((A/'checksums.json').read_text(encoding='utf8'))
 actual={p.relative_to(A).as_posix() for p in A.rglob('*') if p.is_file() and p.name!='checksums.json' and '__pycache__' not in p.parts}
 assert actual==set(m)
 for name,h in m.items():assert sha(A/name)==h,name
 calls=lines(A/'execution/http.jsonl');observations=lines(A/'execution/observations.jsonl')
 pre=json.loads((A/'execution/preflight.json').read_text());end=json.loads((A/'execution/completion.json').read_text())
 assert pre['questions_sha256']==sha(A/'questions.jsonl')
 assert len(pre['checks'])==3 and all(c['passed'] for c in pre['checks'])
 assert end['completed'] and end['cases']==len(observations)==20 and end['gold_access_attempts_after_selftest']==0
 assert collections.Counter(c['kind'] for c in calls)=={k:v for k,v in end['http_calls'].items() if v}
 raw_count=0;verified_rows=0
 def signature(row):
  keys=['ORG_ID','TBL_ID','ITM_ID','PRD_DE','DT','UNIT_NM']+[f'C{i}' for i in range(1,9)]
  return tuple(str(row.get(k,'')) for k in keys)
 for observation in observations:
  available=collections.Counter()
  for c in [c for c in calls if c['case_id']==observation['id']]:
   if 'http_status' not in c:
    assert c.get('error_type');continue
   assert c.get('response_file'),c['request_id']
   file=(A/'execution'/c['response_file']).resolve()
   assert file.is_relative_to((A/'execution').resolve())
   assert sha(file)==c['response_sha256'] and file.stat().st_size==c['response_bytes']
   raw_count+=1
   if c['kind']=='kosis_data':
    body=json.loads(file.read_bytes())
    if isinstance(body,list):available.update(signature(r) for r in body)
  rows=((observation.get('result') or {}).get('execution') or {}).get('rows') or []
  returned=collections.Counter(signature(r) for r in rows)
  assert not returned-available,observation['id']+' final row not found in official response'
  verified_rows+=len(rows)
 scores=lines(A/'scoring/scores.jsonl')
 assert len(scores)==20 and all((s['result']=='통과')==all(s['checks'].values()) for s in scores)
 summary=json.loads((A/'scoring/summary.json').read_text(encoding='utf8'))
 assert summary['questions_sha256']==sha(A/'questions.jsonl')
 assert summary['gold_sha256']==sha(A/'answer_key.jsonl')
 assert summary['observations_sha256']==sha(A/'execution/observations.jsonl')
 print(json.dumps({'files_verified':len(m),'runtime_raw_responses_verified':raw_count,'returned_rows_linked_to_official_bodies':verified_rows,'cases':20,'gold_access_attempts':0},ensure_ascii=False))
if __name__=='__main__':main()
