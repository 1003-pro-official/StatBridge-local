"""Save the current local API decisions for v2 cases without calling KOSIS."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "backend"))

from analysis_service import AnalysisService  # noqa: E402
from evaluate_golden_set import load_cases  # noqa: E402
from statbridge_mcp.statistics_service import StatisticsService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "eval" / "golden-set-v2")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = load_cases(args.corpus)
    analysis = AnalysisService(StatisticsService())
    predictions = {}
    for case in cases:
        result = analysis.analyze({"query": case["query"]})
        predictions[case["id"]] = {
            "resolution": result.get("resolution", {}),
            "ranked_table_ids": [item["table_id"] for item in result.get("candidates", [])],
            "legacy_status": result.get("status"),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(predictions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved {len(predictions)} predictions to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
