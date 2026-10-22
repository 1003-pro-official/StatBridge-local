"""Shared paths and helpers; scoring primitives are imported from bok-reproduction v1, not copied."""
from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).absolute().parents[1]
ROOT = BASE.parents[2]
RESEARCH = ROOT / 'research' / 'kosis-bok-reproduction'
TABLES = ROOT / 'data' / 'tables'
PROCESSED = ROOT / 'data' / 'processed'
CACHE = ROOT / '.venv' / 'cache' / 'statbridge-e2e-v1'
V1_SCRIPTS = ROOT / 'eval' / 'bok-reproduction' / 'v1' / 'scripts'

if str(V1_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(V1_SCRIPTS))

from core import (  # noqa: E402,F401  (reuse of v1 primitives)
    RUBRIC, calculate, compare_series, digest_file, digest_value, identity, number,
    period, read, read_json_line, review_packet, review_valid, rows, write, write_rows,
)
