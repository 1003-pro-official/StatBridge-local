"""Fail closed at the text/sketch boundary; never infer dates from pixels."""
from __future__ import annotations

from output_schema import VisualEditContext


def compatible(target: str, operation: str, item: dict, labels: set[str]) -> bool:
    if target in {"", "chart"}:
        return True
    if target == "title":
        return operation in {"set_title", "set_subtitle"} or (
            operation == "set_presentation" and set(item.get("params") or {}) <= {"title_size", "title_x", "title_y"})
    if target == "legend":
        return operation == "set_legend" or (operation == "set_presentation" and
            set(item.get("params") or {}) <= {"legend_size"})
    if target in {"x_axis", "y_axis"}:
        return (operation == "set_axis_style" and item.get("label") == ("x" if target == "x_axis" else "y")) or (
            operation == "set_axis_labels" and not item.get("y_axis_label" if target == "x_axis" else "x_axis_label"))
    if target in labels:
        return item.get("label") == target or item.get("value") == target
    return False


def validate_visual(visual: VisualEditContext, instruction: str) -> None:
    ids = [mark.id for mark in visual.marks]
    if len(ids) != len(set(ids)):
        raise ValueError("표시 ID가 중복되었습니다. 표시를 다시 만들어 주세요.")
    for mark in visual.marks:
        if mark.tool in {"arrow", "rectangle"} and len(mark.points) < 2:
            raise ValueError("화살표와 사각형은 시작·종료 위치가 필요합니다.")
        if mark.selection and mark.target not in {"", "chart", mark.selection.label}:
            raise ValueError("표시의 수정 대상과 선택 계열이 다릅니다. 대상을 다시 확인해 주세요.")
        if not instruction.strip() and mark.text.strip() in {"제목", "간소하게", "수정", "바꿔줘"}:
            raise ValueError("수정 내용을 구체적으로 알려 주세요. 예: 제목을 '수출 추이'로, 가로축 눈금을 12개월 간격으로 표시해 줘.")


def bind_command(item: dict, visual: VisualEditContext, labels: set[str]) -> str | None:
    """Recover a missing ID only from a unique compatible explicit target."""
    identifier = item.get("mark_id")
    if identifier:
        matches = [mark for mark in visual.marks if mark.id == identifier]
        if not matches:
            raise ValueError("수정 명령의 표시 ID를 찾지 못했습니다.")
        if not compatible(matches[0].target, item["operation"], item, labels):
            raise ValueError("모델의 수정 명령이 선택한 대상과 다릅니다. 기존 그래프는 유지됩니다.")
        return str(identifier)
    matches = [mark for mark in visual.marks if mark.target not in {"", "chart"}
               and compatible(mark.target, item["operation"], item, labels)]
    if len(matches) == 1:
        item["mark_id"] = matches[0].id
        return matches[0].id
    if item["operation"] in {
        "set_series_color", "set_series_dash", "set_series_style", "set_line_width",
        "set_segment_style", "set_point_style", "highlight_period",
    }:
        matches = [mark for mark in visual.marks if mark.selection
            and (not item.get("label") or mark.selection.label == item["label"])
            and (not item.get("start") or (mark.selection.start == str(item["start"])
                and mark.selection.end == str(item.get("end") or item["start"])))]
        if len(matches) == 1:
            item["mark_id"] = matches[0].id
            return matches[0].id
    return None
