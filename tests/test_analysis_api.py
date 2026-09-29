from bridge_api import QueryRequest, query


def test_query_waits_for_period_before_numeric_execution():
    response = query(QueryRequest(query="경제심리지수 추이", execute=True))
    assert response["status"] == "need_period"
    assert response["chart"] == []
    assert response["availablePeriod"]
