import json
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def test_query_api_returns_real_candidates_and_rejects_empty_query():
    from query_api import make_handler
    from statbridge_mcp.metadata_store import MetadataStore
    from statbridge_mcp.statistics_service import StatisticsService

    service = StatisticsService(store=MetadataStore(), client=object())
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        address = f"http://127.0.0.1:{server.server_port}/api/query"
        request = Request(address, data=json.dumps({"query": "경제심리지수"}).encode(), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            payload = json.load(response)
        assert payload["status"] == "search_results"
        assert payload["candidates"][0]["table_id"] == "DT_513Y001"
        assert payload["candidates"][0]["path"]

        empty = Request(address, data=b'{"query":"  "}', headers={"Content-Type": "application/json"})
        try:
            urlopen(empty, timeout=5)
        except HTTPError as error:
            assert error.code == 400
        else:
            raise AssertionError("empty query should be rejected")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_query_api_reports_backend_failure_as_http_error():
    from query_api import make_handler

    class BrokenSearch:
        def search_tables(self, query, top_k):
            raise RuntimeError("backend unavailable")

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(BrokenSearch()))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/query",
            data=b'{"query":"economic sentiment"}',
            headers={"Content-Type": "application/json"},
        )
        try:
            urlopen(request, timeout=5)
        except HTTPError as error:
            assert error.code == 500
        else:
            raise AssertionError("backend error should receive HTTP 500")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
