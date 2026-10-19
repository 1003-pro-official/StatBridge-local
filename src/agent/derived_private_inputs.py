"""Reject private business data outside supported public statistics."""
import re
from expression_tree_validator import DerivedValidationError


def private_metric(query):
    owner = r"(?:우리\s*(?:회사|기업|가게|사업장)|자사|당사|사내|회사\s*내부|개인|특정\s*(?:회사|기업)|내\s*(?:회사|가게|사업장))"
    metrics = r"원재료\s*(?:구매)?\s*비용|구매\s*비용|매입\s*(?:비용|금액)|매출(?:액)?|인건비|급여|원가|재고|판매량|생산량|구매액|판매액|영업이익"
    match = re.search(owner + r"[^.!?\n]{0,50}?(" + metrics + r")", query)
    if not match:
        match = re.search("(" + metrics + r")\s*[（(]" + owner + r"[）)]", query)
    if not match:
        return None
    # An explicitly excluded private input is not a required operand.
    if re.search(owner + r"(?:의\s*)?\s*(?:" + metrics + r")(?:\s*자료)?\s*(?:은|는|을|를)?\s*(?:제외하고|사용하지\s*말고)", query):
        return None
    return re.sub(r"\s+", "", match.group(1))


def require_private_input(query, plan, catalog):
    metric = private_metric(query)
    if not metric:
        return
    raise DerivedValidationError("회사·개인 원자료를 사용하는 계산은 지원하지 않습니다. KOSIS 제공 자료를 사용하는 질문으로 다시 작성해 주세요.", failure_kind="unsupported_request")
