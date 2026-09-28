from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol


class ToolClient(Protocol):
    def search_tables(self, nl_query: str, top_k: int = 5) -> list[dict[str, Any]]: ...

    def get_meta(self, table_id: str, live_period_fallback: bool = True) -> dict[str, Any]: ...

    def fetch_data(
        self,
        table_id: str,
        item_id: str = "ALL",
        classifications: dict[str, str] | None = None,
        frequency: str | None = None,
        start_period: str | None = None,
        end_period: str | None = None,
        prefer_local: bool = True,
    ) -> dict[str, Any]: ...


class InProcessTools:
    """Call the Backend service in this process with the same tool arguments."""

    def __init__(self, service: Any | None = None) -> None:
        self._service = service or self._load_service()

    @staticmethod
    def _load_service() -> Any:
        repository_root = Path(__file__).resolve().parents[3]
        backend_root = repository_root / "src" / "backend"
        if str(backend_root) not in sys.path:
            sys.path.insert(0, str(backend_root))
        try:
            module = import_module("statbridge_mcp.statistics_service")
            return module.StatisticsService()
        except ModuleNotFoundError as exc:
            raise RuntimeError("백엔드 의존성이 없습니다. src/backend/requirements.txt를 설치하세요.") from exc

    def search_tables(self, nl_query: str, top_k: int = 5) -> list[dict[str, Any]]:
        return self._service.search_tables(query=nl_query, top_k=top_k)

    def get_meta(self, table_id: str, live_period_fallback: bool = True) -> dict[str, Any]:
        return self._service.get_table_metadata(table_id=table_id, live_period_fallback=live_period_fallback)

    def fetch_data(
        self,
        table_id: str,
        item_id: str = "ALL",
        classifications: dict[str, str] | None = None,
        frequency: str | None = None,
        start_period: str | None = None,
        end_period: str | None = None,
        prefer_local: bool = True,
    ) -> dict[str, Any]:
        return self._service.get_statistics(
            table_id=table_id,
            item_id=item_id,
            classifications=classifications,
            frequency=frequency,
            start_period=start_period,
            end_period=end_period,
            prefer_local=prefer_local,
        )
