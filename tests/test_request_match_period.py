"""Original user intent, canonical provenance and explicit-date API regressions."""
import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/agent'),str(ROOT/'src/backend')]
from request_period import explicit_period
from request_match_guard import table_evidence, structure_request
from stat_dictionary.stat_language_resolver import StatLanguageResolver
from output_agent import OutputAgent
from test_output_agent_migration import fixture_result


@pytest.fixture
def resolver():return StatLanguageResolver(ROOT/'src/agent/stat_dictionary/stat_language_dictionary.json')


def test_reported_export_currency_is_not_industry_loans(resolver):
    query='지역별 수출 통화 2020년부터 2026년 현재까지 그래프 그려줘'
    result=resolver.resolve(query)
    assert result['status']=='resolved'
    assert result['selected_table']['table_id']=='DT_303Y001'
    assert all('대출' not in c['table_name'] for c in result['candidates'])
    assert structure_request(query)['metrics']==['수출','통화']


def test_all_349_canonical_table_names_pass_original_request_guard(resolver):
    assert len(resolver.tables_by_id)==349
    rejected=[tid for tid,table in resolver.tables_by_id.items() if not table_evidence(table['table_name'],table)[0]]
    assert not rejected,rejected


@pytest.mark.parametrize('query',['지역별 수출 통화','수출물량','수입물가','통화량','생산자물가','GDP'])
def test_modifier_overlap_cannot_validate_a_loan_table(resolver,query):
    assert not table_evidence(query,resolver.tables_by_id['DT_132Y001'])[0]


@pytest.mark.parametrize('query',['지역별 그래프','서울 2020년부터 2025년까지','행복지수 추이','DT_132Y001 수출 통화'])
def test_unknown_or_contradictory_request_does_not_select_first_table(resolver,query):
    assert resolver.resolve(query)['status']!='resolved'


@pytest.mark.parametrize('query,start,end',[
    ('2020년부터 2025년까지','2020-01-01','2025-12-31'),
    ('2020~2025','2020-01-01','2025-12-31'),
    ('2020-2025','2020-01-01','2025-12-31'),
    ('2020년 2월부터 2020년 2월까지','2020-02-01','2020-02-29'),
    ('2020년 1분기부터 2025년 3분기까지','2020-01-01','2025-09-30'),
    ('2020-02-03~2025-12-30','2020-02-03','2025-12-30'),
    ('2020년','2020-01-01','2020-12-31'),
    ('2020년부터 현재까지','2020-01-01','2025-12-31'),
])
def test_explicit_date_range(query,start,end):
    result=explicit_period(query,latest='2025-12-31')
    assert (result['start'],result['end'])==(start,end)


@pytest.mark.parametrize('query',['최근 추이','2020년 이후','2020년과 2025년 비교','DT_2020Y001','2020년 2021년 2022년 비교'])
def test_ambiguous_dates_are_not_invented(query):assert explicit_period(query) is None


@pytest.mark.parametrize('query',['2025년부터 2020년까지','2020년 13월부터 2025년까지','2020-02-30~2025-12-30'])
def test_invalid_dates_fail(query):
    with pytest.raises(ValueError):explicit_period(query)


def test_output_rejects_failed_validation_or_foreign_source():
    agent=OutputAgent();data=fixture_result(1)
    data['request_validation']={'valid':False,'table_ids':['DT_TEST']}
    with pytest.raises(ValueError,match='일치'):agent.prepare(data,{'chart_type':'line'})
    data['request_validation']['valid']=True
    data['execution']['rows'][0]['_SOURCE_SERIES_ID']='DT_FOREIGN'
    with pytest.raises(ValueError,match='출처'):agent.prepare(data,{'chart_type':'line'})


def test_execute_guard_blocks_stale_or_model_replaced_plan(monkeypatch):
    import bridge_api as api
    calls=[];monkeypatch.setattr(api.service,'get_statistics',lambda **kwargs:calls.append(kwargs))
    selected=api.agent.resolver.candidate_shell('DT_132Y001')
    plan=api.agent.build_api_plan('DT_132Y001',selected).as_dict()
    result=api.agent.execute_resolution('지역별 수출 통화',{'status':'resolved','api_plan':plan,'selected_table':selected},generate_answer=False)
    assert result['status']=='no_match' and result['execution']['rows']==[] and not calls


@pytest.mark.parametrize('frequency,table_id,expected',[
    ('M','DT_513Y001',('202001','202512')),
    ('Q','DT_132Y001',('202001','202504')),
    ('A','DT_200Y101',('2020','2025')),
])
def test_api_text_dates_skip_picker_and_use_source_frequency(monkeypatch,frequency,table_id,expected):
    import bridge_api as api
    from fastapi.testclient import TestClient
    selected=api.agent.resolver.candidate_shell(table_id)
    plan=api.agent.build_api_plan(table_id,selected).as_dict();plan['frequency']=frequency
    resolution={'status':'resolved','api_plan':plan,'selected_table':selected,'state':{}}
    monkeypatch.setattr(api.agent,'run',lambda **kwargs:copy.deepcopy(resolution))
    monkeypatch.setattr(api,'_availability_from_plans',lambda plans:{'min':'1990-01-01','max':'2026-12-31'})
    monkeypatch.setattr(api,'_table_card',lambda identifier:{'tableId':identifier})
    calls=[]
    def data(**kwargs):
        calls.append(kwargs)
        return {'status':'success','rows':[{'PRD_DE':expected[0],'DT':'10','ITM_NM':'테스트'}],'source':'mock'}
    monkeypatch.setattr(api.service,'get_statistics',data)
    response=TestClient(api.app).post('/api/query',json={'query':f'{table_id} 2020년부터 2025년까지'})
    assert response.status_code==200,response.text
    result=response.json();assert result['status']=='need_output_config',result
    assert result['periodSelection']['source']=='text'
    assert (calls[0]['start_period'],calls[0]['end_period'])==expected
    api.OUTPUT_SESSIONS.pop(result['outputSessionId'],None)


def test_api_outside_dates_ask_confirmation_without_fetch(monkeypatch):
    import bridge_api as api
    from fastapi.testclient import TestClient
    calls=[];monkeypatch.setattr(api.service,'get_statistics',lambda **kwargs:calls.append(kwargs))
    monkeypatch.setattr(api,'_availability_from_plans',lambda plans:{'min':'2000-01-01','max':'2025-12-31'})
    result=TestClient(api.app).post('/api/query',json={'query':'DT_513Y001 2020년부터 2026년까지'}).json()
    assert result['status']=='need_period' and not calls and result['warnings']


def test_reported_export_query_api_never_fetches_loans(monkeypatch):
    import bridge_api as api
    from fastapi.testclient import TestClient
    calls=[];monkeypatch.setattr(api.service,'get_statistics',lambda **kwargs:calls.append(kwargs))
    monkeypatch.setattr(api.agent.ncp.settings,'api_key','')
    monkeypatch.setattr(api.agent.hybrid,'rank',lambda *args,**kwargs:[])
    result=TestClient(api.app).post('/api/query',json={'query':'지역별 수출 통화 2020년부터 2026년 현재까지 그래프 그려줘'}).json()
    assert result['status']=='need_period',result
    assert [table['tableId'] for table in result['tables']]==['DT_303Y001']
    assert not calls


def test_api_clarification_preview_confirms_text_dates_without_fetch(monkeypatch):
    import bridge_api as api
    from fastapi.testclient import TestClient
    calls=[];monkeypatch.setattr(api.service,'get_statistics',lambda **kwargs:calls.append(kwargs))
    monkeypatch.setattr(api,'_availability_from_plans',lambda plans:{'min':'2000-01-01','max':'2025-12-31'})
    result=TestClient(api.app).post('/api/query',json={'query':'DT_513Y001 2020년부터 2025년까지','execute':False}).json()
    assert result['status']=='need_period' and not calls
    assert result['periodSelection']['applied']=={'start':'2020-01-01','end':'2025-12-31'}


def test_unbound_sketch_cannot_become_whole_series_edit():
    from chart_edit_agent import ChartEditAgent
    from test_chart_edit_agent import FakeEditModel,mark
    output_agent=OutputAgent();source=fixture_result()
    current=output_agent.prepare(source,{'chart_type':'line'})
    editor=ChartEditAgent(FakeEditModel({'commands':[{'operation':'set_series_color','label':'계열0','value':'#ff0000'}]}),output_agent)
    before=copy.deepcopy(current)
    with pytest.raises(ValueError,match='전체 계열은 변경하지 않았습니다'):
        editor.edit(source,current,'표시한 곳을 빨갛게',{'marks':[mark(target='chart')]})
    assert current==before


def test_output_endpoint_revalidates_query_not_just_cached_success(monkeypatch):
    import bridge_api as api
    from fastapi.testclient import TestClient
    selected=api.agent.resolver.candidate_shell('DT_132Y001')
    plan=api.agent.build_api_plan('DT_132Y001',selected).as_dict()
    session={'query':'수출 통화','result':{'status':'resolved','api_plan':plan,'selected_table':selected}}
    api.OUTPUT_SESSIONS['wrong-table-test']=session
    try:
        response=TestClient(api.app).post('/api/output',json={'session_ids':['wrong-table-test'],'chart_type':'line'})
        assert response.status_code==422
        assert api.OUTPUT_SESSIONS['wrong-table-test'] is session
    finally:api.OUTPUT_SESSIONS.pop('wrong-table-test',None)
