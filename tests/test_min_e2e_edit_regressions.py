"""Behavioral regressions found by the public min-e2e actual-model run."""
import copy
import pytest
from output_agent import OutputAgent
from output_schema import ChartSpec,ChartEditCommand
from workspace_text_edits import simple_workspace_commands
from test_output_agent_migration import fixture_result


@pytest.mark.parametrize('opening,closing',[('‘','’'),('“','”'),("'","'"),('"','"')])
def test_title_delimiters_are_not_saved_as_content(opening,closing):
    spec=ChartSpec(title='기존 제목')
    commands=simple_workspace_commands(f'제목을 {opening}상반기 금리 비교{closing}로 바꿔줘.',spec,[])
    assert len(commands)==1 and commands[0].operation=='set_title'
    assert commands[0].value=='상반기 금리 비교'


def test_title_font_size_edit_preserves_text_and_other_presentation():
    agent=OutputAgent();data=fixture_result();spec=ChartSpec(chart_type='line',title='상반기 금리 비교')
    initial=agent._build(data,spec,generate_explanation=False)
    commands=simple_workspace_commands('제목 크기도 24로 해줘.',spec,[])
    assert commands and all(c.operation!='set_title' for c in commands)
    revised=agent.apply_edits(data,initial,commands,generate_explanation=False)
    expected=copy.deepcopy(initial['chartState']);expected['presentation']['title_size']=24
    assert revised['chartState']==expected
    assert revised['plotlyFigure']['layout']['title']['font']['size']==24


@pytest.mark.parametrize('text',['제목 색을 파란색으로 바꿔줘.','제목 위치를 가운데로 바꿔줘.','제목색을 파란색으로 바꿔줘.'])
def test_title_attribute_requests_do_not_become_title_content(text):
    commands=simple_workspace_commands(text,ChartSpec(title='금리 비교'),[])
    assert commands is None or all(c.operation!='set_title' for c in commands)


def test_bar_conversion_retains_neutral_solid_style_and_source_values():
    agent=OutputAgent();data=fixture_result(2);before=copy.deepcopy(data)
    initial=agent._build(data,ChartSpec(chart_type='line'),generate_explanation=False)
    label=agent._series(data['execution']['rows'])[0]['label']
    styled=agent.apply_edits(data,initial,[ChartEditCommand(operation='set_series_style',kind='STYLE_EDIT',label=label,
        params={'color':'#2563eb','dash':'solid','width':2})],generate_explanation=False)
    converted=agent.apply_edits(data,styled,[ChartEditCommand(operation='set_series_chart_type',kind='STYLE_EDIT',label=label,value='bar')],generate_explanation=False)
    assert converted['chartState']['series_styles'][label]['dash']=='solid'
    assert any(t['type']=='bar' for t in converted['plotlyFigure']['data'])
    assert data==before
    assert converted['table']==styled['table']


def test_bar_still_rejects_non_solid_dash_request():
    agent=OutputAgent();data=fixture_result();initial=agent._build(data,ChartSpec(chart_type='bar'),generate_explanation=False)
    label=agent._series(data['execution']['rows'])[0]['label']
    with pytest.raises(ValueError,match='막대'):
        agent.apply_edits(data,initial,[ChartEditCommand(operation='set_series_style',kind='STYLE_EDIT',label=label,params={'dash':'dash'})],generate_explanation=False)


def test_show_and_move_hidden_legend_completes_partial_model_plan():
    from chart_edit_agent import ChartEditAgent
    from test_chart_edit_agent import FakeEditModel
    agent=OutputAgent();data=fixture_result()
    initial=agent._build(data,ChartSpec(show_legend=False),generate_explanation=False)
    editor=ChartEditAgent(FakeEditModel({'commands':[{'operation':'set_legend','value':'bottom'}]}),agent)
    revised=editor.edit(data,initial,'다시 보여주고 아래에 배치해줘.')
    assert revised['chartState']['show_legend'] is True
    assert revised['chartState']['legend_position']=='bottom'
    assert revised['table']==initial['table']
    assert initial['chartState']['show_legend'] is False


@pytest.mark.parametrize('text',['범례는 숨긴 채 아래로 옮겨줘.','범례를 아래로 내려줘.',"제목을 ‘다시 보여주고’로 바꾸고 범례를 아래로 옮겨줘."])
def test_placement_alone_does_not_unhide_legend(text):
    from chart_edit_intents import complete_legend_visibility
    commands=[ChartEditCommand(operation='set_legend',kind='STYLE_EDIT',value='bottom')]
    assert complete_legend_visibility(text,commands)==commands
