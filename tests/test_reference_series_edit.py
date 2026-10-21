"""Reference reconstruction uses synthetic source rows, never image values."""
import copy
import json
from types import SimpleNamespace

import pytest
from chart_reference_data import prepare_reference_data, reference_catalog
from output_agent import OutputAgent
from output_schema import ChartSpec


class CatalogAgent:
    def __init__(self):
        self.output_agent=OutputAgent()
        self.calls=[]
        self.fail=False
        self.wrong=False
        self.tables_by_id={key:{'table_id':key,'table_name':name,'prd_se':'M','dimensions':[
            {'api_param':'objL1','values':[{'value_id':str(i),'value_name':v} for i,v in enumerate(values)]}]}
            for key,name,values in [('export','수출물량지수',['총지수','정제제품','화학제품']),('import','수입물량지수',['총지수','원유'])]}
        self.resolver=SimpleNamespace(tables=list(self.tables_by_id.values()))
        self.service=self

    def resolve(self,query):
        table,category=query.split(' ',1)
        t=next(t for t in self.resolver.tables if t['table_name']==table)
        value=next(v for v in t['dimensions'][0]['values'] if v['value_name']==category)
        plan={'table_id':t['table_id'],'table_name':table,'item_id':'index','org_id':'301','frequency':'M',
              'classifications':{'objL1':'0' if self.wrong else value['value_id']},'start_period':'202506','end_period':'202607'}
        return {'status':'resolved','api_plan':plan,'api_plans':[plan],'request_validation':{'valid':True,'table_ids':[t['table_id']]}}

    def rows(self,plan,start,end):
        t=self.tables_by_id[plan['table_id']]
        cat=plan['classifications']['objL1']
        value=next(v['value_name'] for v in t['dimensions'][0]['values'] if v['value_id']==cat)
        return [{'TBL_ID':t['table_id'],'ITM_ID':'index','C1':cat,'C1_NM':value,'UNIT_NM':'2020=100',
                 'PRD_DE':f'{year}{month:02d}','DT':str(100+int(cat)*10+(year-2024)*5+month),
                 '_SERIES_LABEL':t['table_name'],'_SOURCE_SERIES_ID':t['table_id'],'_FREQUENCY':'M'}
                for year in range(2024,2027) for month in range(1,13) if start<=f'{year}{month:02d}'<=end]

    def execute_resolution(self,query,resolution,start_period,end_period,**kwargs):
        self.calls.append(query)
        rows=[] if self.fail else self.rows(resolution['api_plan'],start_period,end_period)
        return {**resolution,'execution':{'status':'success' if rows else 'error','rows':rows,'sources':[]}}

    def get_statistics_batch(self,requests):
        return {'results':[{'status':'success','data':{'status':'success','rows':self.rows(p,p['start_period'],p['end_period'])
            if p['frequency']=='M' else [],'source':'synthetic'}} for p in requests]}


def fixture():
    agent=CatalogAgent()
    original=agent.execute_resolution('수출물량지수 총지수',agent.resolve('수출물량지수 총지수'),start_period='202506',end_period='202607')
    current=agent.output_agent._build(original,ChartSpec(chart_type='line',title='총지수 추이'),generate_explanation=False)
    catalog=[{'table':t['table_name'],'categories':[v['value_name'] for v in t['dimensions'][0]['values']]} for t in agent.resolver.tables]
    appearance={'chart_type':'line','panel_count':1,'columns':1,'series_types':['line']*3,'mirror_y_axis':True,
        'comparison':'year_over_year','comparison_label':'전년동기대비, %','legend_position':'bottom-left','display_period':{'start':'202507','end':'202607'},
        'data_series':[{'label':'정제제품 수출','table':'수출물량지수','category':'정제제품','style':{'color':'#40516f','markers':True,'marker_symbol':'circle-open'}},
                       {'label':'화공품 수출','table':'수출물량지수','category':'화학제품','style':{'color':'#8eace1','markers':True}},
                       {'label':'원유 수입','table':'수입물량지수','category':'원유','style':{'color':'#e8a6ad','dash':'dash','markers':False}}],
        'emphasis':[{'start':'202603','end':'202607','label':'참고 구간','color':'#cde5f5','opacity':.35}]}
    return agent,original,current,catalog,appearance


def test_catalog_exposes_only_aggregate_siblings(monkeypatch):
    agent,original,*_=fixture()
    agent.resolver.tables.append({**agent.tables_by_id['export'],'table_id':'value','table_name':'수출금액지수'})
    monkeypatch.setattr('semantic_catalog_planner.catalog_paths',lambda:{'export':'한국은행 > 조사 > 공통지수 > 수출물량지수',
        'import':'한국은행 > 조사 > 공통지수 > 수입물량지수','value':'한국은행 > 조사 > 공통지수 > 수출금액지수'})
    assert len(reference_catalog(original,agent))==2
    specific=agent.execute_resolution('',agent.resolve('수출물량지수 정제제품'),start_period='202506',end_period='202607')
    assert reference_catalog(specific,agent)==[]


def test_reference_fetches_each_exact_category_and_preserves_original():
    agent,original,current,catalog,appearance=fixture()
    saved=copy.deepcopy((original,current))
    result,baseline,sessions=prepare_reference_data(original,current,appearance,catalog,agent)
    assert (original,current)==saved
    assert [p['classifications']['objL1'] for p in result['api_plans']]==['1','2','1']
    assert len(agent.output_agent._series(result['execution']['rows']))==3
    assert baseline['chartState']['subtitle']==''
    assert all(row['PRD_DE']>='202507' for row in result['execution']['rows'])
    assert sessions[0]['period']['end']=='2026-07-31'
    assert len(result['execution']['referenceDataBinding'])==3


def test_reference_can_requery_available_history_beyond_the_current_view():
    agent,original,current,catalog,appearance=fixture()
    for c in catalog:c.update(start='202401',end='202607')
    original['execution']['rows']=[r for r in original['execution']['rows'] if r['PRD_DE']>='202508']
    result,_,_=prepare_reference_data(original,current,appearance,catalog,agent)
    assert min(r['PRD_DE'] for r in result['execution']['rows'])=='202507'
    appearance['display_period']['start']='202599'
    with pytest.raises(ValueError):prepare_reference_data(original,current,appearance,catalog,agent)


@pytest.mark.parametrize('problem',['wrong_category','wrong_family','failed_query','outside_period','duplicate'])
def test_unresolved_or_failed_binding_never_changes_the_old_graph(problem):
    agent,original,current,catalog,appearance=fixture()
    saved=copy.deepcopy((original,current))
    if problem=='wrong_category':agent.wrong=True
    if problem=='wrong_family':appearance['data_series'][0]['table']='다른 통계'
    if problem=='failed_query':agent.fail=True
    if problem=='outside_period':appearance['display_period']['end']='202608'
    if problem=='duplicate':appearance['data_series'][1]=appearance['data_series'][0]
    with pytest.raises(ValueError):prepare_reference_data(original,current,appearance,catalog,agent)
    assert (original,current)==saved


def test_reference_edit_api_commits_three_real_series_in_one_image_pass_and_undoes(monkeypatch):
    import bridge_api as api
    from authenticated_client import TestClient
    from chart_edit_agent import ChartEditAgent
    from openai_chart_client import OpenAIChartClient, OpenAIEditModel
    from test_axis_reference_performance import reference,Response
    agent,original,current,catalog,appearance=fixture()
    class Transport:
        calls=0
        def post(self,url,**kwargs):
            self.calls+=1
            return Response(json.dumps({'reference_style':appearance,'commands':[
                {'operation':'set_presentation','params':{'design_template':'snapshot','latest_values':False}},
                {'operation':'set_legend','value':'bottom-left'}]}))
    transport=Transport()
    session={'result':original,'output':current,'sessions':[{'query':'총지수','result':original,'table_name':'수출물량지수','frequency':'M',
        'period':{'start':'2025-06-01','end':'2026-07-31'}}],'undo':[],'redo':[]}
    monkeypatch.setattr(api,'agent',agent)
    monkeypatch.setattr(api,'edit_agent',ChartEditAgent(OpenAIEditModel(OpenAIChartClient(api_key='synthetic',session=transport)),agent.output_agent))
    monkeypatch.setattr(api,'_table_card',lambda tid:{'tableId':tid})
    monkeypatch.setattr('chart_reference_data.reference_catalog',lambda result,agent:catalog)
    monkeypatch.setitem(api.EDIT_SESSIONS,'reference-members',session)
    client=TestClient(api.app)
    def edit(**payload):return client.post('/api/output/edit',json={'edit_session_id':'reference-members',**payload})
    response=edit(instruction='이 형식으로 수정해줘',reference_files=[reference()],revision=0)
    assert response.status_code==200,response.text
    assert transport.calls==1
    output=response.json()['outputSpec']
    spec=output['chartState'];fig=output['plotlyFigure']
    assert len(output['visualization']['series'])==3
    assert spec['transform']=='year_over_year' and spec['presentation']['publication_axes']
    assert not spec['presentation']['publication_yoy']
    assert fig['layout']['yaxis']['range']==fig['layout']['yaxis2']['range']
    assert any(t.get('line',{}).get('dash')=='dash' for t in fig['data'])
    assert 'circle-open' in fig['data'][0]['marker']['symbol']
    assert fig['layout']['legend']['y']==0 and fig['layout']['legend']['yanchor']=='bottom'
    assert fig['layout']['shapes'][0]['layer']=='below'
    assert len(spec['highlights'])==1
    note=next(a for a in fig['layout']['annotations'] if a.get('name','').startswith('statbridge-highlight:'))
    assert note['yanchor']=='top'
    assert all('총지수' not in s['label'] for s in output['visualization']['series'])
    assert output['editChanges'][0].startswith('참고 범례')
    assert edit(action='undo',revision=1).status_code==200
    assert session['result']==original
    saved=copy.deepcopy(session);agent.fail=True
    assert edit(instruction='이 형식으로 수정해줘',reference_files=[reference()],revision=2).status_code==422
    assert session==saved


def test_homogeneous_reference_mismatch_cannot_report_a_color_only_success():
    from chart_reference_policy import bind_reference_structure
    with pytest.raises(ValueError,match='3개 계열'):
        bind_reference_structure({'reference_style':{'chart_type':'line','panel_count':1,'columns':1,'series_types':['line']*3},
                                  'commands':[{'operation':'set_series_color','label':'총지수','value':'#123456'}]},
                                 {'seriesLabels':['총지수'],'chartState':{'chart_type':'line'}})


def test_old_saved_chart_before_optional_mirrored_axes_still_restores():
    from report_export import document,restore_document
    _,result,_,_,_=fixture()
    payload=document(result,ChartSpec(chart_type='line'))
    payload['typography'].pop('publication_axes')
    payload['state']['presentation'].pop('publication_axes')
    assert restore_document(result,payload).presentation.publication_axes is False
