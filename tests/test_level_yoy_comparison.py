import copy
import pytest
from level_yoy_comparison import wants_level_and_yoy,with_comparison_history,append_yoy
from output_agent import OutputAgent
from test_research_chart_edit import source

def rows():
 return [{'_SOURCE_SERIES_ID':'t','_SERIES_LABEL':'가계신용 잔액','UNIT_NM':'십억원','_FREQUENCY':'Q','PRD_DE':p,'DT':str(v)} for p,v in [('202001',100),('202002',200),('202003',0),('202101',110),('202102',180),('202103',15),('202104',20)]]

def test_query_only_explicit_level_and_yoy():
 assert wants_level_and_yoy('가계신용 잔액과 전년동기 대비 증가율을 비교해줘')
 assert not wants_level_and_yoy('가계신용 잔액 추이')
 assert not wants_level_and_yoy('생산자물가 전년동기 대비 증가율')

def test_warmup_preserves_requested_bounds_and_adds_calendar_year():
 req=[{'start_period':'202101','end_period':'202604','frequency':'Q'}];before=copy.deepcopy(req)
 assert with_comparison_history(req)[0]['start_period']=='202001'
 assert req==before

def test_derived_values_calendar_matching_and_explicit_missing():
 original=rows();before=copy.deepcopy(original)
 out,calc,missing=append_yoy(original,[{'table_id':'t','start_period':'202101','end_period':'202104'}])
 assert len(out)==6 and len(calc)==2
 assert calc[0]['value']==pytest.approx(10)
 assert calc[1]['value']==pytest.approx(-10)
 assert missing==['202103','202104']
 assert all(r['PRD_DE']>='202101' for r in out)
 assert original==before and calc[0]['basePeriod']=='202001'

def test_no_comparison_base_does_not_fabricate_a_rate():
 with pytest.raises(ValueError,match='전년 같은'):append_yoy(rows()[3:],[{'table_id':'t','start_period':'202101','end_period':'202104'}])

def test_initial_output_automatically_binds_level_line_and_rate_right_bar():
 data=source(1);raw=rows();out,calc,missing=append_yoy(raw,[{'table_id':'t','start_period':'202101','end_period':'202104'}])
 data['execution'].update(rows=out,calculations=calc)
 data.pop('request_validation',None);data['api_plans']=[];data.pop('api_plan',None)
 result=OutputAgent().prepare(data,{'quick_output':True,'natural_language':'가계신용 잔액과 전년동기 대비 증가율','chart_type':'auto'})
 assert len(result['visualization']['series'])==2
 state=result['chartState'];rate=state['secondary_axis_series'][0]
 assert state['layout']=='combined' and state['series_chart_types'][rate]=='bar'
 assert state['axes']['y2']['title_placement']=='top'
 assert result['explanation']['calculations']==calc
 assert any('서버에서 계산' in w for w in result['warnings'])

def test_execution_fetches_warmup_once_but_preserves_requested_period():
 from types import SimpleNamespace
 from agent_runtime import StatBridgeAgent
 captured=[]
 def batch(requests):
  captured.extend(requests)
  return {'results':[{'status':'success','data':{'status':'success','source':'synthetic','rows':rows()}}]}
 plan={'table_id':'t','table_name':'가계신용 잔액','item_id':'i','classifications':{},'frequency':'Q','start_period':'202101','end_period':'202104','exact_params':{}}
 dummy=SimpleNamespace(validate_resolution=lambda q,r,**kw:r,service=SimpleNamespace(get_statistics_batch=batch),resolver=SimpleNamespace(tables=[{'table_id':'t','table_name':'가계신용 잔액'}]))
 result=StatBridgeAgent.execute_resolution(dummy,'가계신용 잔액과 전년동기 대비 증가율 비교',{'status':'resolved','api_plan':plan},generate_answer=False)
 assert result['execution']['status']=='success'
 assert len(captured)==1 and captured[0]['start_period']=='202001'
 assert result['api_plan']['start_period']=='202101'
 assert result['execution']['comparisonFetchPeriods'][0]['start']=='202001'
 assert all(row['PRD_DE']>='202101' for row in result['execution']['rows'])
 assert len(result['execution']['calculations'])==2

def test_rate_only_request_does_not_duplicate_raw_series():
 out,calc,_=append_yoy(rows(),[{'table_id':'t','start_period':'202101','end_period':'202104'}],{'t':'yoy'})
 assert len(out)==2 and len(calc)==2
 assert all(row['UNIT_NM']=='%' and row.get('_DERIVED_CALCULATION') for row in out)

def test_undefined_rates_offer_correction_instead_of_blind_retry():
 from recovery import recovery_question
 for message in ['전년 같은 시점의 값이 없거나 0이어서 증가율을 계산할 수 없습니다.','금리·비중·비율의 전년동기 비교는 증가율(%)과 차이(%p)가 다릅니다.']:
  recovery=recovery_question(message)
  assert recovery['issue']=='calculation'
  assert recovery['preserveState']
  assert not any(c['id']=='retry' for c in recovery['choices'])
  assert any(c['id']=='revise' for c in recovery['choices'])

def test_rate_difference_uses_percentage_points_and_zero_base_is_valid():
 from level_yoy_comparison import measurement_mode
 data=[{**r,'UNIT_NM':'연%'} for r in rows()]
 assert measurement_mode('대출금리 원자료와 전년동기 대비 차이')=='level_and_difference'
 out,calc,missing=append_yoy(data,[{'table_id':'t','start_period':'202101','end_period':'202104'}],{'t':'level_and_difference'})
 assert len(calc)==3 and calc[0]['unit']=='%p'
 assert calc[0]['value']==10 and calc[1]['value']==-20 and calc[2]['value']==15
 assert missing==['202104']

def test_index_difference_has_point_unit():
 data=[{**r,'UNIT_NM':'2020＝100'} for r in rows()]
 out,calc,_=append_yoy(data,[{'table_id':'t','start_period':'202101','end_period':'202104'}],{'t':'difference'})
 assert calc[0]['unit']=='포인트' and all(r['UNIT_NM']=='포인트' for r in out)
