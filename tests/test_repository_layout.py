"""Guard the portable official layout without requiring a Git checkout."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_duplicate_runtime_tree_or_root_entrypoints():
    for relative in ("data/runtime_data", "data/statbridge_mcp_server"):
        assert not (ROOT / relative).exists(), relative
    for pattern in ("*.cmd", "TEST_*.py", "STATBRIDGE*.md"):
        assert not list(ROOT.glob(pattern)), pattern
    for relative in (
        "data/processed/bok_table_master.csv",
        "src/backend/statbridge_mcp/metadata_store.py",
        "scripts/windows/START_STATBRIDGE.cmd",
        "scripts/windows/STOP_STATBRIDGE.cmd",
        "tools/validate_all_tables_cli.py",
    ):
        assert (ROOT / relative).is_file(), relative
