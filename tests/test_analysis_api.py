import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

from analysis_service import AnalysisService
from query_api import make_handler
from statbridge_mcp.statistics_service import StatisticsService


def test_http_analysis_selects_exact_local_series():
    service = StatisticsService()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        def post(payload):
            request = Request(
                f"http://127.0.0.1:{server.server_port}/api/analyze",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request, timeout=10) as response:
                return json.load(response)

        first = post({"query": "경제심리지수 순환변동치 추이"})
        assert first["status"] == "need_clarification"
        options = post({"query": "경제심리지수 순환변동치 추이", "series": [{"table_id": "DT_513Y001"}]})
        assert options["reason"] == "series"
        series = options["options"]
        result = post({
            "query": "경제심리지수 순환변동치 추이", "source": "local",
            "series": [{"table_id": "DT_513Y001", "item_id": series["items"][0]["id"],
                        "classifications": {"objL1": series["axes"][0]["values"][1]["id"]},
                        "frequency": "M", "start_period": "202501", "end_period": "202512"}],
        })
        assert result["status"] == "resolved"
        assert result["chart"][0]["source"] == "local_csv"
        assert result["chart"][0]["points"][0] == {"period": "202501", "value": 89.8}
    finally:
        server.shutdown()
        server.server_close()
