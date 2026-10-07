"""Preserve the exact executed working copy before clearing release outputs."""
from datetime import datetime, timezone
import argparse
import shutil

from common import BASE, digest, read_json, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook", choices=["v1", "v2"], default="v2")
    args = parser.parse_args()
    source = (BASE.parent / "v1/notebooks/verify.ipynb" if args.notebook == "v1"
              else BASE / "notebooks/review.ipynb")
    notebook = read_json(source)
    if not any(c.get("outputs") or c.get("execution_count") is not None
               for c in notebook["cells"] if c["cell_type"] == "code"):
        print("Release notebook already has empty outputs; unchanged.")
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = BASE / "results" / (args.notebook + "-review-working-" + stamp + ".ipynb")
    backup.parent.mkdir(parents=True, exist_ok=True)
    before = digest(source)
    shutil.copy2(source, backup)
    if digest(backup) != before:
        raise ValueError("working copy was not preserved exactly")
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            cell["outputs"], cell["execution_count"] = [], None
    write_json(source, notebook)
    print({"preserved": str(backup), "working_sha256": before, "release_sha256": digest(source)})


if __name__ == "__main__":
    main()
