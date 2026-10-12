import json
from pathlib import Path

from agent_runtime import StatBridgeAgent
from output_agent import OutputAgent


def test_current_account_breakdown_uses_five_validated_dimension_values():
    dictionary = Path(__file__).resolve().parents[1] / "src/agent/stat_dictionary/stat_language_dictionary.json"
    table = next(item for item in json.loads(dictionary.read_text(encoding="utf-8"))["tables"]
                 if item["table_id"] == "DT_301Y017")
    agent = object.__new__(StatBridgeAgent)
    agent.tables_by_id = {table["table_id"]: table}
    selected = {"table_id": table["table_id"], "dimension_hits": []}

    plans = agent._current_account_component_plans(
        "2025년 우리나라 경상수지와 구성 항목을 그래프로 보여줘", selected,
        "2025년 경상수지 구성 항목",
    )

    assert [plan["series_label"] for plan in plans] == [
        "경상수지", "상품수지", "서비스수지", "본원소득수지", "이전소득수지",
    ]
    assert len({plan["classifications"]["objL1"] for plan in plans}) == 5
    assert all(plan["start_period"] == "202501" and plan["end_period"] == "202512" for plan in plans)
    assert all(plan["exact_params"]["objL1"] == plan["classifications"]["objL1"] for plan in plans)
    assert agent._current_account_component_plans("경상수지를 보여줘", selected, "경상수지") == []

    rows = [
        {"PRD_DE": f"2025{month:02d}", "DT": str(month * 100), "UNIT_NM": "백만달러",
         "_SERIES_LABEL": plan["series_label"], "_SOURCE_SERIES_ID": plan["table_id"], "_FREQUENCY": "M"}
        for plan in plans for month in range(1, 13)
    ]
    output = OutputAgent().prepare({"execution": {"rows": rows}, "api_plans": plans}, {"chart_type": "line"})
    assert len(output["plotlyFigure"]["data"]) == 5
    assert all(trace["x"][0] == "202501" and trace["x"][-1] == "202512"
               for trace in output["plotlyFigure"]["data"])
