"""Original query -> UI selections -> all plans -> mocked MCP -> Plotly output."""
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/agent'),str(ROOT/'src/backend')]


@pytest.fixture
def api(monkeypatch):
    import bridge_api as module
    def forbidden(*args,**kwargs):
        raise AssertionError('named requests must not be rewritten by model/vector')
    monkeypatch.setattr(module.agent,'_classify',forbidden)
    monkeypatch.setattr(module.agent.hybrid,'rank',forbidden)
    monkeypatch.setattr(module.agent.ncp,'clarify_question',lambda q,r,s:r['question'])
    monkeypatch.setattr(module.agent.output_agent,'ncp_client',None)
    monkeypatch.setattr(module,'_availability_from_table_ids',lambda ids:{'min':'2000-01-01','max':'2025-12-31'})
    monkeypatch.setattr(module,'_availability_from_plans',lambda plans:{'min':'2000-01-01','max':'2025-12-31'})
    monkeypatch.setattr(module,'_table_card',lambda tid:{'tableId':tid})
    return module


@pytest.mark.parametrize('rate',['수신금리','대출금리'])
def test_rate_choice_does_not_remove_compared_new_mortgage(api,rate):
    from request_period import explicit_period
    query='2020년과 2025년까지의 금리와 주택담보대출 신규대출을 비교하는 그래프 그려줘'
    assert explicit_period(query)['start']=='2020-01-01'
    assert explicit_period(query)['end']=='2025-12-31'
    assert explicit_period('2020년과 2025년 비교') is None
    result=api.agent.resolve(query)
    assert result['clarification_id']=='comparison:0:rate_type'
    for _ in range(12):
        if result['status']=='resolved':break
        assert result['status']=='need_clarification',result
        gid=result['clarification_id'];values=[o['value'] for o in result['options']]
        if gid=='comparison:1:table':
            assert all('신규취급액' in o['label'] and not any(w in o['label'] for w in ('잔액','금리','비중')) for o in result['options'])
        preferred=rate if gid.endswith('rate_type') else '신규취급액' if gid.endswith('interest_basis') else 'DT_181Y011' if gid.startswith('comparison:1:') else 'DT_121Y002' if rate=='수신금리' else 'DT_121Y006'
        value=preferred if preferred in values else values[0]
        result=api._resolve_selected_options(query,result['state'],[{'clarification_id':gid,'values':[value]}])
    assert result['status']=='resolved',result
    assert len(result['api_plans'])==2
    assert result['api_plans'][0]['table_id']==('DT_121Y002' if rate=='수신금리' else 'DT_121Y006')
    assert result['api_plans'][1]['table_id']=='DT_181Y011'
    assert all(p['start_period'].startswith('2020') and p['end_period'].startswith('2025') for p in result['api_plans'])


@pytest.mark.parametrize('kind',['line','pie','donut'])
def test_mortgage_and_credit_request_keeps_both_products_and_renders(api,monkeypatch,kind):
    from fastapi.testclient import TestClient
    query='2020년과 2025년까지의 주택담보대출과 신용대출을 비교하는 그래프 그려줘'
    result=api.agent.resolve(query)
    for _ in range(12):
        if result['status']=='resolved':break
        assert result['status']=='need_clarification',result
        gid=result['clarification_id']
        assert not gid.endswith('loan_type')  # Credit loans must not become mortgages.
        value='잔액' if gid.endswith('loan_measure') else result['options'][0]['value']
        result=api._resolve_selected_options(query,result['state'],[{'clarification_id':gid,'values':[value]}])
    assert result['status']=='resolved',result
    assert {p['table_id'] for p in result['api_plans']}=={'DT_181Y012','DT_181Y002'}
    credit=next(p for p in result['api_plans'] if p['table_id']=='DT_181Y002')
    assert any('F003' in v for v in credit['classifications'].values())
    missing_credit={**result,'api_plans':[p for p in result['api_plans'] if p['table_id']=='DT_181Y012']}
    assert api.agent.validate_resolution(query,missing_credit)['status']=='no_match'
    result['execution']={'status':'success','rows':[{'PRD_DE':'2025Q4','DT':str(i+10),'ITM_NM':name,'UNIT_NM':'만원','_SOURCE_SERIES_ID':p['table_id'],'_FREQUENCY':'Q'} for i,(p,name) in enumerate(zip(result['api_plans'],['주택담보대출 실제 항목','신용대출 실제 항목']))],'row_count':2}
    monkeypatch.setattr(api.agent.output_agent,'_propose_spec',lambda series,raw:{'series_chart_types':{'주택담보대출':'line','신용대출':'line'}})
    monkeypatch.setitem(api.OUTPUT_SESSIONS,'product-test',{'result':result,'query':query,'table_name':'검증 표','period':{'start':'2020-01-01','end':'2025-12-31'},'frequency':'Q'})
    response=TestClient(api.app).post('/api/output',json={'session_ids':['product-test'],'chart_type':kind,'natural_language':query})
    assert response.status_code==200,response.text
    out=response.json()
    assert out['seriesCount']==2 and out['chartType']==kind and out['warnings']
    assert out['outputSpec']['plotlyFigure']['data']
    api.EDIT_SESSIONS.pop(out['editSessionId'],None)


def test_reported_request_through_actual_ui_selections_and_output(api,monkeypatch):
    from fastapi.testclient import TestClient
    calls=[]
    def data(**kwargs):
        calls.append(kwargs)
        return {'status':'success','rows':[{'PRD_DE':p,'DT':str(v),'ITM_NM':'검증 항목','UNIT_NM':'개'}
            for p,v in [('202001',10),('202002',20),('202003',30)]],'source':'mock'}
    monkeypatch.setattr(api.service,'get_statistics',data)
    query='예금은행 고정 및 변동금리대출 비중과 신용카드 지급 내역을 2020년부터 2025년까지 그래프 그려줘'
    client=TestClient(api.app)
    first=client.post('/api/query',json={'query':query,'execute':True}).json()
    assert first['status']=='need_clarification' and not calls
    # The UI uses selections (not the legacy singular clarification property).
    selection={'clarification_id':first['clarification']['id'],'values':['DT_121Y010']}
    preview=client.post('/api/query',json={'query':query,'state':first['state'],'selections':[selection],'execute':False}).json()
    assert preview['status']=='need_period',preview
    assert preview['periodSelection']['applied']=={'start':'2020-01-01','end':'2025-12-31'}
    assert not calls
    response=client.post('/api/query',json={'query':query,'state':first['state'],'selections':[selection],
        'execute':True,'period_start':'2020-01-01','period_end':'2025-12-31'})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['status']=='need_output_config',result
    assert {t['tableId'] for t in result['tables']}=={'DT_121Y010','DT_601Y003'}
    assert len(calls)==2
    rendered=client.post('/api/output',json={'session_ids':[result['outputSessionId']],
        'chart_type':'line','natural_language':query})
    assert rendered.status_code==200,rendered.text
    out=rendered.json()
    assert out['seriesCount']==2 and len(out['outputSpec']['plotlyFigure']['data'])==2
    assert len(calls)==2  # Output must not re-query statistics.
    api.EDIT_SESSIONS.pop(out['editSessionId'],None)


@pytest.mark.parametrize('ids',[
    ['DT_121Y006','DT_121Y002'],
    ['DT_303Y001','DT_601Y003'],
    ['DT_200Y105','DT_601Y003'],
    ['DT_121Y010','DT_303Y001','DT_601Y003'],
])
def test_other_named_complex_requests_preserve_all_plans(api,ids):
    names=[api.agent.tables_by_id[tid]['table_name'] for tid in ids]
    query=' 그리고 '.join(names)+' 2020년부터 2025년까지 비교 그래프 그려줘'
    result=api.agent.resolve(query)
    assert result['status']=='resolved',result
    assert {p['table_id'] for p in result['api_plans']}==set(ids)
    assert result['request_validation']['valid']
    assert result['request_query']==query


def test_second_ambiguous_table_is_asked_not_discarded(api):
    q='예금은행 고정 및 변동금리대출 비중과 예금은행 대출금리 그래프 그려줘'
    first=api.agent.resolver.resolve(q)
    assert first['status']=='need_clarification'
    tid=first['options'][0]['value']
    next_result=api._resolve_selected_options(q,first['state'],[
        {'clarification_id':first['clarification_id'],'values':[tid]}])
    assert next_result['status']=='need_clarification',next_result
    assert next_result['state']['confirmed'][first['clarification_id']]==tid
    assert next_result['clarification_id']!=first['clarification_id']


def test_excess_combinations_are_not_silently_truncated(api):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        api._resolve_selected_options('신용카드',{},[
            {'clarification_id':'one','values':['a','b','c']},
            {'clarification_id':'two','values':['a','b']}])
    assert exc.value.status_code==422
