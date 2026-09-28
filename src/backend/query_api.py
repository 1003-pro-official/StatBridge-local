"""HTTP bridge for catalog search and validated numeric analysis."""

import argparse
import json
from functools import cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from statbridge_mcp.statistics_service import StatisticsService
from analysis_service import AnalysisService


def make_handler(service: StatisticsService):
    @cache
    def analysis() -> AnalysisService:
        return AnalysisService(service)

    class QueryHandler(BaseHTTPRequestHandler):
        def respond(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if self.path not in {"/api/query", "/api/analyze"}:
                self.respond(404, {"error": "unknown endpoint"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384 or self.headers.get_content_type() != "application/json":
                    raise ValueError("expected a small JSON request")
                payload = json.loads(self.rfile.read(length))
                query = payload.get("query")
                if not isinstance(query, str) or not query.strip():
                    raise ValueError("query must be a nonempty string")
            except (ValueError, TypeError, json.JSONDecodeError, AttributeError) as error:
                self.respond(400, {"error": str(error)})
                return
            try:
                if self.path == "/api/analyze":
                    self.respond(200, analysis().analyze(payload))
                    return
                candidates = service.search_tables(query.strip(), top_k=5)
            except ValueError as error:
                self.respond(400, {"error": str(error)})
                return
            except Exception:
                self.log_error("catalog search failed")
                self.respond(500, {"error": "catalog search failed"})
                return
            self.respond(200, {
                "status": "search_results",
                "query": query.strip(),
                "candidates": candidates,
                "note": "검색 후보이며 정답 표 또는 수치 결과로 확정되지 않았습니다.",
            })

    return QueryHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="StatBridge catalog search API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(StatisticsService()))
    print(f"StatBridge search API: http://{args.host}:{server.server_port}/api/query")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
