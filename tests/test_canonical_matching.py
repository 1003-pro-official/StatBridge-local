"""Canonical names beat similarity; conditions are scoped to their named table."""
import sys
from pathlib import Path
from collections import Counter

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/agent'),str(ROOT/'src/backend')]
from request_match_guard import catalog_mentions, structure_request
from stat_dictionary.stat_language_resolver import StatLanguageResolver


@pytest.fixture(scope='module')
def resolver():
    return StatLanguageResolver(ROOT/'src/agent/stat_dictionary/stat_language_dictionary.json')


def test_every_canonical_name_resolves_or_asks_about_real_duplicates(resolver):
    assert len(resolver.tables)==349
    for table in resolver.tables:
        query=table['table_name']+' 2020년부터 2025년까지 그래프 그려줘'
        mentions=catalog_mentions(query,resolver.tables)
        result=resolver.resolve(query)
        if any(len(m['table_ids'])>1 for m in mentions):
            assert result['status']=='need_clarification',table['table_id']
            assert table['table_id'] in [o['value'] for o in result['options']]
            chosen=resolver.apply_clarification(result['state'],result['clarification_id'],table['table_id'])
            assert chosen['selected_table']['table_id']==table['table_id']
        else:
            assert result['status']=='resolved',table['table_id']
            assert result['selected_table']['table_id']==table['table_id']


def test_institution_is_not_deposit_metric():
    assert '수신' not in structure_request('예금은행 고정 및 변동금리대출 비중')['metrics']
    assert '수신' in structure_request('예금은행 예금 잔액')['metrics']


def plans(resolver,ids):
    return [{'table_id':tid,'table_name':resolver.tables_by_id[tid]['table_name']} for tid in ids]


def test_reported_multi_table_validation(resolver):
    import bridge_api as api
    q='예금은행 고정 및 변동금리대출 비중과 신용카드 지급 내역을 2020년부터 2025년까지 그래프 그려줘'
    data={'status':'resolved','api_plans':plans(resolver,['DT_121Y010','DT_601Y003'])}
    assert api.agent.validate_resolution(q,data)['request_validation']['valid']
    first=resolver.resolve(q)
    assert first['status']=='need_clarification'
    chosen=resolver.apply_clarification(first['state'],first['clarification_id'],'DT_121Y010')
    assert {t['table_id'] for t in chosen['selected_tables']}=={'DT_121Y010','DT_601Y003'}


def test_all_unique_names_in_pairs_have_no_qualifier_cross_contamination(resolver):
    import bridge_api as api
    counts=Counter(t['table_name'] for t in resolver.tables)
    tables=[t for t in resolver.tables if counts[t['table_name']]==1]
    for index,table in enumerate(tables):
        other=tables[(index+19)%len(tables)]
        q=table['table_name']+' 그리고 '+other['table_name']+' 그래프 그려줘'
        result=api.agent.validate_resolution(q,{'status':'resolved','api_plans':plans(resolver,[table['table_id'],other['table_id']])})
        assert result['request_validation']['valid'],result['request_validation']


def test_exact_title_cannot_be_replaced_by_sibling(resolver):
    import bridge_api as api
    q=resolver.tables_by_id['DT_121Y010']['table_name']+' 그래프 그려줘'
    bad=api.agent.validate_resolution(q,{'status':'resolved','api_plans':plans(resolver,['DT_121Y011'])})
    assert not bad['request_validation']['valid']


def test_missing_second_table_fails(resolver):
    import bridge_api as api
    q=resolver.tables_by_id['DT_121Y010']['table_name']+'와 신용카드 그래프 그려줘'
    assert not api.agent.validate_resolution(q,{'status':'resolved','api_plans':plans(resolver,['DT_121Y010'])})['request_validation']['valid']


def test_canonical_multi_request_does_not_call_classification_or_vector(monkeypatch,resolver):
    import bridge_api as api
    def forbidden(*args,**kwargs):
        raise AssertionError('canonical names must not be replaced by model/vector ranking')
    monkeypatch.setattr(api.agent,'_classify',forbidden)
    monkeypatch.setattr(api.agent.hybrid,'rank',forbidden)
    q=resolver.tables_by_id['DT_121Y010']['table_name']+'와 신용카드 2020년부터 2025년까지 그래프 그려줘'
    result=api.agent.resolve(q)
    assert result['status']=='resolved'
    assert {p['table_id'] for p in result['api_plans']}=={'DT_121Y010','DT_601Y003'}


def test_generic_rate_and_card_conditions_stay_separate(resolver):
    import bridge_api as api
    q='예금은행 대출금리와 신용카드 지급 내역 그래프 그려줘'
    data={'status':'resolved','api_plans':plans(resolver,['DT_121Y006','DT_601Y003'])}
    assert api.agent.validate_resolution(q,data)['request_validation']['valid']


def test_unknown_second_quantity_is_not_silently_dropped(resolver):
    import bridge_api as api
    q='신용카드와 행복지수를 그래프 그려줘'
    assert resolver.resolve(q)['status']!='resolved'
    data={'status':'resolved','api_plans':plans(resolver,['DT_601Y003'])}
    assert not api.agent.validate_resolution(q,data)['request_validation']['valid']


def test_output_endpoint_renders_both_tables_and_rejects_changed_title(monkeypatch,resolver):
    import bridge_api as api
    from fastapi.testclient import TestClient
    from test_output_agent_migration import fixture_result
    monkeypatch.setattr(api.agent.output_agent,'ncp_client',None)
    monkeypatch.setattr(api,'_table_card',lambda tid:{'tableId':tid})
    session_ids=[]
    for index,tid in enumerate(['DT_121Y010','DT_601Y003']):
        data=fixture_result(1)
        data['status']='resolved'
        data['api_plan'].update(table_id=tid,table_name=resolver.tables_by_id[tid]['table_name'])
        for row in data['execution']['rows']:
            row['_SOURCE_SERIES_ID']=tid
            row['ITM_NM']=f'검증 계열 {index}'
            row['UNIT_NM']='%' if index==0 else '백만원'
        sid=f'canonical-regression-{index}'
        session_ids.append(sid)
        monkeypatch.setitem(api.OUTPUT_SESSIONS,sid,{'query':data['api_plan']['table_name'],
            'result':data,'table_name':data['api_plan']['table_name'],'frequency':'M',
            'period':{'start':'2024-01-01','end':'2024-03-31'}})
    client=TestClient(api.app)
    payload={'session_ids':session_ids,'chart_type':'line','natural_language':
             '예금은행 고정 및 변동금리대출 비중과 신용카드 지급 내역을 그래프 그려줘'}
    wrong={**payload,'natural_language':resolver.tables_by_id['DT_121Y011']['table_name']+'와 신용카드 그래프'}
    assert client.post('/api/output',json=wrong).status_code==422
    assert client.post('/api/output',json=payload).status_code==422
    response=client.post('/api/output',json={**payload,'chart_mode':'separate'})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['seriesCount']==2
    assert len(result['outputSpec']['plotlyFigure']['data'])==2
    assert result['chartMode']=='separate'  # Percentages and amounts are not added.
    api.EDIT_SESSIONS.pop(result['editSessionId'],None)


def test_output_session_accepts_confirmed_period_without_accepting_changed_item(monkeypatch):
    import copy
    import bridge_api as api
    from fastapi.testclient import TestClient
    from output_agent import OutputAgent
    query='「차주당 주택담보대출 신규취급액」 자료를 한 계열로 찾아줘'
    result=copy.deepcopy(api.agent.resolve(query))
    plan=result['api_plans'][0]
    plan.update(start_period='202001',end_period='202602')
    plan['exact_params'].update(startPrdDe='202001',endPrdDe='202602')
    result['execution']={'status':'success','row_count':2,'rows':[
        {'PRD_DE':p,'DT':str(i),'UNIT_NM':'십만원','_SERIES_LABEL':plan['table_name'],'_FREQUENCY':'Q'}
        for i,p in enumerate(['202001','202602'],1)]}
    session={'query':query,'result':result,'table_name':plan['table_name'],'frequency':'Q',
             'period':{'start':'2020-01-01','end':'2026-06-30'}}
    monkeypatch.setitem(api.OUTPUT_SESSIONS,'confirmed-period-test',session)
    monkeypatch.setattr(api.agent,'output_agent',OutputAgent())
    client=TestClient(api.app)
    payload={'session_ids':['confirmed-period-test'],'chart_type':'line','natural_language':query}
    original=plan['exact_params']['itmId']
    plan['exact_params']['itmId']='invented'
    assert client.post('/api/output',json=payload).status_code==422
    assert 'confirmed-period-test' in api.OUTPUT_SESSIONS
    plan['exact_params']['itmId']=original
    response=client.post('/api/output',json=payload)
    assert response.status_code==200,response.text
    assert response.json()['period']==session['period']
    assert response.json()['chart'][0]['points'][0]['date']=='202001'
    api.EDIT_SESSIONS.pop(response.json()['editSessionId'],None)
