"""The mixed selector sends existing, atomic commands; observations remain bound."""
import copy
import pytest
from output_agent import OutputAgent
from output_schema import ChartSpec,ChartEditCommand
from report_table import TableOptions
from report_export import document,restore_document,render_file


def fixture(two_units=False):
    return {'execution':{'rows':[{'PRD_DE':f'20240{month}','DT':str(1+i+month*.1),'_SERIES_LABEL':f'지표 {i+1}','UNIT_NM':'억원' if two_units and i==1 else '%','_FREQUENCY':'M'} for i in range(2) for month in range(1,4)]}}


@pytest.mark.parametrize('two_units',[False,True])
def test_selector_edit_restore_and_vector_exports(two_units):
    agent=OutputAgent();result=fixture(two_units);original=copy.deepcopy(result)
    before=agent.prepare(result,{'chart_type':'line','quick_output':True})
    commands=[ChartEditCommand(operation='set_chart_type',kind='STYLE_EDIT',value='line'),ChartEditCommand(operation='set_layout',kind='STYLE_EDIT',value='combined'),ChartEditCommand(operation='set_presentation',kind='STYLE_EDIT',params={'shared_y':False})]
    commands.append(ChartEditCommand(operation='set_report',kind='STYLE_EDIT',params={'patch':{'kind':'dual_axis','right_axis':['지표 2']}}) if two_units else ChartEditCommand(operation='set_series_chart_type',kind='STYLE_EDIT',label='지표 2',value='bar'))
    edited=agent.apply_edits(result,before,commands,generate_explanation=False)
    traces=edited['plotlyFigure']['data']
    assert [t['type'] for t in traces]==['scatter','bar']
    assert traces[0]['y']==[1.1,1.2,1.3] and traces[1]['y']==[2.1,2.2,2.3]
    spec=ChartSpec.model_validate(edited['chartState'])
    assert restore_document(result,document(result,spec))==spec
    data=agent._series(result['execution']['rows'])
    for format in ['svg','png','pdf']:
        content=render_file(data,spec,result,format)
        assert len(content)>1000
    if two_units:
        assert spec.secondary_axis_series==spec.report.right_axis==['지표 2']
        with pytest.raises(ValueError,match='right_axis'):
            render_file(data,spec.model_copy(update={'secondary_axis_series':['지표 1']}),result,'svg')
        for kind in ['line','bar']:
            plain=agent.apply_edits(result,edited,[ChartEditCommand(operation='set_chart_type',kind='STYLE_EDIT',value=kind)],generate_explanation=False)
            assert plain['chartState']['secondary_axis_series']==['지표 2']
            assert [t['type'] for t in plain['plotlyFigure']['data']]==(['scatter']*2 if kind=='line' else ['bar']*2)
    assert result==original


def test_pre_pack_table_document_restores_without_changing_observations():
    result=fixture();spec=ChartSpec(report_table=TableOptions(decimals=3))
    saved=document(result,spec)
    saved['state']['report_table'].pop('template')
    saved['state']['report_table'].pop('emphasized_labels')
    restored=restore_document(result,saved)
    assert restored.report_table.template=='default'
    assert restored.report_table.decimals==3
    saved['state']['report_table']['template']='invented'
    with pytest.raises(ValueError):restore_document(result,saved)


@pytest.mark.parametrize('shapes,stack',[
    (['line','bar'],False),(['line','area'],False),(['bar','area'],False),
    (['line','bar','area'],False),(['line','bar','bar'],True),
    (['area','bar','bar'],True),(['line','area','bar','bar'],True)])
def test_every_composition_survives_render_edit_restore_and_all_exports(shapes,stack,monkeypatch):
    from advanced_chart_render import report_style,echarts_report
    from advanced_chart_spec import ReportOptions
    import matplotlib.axes
    rows=[{'PRD_DE':f'20240{month}','DT':str(i+1+(month-2)*.2),'_SERIES_LABEL':f'항목 {i}','UNIT_NM':'%','_FREQUENCY':'M'} for i in range(len(shapes)) for month in range(1,4)]
    result={'execution':{'rows':rows}};original=copy.deepcopy(result);agent=OutputAgent()
    mapping={f'항목 {i}':kind for i,kind in enumerate(shapes)}
    spec=ChartSpec(chart_type='line',series_chart_types=mapping,presentation={'bar_mode':'relative' if stack else 'group'})
    before=agent._build(result,ChartSpec(),generate_explanation=False)
    bulk=ChartEditCommand(operation='set_series_chart_types',kind='STYLE_EDIT',params={'types':mapping})
    output=agent.apply_edits(result,before,[bulk],generate_explanation=False)
    figure=agent._build(result,spec,generate_explanation=False)['plotlyFigure']
    assert [t['type'] for t in figure['data']]==['bar' if s=='bar' else 'scatter' for s in shapes]
    assert [bool(t.get('fill')) for t in figure['data']]==[s=='area' for s in shapes]
    assert restore_document(result,document(result,spec))==spec
    reported=spec.model_copy(update={'report':ReportOptions(kind='forecast')})
    assert report_style(reported).series_chart_types==mapping
    data=agent._series(rows);echarts=echarts_report(data,reported,result)
    assert [bool(t.get('areaStyle')) for t in echarts['series']]==[s=='area' for s in shapes]
    bottoms=[];fills=[];original_bar=matplotlib.axes.Axes.bar;original_fill=matplotlib.axes.Axes.fill_between
    def bar(self,*args,**kwargs):
        if 'bottom' in kwargs:bottoms.append(list(kwargs['bottom']))
        return original_bar(self,*args,**kwargs)
    def fill(self,*args,**kwargs):
        fills.append(True);return original_fill(self,*args,**kwargs)
    monkeypatch.setattr(matplotlib.axes.Axes,'bar',bar);monkeypatch.setattr(matplotlib.axes.Axes,'fill_between',fill)
    for format in ['png','svg','pdf']:assert len(render_file(data,spec,result,format))>1000
    assert bool(fills)==('area' in shapes)
    if stack:assert any(any(value!=0 for value in base) for base in bottoms)
    if stack:
        ordinary=agent.apply_edits(result,agent._build(result,spec,generate_explanation=False),[ChartEditCommand(operation='set_chart_type',kind='STYLE_EDIT',value='bar')],generate_explanation=False)
        assert ordinary['plotlyFigure']['layout']['barmode']=='group'
    assert result==original


def test_bulk_mixed_style_rejects_unqueried_labels_and_unknown_shapes():
    agent=OutputAgent();result=fixture();output=agent.prepare(result,{'chart_type':'line','quick_output':True})
    for mapping in [{'없는 지표':'line'},{'지표 1':'pie'}]:
        with pytest.raises(ValueError):agent.apply_edits(result,output,[ChartEditCommand(operation='set_series_chart_types',kind='STYLE_EDIT',params={'types':mapping})],generate_explanation=False)


@pytest.mark.parametrize('shapes',[['line','area'],['bar','area'],['line','bar','area']])
def test_area_compositions_with_two_units_keep_axis_binding(shapes):
    from advanced_chart_spec import ReportOptions
    from advanced_chart_render import echarts_report
    rows=[{'PRD_DE':f'20240{month}','DT':str(i+1+month*.1),'_SERIES_LABEL':f'항목 {i}','UNIT_NM':'억원' if i==len(shapes)-1 else '%','_FREQUENCY':'M'} for i in range(len(shapes)) for month in range(1,4)]
    result={'execution':{'rows':rows}};agent=OutputAgent();right=f'항목 {len(shapes)-1}'
    spec=ChartSpec(chart_type=shapes[0],series_chart_types={f'항목 {i}':kind for i,kind in enumerate(shapes)},report=ReportOptions(kind='dual_axis',right_axis=[right]))
    output=agent._build(result,spec,generate_explanation=False)
    assert output['plotlyFigure']['data'][-1]['yaxis']=='y2'
    assert output['plotlyFigure']['data'][-1]['fill']=='tozeroy'
    data=agent._series(rows);ec=echarts_report(data,spec,result)
    assert ec['series'][-1]['type']=='line' and ec['series'][-1]['yAxisIndex']==1 and ec['series'][-1]['areaStyle']
    for format in ['svg','png','pdf']:assert len(render_file(data,spec,result,format))>1000


def test_scatter_regression_selector_uses_observed_pairs_only():
    result=fixture(two_units=True);original=copy.deepcopy(result);agent=OutputAgent()
    before=agent.prepare(result,{'chart_type':'line','quick_output':True})
    commands=[ChartEditCommand(operation='set_chart_type',kind='STYLE_EDIT',value='scatter'),ChartEditCommand(operation='set_layout',kind='STYLE_EDIT',value='combined'),ChartEditCommand(operation='set_presentation',kind='STYLE_EDIT',params={'shared_y':False}),ChartEditCommand(operation='set_report',kind='STYLE_EDIT',params={'patch':{'kind':'regression'}})]
    output=agent.apply_edits(result,before,commands,generate_explanation=False)
    assert [trace['mode'] for trace in output['plotlyFigure']['data']]==['markers','lines']
    spec=ChartSpec.model_validate(output['chartState']);assert restore_document(result,document(result,spec))==spec
    data=agent._series(result['execution']['rows'])
    for format in ['png','svg','pdf']:assert len(render_file(data,spec,result,format))>1000
    assert result==original


def test_stacked_mixed_latest_labels_use_bar_tops_but_display_original_values(monkeypatch):
    from plotly_renderer import render_plotly
    import matplotlib.axes
    rows=[{'PRD_DE':f'20240{month}','DT':str(i+1+month*.1),'_SERIES_LABEL':f'항목 {i}','UNIT_NM':'%','_FREQUENCY':'M'} for i in range(3) for month in range(1,4)]
    result={'execution':{'rows':rows}};data=OutputAgent()._series(rows)
    spec=ChartSpec(chart_type='line',series_chart_types={'항목 0':'line','항목 1':'bar','항목 2':'bar'},presentation={'design_template':'snapshot','bar_mode':'relative','latest_values':True,'number_decimals':2})
    figure=render_plotly(data,spec)
    annotations={a['name']:a for a in figure['layout']['annotations'] if str(a.get('name','')).startswith('statbridge-latest:')}
    last=annotations['statbridge-latest:항목 2'];assert last['y']==pytest.approx(5.6) and last['text']=='3.30'
    captured=[];original=matplotlib.axes.Axes.annotate
    def annotate(self,text,xy,*args,**kwargs):
        captured.append((text,xy));return original(self,text,xy,*args,**kwargs)
    monkeypatch.setattr(matplotlib.axes.Axes,'annotate',annotate)
    render_file(data,spec,result,'svg')
    assert any(text=='3.30' and xy[1]==pytest.approx(5.6) for text,xy in captured)
