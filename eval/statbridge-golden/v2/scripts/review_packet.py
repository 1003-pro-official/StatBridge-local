"""Build an ignored human interpretation packet bound to actual observations."""
from __future__ import annotations

import argparse
import hashlib
import json
from common import BASE, local_path, read_json, read_jsonl, write_jsonl
from run import observation_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases")
    parser.add_argument("predictions")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    path = local_path(BASE, args.output)
    if not path.is_relative_to(BASE / "results"):
        raise ValueError("review results belong in ignored results/")
    if path.exists():
        raise ValueError("refusing to overwrite existing reviews; choose a new output filename")
    cases = {c["id"]: c for c in read_jsonl(args.cases)}
    rows = []
    for p in read_jsonl(args.predictions):
        c = cases[p["id"]]
        clarify = c["expected"].get("resolution", {}).get("clarification", {}).get("required", False)
        if ("output" not in c["expected"] and not clarify) or p["execution_status"] != "observed":
            continue
        if p.get("observation_sha256") != observation_hash(p):
            raise ValueError("observation hash mismatch: " + p["id"])
        input_hash = hashlib.sha256(json.dumps(c["input"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if p.get("input_sha256") != input_hash:
            raise ValueError("input hash mismatch/missing: " + p["id"])
        rows.append({"id": p["id"], "prediction_sha256": p["observation_sha256"],
            "reviewer": None, "human_approved": False,
            "facts_correct": None, "no_contradiction": None, "no_unsupported_claim": None, "claims_covered": None,
            "clarification_options_correct": None,
            "expected_clarification": c["expected"].get("resolution", {}).get("clarification"),
            "actual_clarification": p.get("resolution", {}).get("clarification"),
            "notes": "", "required_facts": read_json(BASE / c["expected"]["output"]["claims"])["facts"] if "output" in c["expected"] else [],
            "actual_explanation": p.get("explanation"), "fixture": c["expected"].get("data", {}).get("fixture"),
            "sources": c["evidence"]["sources"]})
    write_jsonl(path, rows)
    print("Human reviews pending: " + str(len(rows)))


if __name__ == "__main__":
    main()
