"""Teammate marked-color behavior integrated with validated visual selections."""
import copy
import pytest
from chart_edit_agent import ChartEditAgent, explicit_color_change
from output_agent import OutputAgent


class NoModelCalls:
    model_name = "offline-color"
    supports_images = False
    def interpret(self, *_):
        pytest.fail("A standalone supported color edit must not require the provider")


def test_marked_color_changes_only_verified_segment_without_highlight_or_model():
    result = {"execution":{"rows":[{"_SERIES_LABEL":"경상수지","PRD_DE":period,"DT":str(value),
        "UNIT_NM":"백만달러","_FREQUENCY":"M"} for period,value in
        [("202501",10),("202502",12),("202503",11),("202504",14)]]}}
    saved = copy.deepcopy(result)
    output = OutputAgent()
    original = output.prepare(result,{"chart_type":"line"})
    editor = ChartEditAgent(NoModelCalls(),output)
    edited = editor.edit(result,original,"이 부분 그래프 색을 빨간색으로 바꿔줘",{
        "marks":[{"id":"pen-1","tool":"pen","points":[{"x":.2,"y":.2},{"x":.4,"y":.4}],
                  "text":"", "target":"경상수지",
                  "selection":{"label":"경상수지","scope":"segment","start":"202502","end":"202503"}}]})
    assert edited['chartState']['highlights'] == []
    rule = edited['chartState']['range_styles'][0]
    assert (rule['start'],rule['end'],rule['style']['color']) == ('202502','202503','#e53935')
    red = [trace for trace in edited['plotlyFigure']['data'] if trace.get('line',{}).get('color') == '#e53935']
    assert len(red) == 1 and red[0]['x'] == ['202502','202503']
    assert result == saved
    with pytest.raises(ValueError,match='표시'):
        editor.edit(result,original,"이 부분 그래프 색을 빨간색으로 바꿔줘")


@pytest.mark.parametrize('instruction',['빨간색으로 바꾸지 마','빨간색으로 바꾸고 제목도 변경해줘','빨간 점선으로 바꿔줘'])
def test_compound_negative_and_dash_requests_do_not_use_color_shortcut(instruction):
    assert explicit_color_change(instruction) is None
