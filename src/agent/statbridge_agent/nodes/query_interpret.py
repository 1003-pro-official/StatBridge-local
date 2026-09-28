from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from statbridge_agent.models import TextGenerator

PARSED_QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["trend", "comparison", "single_value", "multi_indicator"],
        },
        "indicators": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "original_term": {"type": "string"},
                    "normalized_term": {"type": "string"},
                    "search_terms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                },
                "required": ["original_term", "normalized_term", "search_terms"],
                "additionalProperties": False,
            },
        },
        "start_period": {"type": ["string", "null"]},
        "end_period": {"type": ["string", "null"]},
        "frequency": {"type": ["string", "null"]},
        "filters": {"type": "object"},
        "output_type": {"type": "string", "enum": ["table", "chart"]},
    },
    "required": [
        "intent",
        "indicators",
        "start_period",
        "end_period",
        "frequency",
        "filters",
        "output_type",
    ],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Indicator:
    original_term: str
    normalized_term: str
    search_terms: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedQuery:
    intent: str
    indicators: list[Indicator]
    start_period: str | None = None
    end_period: str | None = None
    frequency: str | None = None
    filters: dict[str, Any] = field(default_factory=dict)
    output_type: str = "table"


def build_parsed_query_prompt(query: str) -> str:
    return (
        "사용자의 한국어 통계 질의를 검색 가능한 JSON으로 변환하라. "
        "지표마다 원문(original_term), 공식 통계 개념(normalized_term), "
        "메타데이터 검색어(search_terms)를 작성하라. "
        "표 ID, 항목 ID, 분류 ID는 추측하거나 생성하지 마라. "
        "기간은 start_period/end_period, 주기는 frequency, 지역 등 조건은 filters, "
        "표나 그래프 요구는 output_type에 기록하라. "
        f"질의: {query}"
    )


def parse_query(raw: str | dict[str, Any]) -> ParsedQuery:
    data = json.loads(raw) if isinstance(raw, str) else raw
    indicators = [
        Indicator(
            original_term=item["original_term"],
            normalized_term=item["normalized_term"],
            search_terms=list(item["search_terms"]),
        )
        for item in data["indicators"]
    ]
    if not indicators:
        raise ValueError("indicators must contain at least one indicator")
    return ParsedQuery(
        intent=data["intent"],
        indicators=indicators,
        start_period=data.get("start_period"),
        end_period=data.get("end_period"),
        frequency=data.get("frequency"),
        filters=dict(data.get("filters") or {}),
        output_type=data.get("output_type", "table"),
    )


def parse_with_hcx(gen: TextGenerator, query: str) -> ParsedQuery:
    """Parse with any TextGenerator; HCXGenerator provides the production path."""
    raw = gen.generate(build_parsed_query_prompt(query), schema=PARSED_QUERY_SCHEMA)
    return parse_query(raw)
