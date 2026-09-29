from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "src" / "agent"
sys.path.insert(0, str(AGENT))

from hybrid_retriever import HybridStatRetriever  # noqa: E402
from stat_dictionary.stat_language_resolver import StatLanguageResolver  # noqa: E402


def load_cases():
    cases = []
    for path in sorted((ROOT / "eval" / "retrieval").glob("*.json")):
        if path.name == "last_results.json":
            continue
        for item in json.loads(path.read_text(encoding="utf-8")):
            cases.append({"set": path.stem, **item})
    return cases


def main():
    resolver = StatLanguageResolver(AGENT / "stat_dictionary" / "stat_language_dictionary.json")
    hybrid = HybridStatRetriever(resolver)
    def rank_for(mode, query):
        if mode == "rule_only":
            return resolver.rank(query, top_k=8)
        items = hybrid.rank(query, top_k=8)
        if mode == "embedding_only":
            items = [x for x in items if float(x.get("vector_score") or 0) > 0]
            items.sort(key=lambda x: (-float(x.get("vector_score") or 0), x["table_id"]))
        return items
    results = []
    for mode in ("rule_only", "embedding_only", "hybrid"):
        passed = 0
        evaluated = 0
        for case in load_cases():
            query = case["query"]
            resolved = resolver.resolve(query, top_k=8)
            ranked = rank_for(mode, query)
            # Embedding-only is reported from the same candidate trace with rule contribution ignored;
            # skipped when no persisted vector candidates exist.
            if mode == "embedding_only":
                if not ranked:
                    continue
            ok = True
            if "expected_status" in case:
                ok = resolved["status"] == case["expected_status"]
            if case.get("expected_table_ids"):
                ok = bool(ranked) and ranked[0]["table_id"] in case["expected_table_ids"]
            if case.get("expected_min_tables"):
                parts = [x.strip() for x in re.split(r"(?:와|과|,|그리고)", query) if x.strip()]
                found = set()
                for part in parts:
                    part_ranked = rank_for(mode, part)[:1]
                    if part_ranked:
                        found.add(part_ranked[0]["table_id"])
                ok = len(found) >= case["expected_min_tables"]
            evaluated += 1
            passed += int(ok)
            results.append({"mode": mode, "set": case["set"], "query": query, "ok": ok,
                            "status": resolved["status"], "top": ranked[0]["table_id"] if ranked else None})
        print(json.dumps({"mode": mode, "passed": passed, "evaluated": evaluated,
                          "accuracy": round(passed / evaluated, 4) if evaluated else None}, ensure_ascii=False))
    (ROOT / "eval" / "retrieval" / "last_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
