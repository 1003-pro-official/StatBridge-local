"""Validate a bounded public annotation vocabulary, NOT the application's NLP."""
import re

CLARIFICATION_GROUPS = {
    frozenset({"말잔", "평잔"}), frozenset({"수신", "대출"}),
    frozenset({"명목", "실질"}), frozenset({"계절조정", "원계열"}),
    frozenset({"신규취급", "잔액"}), frozenset({"기관", "용도"}),
    frozenset({"태도", "신용위험", "수요"}),
}


def instruction_command(instruction):
    text = instruction.strip()
    title = re.fullmatch(r"제목을 '([^']+)'로 변경해 주세요\.", text)
    if title:
        return {"operation": "set_title", "kind": "STYLE_EDIT", "value": title[1]}
    commands = {
        "범례를 숨겨 주세요. 데이터와 출처는 유지해 주세요.": {"operation": "set_legend", "kind": "STYLE_EDIT", "value": False},
        "전기 대비 증감률(%)로 변경해 주세요.": {"operation": "set_transform", "kind": "DATA_EDIT", "value": "growth_rate"},
        "첨부 계열을 전기 대비 증감률(%)로 바꿔 주세요.": {"operation": "set_transform", "kind": "DATA_EDIT", "value": "growth_rate"},
        "전년 같은 달 대비 증감률(%)로 변경해 주세요.": {"operation": "set_transform", "kind": "DATA_EDIT", "value": "year_over_year"},
        "첨부된 값으로 누적합을 계산해 주세요.": {"operation": "set_transform", "kind": "DATA_EDIT", "value": "cumulative"},
    }
    if text in commands:
        return dict(commands[text])
    period = re.fullmatch(r"(\d{4})년 (\d{1,2})월부터 (\d{1,2})월까지로 표시 기간을 좁혀 주세요\.", text)
    if period and 1 <= int(period[2]) <= int(period[3]) <= 12:
        return {"operation": "filter_period", "kind": "DATA_EDIT",
                "start": period[1] + period[2].zfill(2), "end": period[1] + period[3].zfill(2)}
    return None
