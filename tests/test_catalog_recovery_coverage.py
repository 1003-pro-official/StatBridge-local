"""Public catalog coverage; no benchmark answers or provider calls."""
from types import SimpleNamespace
import pytest
from agent_runtime import StatBridgeAgent
from catalog_request_planner import selections
from recovery import recovery_question

@pytest.fixture(scope='module')
def agent():
    return StatBridgeAgent(object(), ncp_client=SimpleNamespace(configured=False))

def test_shared_names_preserve_four_tables_and_exact_period(agent):
    q='국가별 결제통화 수입,수출 그리고 지역별 결제통화 수입, 수출 2020년1월부터 2025년 12월까지 그래프 그려줘'
    r=agent.resolve(q)
    assert r['status']=='resolved'
    assert {p['table_id'] for p in r['api_plans']}=={'DT_303Y005','DT_303Y002','DT_303Y004','DT_303Y001'}
    assert all((p['start_period'],p['end_period'])==('202001','202512') for p in r['api_plans'])
    assert all(item['_missing_dimensions'] for item in r['selected_tables'])

def test_shared_names_are_derived_from_catalog_and_do_not_drop_other_metrics(agent):
    tables=[{'table_id':'one','table_name':'시험 통계(원계열)','dimensions':[]},{'table_id':'two','table_name':'시험 통계(계절조정)','dimensions':[]}]
    assert {s['table_id'] for s in selections('시험 통계 원계열, 계절조정 추이',tables)}=={'one','two'}
    assert selections('시험 통계 원계열, 계절조정 그리고 기준금리',tables)==[]
    assert selections('시험 통계 원계열, 계절조정',tables+[dict(tables[0],table_id='duplicate')])==[]

def test_missing_indicators_and_recovery_actions_are_precise(agent):
    r=agent.resolve('2020년부터 2025년까지 한국의 기준금리와 소비자물가지수 추이를 각각 조회해줘')
    assert r['status']=='no_match'
    assert set(r['missing_series'])=={'기준금리','소비자물가지수'}
    actions=lambda r:[c['id'] for c in r['choices']]
    assert actions(recovery_question('2020년부터 2025년까지 기준금리',issue='no_match'))==['revise','table']
    assert actions(recovery_question('HTTP 503 호출 실패'))==['retry','revise']
    assert actions(recovery_question('날짜는 YYYY-MM-DD 형식이어야 합니다.'))==['period','revise']
    assert actions(recovery_question('색상 값이 잘못되었습니다.'))==['revise']

def test_every_public_catalog_title_and_id_resolves_to_itself(agent):
    assert len(agent.resolver.tables)==349
    failures=[]
    for table in agent.resolver.tables:
        q=f"「{table['table_name']}」 [{table['table_id']}] 조회해줘"
        r=agent.resolve(q)
        if r['status']!='resolved' or {p['table_id'] for p in r.get('api_plans',[])}!={table['table_id']}:
            failures.append((table['table_id'],r['status'],r.get('missing_series'),r.get('request_validation')))
    assert not failures,failures


def test_exact_public_classifications_clear_missing_dimensions(agent):
    q='국가별 결제통화 수입,수출 그리고 지역별 결제통화 수입, 수출 「달러 (호주)」 「달러 (중국)」 「금액」 2020년1월부터 2025년12월까지'
    r=agent.resolve(q)
    assert r['status']=='resolved'
    assert len(r['api_plans'])==4
    assert all(not item['_missing_dimensions'] for item in r['selected_tables'])
    for item in r['selected_tables']:
        assert [h['value_name'] for h in item['dimension_hits']]==['달러 (호주)' if '국가별' in item['table_name'] else '달러 (중국)','금액']


def test_api_preserves_period_and_identifies_real_missing_step(monkeypatch, agent):
    import bridge_api as api
    from authenticated_client import TestClient
    monkeypatch.setattr(api,'agent',agent)
    client=TestClient(api.app)
    missing=client.post('/api/query',json={'query':'2020년부터 2025년까지 한국의 기준금리와 소비자물가지수 추이를 각각 조회해줘','execute':False}).json()
    assert missing['status']=='no_match'
    assert [c['id'] for c in missing['recovery']['choices']]==['revise','table']
    assert missing['period']=={'start':'2020-01-01','end':'2025-12-31'}
    details=client.post('/api/query',json={'query':'국가별 결제통화 수입,수출 그리고 지역별 결제통화 수입, 수출 2020년1월부터 2025년 12월까지 그래프 그려줘','execute':False}).json()
    assert details['status']=='need_details'
    assert len(details['tables'])==4 and not details['chart']
    assert details['recovery']['issue']=='dimensions'
    assert details['period']==missing['period']


def test_whitespace_equivalent_shared_titles_do_not_pick_another_vintage():
    tables=[{'table_id':'old-a','table_name':'시험 통계(말잔)','dimensions':[]},{'table_id':'old-b','table_name':'시험 통계(평잔)','dimensions':[]},{'table_id':'new-a','table_name':'시험통계(말잔)','dimensions':[]},{'table_id':'new-b','table_name':'시험통계(평잔)','dimensions':[]}]
    assert selections('시험 통계 말잔, 평잔 추이',tables)==[]


def test_catalog_all_349_dimension_counts_names_and_codes_are_consistent():
    import bridge_api as api
    response=api.catalog()
    tables=[t for major in response['categories'] for middle in major['children'] for t in middle['children']]
    assert len(tables)==349
    for table in tables:
        for d in table['dimensions']:
            assert d['count']==len(d['values'])==len(d['valueOptions']),table['tableId']
            assert d['values']==[v['name'] for v in d['valueOptions']]
            assert not d['defaultValueId'] or d['defaultValueId'] in {v['id'] for v in d['valueOptions']}


def test_execution_validation_failure_returns_complete_recovery_response(monkeypatch,agent):
    import bridge_api as api
    from authenticated_client import TestClient
    monkeypatch.setattr(api,'agent',agent)
    monkeypatch.setattr(agent,'run_resolution',lambda **kwargs:{'status':'no_match','request_validation':{'errors':['조회 계획 불일치']}})
    q='국가별 결제통화 수입,수출 그리고 지역별 결제통화 수입, 수출 「달러 (호주)」 「달러 (중국)」 「금액」 2020년1월부터 2025년12월까지'
    result=TestClient(api.app).post('/api/query',json={'query':q,'execute':True})
    assert result.status_code==200
    data=result.json()
    assert data['status']=='no_match' and data['tables']==[] and data['chart']==[]
    assert data['period']=={'start':'2020-01-01','end':'2025-12-31'}
    assert [c['id'] for c in data['recovery']['choices']]==['revise','table']


def test_all_catalog_shared_name_families_handle_spacing_case_and_punctuation(agent):
    import re
    from collections import defaultdict
    families=defaultdict(lambda:defaultdict(list))
    for table in agent.resolver.tables:
        match=re.fullmatch(r'(.+?)\s*\(([^()]+)\)',table['table_name'])
        if match:
            base=re.sub(r'\s+','',match[1])
            families[base][match[2]].append(table)
    checked=0
    for base,variants in families.items():
        if len(variants)<2:
            continue
        pair=list(variants)[:2]
        q=base+' '+pair[0]+', '+pair[1]+' 추이'
        got={s['table_id'] for s in selections(q,agent.resolver.tables)}
        # Names that differ only in spaces are deliberately ambiguous.
        normalized_base=re.sub('[^a-z0-9가-힣]','',base.lower())
        all_equivalent=[t for t in agent.resolver.tables if (m:=re.fullmatch(r'(.+?)\s*\(([^()]+)\)',t['table_name'])) and re.sub('[^a-z0-9가-힣]','',m[1].lower())==normalized_base and m[2] in pair]
        if len(all_equivalent)>2:
            assert got==set(),q
        else:
            assert got=={variants[v][0]['table_id'] for v in pair},q
        checked+=1
    assert checked>=58
