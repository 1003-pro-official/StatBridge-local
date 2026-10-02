"""Guard the portable official layout without requiring a Git checkout."""
from pathlib import Path
import importlib

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


def test_bridge_and_mcp_imports_use_canonical_backend():
    # Import the UI bridge first: this order previously shadowed the backend.
    import bridge_api

    assert bridge_api.MCP_ROOT == ROOT / "src" / "backend"
    assert bridge_api.DATA_DIR == ROOT / "data" / "processed"
    package_root = ROOT / "src" / "backend" / "statbridge_mcp"
    for name in (
        "config", "kosis_client", "metadata_store", "search_engine",
        "statistics_service", "server",
    ):
        module = importlib.import_module(f"statbridge_mcp.{name}")
        assert Path(module.__file__).resolve() == package_root / f"{name}.py"
    client = importlib.import_module("statbridge_mcp.kosis_client")
    assert callable(client._loads_lenient)
