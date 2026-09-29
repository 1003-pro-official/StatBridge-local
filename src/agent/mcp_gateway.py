from __future__ import annotations
from typing import Any

class McpToolGateway:
    """Agent-side gateway with the same contract as the StatBridge MCP tools.

    The portable runtime currently exposes MCP over stdio for external clients. The UI Agent
    runs in the same Python runtime, so this gateway calls the shared StatisticsService used
    by those MCP tools without opening a second stdio subprocess per HTTP request.
    """
    def __init__(self, service: Any) -> None:
        self.service = service

    def search_tables(self, query: str, top_k: int = 5):
        return self.service.search_tables(query=query, top_k=top_k)

    def get_table_metadata(self, table_id: str, live_period_fallback: bool = True):
        return self.service.get_table_metadata(table_id=table_id, live_period_fallback=live_period_fallback)

    def get_statistics(self, **kwargs: Any):
        return self.service.get_statistics(**kwargs)
