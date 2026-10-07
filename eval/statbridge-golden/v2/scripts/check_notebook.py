"""Check notebook cells without installing/running a Jupyter kernel.

Optional rich preview is local-only. It records real Python cell execution,
not an ipykernel session. No external service or pilot execution is enabled.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
from unittest.mock import patch

from common import BASE, ROOT, read_json, write_json


def check_notebook(preview=False):
    import plotly.graph_objects as go
    import plotly.io as pio
    path = BASE / "notebooks/review.ipynb"
    source = read_json(path)
    assert source["nbformat"] == 4 and source["nbformat_minor"] == 5
    assert len({c["id"] for c in source["cells"]}) == len(source["cells"])
    notebook = copy.deepcopy(source)
    notebook["metadata"]["statbridge"]["execution_environment"] = "python_exec_without_ipykernel"
    namespace = {"__name__": "__notebook_check__"}
    output = []
    count, figures = 0, []

    def capture_display(value):
        data = {"text/plain": str(value)}
        if hasattr(value, "to_html"):
            data["text/html"] = value.to_html(index=False, escape=True)
        elif hasattr(value, "_repr_markdown_"):
            data["text/markdown"] = value._repr_markdown_()
        elif hasattr(value, "_repr_html_"):
            data["text/html"] = value._repr_html_()
        output.append({"output_type": "display_data", "metadata": {}, "data": data})

    def capture_figure(figure, *args, **kwargs):
        payload = json.loads(pio.to_json(figure))
        figures.append(payload)
        output.append({"output_type": "display_data", "metadata": {},
                       "data": {"application/vnd.plotly.v1+json": payload,
                                "text/plain": "Plotly figure (actual Python construction)"}})

    # Cell root discovery is independent of where this check command is launched.
    import os
    previous_directory = os.getcwd()
    try:
        os.chdir(ROOT)
        with patch.object(go.Figure, "show", capture_figure):
            for cell in notebook["cells"]:
                if cell["cell_type"] != "code":
                    continue
                assert cell["execution_count"] is None and cell["outputs"] == []
                code = "".join(cell["source"])
                assert "RUN_PILOT = False" in code or "RUN_PILOT" not in code
                count += 1
                output = []
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exec(compile(code, str(path) + "#" + cell["id"], "exec"), namespace)
                if stdout.getvalue():
                    output.insert(0, {"output_type": "stream", "name": "stdout", "text": stdout.getvalue()})
                cell["execution_count"], cell["outputs"] = count, output
                namespace["display"] = capture_display
        assert len(namespace["cases"]) == 72
        assert namespace["RUN_PILOT"] is False
        assert not namespace["validation"]["errors"]
        assert len(figures) >= 1
        if preview:
            write_json(BASE / "results/review-preview.ipynb", notebook)
        actual_observed = bool(namespace["prediction"] and namespace["prediction"].get("plotly_figure"))
        return {"executed_code_cells": count, "figures": len(figures), "actual_plotly_observed": actual_observed,
                "public_cases": len(namespace["cases"]),
                "observation_set": namespace["OBSERVATION_SET"], "stored_observations": len(namespace["predictions"]),
                "execution": "Python exec; not a Jupyter kernel", "preview_saved": preview}
    finally:
        os.chdir(previous_directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check_notebook(args.preview), ensure_ascii=False))


if __name__ == "__main__":
    main()
