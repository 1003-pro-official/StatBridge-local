"""Regression contracts independent of evaluation case IDs and numeric answers."""
from types import SimpleNamespace
from catalog_classifications import refresh_classifications
from semantic_catalog_planner import matches
from catalog_request_planner import selections


def test_calendar_months_are_not_numeric_classifications():
    dimension={'values':[{'value_id':'range','value_name':'1~2%'},
                         {'value_id':'forecast','value_name':'향후1년 기대인플레이션율'}]}
    found=matches('2021년 1월부터 2022년 12월까지 향후1년 기대인플레이션율',dimension)
    assert [v['value_id'] for v in found]==['forecast']
    assert [v['value_id'] for v in matches('1~2% 구간',dimension)]==['range']


def test_metadata_refresh_restores_values_beyond_language_index():
    table={'table_id':'DT_TEST','dimensions':[{'api_param':'objL1','values':[
        {'value_id':'a','value_name':'이전 이름','aliases':['별칭']}]}]}
    class Store:
        def table_ids(self):return ['DT_TEST']
        def get(self,tid):return SimpleNamespace(dimensions=[{'mcp_param':'objL1','values':[
            {'class_id':'a','class_name':'자산'},{'class_id':'b','class_name':'부채'}]}])
    refresh_classifications([table],Store())
    assert table['dimensions'][0]['values']==[
        {'value_id':'a','value_name':'자산','aliases':['별칭']},
        {'value_id':'b','value_name':'부채'}]


def test_explicit_id_preserves_multiple_named_classifications():
    table={'table_id':'DT_TEST','table_name':'생산 통계(월별)','frequency':'M',
           'item_names':['생산'],'units':['건'],'dimensions':[{'api_param':'objL1','values':[
               {'value_id':'a','value_name':'제조업'},{'value_id':'b','value_name':'서비스업'}]}]}
    ordinary=selections('생산 통계(월별) 제조업과 서비스업 자료를 보여줘',[table])
    explicit=selections('생산 통계(월별) 제조업과 서비스업 [DT_TEST] 자료를 보여줘',[table])
    assert ordinary and explicit==ordinary


def test_refresh_does_not_add_an_identically_named_series_to_a_query():
    table={'table_id':'DT_TEST','dimensions':[{'api_param':'objL1','values':[
        {'value_id':'current','value_name':'특정 품목'}]}]}
    class Store:
        def table_ids(self):return ['DT_TEST']
        def get(self,tid):return SimpleNamespace(dimensions=[{'mcp_param':'objL1','values':[
            {'class_id':'older','class_name':'특정 품목'},
            {'class_id':'current','class_name':'특정 품목'}]}])
    refresh_classifications([table],Store())
    dimension=table['dimensions'][0]
    assert {v['value_id'] for v in dimension['values']}=={'older','current'}
    assert [v['value_id'] for v in matches('특정 품목 자료',dimension)]==['current']


def test_published_growth_measure_and_aggregate_are_not_arithmetic_commands():
    from derived_indicator_planner import is_derived_request
    assert not is_derived_request('기업경영분석 제조업 매출액증가율 자료를 보여줘')
    assert not is_derived_request('전자지급결제대행 이용금액 합계 [DT_TEST] 자료를 표로 보여줘')
    assert is_derived_request('기업경영분석 매출액증가율의 평균을 계산해줘')


def test_institution_is_not_a_second_deposit_measure():
    from request_match_guard import structure_request
    assert structure_request('예금취급기관 제조업 산업별대출금 잔액')['metrics']==['대출']
    assert '수신' in structure_request('예금취급기관 대출과 예금 수신 자료')['metrics']


def test_selected_classification_can_cover_a_same_named_table_mention():
    from request_match_guard import missing_requested_scopes
    tables=[{'table_id':'DT_MAIN','table_name':'국제수지','item_names':['국제수지'],
             'dimensions':[{'api_param':'objL1','values':[{'value_id':'balance','value_name':'경상수지'}]}]},
            {'table_id':'DT_OTHER','table_name':'경상수지(계절조정)','dimensions':[]}]
    selected=[{'table_id':'DT_MAIN','classifications':{'objL1':'balance'}}]
    assert missing_requested_scopes('국제수지 경상수지',selected,tables)==[]
    assert missing_requested_scopes('국제수지 경상수지(계절조정)',selected,tables)


def test_selection_reuse_invalidates_on_catalog_change_and_returns_copies(monkeypatch):
    import agent_runtime
    from threading import RLock
    agent=object.__new__(agent_runtime.StatBridgeAgent)
    agent.resolver=SimpleNamespace(tables=[{'table_id':'DT_TEST','dimensions':[]}])
    agent._catalog_selection_cache={}
    agent._catalog_selection_lock=RLock()
    calls=[]
    def select(query,tables):
        calls.append(query)
        return [{'table_id':tables[0]['table_id']}]
    monkeypatch.setattr(agent_runtime,'catalog_selections',select)
    first=agent._catalog_candidates('질문')
    first[0]['table_id']='tampered'
    assert agent._catalog_candidates('질문')==[{'table_id':'DT_TEST'}]
    assert len(calls)==1
    agent.resolver.tables[0]['table_id']='DT_CHANGED'
    assert agent._catalog_candidates('질문')==[{'table_id':'DT_CHANGED'}]
    assert len(calls)==2


def test_title_owned_aggregate_is_kept_only_without_a_specific_classification():
    from semantic_catalog_planner import dimension_matches
    table={'table_name':'통계 부채'}
    dimension={'values':[{'value_id':'total','value_name':'통계 부채'},
                         {'value_id':'short','value_name':'단기 부채'}]}
    assert [v['value_id'] for v in dimension_matches('통계 부채 자료',table,dimension)]==['total']
    assert [v['value_id'] for v in dimension_matches('통계 부채 중 단기 부채 자료',table,dimension)]==['short']
