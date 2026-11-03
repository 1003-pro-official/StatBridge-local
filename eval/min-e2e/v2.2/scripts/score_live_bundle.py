"""Portable replay of captured rules. No product/API/LLM call; no oracle approval."""
from pathlib import Path
from collections import Counter
import argparse,json
from score_reviewed import score
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--evidence-root',type=Path,required=True,help='StatBridge_live_verification folder from extracted evidence ZIP');p.add_argument('--observations',type=Path,default=ROOT/'results/ai_adjudication_20261030/all_observations.json');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
if a.output.exists():raise SystemExit('Refuse overwrite: use a new output path')
cases={c['id']:c for c in map(json.loads,(ROOT/'oracle/cases.jsonl').read_text(encoding='utf-8').splitlines())}
obs=json.loads(a.observations.read_text(encoding='utf-8'));assert len(obs)==120 and {o['id'] for o in obs}==set(cases)
results=[score(cases[o['id']],o,a.evidence_root/'runs'/o['run_id']) for o in obs]
result={'scope':'replay rules on existing evidence; not a new live product run','records':results,'rule_summary':{g:dict(Counter(r['rule_status'] for r in results if r['group']==g)) for g in ['QT','CQ','DA','D','E','F']}}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result['rule_summary']))
