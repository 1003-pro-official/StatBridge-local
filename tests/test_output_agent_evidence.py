from output_agent import OutputAgent


def test_output_agent_preserves_plotted_values_and_query_evidence():
    result = {
        "api_plan": {
            "table_id": "DT_513Y001",
            "table_name": "경제심리지수",
            "org_id": "301",
            "item_id": "13103134473999",
            "frequency": "M",
            "start_period": "202501",
            "end_period": "202502",
        },
        "execution": {
            "rows": [
                {"PRD_DE": "202501", "DT": "100.1", "ITM_NM": "경제심리지수", "UNIT_NM": ""},
                {"PRD_DE": "202502", "DT": "101.2", "ITM_NM": "경제심리지수", "UNIT_NM": ""},
            ],
            "sources": [{"table_id": "DT_513Y001", "source": "local_csv", "row_count": 2}],
        },
    }

    output = OutputAgent().prepare(result)

    assert output["status"] == "ready"
    assert output["table"]["rows"] == [
        {"series": "경제심리지수", "period": "202501", "value": 100.1, "unit": ""},
        {"series": "경제심리지수", "period": "202502", "value": 101.2, "unit": ""},
    ]
    assert output["explanation"]["text"] == output["summary"]
    assert output["evidence"] == [{
        "tableId": "DT_513Y001", "tableName": "경제심리지수",
        "organizationId": "301", "itemId": "13103134473999", "frequency": "M",
        "requestedPeriod": {"start": "202501", "end": "202502"},
        "rowCount": 2, "source": "local_csv",
    }]
