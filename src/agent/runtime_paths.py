"""Resolve repository and portable layouts without sharing local settings."""
from pathlib import Path


def layout(agent_dir: Path | None = None) -> dict[str, Path]:
    agent_dir = (agent_dir or Path(__file__).resolve().parent).resolve()
    project = agent_dir.parents[1]
    portable = project.parent / "statbridge_mcp_server"
    if portable.is_dir() and project.name == "StatBridge-official":
        return {"root": project.parent, "backend": portable,
                "data": project.parent / "runtime_data" / "processed",
                "tables": project.parent / "runtime_data" / "tables",
                "env": portable / ".env", "vector": project / "data" / "vector_store_349"}
    return {"root": project, "backend": project / "src" / "backend",
            "data": project / "data" / "processed", "tables": project / "data" / "tables",
            "env": project / ".env", "vector": project / ".venv" / "cache" / "vector_store_349"}
