"""Follow-up arithmetic routing and actionable missing-window diagnostics."""
import pytest
from derived_intent_router import is_calculation_edit
from dynamic_expression_executor import DynamicExpressionExecutor,Series
from expression_tree_schema import ExpressionPlan
from expression_tree_validator import DerivedValidationError


def test_subtraction_order_followup_reaches_calculation_planner():
    assert is_calculation_edit('같은 기간과 계열을 유지하고 반대로 예금은행 저축성수신(금융채 제외) 신규취급액 금리−예금은행 가계대출 신규취급액 금리로 바꿔줘.')


@pytest.mark.parametrize('text',[
    '제목을 ‘수신금리−대출금리’로 바꿔줘.',
    '제목을 “금리 비교”로 바꿔줘.',
    '수신금리 선 색상을 빨간색으로 바꿔줘.',
])
def test_chart_text_and_style_do_not_reach_calculation_planner(text):
    assert not is_calculation_edit(text)


def mean_plan():
    return ExpressionPlan.model_validate({'plan_version':'1.0','indicator_name':'월간 평균',
        'economic_definition':'4월과 이전 두 달 공표값의 산술평균',
        'sources':[{'alias':'a','table_id':'DT_121Y002','item_id':'13103134588999',
                    'classifications':{'objL1':'13102134588ACC_ITEM.BEABAA1'},'frequency':'M','required_data':'수신금리'}],
        'nodes':[{'id':'mean','operator':'rolling_mean','inputs':['a'],'window':3}],
        'outputs':[{'node':'mean','label':'3개월 평균'}],'start_period':'202504','end_period':'202504'})


def test_missing_middle_month_is_named_and_not_filled():
    data={'a':Series({'202502':2.97,'202504':2.72},'연리%','M',['a'])}
    with pytest.raises(DerivedValidationError,match='202503'):
        DynamicExpressionExecutor().execute(mean_plan(),data)
    assert data['a'].values=={'202502':2.97,'202504':2.72}


def test_complete_window_still_produces_only_requested_month():
    data={'a':Series({'202502':2.97,'202503':2.83,'202504':2.72},'연리%','M',['a'])}
    rows=DynamicExpressionExecutor().execute(mean_plan(),data)['rows']
    assert len(rows)==1 and rows[0]['PRD_DE']=='202504'
    assert rows[0]['DT']==pytest.approx(2.84)
