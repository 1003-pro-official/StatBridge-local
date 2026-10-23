"""Keep visual edits distinct from edits of the current expression."""
import re
from chart_edit_period import period_redraw
from derived_indicator_planner import is_derived_request


def is_calculation_edit(instruction):
    visual = re.search(r'제목|색상|색|범례|글꼴|두께|강조|음영|주석|배경|격자', instruction)
    # Ignore quoted chart text when deciding whether an edit changes arithmetic.
    residual = re.sub(r""""[^"]*"|'[^']*'|「[^」]*」|“[^”]*”|‘[^’]*’""", '', instruction)
    # A follow-up can name the new expression without repeating "계산".
    # Route it to the existing DAG planner, never to a visual-only editor.
    symbol_math = not visual and re.search(
        r'(?:금리|환율|지수|지표|계열)\s*[−\-+×÷/]\s*.+?(?:금리|환율|지수|지표|계열)',residual)
    explicit_math = re.search(r'계산|기준연도|이동\s*평균|재지수|시차|역수|연산|분모|분자', residual)
    math_action = re.search(r'(?:변화율|증감률|비율|실질|전년|전월|차이|누적|나눠|곱해|더해).*(?:계산|바꿔|변경|적용|구해|만들)|(?:나눠|곱해|더해|차감)', residual)
    if visual and not explicit_math and not math_action:
        return False
    return bool(symbol_math or explicit_math or is_derived_request(instruction) or period_redraw(instruction) or re.search(
        r'(?:지표|항목|원자료|통계표|물가|금리|환율).*(?:추가|대체|교체|비교|대신)|'
        r'(?:추가|비교).*(?:지표|항목|물가|금리|환율)', instruction))
