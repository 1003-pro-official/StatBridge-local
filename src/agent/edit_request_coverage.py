"""Common request accounting for every chart edit operation and every input source."""
from __future__ import annotations
import re
from typing import Any


class CoverageContractError(ValueError):
    """Malformed model accounting, eligible for one bounded correction."""


def request_sources(instruction: str, visual: dict) -> list[dict[str, str]]:
    sources = []
    # Keep titles and comma-separated values intact; the reviewer must split
    # conjunctions inside a source into separate checks, not just one per line.
    for index, text in enumerate(re.split(r"[\n;]+", instruction)):
        if text.strip():
            sources.append({"id":f"text:{index}", "text":text.strip()})
    for mark in visual.get("marks", []):
        if str(mark.get("text") or "").strip():
            sources.append({"id":f"mark:{mark['id']}", "text":mark["text"].strip()})
    return sources


def validate_coverage(proposal: dict[str, Any], sources: list[dict[str, str]]) -> list[dict]:
    commands = proposal.get("commands")
    coverage = proposal.get("coverage")
    if not isinstance(commands, list) or not 1 <= len(commands) <= 12:
        raise CoverageContractError("전체 수정 요청의 명령을 확인하지 못했습니다. 기존 그래프는 유지됩니다.")
    if not isinstance(coverage, list):
        raise CoverageContractError("수정 요청별 확인 결과가 없습니다. 기존 그래프는 유지됩니다.")
    source_map = {source["id"]:source["text"] for source in sources}
    seen, command_ids = set(), set()
    for entry in coverage:
        if not isinstance(entry, dict) or entry.get("source_id") not in source_map:
            raise CoverageContractError("수정 요청 확인 결과의 입력 출처가 다릅니다. 기존 그래프는 유지됩니다.")
        text = entry.get("text")
        # Korean models may normalize spaces while quoting a request. Accept
        # only whitespace differences; words, values and punctuation must match.
        source_text = source_map[entry["source_id"]]
        quoted = re.sub(r"\s+", "", text) if isinstance(text, str) else ""
        if not quoted or quoted not in re.sub(r"\s+", "", source_text):
            raise CoverageContractError("수정 요청 확인 결과가 원문과 다릅니다. 기존 그래프는 유지됩니다.")
        status = entry.get("status")
        indices = entry.get("command_indices")
        if status != "covered":
            reason = str(entry.get("reason") or "수정 대상 또는 내용을 구체적으로 알려 주세요.")[:200]
            raise ValueError(f"수정 요청을 확인해 주세요: {text[:160]} — {reason}. 기존 그래프는 유지됩니다.")
        if not isinstance(indices, list) or not indices or any(type(i) is not int or not 0 <= i < len(commands) for i in indices):
            raise CoverageContractError(f"수정 요청에 연결된 명령이 없습니다: {text[:160]}. 기존 그래프는 유지됩니다.")
        seen.add(entry["source_id"])
        command_ids.update(indices)
    omitted = [s["text"] for s in sources if s["id"] not in seen]
    if omitted:
        raise CoverageContractError("확인하지 못한 수정 요청: " + " / ".join(omitted)[:400] + ". 기존 그래프는 유지됩니다.")
    # Models sometimes link only the first deletion in "remove A and B".
    # Recover a link only when an exact literal value occurs in one source
    # whose already linked command uses the identical operation. No command
    # or setting is invented, and ambiguous source matches remain rejected.
    for index in sorted(set(range(len(commands))) - command_ids):
        command = commands[index]
        value = command.get("value") if isinstance(command, dict) else None
        if not isinstance(value, str) or len(value) < 2:
            continue
        matches = [entry for entry in coverage if value in entry["text"] and any(
            commands[i].get("operation") == command.get("operation") for i in entry["command_indices"])]
        if len(matches) == 1:
            matches[0]["command_indices"] = [*matches[0]["command_indices"], index]
            command_ids.add(index)
    if command_ids != set(range(len(commands))):
        raise CoverageContractError("입력 요청에 연결되지 않은 수정 명령이 있습니다. 기존 그래프는 유지됩니다.")
    return coverage


REVIEW_SYSTEM = """너는 그래프 수정 계획의 독립 검토자이다. candidateProposal을 그대로 승인하지 말고 sources의 현재 사용자 지시를 처음부터 모두 읽어라.
sources 배열의 모든 id를 coverage.source_id에 반드시 넣어라. text와 mark는 중복 지시여도 각각 기록한다. mark:arrow, mark:box처럼 표시 설명 출처를 생략하지 마라. 동일 명령 인덱스를 여러 출처의 coverage에 연결할 수 있다. 원문을 요약하거나 어미를 바꾸지 말고 sources.text의 연속 구절을 복사해라.
한 문장에도 제목 변경과 위치, 색과 두께처럼 여러 지시가 있다. 반드시 각각 별도의 coverage 항목으로 분해하라.
텍스트 입력과 모든 도구(펜/화살표/사각형/원/텍스트)의 설명은 동등한 현재 지시다. 대화 이력은 맥락만이며 이전 요청을 반복 실행하지 마라.
모든 지원 operation과 설정에 이 검토를 적용한다. 제목/부제/폰트/배경/크기/여백/축/격자/눈금/범례/계열/부분 스타일/값표시/종류/배치/기간/변환/주석/기준선/강조/도형/초기화를 빠뜨리지 마라.
후보에서 누락 또는 잘못 해석한 지시를 보완한 전체 commands를 반환해라. 후보와 보정 명령을 단순 합쳐 중복 실행하지 마라.
사용자가 말하지 않은 변경을 만들지 마라. 색/수치/범위/위치가 명확하면 그 값을 사용하고, 표시 selection은 실제 데이터에서 검증된 범위이다.
표시의 색상/두께는 선택 범위에만 적용하고 mark_id를 연결한다. 전체 요소 지시는 mark_id 없이 처리한다.
이미 적용된 설정도 해당 요청을 무시하지 말고 동일 설정 명령으로 포함한다. 마지막 전체 상태에서도 모든 요청이 유지되어야 한다. 서로 충돌하면 확인 질문을 반환한다.
지원하지 않는 변경, 모호한 지시는 coverage status=blocked와 reason으로 구체적으로 설명한다. 다른 지시만 실행한 성공을 반환하지 마라.
validationError는 서버가 검증한 실패 이유다. 원문이 명확하면 올바른 전체 commands로 수정하고 clarification=null로 반환하라. 보정했다는 설명을 clarification에 넣지 마라. clarification은 반드시 사용자 답변이 필요한 확인 질문에만 사용한다.\n출력은 JSON {commands:[전체 보정 명령 최대12개], coverage:[{source_id:sources의id,text:원문에서 그대로 인용한 해당 지시,status:covered/blocked,command_indices:[0부터 명령 인덱스],reason:확인 이유}],clarification:null 또는 확인질문}이다.
모든 sources에 한 개 이상 coverage가 필요하며 한 source 안의 독립 지시 수만큼 coverage를 작성한다. 모든 commands는 하나 이상 coverage와 연결해야 한다.
다음의 해석/데이터/보안 규칙을 모두 준수하라:
"""


def normalize_parameter_names(item: dict) -> dict:
    op = item.get("operation")
    aliases = {}
    if op in {"set_segment_style", "set_point_style", "set_series_style", "add_guide", "update_guide", "add_shape", "update_shape"}:
        aliases = {"line_width":"width", "line_dash":"dash"}
    elif op == "set_axis_style":
        aliases = {"showgrid":"show_grid", "zeroline":"zero_line", "tickangle":"tick_angle", "dtick":"tick_step"}
    elif op == "set_presentation":
        aliases = {"title_font_size":"title_size", "legend_font_size":"legend_size"}
    params = item.get("params")
    if not isinstance(params, dict):
        return item
    normalized = dict(params)
    for old, new in aliases.items():
        if old not in normalized:
            continue
        if new in normalized and normalized[new] != normalized[old]:
            raise CoverageContractError(f"수정 설정 {old}와 {new}의 값이 서로 다릅니다. 기존 그래프는 유지됩니다.")
        normalized[new] = normalized.pop(old)
    return {**item, "params":normalized}
