from __future__ import annotations

from functools import lru_cache
from typing import Any

from mcp.server import MCPServer

from .config import settings
from .statistics_service import StatisticsService

mcp = MCPServer("StatBridge-MCP")


@lru_cache(maxsize=1)
def get_service() -> StatisticsService:
    return StatisticsService()


@mcp.tool()
def healthcheck() -> dict[str, Any]:
    """StatBridge MCP 서버 상태와 데이터 경로를 확인한다."""
    service = get_service()
    csv_ids = {path.stem.split("__")[0] for path in service.tables_dir.glob("*.csv")}
    return {
        "status": "ok",
        "sdk": "mcp-2.x",
        "catalog_table_count": len(service.store.table_ids()),
        "local_csv_table_count": len(csv_ids.intersection(service.store.table_ids())),
        "data_dir": str(service.store.data_dir),
        "tables_dir": str(service.tables_dir),
        "kosis_api_key_configured": bool(settings.kosis_api_key),
    }


@mcp.tool()
def search_tables(nl_query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """자연어 또는 키워드와 관련된 한국은행 KOSIS 통계표 후보를 검색한다."""
    return get_service().search_tables(query=nl_query, top_k=top_k)


@mcp.tool()
def get_meta(
    table_id: str,
    live_period_fallback: bool = True,
) -> dict[str, Any]:
    """통계표의 항목, 분류, 주기, 기간, 주석 등 메타데이터를 조회한다."""
    return get_service().get_table_metadata(
        table_id=table_id,
        live_period_fallback=live_period_fallback,
    )


@mcp.tool()
def fetch_data(
    table_id: str,
    item_id: str = "ALL",
    classifications: dict[str, str] | None = None,
    frequency: str | None = None,
    start_period: str | None = None,
    end_period: str | None = None,
    prefer_local: bool = True,
) -> dict[str, Any]:
    """실제 통계 데이터를 조회한다. 로컬 CSV를 우선하고 KOSIS OpenAPI로 fallback한다."""
    return get_service().get_statistics(
        table_id=table_id,
        item_id=item_id,
        classifications=classifications,
        frequency=frequency,
        start_period=start_period,
        end_period=end_period,
        prefer_local=prefer_local,
    )


if __name__ == "__main__":
    mcp.run()
