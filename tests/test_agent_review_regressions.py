from pathlib import Path

from stat_dictionary.stat_language_resolver import StatLanguageResolver


AGENT_ROOT = Path(__file__).resolve().parents[1] / "src" / "agent"


def resolver() -> StatLanguageResolver:
    return StatLanguageResolver(
        AGENT_ROOT / "stat_dictionary" / "stat_language_dictionary.json"
    )


def test_initial_household_loan_query_keeps_sibling_measure_choices():
    result = resolver().resolve("가계대출 자료")

    assert result["status"] == "need_clarification"
    assert result["clarification_id"] == "loan_measure"
    assert len(result["options"]) >= 2


def test_initial_corporate_finance_query_does_not_auto_select_one_statement():
    result = resolver().resolve("기업 재무상태 좀 봐줘")

    assert result["status"] == "need_clarification"
    assert result["clarification_id"] == "corporate_finance_view"
    assert len(result["options"]) >= 2


def test_unsupported_consumer_price_is_not_exposed_as_a_clarification_option():
    stat_resolver = resolver()
    result = stat_resolver.resolve("요즘 물가 어때?")

    assert result["status"] == "need_clarification"
    assert "소비자물가" not in {option["value"] for option in result["options"]}
    assert stat_resolver.resolve("소비자물가지수 추이")["status"] == "no_match"


def test_industry_loan_breakdown_options_only_match_industry_loan_tables():
    stat_resolver = resolver()
    candidates = stat_resolver.rank("산업별대출", top_k=12)
    clarification = stat_resolver._clarification(
        "산업별대출", candidates, confirmed={"industry_loan_institution": "예금은행"}
    )

    assert clarification["clarification_id"] == "industry_loan_breakdown"
    for option in clarification["options"]:
        for table_id in option["matching_table_ids"]:
            assert "산업별대출금" in stat_resolver.tables_by_id[table_id]["table_name"]


def test_frontend_does_not_rewrite_comparison_queries_or_hide_warnings():
    source = (AGENT_ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")

    assert 'submitQuery({query:"대출 얼마나 늘었어?"' not in source
    assert 'submitQuery({query:"금리 추이를 보여줘"' not in source
    assert "result.warnings?.map" in source
