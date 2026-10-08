from pathlib import Path
from runtime_paths import layout


def test_repository_and_portable_preserve_independent_runtime_locations(tmp_path):
    repository = tmp_path / "local" / "src" / "agent"
    repository.mkdir(parents=True)
    paths = layout(repository)
    assert paths["backend"] == tmp_path / "local" / "src" / "backend"
    assert paths["env"] == tmp_path / "local" / ".env"
    assert paths["tables"] == tmp_path / "local" / "data" / "tables"
    assert paths["vector"] == tmp_path / "local" / ".venv" / "cache" / "vector_store_349"
    portable = tmp_path / "portable"
    (portable / "statbridge_mcp_server").mkdir(parents=True)
    agent = portable / "StatBridge-official" / "src" / "agent"
    agent.mkdir(parents=True)
    paths = layout(agent)
    assert paths["backend"] == portable / "statbridge_mcp_server"
    assert paths["env"] == portable / "statbridge_mcp_server" / ".env"
    assert paths["data"] == portable / "runtime_data" / "processed"
    assert paths["tables"] == portable / "runtime_data" / "tables"
    assert paths["vector"] == portable / "StatBridge-official" / "data" / "vector_store_349"
