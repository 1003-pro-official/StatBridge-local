"""Synthetic layout fixtures, never an external statistics accuracy score."""
import copy
import json
import pytest
from output_schema import ChartSpec, ChartEditCommand
from chart_designs import apply_design,materialize
from plotly_renderer import render_plotly
from report_export import document,restore_document,render_file,export_preflight


def series(count=3):
    return [{'id':str(i),'label':f'지표 {i+1}','color':'#4568ff','unit':'%','frequency':'M',
        'points':[{'date':f'{2020+m//12}{m%12+1:02d}','value':2+i*.003+m*.01} for m in range(72)]} for i in range(count)]


@pytest.mark.parametrize('count',range(1,11))
@pytest.mark.parametrize('layout',['combined','horizontal','separate','grid'])
def test_snapshot_keeps_all_observations_and_legible_dates(count,layout):
    data=series(count);original=copy.deepcopy(data)
    spec=materialize(apply_design(ChartSpec(chart_type='line',layout=layout),'snapshot'),[s['label'] for s in data])
    figure=render_plotly(data,spec)
    assert data==original
    assert len(figure['data'])==count
    for trace,item in zip(figure['data'],data):
        assert trace['y']==[p['value'] for p in item['points']]
        assert trace['x']==[p['date'] for p in item['points']]
        assert trace['mode']=='lines'
    latest=[a for a in figure['layout'].get('annotations',[]) if str(a.get('name','')).startswith('statbridge-latest:')]
    assert len(latest)==count
    assert len({a['yshift'] for a in latest})==count if layout=='combined' else True
    for name,axis in figure['layout'].items():
        if name.startswith('xaxis') and axis.get('visible') is not False:
            assert len(axis['ticktext'])<=8
            assert axis['ticktext'][0]=='2020-01'
            assert axis['ticktext'][-1]=='2025-12'
            assert axis['showgrid'] is False


def test_user_settings_win_and_latest_labels_can_be_disabled():
    spec=ChartSpec(chart_type='line',axes={'x':{'tick_step':12,'show_grid':True}},series_styles={'지표 1':{'markers':True,'color':'#ff0000'}},presentation={'latest_values':False})
    styled=apply_design(spec,'snapshot').model_copy(update={'presentation':apply_design(spec,'snapshot').presentation.model_copy(update={'latest_values':False})})
    figure=render_plotly(series(1),materialize(styled,['지표 1']))
    assert figure['layout']['xaxis']['showgrid'] is True
    assert figure['data'][0]['line']['color']=='#ff0000'
    assert 'markers' in figure['data'][0]['mode']
    assert not any(str(a.get('name','')).startswith('statbridge-latest:') for a in figure['layout'].get('annotations',[]))


def test_common_table_heading_keeps_distinct_legend_and_full_hover_identity():
    from snapshot_chart_style import legend_name
    data=series(2)
    for s in data:s['label']='예금은행 대출금리(신규취급액 기준) · '+s['label']
    spec=materialize(apply_design(ChartSpec(chart_type='line'),'snapshot'),[s['label'] for s in data])
    figure=render_plotly(data,spec)
    assert [t['name'] for t in figure['data']]==['지표 1','지표 2']
    assert [t['meta']['seriesLabel'] for t in figure['data']]==[s['label'] for s in data]
    spec=spec.model_copy(update={'display_names':{data[0]['label']:'사용자 이름'}})
    assert legend_name(data[0],data,spec)=='사용자 이름'


def test_old_report_json_restores_without_new_label_field():
    from output_agent import OutputAgent
    result={'execution':{'rows':[{'PRD_DE':'202401','DT':'3.25','ITM_NM':'검증','UNIT_NM':'%'}]}}
    spec=ChartSpec(chart_type='line')
    saved=document(result,spec)
    for p in (saved['state']['presentation'],saved['typography']):p.pop('latest_values')
    restored=restore_document(result,saved)
    assert restored.presentation.latest_values is False
    output=OutputAgent().prepare(result,{'chart_type':'line','quick_output':True})
    assert output['chartState']['presentation']['design_template']=='snapshot'
    assert output['plotlyFigure']['data'][0]['y']==[3.25]


def test_mixed_axis_vector_export_keeps_current_labels_and_values():
    data=series(3)
    data[2]['unit']='%p'
    spec=materialize(apply_design(ChartSpec(chart_type='line',secondary_axis_series=['지표 3'],series_chart_types={'지표 3':'bar'}),'snapshot'),[s['label'] for s in data])
    original=copy.deepcopy(data)
    normalized,legacy,periods,colors=export_preflight(data,spec,{},'svg')
    assert normalized.report.kind=='dual_axis' and normalized.report.right_axis==['지표 3']
    assert data==original
    content=render_file(data,spec,{},'svg')
    assert b'<svg' in content
    assert data==original
    figure=render_plotly(data,spec)
    assert [t['type'] for t in figure['data']]==['scatter','scatter','bar']
    assert figure['data'][2]['yaxis']=='y2'
    assert figure['data'][2]['y']==[p['value'] for p in data[2]['points']]


def test_right_axis_line_stays_a_line_in_vector_export():
    data=series(2)
    spec=materialize(apply_design(ChartSpec(chart_type='line',secondary_axis_series=['지표 2']),'snapshot'),[s['label'] for s in data])
    normalized,_,_,_=export_preflight(data,spec,{},'svg')
    assert normalized.series_chart_types['지표 2']=='line'
    assert b'<svg' in render_file(data,spec,{},'svg')


def test_panel_export_uses_chosen_columns_and_grows_with_rows():
    for count in (3,10):
        data=series(count)
        spec=apply_design(ChartSpec(chart_type='line',layout='horizontal'),'snapshot')
        normalized,_,_,_=export_preflight(data,spec,{},'svg')
        assert normalized.report.columns==min(4,count)
        assert normalized.report.height>=((count+3)//4)*320+280
