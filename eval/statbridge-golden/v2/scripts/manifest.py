"""Record reproducible public-data/code hashes after real validation."""
from common import BASE, digest, read_jsonl, write_json
from validate import validate_cases


def main():
    cases = read_jsonl(BASE / "dev.jsonl") + read_jsonl(BASE / "test.jsonl")
    validation = validate_cases(cases, verify_sources=True)
    if validation["errors"]:
        raise ValueError(validation["errors"])
    files = [BASE / "dev.jsonl", BASE / "test.jsonl", BASE / "pilot.jsonl", BASE / "schema.json",
             BASE / "series_registry.json", BASE / "source_inventory.json"]
    files.append(BASE / "attachment_registry.json")
    files.append(BASE / "candidate_probes.json")
    files.append(BASE / "unit_rules.json")
    files.append(BASE / "dataset_policy.json")
    files.extend(BASE / name for name in (".gitattributes", ".gitignore"))
    files.extend(p for p in (BASE / "internal/components").rglob("*") if p.is_file() and p.suffix in {".json", ".jsonl", ".md"})
    for folder, pattern in [("fixtures", "*.json"), ("claims", "*.json"), ("scripts", "*.py"), ("tests", "*.py"), ("review", "*.jsonl")]:
        files.extend((BASE / folder).glob(pattern))
    files.extend(BASE.glob("*.md"))
    files.extend((BASE / "review").glob("*.md"))
    files.extend((BASE / "notebooks").glob("*.ipynb"))
    files.extend(p for p in (BASE / "holdout_support").glob("*") if p.suffix in {".py", ".md"})
    write_json(BASE / "dataset_manifest.json", {"schema_version": "2.0", "ai_assisted": True,
        "production_status": "machine_validated_ready_for_human_review", "public_cases": len(cases),
        "human_approved": validation["human_approved"], "official_evaluation_ready": validation["human_approved"] == len(cases),
        "files": {str(p.relative_to(BASE)).replace("\\", "/"): digest(p) for p in sorted(files)}})


if __name__ == "__main__":
    main()
