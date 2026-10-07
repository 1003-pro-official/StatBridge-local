"""Private-only entry point. This file contains no holdout data."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from contract import CHECKS, aggregate_report, check_approvals, check_candidates, value_hash

KIT = Path(__file__).resolve().parent
BRANCH = "eval/statbridge-golden-v2-holdout"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def contained(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("path escapes declared root")
    return path


def write_new(path, value, jsonl=False):
    if path.exists():
        raise ValueError("refusing to overwrite " + path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = ("".join(json.dumps(v, ensure_ascii=False, allow_nan=False) + "\n" for v in value) if jsonl
            else json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
    path.write_text(text, encoding="utf-8")


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def private_base(workspace):
    root = workspace.resolve()
    if Path(git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise ValueError("workspace must be the private repository root")
    remote = git(root, "remote", "get-url", "origin").rstrip("/")
    if not re.search(r"(?:github\.com[:/])1003-pro-official/StatBridge-evaluation-private(?:\.git)?$", remote):
        raise ValueError("only the designated private repository is allowed; no cases were read")
    if git(root, "branch", "--show-current") != BRANCH:
        raise ValueError("use the dedicated feature branch: " + BRANCH)
    return root / "statbridge-golden/v2"


def verify_kit():
    manifest = read(KIT / "bundle-manifest.json")
    for name, expected in manifest["files"].items():
        path = contained(KIT, name)
        if sha(path) != expected:
            raise ValueError("handoff tool hash mismatch: " + name)
    return sha(KIT / "bundle-manifest.json")


def initialize(base):
    if base.exists():
        raise ValueError("existing v2 directory is preserved; initialization refused")
    base.mkdir(parents=True)
    shutil.copy2(KIT / "holdout-schema.json", base / "schema.json")
    shutil.copy2(KIT / "pinned/unit_rules.json", base / "unit_rules.json")
    for name, value in (("series_registry.json", []), ("attachment_registry.json", []),
                        ("fixtures/provider.json", {"series": []})):
        write_new(base / name, value)
    write_new(base / "cases.jsonl", [], jsonl=True)
    (base / ".gitignore").write_text("results/\nsource-originals/\n__pycache__/\n.env\n", encoding="ascii")
    write_new(base / "authoring_protocol.json", {"ai_assisted": True, "human_approved": False,
              "implementation_exposure": None, "purpose": "official evaluation candidate",
              "private_cases_created": 0, "note": "PM declares author exposure; do not infer independence from a separate chat."})


def load_tools(base, product):
    # Fresh processes prevent accidental mixing of public and private module globals.
    if any(name in sys.modules for name in ("common", "validate", "score", "run")):
        raise ValueError("start adapter in a fresh Python process")
    sys.path.insert(0, str(KIT / "pinned/scripts"))
    import common
    common.BASE, common.ROOT = base, product
    import validate
    import run
    import score
    return common, validate, run, score


def validate_holdout(cases, base, validator, partial=False):
    result = validator.validate_cases(cases, base=base, verify_sources=True, enforce_counts=False)
    if not result["errors"]:
        result["errors"] += check_candidates(cases, read(KIT / "public-exclusions.json"),
                                              lambda p: read(contained(base, p)), complete=not partial)
    if cases and not result["errors"]:
        provider = read(base / "fixtures/provider.json")
        result["errors"] += ["provider: " + error for error in validator.validate_fixture(provider, validator.catalog_contract())]
        if result["errors"]:
            return result
        lookup = {value_hash([s["provider"], s["table_id"], s["item_id"], sorted(s["classifications"].items()),
                              s["frequency"], s["unit"]]): {p["period"]: p["value"] for p in s["points"]}
                  for s in provider.get("series", []) if s.get("provider") == "kosis"}
        for case in cases:
            data = case["expected"].get("data")
            if not data:
                continue
            for series in read(contained(base, data.get("source_fixture") or data["fixture"]))["series"]:
                key = value_hash([series["provider"], series["table_id"], series["item_id"],
                                  sorted(series["classifications"].items()), series["frequency"], series["unit"]])
                values = lookup.get(key, {})
                if any(p["period"] not in values or values[p["period"]] != p["value"] for p in series["points"]):
                    result["errors"].append(case["id"] + ": frozen provider coverage/value mismatch")
    result["human_approved"] = sum(c["review"]["human_approved"] for c in cases)
    return result


def dataset_files(cases):
    paths = {"cases.jsonl", "schema.json", "series_registry.json", "attachment_registry.json",
             "unit_rules.json", "fixtures/provider.json", "review/gold-approvals.jsonl", "authoring_protocol.json"}
    for case in cases:
        data = case["expected"].get("data", {})
        paths.update(p for p in (data.get("fixture"), data.get("source_fixture"),
                                 case["expected"].get("output", {}).get("claims")) if p)
    return sorted(paths)


def product_version(product, commit):
    actual = git(product, "rev-parse", "HEAD")
    expected = git(product, "rev-parse", commit + "^{commit}")
    if actual != expected:
        raise ValueError("product HEAD does not match the PM-pinned commit")
    if git(product, "status", "--porcelain", "--", "src", "data/processed"):
        raise ValueError("product implementation/catalog must be clean")
    return actual


def freeze(cases, base, product, commit, run):
    errors = check_approvals(cases, rows(base / "review/gold-approvals.jsonl"))
    protocol = read(base / "authoring_protocol.json")
    if not isinstance(protocol.get("implementation_exposure"), bool):
        errors.append("PM must declare implementation exposure")
    elif protocol["implementation_exposure"] != any(a.get("implementation_exposure") is True
                                                     for a in rows(base / "review/gold-approvals.jsonl")):
        errors.append("protocol exposure must match case approval declarations")
    if errors:
        raise ValueError("; ".join(errors))
    write_new(base / "release.json", {"ai_assisted": True, "human_approved_cases": len(cases),
              "implementation_exposure": protocol["implementation_exposure"],
              "bundle_sha256": verify_kit(), "product_commit": product_version(product, commit),
              "product_files": run.implementation_hashes(),
              "files": {p: sha(contained(base, p)) for p in dataset_files(cases)}})


def verify_release(base, product, run):
    release = read(base / "release.json")
    if release["bundle_sha256"] != verify_kit():
        raise ValueError("tool version changed; reapproval required")
    product_version(product, release["product_commit"])
    if release["product_files"] != run.implementation_hashes():
        raise ValueError("product/catalog hashes changed")
    for name, expected in release["files"].items():
        if sha(contained(base, name)) != expected:
            raise ValueError("dataset changed after approval: " + name)
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "validate", "approval-template", "freeze", "run", "review-packet", "score"])
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--product-root", type=Path)
    parser.add_argument("--product-commit")
    parser.add_argument("--partial", action="store_true")
    parser.add_argument("--run-id", default="offline-001")
    args = parser.parse_args()
    verify_kit()
    base = private_base(args.workspace)
    if args.command == "init":
        initialize(base)
        print("Initialized only; 0 cases, no human approval.")
        return 0
    if not args.product_root:
        parser.error("--product-root is required except for init")
    product = args.product_root.resolve()
    common, validator, run, scorer = load_tools(base, product)
    cases = rows(base / "cases.jsonl")
    result = validate_holdout(cases, base, validator, partial=args.command == "validate" and args.partial)
    if result["errors"]:
        print(json.dumps(result, ensure_ascii=False))
        return 1
    if args.command == "validate":
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.command == "approval-template":
        write_new(base / "review/gold-approvals.jsonl", [
            {"id": c["id"], "case_sha256": value_hash(c), "author": None, "reviewer": None,
             "human_approved": False, "implementation_exposure": None,
             **{key: None for key in CHECKS}, "notes": ""} for c in cases], jsonl=True)
        print("Human approval remains pending. Finalize case review fields, then bind case_sha256 again.")
        return 0
    if args.command == "freeze":
        if not args.product_commit:
            parser.error("freeze requires PM-specified --product-commit")
        freeze(cases, base, product, args.product_commit, run)
        print("Frozen approved dataset and product version; no evaluation executed.")
        return 0
    release = verify_release(base, product, run)
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", args.run_id):
        raise ValueError("invalid run ID")
    directory = base / "results" / args.run_id
    prediction_path = directory / "predictions.jsonl"
    review_path = directory / "interpretation-review.jsonl"
    if args.command == "run":
        if directory.exists():
            raise ValueError("run directory exists; choose a new run ID")
        directory.mkdir(parents=True)
        # Record pre-execution versions, not only hashes after the run.
        write_new(directory / "execution-manifest.json", {"release_sha256": sha(base / "release.json"),
                  "bundle_sha256": release["bundle_sha256"], "product_commit": release["product_commit"],
                  "environment": "offline_fixed_provider", "edit_parser": "input_command_replay"})
        common.write_jsonl(prediction_path, run.run_cases(cases, live=False))
        verify_release(base, product, run)
        print("Private observations saved; interpretation pending.")
        return 0
    execution = read(directory / "execution-manifest.json")
    if execution["release_sha256"] != sha(base / "release.json"):
        raise ValueError("observations belong to another release")
    if args.command == "review-packet":
        import review_packet
        sys.argv = ["review_packet", str(base / "cases.jsonl"), str(prediction_path), "--output", str(review_path.relative_to(base))]
        review_packet.main()
        return 0
    scored = scorer.score(cases, rows(prediction_path), rows(review_path) if review_path.exists() else [], base=base)
    write_new(directory / "private-score.json", scored)
    summary = aggregate_report(scored, "offline_fixed_provider")
    summary.update(product_commit=release["product_commit"], release_sha256=sha(base / "release.json"),
                   implementation_exposure=release["implementation_exposure"], blind_status="not_asserted")
    write_new(directory / "aggregate-report.json", summary)
    print("Private scoring complete. Only aggregate-report.json may be shared after PM review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
