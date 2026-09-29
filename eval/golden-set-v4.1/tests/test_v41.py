import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(n): return [json.loads(x) for x in (ROOT/n).read_text(encoding='utf-8').splitlines() if x.strip()]
class V41(unittest.TestCase):
 def test_counts(self): self.assertEqual((len(load('dev.jsonl')),len(load('test.jsonl')),len(load('holdout_queries.jsonl'))),(50,70,30))
 def test_holdout_no_gold(self):
  for r in load('holdout_queries.jsonl'):
   self.assertEqual(set(r),{'id','query','prior_turns'})
 def test_public_ids_unique(self):
  ids=[r['id'] for r in load('dev.jsonl')+load('test.jsonl')+load('holdout_queries.jsonl')]; self.assertEqual(len(ids),len(set(ids)))
 def test_human_approval_not_claimed(self):
  for r in load('dev.jsonl')+load('test.jsonl'): self.assertFalse(r['review']['human_approved'])
if __name__=='__main__': unittest.main()
