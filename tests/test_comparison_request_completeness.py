import pytest
from types import SimpleNamespace
from agent_runtime import StatBridgeAgent
from request_match_guard import missing_requested_scopes,catalog_mentions
from level_yoy_comparison import measurement_mode,comparison_modes,append_yoy
from chart_data_transforms import previous_year_period

@pytest.fixture(scope='module')
def agent():return StatBridgeAgent(object(),ncp_client=SimpleNamespace(configured=False,settings=SimpleNamespace(classifier_model='disabled'),clarify_question=lambda q,r,s:r.get('question','기준을 선택해 주세요.')))

@pytest.mark.parametrize('query,expected',[
 ('경상수지와 경제심리지수를 비교해줘',{'경상수지','경제심리'}),
 ('생산자물가지수 총지수와 경제심리지수를 비교해줘',{'생산자물가','경제심리'}),
 ('생산자물가지수 총지수와 가계신용 잔액을 비교해줘',{'생산자물가','가계신용'})])
def test_independent_requested_subjects_are_never_silently_dropped(agent,query,expected):
 r=agent.resolve(query)
 assert r['status'] in {'resolved','need_clarification'}
 if r['status']=='resolved':
  names=' '.join(p['table_name'] for p in r['api_plans'])
  assert all(name in names for name in expected)
 else:assert r.get('options') and r['state'].get('_user_query')==query

def test_all_349_tables_detect_deleted_comparison_partner(agent):
 tables=list(agent.tables_by_id.values());assert len(tables)==349
 for i,t in enumerate(tables):
  other=tables[(i+1)%len(tables)]
  q=f'「{t["table_name"]}」 [{t["table_id"]}]와 「{other["table_name"]}」 [{other["table_id"]}] 비교'
  assert missing_requested_scopes(q,[{'table_id':t['table_id']}],tables),t['table_id']

def test_generic_level_and_growth_requests_are_not_household_credit_specific():
 for subject in ['생산자물가지수','수출금액','가계신용 잔액','인원','건수','통화량 수준']:
  assert measurement_mode(subject+'와 전년동기 대비 증가율 비교')=='level_and_yoy'
 assert measurement_mode('생산자물가지수 전년동기 대비 증가율')=='yoy'
 assert measurement_mode('가계신용 잔액과 생산자물가지수 전년동기 대비 증가율 비교')=='yoy'
 assert measurement_mode('전년동기 대비 증가율 말고 잔액')=='raw'

def test_transform_is_scoped_to_its_own_table():
 tables=[{'table_id':'a','table_name':'가계신용(분기)'},{'table_id':'b','table_name':'생산자물가지수(기본분류)'}]
 modes=comparison_modes('가계신용 잔액과 생산자물가지수 전년동기 대비 증가율 비교',[{'table_id':'a'},{'table_id':'b'}],tables)
 assert modes=={'a':'raw','b':'yoy'}

@pytest.mark.parametrize('frequency,period,previous',[('D','20240229','20230229'),('H','202402','202302'),('S','202401','202301'),('M','202412','202312'),('Q','202404','202304'),('Y','2024','2023')])
def test_calendar_aligned_comparison_periods(frequency,period,previous):assert previous_year_period(period,frequency)==previous

def test_historical_title_base_does_not_hijack_current_total_index(agent):
 matches=catalog_mentions('생산자물가지수 총지수',agent.resolver.tables)
 assert all('DT_404Y017' not in m['table_ids'] for m in matches)

def test_catalog_named_request_accepts_measure_without_footnote_number(agent):
 result=agent.resolve('예금은행 대출금리(신규취급액 기준)의 대출평균 원자료와 전년동기 대비 증가율을 2024년 월별로 비교해줘')
 assert result['status']=='resolved'
 assert not any(c.get('_missing_dimensions') for c in result.get('selected_tables',[]))
 assert '대출평균' in str(result['api_plan'].get('series_label','')) or result['api_plan']['classifications']
