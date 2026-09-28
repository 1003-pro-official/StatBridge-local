from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from statbridge_agent.models import TextGenerator
from statbridge_agent.nodes.query_interpret import ParsedQuery, parse_with_hcx
from statbridge_agent.nodes.retrieve import retrieve_top_tables
from statbridge_agent.tools import ToolClient


@dataclass(frozen=True)
class SearchResult:
    query: str
    parsed_query: ParsedQuery
    candidates: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "parsed_query": asdict(self.parsed_query),
            "candidates": self.candidates,
        }


class SearchPipeline:
    """AGENTS.md milestone: natural language -> ParsedQuery -> Top-K tables."""

    def __init__(self, generator: TextGenerator, tools: ToolClient) -> None:
        self._generator = generator
        self._tools = tools

    def run(self, query: str, top_k: int = 5) -> SearchResult:
        if not query.strip():
            raise ValueError("query must not be empty")
        parsed = parse_with_hcx(self._generator, query)
        candidates = retrieve_top_tables(query, parsed, self._tools, top_k=top_k)
        return SearchResult(query=query, parsed_query=parsed, candidates=candidates)
