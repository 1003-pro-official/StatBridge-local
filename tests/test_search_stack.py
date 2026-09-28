from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_backend_searches_current_catalog_without_api_call():
    from statbridge_mcp.metadata_store import MetadataStore
    from statbridge_mcp.statistics_service import StatisticsService

    store = MetadataStore()
    service = StatisticsService(store=store, client=object())
    candidates = service.search_tables("경제심리지수", top_k=5)

    assert len(store.table_ids()) == 349
    assert candidates[0]["table_id"] == "DT_513Y001"
    assert candidates[0]["table_name"]
    assert candidates[0]["local_csv_available"] is True


def test_backend_search_does_not_require_kosis_key(monkeypatch):
    from statbridge_mcp.config import settings
    from statbridge_mcp.metadata_store import MetadataStore
    from statbridge_mcp.statistics_service import StatisticsService

    monkeypatch.setattr(settings, "kosis_api_key", "")
    service = StatisticsService(store=MetadataStore())

    assert service.search_tables("경제심리지수")[0]["table_id"] == "DT_513Y001"


def test_search_covers_colloquial_and_multi_indicator_questions():
    from statbridge_mcp.metadata_store import MetadataStore
    from statbridge_mcp.search_engine import SearchEngine

    search = SearchEngine(MetadataStore()).search
    assert "DT_513Y001" in [x["table_id"] for x in search("요즘 경기가 체감상 어떤지 경제심리 지표로 보여줘")]
    assert "DT_512Y013" in [x["table_id"] for x in search("기업경기조사에서 전 산업 업황실적은 어떻게 변했나")]
    assert {"DT_121Y006", "DT_121Y002"} <= {
        x["table_id"] for x in search("예금은행 신규취급액 기준 대출금리와 수신금리를 비교해줘")
    }
    assert search("서울 강남구 오늘 미세먼지 농도 알려줘") == []


def test_exact_statistics_keeps_selected_ids_and_never_retries():
    import pandas as pd
    from statbridge_mcp.metadata_store import MetadataStore
    from statbridge_mcp.statistics_service import StatisticsService

    class RecordingClient:
        def __init__(self):
            self.calls = []

        def get_statistics(self, **kwargs):
            self.calls.append(kwargs)
            return [{"PRD_DE": "202501", "DT": "97.5", "UNIT_NM": ""}]

    store = MetadataStore()
    meta = store.get("DT_513Y001")
    client = RecordingClient()
    service = StatisticsService(store=store, client=client)
    first_row = pd.read_csv(service._find_local_table_csv(meta.table_id), nrows=1, dtype=str).iloc[0]
    selected = {"objL1": first_row["C1"]}
    result = service.get_exact_statistics(
        table_id=meta.table_id,
        item_id=first_row["ITM_ID"],
        classifications=selected,
        frequency="M",
        start_period="202501",
        end_period="202512",
        source="kosis",
    )

    assert result["row_count"] == 1
    assert len(client.calls) == 1
    assert client.calls[0]["classifications"] == selected


def test_search_keeps_catalog_only_tables_as_candidates():
    from statbridge_mcp.metadata_store import MetadataStore
    from statbridge_mcp.statistics_service import StatisticsService

    service = StatisticsService(store=MetadataStore(), client=object())
    candidates = service.search_tables("상세자금순환표 잔액표", top_k=10)

    by_id = {candidate["table_id"]: candidate for candidate in candidates}
    assert "DT_284Y001" in by_id
    assert by_id["DT_284Y001"]["local_csv_available"] is False


def test_mcp_health_distinguishes_catalog_from_local_data():
    from statbridge_mcp.server import healthcheck

    status = healthcheck()

    assert status["catalog_table_count"] == 349
    assert status["local_csv_table_count"] == 347


def test_agent_passes_interpreted_query_to_backend():
    from statbridge_agent.models import MockGenerator
    from statbridge_agent.nodes.query_interpret import build_parsed_query_prompt
    from statbridge_agent.pipeline import SearchPipeline
    from statbridge_agent.tools import InProcessTools
    from statbridge_mcp.metadata_store import MetadataStore
    from statbridge_mcp.statistics_service import StatisticsService

    query = "경제심리지수 추이를 보여줘"
    parsed = {
        "intent": "trend",
        "indicators": [{
            "original_term": "경제심리지수",
            "normalized_term": "경제심리지수",
            "search_terms": ["경제심리지수"],
        }],
        "start_period": None,
        "end_period": None,
        "frequency": None,
        "filters": {},
        "output_type": "chart",
    }
    generator = MockGenerator({build_parsed_query_prompt(query): parsed})
    service = StatisticsService(store=MetadataStore(), client=object())

    result = SearchPipeline(generator, InProcessTools(service)).run(query)

    assert result.candidates[0]["table_id"] == "DT_513Y001"
    assert result.parsed_query.indicators[0].original_term == "경제심리지수"


def test_mcp_service_reads_existing_local_csv_without_api_key(monkeypatch):
    from statbridge_mcp.config import settings
    from statbridge_mcp.statistics_service import StatisticsService

    monkeypatch.setattr(settings, "kosis_api_key", "")
    result = StatisticsService().get_statistics(
        "DT_513Y001",
        classifications={"objL1": "ALL"},
        frequency="M",
        start_period="200301",
        end_period="200301",
    )

    assert result["source"] == "local_csv"
    assert result["row_count"] > 0
    assert all(row["PRD_DE"] == "200301" for row in result["rows"])
