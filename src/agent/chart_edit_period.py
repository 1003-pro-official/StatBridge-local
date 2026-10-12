"""Re-query a confirmed statistic when a follow-up changes the chart period."""
from copy import deepcopy
import re
from request_period import explicit_period, TOKEN
from output_schema import ChartSpec

STYLE_WORDS=r"제목|부제|색|두께|굵|점선|격자|눈금|범례|강조|음영|주석|메모|도형|글꼴|폰트|배경|여백|크기|가운데|보조축|증가율|누적|숨겨|숨기|축"


def period_redraw(instruction,latest=None):
    period=explicit_period(instruction,latest=latest)
    if not period: return None
    explicit_change=re.search(r"날짜|(?:조회)?기간.*(?:바꿔|변경|수정)",instruction)
    draw=re.search(r"그려|그리|보여|조회",instruction)
    if not explicit_change and (not draw or re.search(r"색|두께|강조|음영|점선|주석|메모",instruction)):
        return None
    residual=TOKEN.sub("",instruction)
    residual=re.sub(r"날짜|조회|기간|그래프|차트|시작(?:일|시점)?|종료(?:일|시점)?|변경|수정|다시|바꿔|바꾸어|그려|그리|보여|하자|해|부터|이후|까지|로|으로|을|를|은|는|줘|주세요|주세요|처음|끝|[\s.,!?~～–—-]", "",residual)
    style=bool(re.search(STYLE_WORDS,instruction))
    # A different statistic is not a period edit of this confirmed dataset.
    if residual and not style: return None
    return {**period,"only_period":not style}


def revise_period(session,instruction,output_agent,execute,availability,api_period):
    if not TOKEN.search(instruction) or not re.search(r"날짜|기간|그려|그리|보여|조회",instruction): return None
    original=session["result"]
    plans=original.get("api_plans") or [original.get("api_plan")]
    plans=[p for p in plans if p]
    if not plans: return None
    available=availability(plans)
    request=period_redraw(instruction,latest=available.get("max"))
    if not request: return None
    start=max(request["start"],available.get("min") or request["start"])
    end=min(request["end"],available.get("max") or request["end"])
    if start>end: raise ValueError("요청 기간에 제공되는 통계가 없습니다. 기존 그래프는 유지됩니다.")
    overrides={str(p["table_id"]):(api_period(start,str(p["frequency"])),api_period(end,str(p["frequency"]),end=True)) for p in plans}
    old_query=" · ".join(str(s["query"]) for s in session["sessions"])
    confirmed_periods={}
    for item in session["sessions"]:
        saved=item.get("result") or original
        saved_plans=saved.get("api_plans") or [saved.get("api_plan")]
        for p in saved_plans:
            if p:
                confirmed_periods[str(p["table_id"])]=(
                    api_period(item["period"]["start"],str(p["frequency"])),
                    api_period(item["period"]["end"],str(p["frequency"]),end=True))
    refreshed=execute(query=old_query,resolution=deepcopy(original),execute=True,period_overrides=overrides,
                      confirmed_periods=confirmed_periods,generate_answer=False)
    execution=refreshed.get("execution") or {}
    if execution.get("status")!="success" or not execution.get("rows"):
        raise ValueError("수정할 기간의 원자료를 조회하지 못했습니다. "+str(execution.get("error") or "조회된 데이터가 없습니다.")+" 기존 그래프는 유지됩니다.")
    spec=ChartSpec.model_validate(session["output"]["chartState"])
    # All selected plans are queried at the same UI boundaries. Period filtering
    # is reset because those exact boundaries are now owned by the source plans.
    updated=spec.model_copy(update={"period_start":None,"period_end":None})
    output=output_agent._build(refreshed,updated,generate_explanation=False)
    if output.get("plotlyFigure")==session["output"].get("plotlyFigure"):
        raise ValueError(f"현재 제공되는 데이터 범위는 {start} ~ {end}이며 요청 기간의 추가 관측값이 없습니다. 기존 그래프는 유지됩니다.")
    period_selection={"source":"text","requested":{"start":request["start"],"end":request["end"]},"applied":{"start":start,"end":end}}
    sessions=deepcopy(session["sessions"])
    for item in sessions:
        item.update(result=refreshed,period={"start":start,"end":end},periodSelection=period_selection)
    edit={"operation":"filter_period","kind":"DATA_EDIT","start":start,"end":end,"params":{},"value":None}
    output.update(editHistory=[*session["output"].get("editHistory",[]),edit][-120:],lastEdit=edit,
        editChanges=[f"조회 기간: {start} ~ {end} (기존 통계표·항목 유지, 원자료 재조회)"],
        editCapabilities=session["output"].get("editCapabilities",{}))
    warnings=[] if (start,end)==(request["start"],request["end"]) else [f"요청 기간 중 제공되는 {start} ~ {end}의 실제 관측값만 표시합니다."]
    return {"result":refreshed,"output":output,"sessions":sessions,"warnings":warnings,"only_period":request["only_period"]}
