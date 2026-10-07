from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))

from check_notebook import check_notebook
from common import read_json


def test_notebook_executes_public_review_without_kernel_or_live_calls():
    result = check_notebook(preview=False)
    assert result["executed_code_cells"] == 12
    assert result["figures"] == (2 if result["actual_plotly_observed"] else 1)
    assert result["public_cases"] == 72
    assert result["preview_saved"] is False
    assert result["observation_set"] == "ui-dev-test"
    expected_count = sum(len(path.read_text(encoding="utf-8").splitlines()) for path in
                         (BASE / "results/dev-ui.jsonl", BASE / "results/test-ui.jsonl") if path.exists())
    assert result["stored_observations"] == expected_count


def test_source_notebook_has_no_stored_observations():
    notebook = read_json(BASE / "notebooks/review.ipynb")
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == []
            assert cell["execution_count"] is None


def test_missing_local_observations_are_not_replaced_with_gold(monkeypatch):
    original_exists = Path.exists
    def exists(path):
        if path.parent == BASE / "results":
            return False
        return original_exists(path)
    monkeypatch.setattr(Path, "exists", exists)
    result = check_notebook(preview=False)
    assert result["actual_plotly_observed"] is False
    assert result["figures"] == 1
    assert result["stored_observations"] == 0
