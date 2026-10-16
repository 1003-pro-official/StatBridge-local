"""Axis-title control contract through output rendering and export SVG."""
import copy
from output_agent import OutputAgent
from output_schema import ChartEditCommand, ChartSpec
from report_export import render_file
from test_research_chart_edit import source


def test_axis_title_edit_preserves_observations_and_renders_svg():
    agent=OutputAgent();data=source(2);original=copy.deepcopy(data)
    initial=agent.prepare(data,{'chart_type':'line'})
    edited=agent.apply_edits(data,initial,[ChartEditCommand(operation='set_axis_labels',kind='STYLE_EDIT',x_axis_label='조회 기간(월)',y_axis_label='비중(%)')],generate_explanation=False)
    assert edited['plotlyFigure']['layout']['xaxis']['title']['text']=='조회 기간(월)'
    assert edited['plotlyFigure']['layout']['yaxis']['title']['text']=='비중(%)'
    assert data==original
    assert edited['chartState']['x_axis_label']=='조회 기간(월)'
    assert any('조회 기간(월)' in x for x in edited['editChanges'])
    svg=render_file(agent._series(data['execution']['rows']),ChartSpec.model_validate(edited['chartState']),data,'svg').decode('utf8')
    assert '조회 기간(월)' in svg and '비중(%)' in svg
    restored=agent.apply_edits(data,edited,[ChartEditCommand(operation='set_axis_labels',kind='STYLE_EDIT',x_axis_label='',y_axis_label='')],generate_explanation=False)
    assert restored['chartState']['x_axis_label']==restored['chartState']['y_axis_label']==''
    assert restored['plotlyFigure']['layout']['xaxis']['title']['text']==initial['plotlyFigure']['layout']['xaxis']['title']['text']
    assert restored['plotlyFigure']['layout']['yaxis']['title']['text']==initial['plotlyFigure']['layout']['yaxis']['title']['text']
