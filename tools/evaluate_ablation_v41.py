from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "src" / "agent"
sys.path.insert(0, str(AGENT))

from hybrid_retriever import HybridStatRetriever
from stat_dictionary.stat_language_resolver import StatLanguageResolver


def div(a, b): return a / b if b else 0.0


def metrics(cases):
    labeled=[x for x in cases if x["gold"]]
    return {
        "evaluated": len(cases),
        "recall_at_1": div(sum(x["best_rank"] is not None and x["best_rank"] <= 1 for x in labeled),len(labeled)),
        "recall_at_3": div(sum(x["best_rank"] is not None and x["best_rank"] <= 3 for x in labeled),len(labeled)),
        "recall_at_5": div(sum(x["best_rank"] is not None and x["best_rank"] <= 5 for x in labeled),len(labeled)),
        "mrr": div(sum(1/x["best_rank"] if x["best_rank"] else 0 for x in labeled),len(labeled)),
        "top1_accuracy": div(sum(bool(x["ranked"]) and x["ranked"][0] in set(x["gold"]) for x in labeled),len(labeled)),
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dataset",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    cases=[json.loads(line) for line in args.dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    resolver=StatLanguageResolver(AGENT/"stat_dictionary/stat_language_dictionary.json")
    hybrid=HybridStatRetriever(resolver)
    modes={name:[] for name in ("rule_only","embedding_only","rule_embedding","embedding_reranker","rule_embedding_reranker")}
    traces=[]
    for index,case in enumerate(cases,1):
        query=case["query"]
        prior=[x.get("content","") for x in case.get("prior_turns",[]) if x.get("role")=="user"]
        if prior: query=resolver.merge_followup_query(prior[-1],query)
        fused=hybrid.rank(query,top_k=40)
        by_id={x["table_id"]:x for x in fused}
        rule=resolver.rank(query,top_k=40)
        for item in rule:
            by_id.setdefault(item["table_id"],{**item,"rule_score":item.get("score",0),"vector_score":0,"rerank_score":0})
        items=list(by_id.values())
        scorers={
            "rule_only":lambda x:float(x.get("rule_score",x.get("score",0)) or 0)/220,
            "embedding_only":lambda x:float(x.get("vector_score") or 0),
            "rule_embedding":lambda x:.55*min(1,float(x.get("rule_score",0) or 0)/220)+.45*float(x.get("vector_score") or 0),
            "embedding_reranker":lambda x:.45*float(x.get("vector_score") or 0)+.55*float(x.get("rerank_score") or 0),
            "rule_embedding_reranker":lambda x:float(x.get("final_score") or 0),
        }
        gold=list(case.get("table_ids") or [])
        for name,score_fn in scorers.items():
            ranked=[x["table_id"] for x in sorted(items,key=lambda x:(-score_fn(x),x["table_id"])) if score_fn(x)>0]
            hits=[ranked.index(value)+1 for value in gold if value in ranked]
            modes[name].append({"id":case["id"],"split":case["split"],"type":case["type"],"gold":gold,"ranked":ranked[:12],"best_rank":min(hits) if hits else None})
        traces.append({"id":case["id"],"query":case["query"],"candidates":[{
            "table_id":x["table_id"],"rule_score":x.get("rule_score",x.get("score")),
            "vector_score":x.get("vector_score"),"reranker_score":x.get("rerank_score"),"final_score":x.get("final_score")
        } for x in fused[:12]]})
        print(f"{index}/{len(cases)} {case['id']}",flush=True)
    payload={"metrics":{name:metrics(rows) for name,rows in modes.items()},"cases_by_mode":modes,"traces":traces}
    args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(payload["metrics"],ensure_ascii=False,indent=2))


if __name__=="__main__": main()
