#!/usr/bin/env python3
import json,sys
from pathlib import Path
def load(p): return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]
def score(gold_path,pred_path):
 g={r["id"]:r for r in load(gold_path)}; p={r["id"]:r for r in load(pred_path)}
 n=len(g); status=exact=0; tp=fp=fn=0
 by_type={}
 for i,x in g.items():
  y=p.get(i,{})
  gs=x["expected_status"]; ps=y.get("status") or y.get("expected_status")
  okst=(gs==ps); status+=okst
  A=set(x.get("table_ids",[])); B=set(y.get("table_ids",[]))
  ex=(A==B and okst); exact+=ex
  tp+=len(A&B); fp+=len(B-A); fn+=len(A-B)
  t=x["type"]; z=by_type.setdefault(t,[0,0]); z[0]+=ex; z[1]+=1
 prec=tp/(tp+fp) if tp+fp else 1.0; rec=tp/(tp+fn) if tp+fn else 1.0; f1=2*prec*rec/(prec+rec) if prec+rec else 0
 print(json.dumps({"n":n,"status_accuracy":status/n,"exact_case_accuracy":exact/n,"table_set_precision":prec,"table_set_recall":rec,"table_set_f1":f1,"by_type_exact":{k:v[0]/v[1] for k,v in by_type.items()}},ensure_ascii=False,indent=2))
if __name__=="__main__": score(sys.argv[1],sys.argv[2])
