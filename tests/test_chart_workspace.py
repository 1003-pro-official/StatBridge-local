"""Shared current-state edits and presentation/data boundaries."""
import copy
import json
import pytest
from output_agent import OutputAgent
from output_schema import ChartSpec,ChartEditCommand
from advanced_chart_spec import ReportOptions,fingerprint
from chart_designs import DESIGNS
from report_export import document,restore_document
from test_advanced_reports import fixture

def edit(agent,data,output,op,value=None,**kwargs):
    return agent.apply_edits(data,output,[ChartEditCommand(operation=op,kind='STYLE_EDIT',value=value,**kwargs)],generate_explanation=False)

def test_six_designs_change_rendered_properties_without_changing_values():
    agent=OutputAgent();data=fixture();before=copy.deepcopy(data)
    current=agent._build(data,ChartSpec(title='유지할 제목',report=ReportOptions()),generate_explanation=False)
    signatures=[]
    for key in DESIGNS:
        current=edit(agent,data,current,'set_presentation',params={'design_template':key})
        f=current['plotlyFigure'];signatures.append((f['layout']['font']['size'],f['data'][0]['line']['color'],f['data'][0]['line']['width'],f['layout']['xaxis'].get('gridcolor')))
        assert current['chartState']['title']=='유지할 제목'
        assert current['table']['rows']==agent._table(agent._series(data['execution']['rows']))['rows']
    assert len(set(signatures))==6 and data==before

def test_markers_can_be_disabled_and_remain_off_after_design_change():
    agent=OutputAgent();data=fixture()
    current=agent._build(data,ChartSpec(report=ReportOptions()),generate_explanation=False)
    before=copy.deepcopy(current['table']['rows'])
    current=edit(agent,data,current,'set_series_style',label='한국',params={'markers':False,'width':2.5,'dash':'solid'})
    current=edit(agent,data,current,'set_presentation',params={'design_template':'explore'})
    assert current['chartState']['series_styles']['한국']['markers'] is False
    trace=next(t for t in current['plotlyFigure']['data'] if t.get('name')=='한국')
    assert 'markers' not in trace.get('mode','') or trace['marker']['size']==0 or all(n==0 for n in trace['marker']['size'])
    assert current['table']['rows']==before

def test_ten_sequential_edits_preserve_current_state_and_json_restore():
    agent=OutputAgent();data=fixture();output=agent._build(data,ChartSpec(report=ReportOptions()),generate_explanation=False)
    initial_values=copy.deepcopy(output['table']['rows']);history=[]
    actions=[('set_title','지속 편집',{}),('set_series_color','#111111',{'label':'한국'}),
      ('highlight_period',None,{'start':'202101','end':'202104','params':{'color':'#aabbcc','opacity':.2}}),
      ('add_guide',None,{'params':{'value':15,'text':'기준선'}}),('set_legend','bottom',{}),
      ('set_presentation',None,{'params':{'design_template':'slides'}}),('add_note',None,{'params':{'text':'주석','x':.5,'y':.8}}),
      ('set_series_style',None,{'label':'한국','params':{'width':5}}),('set_axis_style',None,{'label':'x','params':{'show_grid':False}}),('set_subtitle','반복 수정 결과',{})]
    for op,value,kw in actions:
        history.append(copy.deepcopy(output));output=edit(agent,data,output,op,value,**kw)
        assert output['table']['rows']==initial_values
    state=output['chartState'];assert state['title']=='지속 편집' and state['series_colors']['한국']=='#111111'
    assert state['highlights'] and state['guides'] and state['notes'] and state['subtitle']=='반복 수정 결과'
    restored=restore_document(data,json.loads(json.dumps(document(data,ChartSpec.model_validate(state)),ensure_ascii=False)))
    again=agent._build(data,restored,generate_explanation=False)
    again=edit(agent,data,again,'set_title','저장 후 재편집')
    assert again['chartState']['highlights']==state['highlights'] and again['table']['rows']==initial_values

def test_design_rejects_unknown_names_atomically():
    agent=OutputAgent();data=fixture();output=agent._build(data,ChartSpec(),generate_explanation=False)
    before=copy.deepcopy(output)
    with pytest.raises(ValueError):edit(agent,data,output,'set_presentation',params={'design_template':'made_up'})
    assert output==before

def test_latest_color_edit_overrides_old_series_style_and_matches_legend():
    agent=OutputAgent();data=fixture();output=agent._build(data,ChartSpec(),generate_explanation=False)
    output=edit(agent,data,output,'set_series_style',label='한국',params={'color':'#112233','width':4})
    assert output['visualization']['series'][0]['color']=='#112233'
    output=edit(agent,data,output,'set_series_color','#334455',label='한국')
    assert output['plotlyFigure']['data'][0]['line']['color']=='#334455'
    assert output['visualization']['series'][0]['color']=='#334455'
    assert output['chartState']['series_styles']['한국']['width']==4

def test_explicit_same_width_override_and_export_dpi_are_valid_state_changes():
    agent=OutputAgent();data=fixture();output=agent._build(data,ChartSpec(report=ReportOptions()),generate_explanation=False)
    changed=edit(agent,data,output,'set_series_style',label='한국',params={'width':3})
    assert changed['chartState']['series_styles']['한국']['width']==3
    changed=edit(agent,data,changed,'set_report',params={'patch':{'dpi':300}})
    assert changed['chartState']['report']['dpi']==300 and changed['stateOnlyChange'] is True
    with pytest.raises(ValueError,match='변경된 내용이 없습니다'):edit(agent,data,changed,'set_title',changed['chartState']['title'])

def test_grid_disable_survives_matplotlib_export(monkeypatch):
    from matplotlib.figure import Figure
    from report_export import render_file
    observed=[];original=Figure.savefig
    def save(self,*args,**kwargs):
        observed.append([line.get_visible() for line in self.axes[0].get_xgridlines()])
        return original(self,*args,**kwargs)
    monkeypatch.setattr(Figure,'savefig',save)
    spec=ChartSpec(report=ReportOptions(),axes={'x':{'show_grid':False}})
    data=fixture();blob=render_file(OutputAgent()._series(data['execution']['rows']),spec,data,'svg')
    assert b'<svg' in blob and observed and not any(observed[0])

def test_old_optional_design_field_migrates_without_altering_data():
    data=fixture();spec=ChartSpec(report=ReportOptions());doc=document(data,spec)
    del doc['typography']['design_template'];del doc['state']['presentation']['design_template']
    restored=restore_document(data,doc)
    assert restored==spec

def test_workspace_http_specific_undo_and_live_read(monkeypatch):
    from authenticated_client import TestClient
    import bridge_api as api
    from test_chart_edit_period_and_box import fixture_session
    _,session=fixture_session();session['result']=fixture();session['output']=OutputAgent()._build(fixture(),ChartSpec(),generate_explanation=False)
    monkeypatch.setattr(api,'_table_card',lambda t:{'tableId':t})
    monkeypatch.setitem(api.EDIT_SESSIONS,'workspace-test',session)
    client=TestClient(api.app)
    def post(**fields):
        r=client.post('/api/output/edit',json={'edit_session_id':'workspace-test',**fields});assert r.status_code==200,r.text;return r.json()
    post(commands=[{'operation':'set_title','kind':'STYLE_EDIT','value':'먼저 제목'}])
    post(commands=[{'operation':'set_series_color','kind':'STYLE_EDIT','label':'한국','value':'#112233'}])
    restored=post(undo_property='title')
    assert restored['outputSpec']['chartState']['title']==''
    assert restored['outputSpec']['chartState']['series_colors']['한국']=='#112233'
    read=client.get('/api/workspace/workspace-test').json()
    assert read['outputSpec']['editVersion']==3 and read['outputSpec']['chartState']==restored['outputSpec']['chartState']
    undo=post(action='undo');assert undo['outputSpec']['chartState']['title']=='먼저 제목'
    initial=post(restore_initial=True)
    assert initial['outputSpec']['chartState']['series_colors']=={}
    assert client.post('/api/output/edit',json={'edit_session_id':'workspace-test','revision':0,'restore_initial':True}).status_code==409

def test_workspace_data_append_replace_and_undo_preserve_provenance(monkeypatch):
    from authenticated_client import TestClient
    import bridge_api as api
    from test_chart_edit_period_and_box import fixture_session
    _,session=fixture_session();original=fixture(1);session['result']=original
    session['sessions'][0]['result']=original;session['output']=OutputAgent()._build(original,ChartSpec(title='사용자 제목'),generate_explanation=False)
    incoming=fixture(1)
    for row in incoming['execution']['rows']:row['ITM_NM']='추가 항목';row['UNIT_NM']='조원';row['_SOURCE_SERIES_ID']='DT_NEW'
    incoming['api_plan']['table_id']='DT_NEW';incoming['execution']['sources'][0]['table_id']='DT_NEW'
    added={**session['sessions'][0],'query':'추가 통계','result':incoming}
    monkeypatch.setitem(api.EDIT_SESSIONS,'workspace-data',session);monkeypatch.setitem(api.OUTPUT_SESSIONS,'new-data',added)
    monkeypatch.setattr(api.agent,'validate_resolution',lambda *a,**k:{'status':'resolved'})
    monkeypatch.setattr(api,'_table_card',lambda t:{'tableId':t})
    client=TestClient(api.app)
    r=client.post('/api/output/edit',json={'edit_session_id':'workspace-data','append_session_ids':['new-data']});assert r.status_code==200,r.text
    assert r.json()['seriesCount']==2 and r.json()['chartMode']=='grid'
    assert {t['tableId'] for t in r.json()['tables']}=={'DT_TEST','DT_NEW'}
    replaced=client.post('/api/output/edit',json={'edit_session_id':'workspace-data','replace_session_ids':['new-data']});assert replaced.status_code==200,replaced.text
    assert replaced.json()['seriesCount']==1 and replaced.json()['outputSpec']['chartState']['title']=='사용자 제목'
    undo=client.post('/api/output/edit',json={'edit_session_id':'workspace-data','action':'undo'});assert undo.status_code==200 and undo.json()['seriesCount']==2
    assert session['result']['execution']['rows'][:len(original['execution']['rows'])]==original['execution']['rows']

def test_saved_workspace_survives_memory_reset_and_rejects_corruption(monkeypatch,tmp_path):
    from authenticated_client import TestClient
    import bridge_api as api
    from test_chart_edit_period_and_box import fixture_session
    import gzip
    _,session=fixture_session();session['result']=fixture();session['output']=OutputAgent()._build(fixture(),ChartSpec(title='저장할 그래프'),generate_explanation=False)
    monkeypatch.setattr(api,'_saved_workspace_path',lambda identifier:tmp_path/(identifier+'.json.gz'))
    monkeypatch.setattr(api,'_table_card',lambda t:{'tableId':t});monkeypatch.setitem(api.EDIT_SESSIONS,'saved-workspace',session)
    client=TestClient(api.app)
    saved=client.post('/api/workspace/saved-workspace/save',json={'edit_session_id':'saved-workspace','format':'json','revision':0});assert saved.status_code==200,saved.text
    monkeypatch.delitem(api.EDIT_SESSIONS,'saved-workspace')
    restored=client.get('/api/workspace/saved-workspace');assert restored.status_code==200,restored.text
    assert restored.json()['outputSpec']['chartState']['title']=='저장할 그래프' and restored.json()['outputSpec']['cachedSnapshot'] is True
    edited=client.post('/api/output/edit',json={'edit_session_id':'saved-workspace','commands':[{'operation':'set_title','kind':'STYLE_EDIT','value':'재편집 성공'}]});assert edited.status_code==200
    path=tmp_path/'saved-workspace.json.gz'
    with gzip.open(path,'rt',encoding='utf-8') as stream:payload=json.load(stream)
    payload['session']['result']['execution']['rows'][0]['DT']='99999'
    with gzip.open(path,'wt',encoding='utf-8') as stream:json.dump(payload,stream,ensure_ascii=False)
    monkeypatch.delitem(api.EDIT_SESSIONS,'saved-workspace')
    assert client.get('/api/workspace/saved-workspace').status_code==422

def test_edit_provider_retries_only_transient_errors(monkeypatch):
    from chart_edit_agent import Hcx007EditModel
    from ncp_clova_client import NcpClovaClient,NcpSettings
    import time
    model=Hcx007EditModel(NcpClovaClient(NcpSettings(api_key='test-only-placeholder')))
    attempts=[];sleeps=[]
    def request(*a,**k):
        attempts.append(1)
        if len(attempts)==1:raise ValueError('CLOVA HTTP 503: temporarily unavailable')
        return '{"commands":[]}',{}
    monkeypatch.setattr(model.client,'chat_main',request);monkeypatch.setattr(time,'sleep',sleeps.append)
    assert model.interpret('test',{'visual':{}})=={'commands':[]}
    assert len(attempts)==2 and sleeps==[3]
    def invalid(*a,**k):raise ValueError('CLOVA HTTP 401: unauthorized')
    monkeypatch.setattr(model.client,'chat_main',invalid)
    with pytest.raises(ValueError,match='응답 401'):model.interpret('test',{'visual':{}})
    assert sleeps==[3]

def test_natural_style_edits_do_not_regenerate_statistical_narration(monkeypatch):
    from chart_edit_agent import ChartEditAgent
    from test_chart_edit_agent import FakeEditModel
    agent=OutputAgent();data=fixture();initial=agent._build(data,ChartSpec(),generate_explanation=False)
    def forbidden(*args):raise AssertionError('추가 통계 요약 호출을 하면 안 됩니다.')
    monkeypatch.setattr(agent,'_explain',forbidden)
    model=FakeEditModel({'commands':[{'operation':'set_title','value':'수정한 제목'}]})
    output=ChartEditAgent(model,agent).edit(data,initial,'제목을 수정한 제목으로 바꿔줘')
    assert output['chartState']['title']=='수정한 제목' and output['explanation']['source']=='rules'

def test_standalone_period_color_opacity_use_current_highlight_without_model():
    from workspace_text_edits import simple_workspace_commands
    data=fixture();series=OutputAgent()._series(data['execution']['rows']);spec=ChartSpec()
    command=simple_workspace_commands('2020년 1분기부터 2021년 4분기까지 회색으로 강조해줘',spec,series)[0]
    output=OutputAgent()._build(data,spec,generate_explanation=False)
    output=OutputAgent().apply_edits(data,output,[command],generate_explanation=False);spec=ChartSpec.model_validate(output['chartState'])
    color=simple_workspace_commands('가장 최근 강조 영역의 색을 #777777로 바꿔줘',spec,series)[0]
    alpha=simple_workspace_commands('가장 최근 강조 영역의 불투명도를 35%로 바꿔줘',spec,series)[0]
    assert color.value==alpha.value==spec.highlights[-1].id
    assert color.params=={'color':'#777777'} and alpha.params=={'opacity':.35}
    assert simple_workspace_commands('제목을 바꾸고 격자를 지워줘',spec,series) is None
    with pytest.raises(ValueError):simple_workspace_commands('2015년 1분기부터 2021년 4분기까지 회색으로 강조해줘',spec,series)
