"""Report charts use supplied observations and explicit metadata, never pseudo-gold."""
import copy
import io
import json
import pytest

from output_schema import ChartSpec,ChartEditCommand
from output_agent import OutputAgent
from advanced_chart_spec import ReportOptions,TEMPLATES,validate_report
from advanced_chart_render import echarts_report,regression
from report_export import document,restore_document,migrate_legacy,render_file


def fixture(count=2):
    dates=['202001','202002','202003','202004','202101','202102','202103','202104']
    labels=['한국','미국','크기'][:count]
    rows=[{'PRD_DE':d,'DT':str(10+i*2+j*j*.3),'ITM_NM':label,'UNIT_NM':'%',
           '_SOURCE_SERIES_ID':'DT_TEST','_FREQUENCY':'Q'} for i,label in enumerate(labels) for j,d in enumerate(dates)]
    return {'api_plan':{'table_id':'DT_TEST','table_name':'합성 검증 자료','org_id':'301','item_id':'ITEM','frequency':'Q','start_period':dates[0],'end_period':dates[-1]},
        'execution':{'status':'success','rows':rows,'sources':[{'table_id':'DT_TEST','source':'synthetic fixture','row_count':len(rows)}]}}


def test_mixed_frequency_panels_keep_their_own_period_labels():
    data=fixture()
    for row in data['execution']['rows']:
        if row['ITM_NM']=='미국':row['_FREQUENCY']='M'
    series=OutputAgent()._series(data['execution']['rows'])
    result=echarts_report(series,ChartSpec(report=ReportOptions(kind='panels')),data)
    assert result['xAxis'][0]['reportPeriodLabels']['202002']=='2020Q2'
    assert result['xAxis'][1]['reportPeriodLabels']['202002']=='2020-02'


def options(kind):
    params={'kind':kind,'template':next(k for k,v in TEMPLATES.items() if v['kind']==kind)}
    if kind=='dual_axis':params['right_axis']=['미국']
    if kind=='contribution':params['contribution_confirmed']=True
    if kind=='fan':
        source=OutputAgent()._series(fixture()['execution']['rows'])
        params['intervals']=[{'label':'한국','level':.68,'periods':[p['date'] for p in source[0]['points']],
            'lower':[p['value']-1 for p in source[0]['points']], 'upper':[p['value']+1 for p in source[0]['points']],
            'method':'synthetic supplied bounds','source':'test fixture'}]
    return ReportOptions(**params)


@pytest.mark.parametrize('kind',['forecast','dual_axis','contribution','panels','events','fan','waterfall','regression'])
def test_required_eight_types_preserve_values_and_have_three_renderers(kind):
    data=fixture(1 if kind=='waterfall' else 2);before=copy.deepcopy(data)
    if kind=='dual_axis':
        for row in data['execution']['rows']:
            if row['ITM_NM']=='미국':row['UNIT_NM']='조원'
        before=copy.deepcopy(data)
    spec=ChartSpec(title='보고서 차트 검증',report=options(kind))
    result=OutputAgent()._build(data,spec,generate_explanation=False)
    series=result['visualization']['series']
    assert result['plotlyFigure']['data']
    if kind=='forecast':
        assert result['plotlyFigure']['layout']['xaxis']['tickvals']==['period:'+d for d in ['202001','202002','202003','202004','202101','202102','202103','202104']]
        assert len(set(result['plotlyFigure']['layout']['xaxis']['ticktext']))==8
    assert result['echartsOption']['series']
    assert data==before
    assert result['table']['rows']
    svg=render_file(series,spec,data,'svg')
    assert b'<svg' in svg and '보고서 차트 검증'.encode() in svg
    doc=result['reportDocument']
    assert restore_document(data,json.loads(json.dumps(doc,ensure_ascii=False))).model_dump()==spec.model_dump()


@pytest.mark.parametrize('format',['png','svg','pdf'])
def test_binary_export_has_real_format_and_korean_text(format):
    from PIL import Image
    from pypdf import PdfReader
    data=fixture();spec=ChartSpec(title='소비자물가 추이',report=ReportOptions(footnotes=['주: 합성 검증 자료']))
    series=OutputAgent()._series(data['execution']['rows'])
    content=render_file(series,spec,data,format)
    if format=='png':assert Image.open(io.BytesIO(content)).size==(2400,1440)
    if format=='svg':assert b'<path' in content and '소비자물가'.encode() in content
    if format=='pdf':
        reader=PdfReader(io.BytesIO(content));text=reader.pages[0].extract_text()
        assert '소비자물가' in text and 'DT_TEST' in text


def test_bad_data_and_metadata_fail_without_fallback():
    series=OutputAgent()._series(fixture()['execution']['rows'])
    for report in [ReportOptions(kind='fan'),ReportOptions(kind='contribution'),ReportOptions(kind='network'),ReportOptions(forecast_start='209901')]:
        with pytest.raises(ValueError):validate_report(series,report)
    changed=copy.deepcopy(series);changed[1]['unit']='조원'
    with pytest.raises(ValueError):validate_report(changed,ReportOptions(kind='contribution',contribution_confirmed=True))
    with pytest.raises(ValueError):ReportOptions(template='invented')


def test_repeated_edit_keeps_report_and_stickers():
    data=fixture();output=OutputAgent();spec=ChartSpec(title='기존',report=options('panels'))
    initial=output._build(data,spec,generate_explanation=False)
    edited=output.apply_edits(data,initial,[ChartEditCommand(operation='set_report',kind='STYLE_EDIT',params={'patch':{'source_note':'사용자 추가 설명'}}),
        ChartEditCommand(operation='set_title',kind='STYLE_EDIT',value='변경 제목')],generate_explanation=False)
    assert edited['chartState']['report']['kind']=='panels'
    assert edited['chartState']['report']['source_note']=='사용자 추가 설명'
    assert edited['table']==initial['table']
    broken=copy.deepcopy(edited['reportDocument']);broken['series'][0]['points'][0]['value']=999
    with pytest.raises(ValueError):restore_document(data,broken)
    other=fixture();other['execution']['rows'][0]['DT']='99'
    with pytest.raises(ValueError):restore_document(other,edited['reportDocument'])
    assert migrate_legacy(data,{'title':'legacy'})['state']['report'] is None
    ordinary=output.apply_edits(data,edited,[ChartEditCommand(operation='set_chart_type',kind='STYLE_EDIT',value='bar')],generate_explanation=False)
    assert ordinary['chartState']['report'] is None
    assert all(t['type']=='bar' for t in ordinary['plotlyFigure']['data'])


def test_intervals_are_supplied_nested_and_regression_is_reproducible():
    series=OutputAgent()._series(fixture()['execution']['rows'])
    fit=regression(series)
    assert fit['n']==8 and abs(fit['slope']-1)<1e-10 and abs(fit['intercept']-2)<1e-10
    bad=options('fan').model_dump();bad['intervals'][0]['lower'][0]=999
    with pytest.raises(ValueError):ReportOptions.model_validate(bad)
    outer=options('fan').intervals[0].model_copy(update={'level':.9,'lower':[p['value']-.5 for p in series[0]['points']]})
    with pytest.raises(ValueError):validate_report(series,ReportOptions(kind='fan',intervals=[options('fan').intervals[0],outer]))


def test_http_report_edit_export_restore_and_undo(monkeypatch):
    import bridge_api as api
    from authenticated_client import TestClient
    from test_chart_edit_period_and_box import fixture_session
    output,session=fixture_session()
    monkeypatch.setattr(api.agent,'output_agent',output)
    monkeypatch.setattr(api,'_table_card',lambda tid:{'tableId':tid})
    monkeypatch.setitem(api.EDIT_SESSIONS,'report-http',session)
    client=TestClient(api.app)
    request={'edit_session_id':'report-http','revision':0,'report':{'template':'economic_outlook','kind':'forecast'}}
    response=client.post('/api/output/edit',json=request)
    assert response.status_code==200,response.text
    assert len(client.get('/api/report/templates').json()['templates'])>=10
    response=client.post('/api/report/export',json={'edit_session_id':'report-http','format':'json','revision':1})
    assert response.status_code==200,response.text
    saved=response.json()
    assert client.post('/api/report/export',json={'edit_session_id':'report-http','format':'json','revision':0}).status_code==409
    recommendation=client.post('/api/report/recommend',json={'edit_session_id':'report-http','format':'json','revision':1})
    assert recommendation.status_code==200 and recommendation.json()['reasons']
    undo=client.post('/api/output/edit',json={'edit_session_id':'report-http','action':'undo','revision':1})
    assert undo.status_code==200 and undo.json()['outputSpec']['chartState']['report'] is None
    restored=client.post('/api/output/edit',json={'edit_session_id':'report-http','document':saved,'revision':2})
    assert restored.status_code==200,restored.text
    assert restored.json()['outputSpec']['chartState']['report']['kind']=='forecast'
    saved['dataset_version']='forged'
    assert client.post('/api/output/edit',json={'edit_session_id':'report-http','document':saved,'revision':3}).status_code==422


def test_recommendation_does_not_invent_forecasts_or_force_dual_axes():
    from advanced_chart_spec import recommend_report
    series=OutputAgent()._series(fixture()['execution']['rows'])
    series[1]['unit']='조원'
    recommended=recommend_report(series,[])
    assert recommended['options']['kind']=='panels'
    assert recommended['options']['forecast_start'] is None
    assert not recommended['options']['intervals']


@pytest.mark.parametrize('frequency,dates',[
    ('Q',['202001','202004','202101','202104']),
    ('M',['202001','202003','202101','202103']),
    ('A',['2018','2019','2020','2022']),
    ('Q',['2020Q1','2020Q4','2021Q1','2021Q4']),
])
def test_year_over_year_uses_calendar_period_not_observation_offset(frequency,dates):
    from chart_data_transforms import year_over_year
    points=[{'date':date,'value':value} for date,value in zip(dates,[10,20,15,30])]
    before=copy.deepcopy(points);transformed=year_over_year(points,frequency)
    if frequency=='A':
        assert [p['date'] for p in transformed]==['2019','2020']
    else:
        assert [p['value'] for p in transformed]==[50,50]
    assert points==before
