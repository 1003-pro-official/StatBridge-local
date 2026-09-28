from __future__ import annotations

from typing import Any

from statbridge_agent.nodes.query_interpret import ParsedQuery
from statbridge_agent.tools import ToolClient


def build_retrieval_query(user_query: str, parsed: ParsedQuery) -> str:
    """Keep the original context and append deduplicated statistical search terms."""
    terms: list[str] = []
    for indicator in parsed.indicators:
        for term in (
            indicator.original_term,
            indicator.normalized_term,
            *indicator.search_terms,
        ):
            cleaned = term.strip()
            if cleaned and cleaned not in terms:
                terms.append(cleaned)
    return f"{user_query.strip()} {' '.join(terms)}".strip()


def retrieve_top_tables(
    user_query: str,
    parsed: ParsedQuery,
    tools: ToolClient,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    if not 1 <= top_k <= 20:
        raise ValueError("top_k must be between 1 and 20")
    return tools.search_tables(build_retrieval_query(user_query, parsed), top_k=top_k)
