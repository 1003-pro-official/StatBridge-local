"""Catalog reference boundaries and complete classification combinations."""
from canonical_request_planner import selections, instruction_text
from request_period import explicit_period


def table(tid,name):
    return {'table_id':tid,'table_name':name,'dimensions':[
        {'level':1,'api_param':'objL1','representative_value_id':'total','values':[{'value_id':'total','value_name':'전체'},{'value_id':'a','value_name':'제조업'},{'value_id':'b','value_name':'서비스업'}]},
        {'level':2,'api_param':'objL2','values':[{'value_id':'base','value_name':'2024 기준'},{'value_id':'other','value_name':'다른 기준'}]}]}


def test_title_does_not_select_its_classification():
    t=table('DT_A','제조업 통계(2009~)')
    got=selections('「제조업 통계(2009~)」 자료를 찾아줘',[t])
    assert got[0]['dimension_hits'][0]['value_id']=='total'
    assert explicit_period(instruction_text('「제조업 통계(2009~)」 자료를 찾아줘',[t])) is None


def test_multiple_and_fixed_classifications_keep_every_series():
    t=table('DT_A','산업 통계')
    q='「산업 통계」에서 1번째 분류의 「제조업」와 「서비스업」 비교. 2번째 분류는 「2024 기준」로 고정해줘'
    got=selections(q,[t])
    assert [g['dimension_hits'][0]['value_id'] for g in got]==['a','b']
    assert all(g['dimension_hits'][1]['value_id']=='base' for g in got)
    assert explicit_period(instruction_text(q,[t])) is None


def test_identifier_belongs_to_its_table_only():
    tables=[table('DT_A','같은 통계'),table('DT_B','같은 통계'),table('DT_C','다른 통계')]
    got=selections('「같은 통계」 [DT_A]와 「다른 통계」 자료 비교',[*tables])
    assert [g['table_id'] for g in got]==['DT_A','DT_C']
    assert selections('「같은 통계」 자료',[*tables])==[]


def test_exact_spaces_take_priority_and_external_dates_survive():
    tables=[table('DT_A','산업별통계(2010~)'),table('DT_B','산업별 통계(2010~)')]
    q='「산업별 통계(2010~)」 자료를 2020년부터 2025년까지'
    assert selections(q,tables)[0]['table_id']=='DT_B'
    assert explicit_period(instruction_text(q,tables))['start']=='2020-01-01'


def test_four_duplicate_titles_accept_prefix_ids_in_reversed_order():
    tables=[table('DT_A','같은 표'),table('DT_B','같은 표'),table('DT_C','다른 표'),table('DT_D','다른 표')]
    q='[DT_D] 다른 표; [DT_C] 다른 표; [DT_B] 같은 표; [DT_A] 같은 표 각각 찾아줘'
    assert [x['table_id'] for x in selections(q,tables)]==['DT_D','DT_C','DT_B','DT_A']


def test_mixed_id_positions_do_not_leak_to_adjacent_title():
    tables=[table('DT_A','첫 통계'),table('DT_B','둘째 통계'),table('DT_C','셋째 통계'),table('DT_D','넷째 통계')]
    q='「첫 통계」 [DT_A]; [DT_B] 둘째 통계; 「셋째 통계」; [DT_D] 넷째 통계'
    assert [x['table_id'] for x in selections(q,tables)]==['DT_A','DT_B','DT_C','DT_D']


def test_conflicting_or_unknown_ids_are_not_grounded():
    tables=[table('DT_A','첫 통계'),table('DT_B','둘째 통계')]
    assert selections('[DT_B] 첫 통계',tables)==[]
    assert selections('[DT_Z] 첫 통계',tables)==[]
    assert selections('[DT_A] 첫 통계 [DT_B]',tables)==[]
    assert selections('「첫 통계」 [DT_A] 와 알 수 없는 [DT_Z]',tables)==[]
