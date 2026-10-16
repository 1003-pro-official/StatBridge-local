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


def healthcheck() -> dict[str, Any]:
    """StatBridge MCP 서버 상태와 데이터 경로를 확인한다."""
    service = get_service()
    return {
        "status": "ok",
        "sdk": "mcp-2.x",
        "catalog_table_count": len(service.store.table_ids()),
        "supported_table_count": len(service.store.available_supported_tables()),
        "local_csv_table_count": sum(
            any(service.tables_dir.glob(f"{table_id}*.csv"))
            for table_id in service.store.table_ids()
        ),
        "data_dir": str(service.store.data_dir),
        "tables_dir": str(service.tables_dir),
        "kosis_api_key_configured": bool(settings.kosis_api_key),
    }


@mcp.tool()
def search_tables(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """자연어 또는 키워드와 관련된 한국은행 KOSIS 통계표 후보를 검색한다."""
    return get_service().search_tables(query=query, top_k=top_k)


@mcp.tool()
def get_table_metadata(
    table_id: str,
    live_period_fallback: bool = True,
) -> dict[str, Any]:
    """통계표의 항목, 분류, 주기, 기간, 주석 등 메타데이터를 조회한다."""
    return get_service().get_table_metadata(
        table_id=table_id,
        live_period_fallback=live_period_fallback,
    )


@mcp.tool()
def get_statistics(
    table_id: str,
    item_id: str = "ALL",
    classifications: dict[str, str] | None = None,
    frequency: str | None = None,
    start_period: str | None = None,
    end_period: str | None = None,
    prefer_local: bool = True,
    allow_fallback: bool = True,
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
        allow_fallback=allow_fallback,
    )


def validate_tables_batch(
    offset: int = 0,
    limit: int = 20,
    prefer_local: bool = False,
    include_success_results: bool = True,
) -> dict[str, Any]:
    """347개 표를 offset/limit 단위로 나눠 smoke test한다. Inspector timeout 방지를 위해 이 도구 사용을 권장한다."""
    return get_service().validate_tables_batch(
        offset=offset,
        limit=limit,
        prefer_local=prefer_local,
        include_success_results=include_success_results,
    )


def validate_all_tables(
    limit: int = 0,
    prefer_local: bool = False,
) -> dict[str, Any]:
    """호환용 전체 검증 도구. Inspector에서는 긴 호출로 timeout이 날 수 있으므로 batch 도구를 권장한다."""
    return get_service().validate_all_tables(
        limit=limit,
        prefer_local=prefer_local,
    )


@mcp.tool()
def get_statistics_batch(requests: list[dict[str, Any]], timeout_seconds: float = 20) -> dict[str, Any]:
    """확정한 조회 조건을 제한적으로 병렬 조회한다. 각 요청의 성공·실패·시간 초과를 반환한다."""
    from .statistics_batch import get_statistics_batch as batch
    return batch(get_service(),requests,timeout_seconds)


if __name__ == "__main__":
    mcp.run()
