"""Bare requests must not need API/file instructions to recover missing inputs."""
import pytest
from request_period import explicit_period
from derived_request_period import requested_display_period
from test_derived_supplement import setup

QUESTION='2023년 1월부터 4월까지 생산자물가지수(기본분류) 총지수를 소비자물가지수 총지수로 나눈 비율을 계산해줘. 두 지수는 2020=100으로 맞춰줘'

@pytest.mark.parametrize('question',[
 QUESTION,QUESTION.replace('2020=100','2020＝100'),QUESTION.replace('2020=100','2020년 = 100'),
 QUESTION.replace('2023년 1월부터 4월까지','2023년 1월부터 2023년 4월까지'),
 QUESTION.replace('2023년 1월부터 4월까지','2023년 1월~4월까지'),
 QUESTION.replace('2023년 1월부터 4월까지','2023년 1월에서 4월까지'),
 '2020=100 기준의 생산자물가지수를 2023년 1월부터 4월까지 보여줘',
])
def test_index_base_never_becomes_observation_end_year(question):
 for parser in [explicit_period,requested_display_period]:
  r=parser(question)
  assert (r['start'],r['end'])==('2023-01-01','2023-04-30')

@pytest.mark.parametrize('question,start,end',[
 ('2024년 2월 27일부터 29일까지 변화율','2024-02-27','2024-02-29'),
 ('2023년 1월 15일부터 4월 20일까지 비교, 2020=100','2023-01-15','2023-04-20'),
 ('2023년 1분기부터 4분기까지 2020=100 기준','2023-01-01','2023-12-31'),
 ('2023년 1월부터 12월까지 2015＝100으로 맞춰줘','2023-01-01','2023-12-31'),
])
def test_inherited_date_parts_preserve_calendar_bounds(question,start,end):
 r=explicit_period(question);assert (r['start'],r['end'])==(start,end)

@pytest.mark.parametrize('question',[
 '2023년 4월부터 1월까지 2020=100',
 '2024년 1월부터 2023년 4월까지 2020=100',
 '2023년 2월 27일부터 29일까지 2020=100',
])
def test_invalid_or_reverse_dates_are_still_rejected(question):
 with pytest.raises(ValueError):explicit_period(question)


def test_multiple_comparison_periods_are_not_silently_merged():
 assert explicit_period('2023년 1월부터 4월까지와 2024년 1월부터 4월까지 비교. 2020=100') is None


def test_bare_question_automatically_requests_missing_file_via_real_http_contract(monkeypatch,setup):
 import bridge_api as api
 from authenticated_client import TestClient
 service,calls,_,_=setup
 service.base.planner.client.configured=True
 monkeypatch.setattr(api.agent.workflow,'derived_runtime',service.base)
 monkeypatch.setattr(api,'derived_supplements',service)
 # No API / file / upload instruction appears in this user sentence.
 q='2020년 1월부터 4월까지 경제심리지수를 사용자 비용지수로 나눈 비율을 계산해줘. 두 지수는 2015=100으로 맞춰줘'
 result=TestClient(api.app).post('/api/query',json={'query':q})
 assert result.status_code==200,result.text
 d=result.json();assert d['supplement']['missing'] and len(d['supplement']['available'])==1
 assert len(calls)==1 and calls[0]['start_period']=='202001' and calls[0]['end_period']=='202004'
 assert not d['chart']


@pytest.mark.parametrize('question',[
 QUESTION,'지표 A를 지표 B로 나누어 비율을 계산해줘','두 지표의 격차를 구해줘',
 '가격과 수량의 가중 평균을 계산해줘','두 계열을 곱해서 보여줘','두 지수의 차이를 보여줘',
 '명목 금액을 실질화해줘','두 계열의 평균을 구해줘','두 계열 합계를 보여줘',
 '앞 값에서 뒤 값을 빼줘','앞 값과 뒤 값을 더한 결과를 보여줘',
])
def test_combined_inputs_checked_without_api_or_upload_instruction(question):
 from derived_indicator_planner import needs_source_preflight
 assert needs_source_preflight(question)


def test_simple_single_series_change_does_not_add_unneeded_preflight():
 from derived_indicator_planner import needs_source_preflight
 assert not needs_source_preflight('2023년 생산자물가지수 총지수의 전년동월 대비 변화율을 계산해줘')


def test_model_search_exhaustion_is_not_proof_of_zero_api_inputs(monkeypatch):
 from types import SimpleNamespace as NS
 import derived_availability
 from derived_indicator_runtime import DerivedIndicatorRuntime
 r=object.__new__(DerivedIndicatorRuntime);r.api_inventory=object()
 r.catalog=NS(allow_file_inputs=False)
 r.planner=NS(plan=lambda *a,**kw:{'status':'need_details','unsupported':True,'usage':[{'stage':'planning'}]})
 verified={'status':'need_details','availability':{'status':'checked','sources':[{'status':'available'},{'status':'not_found'}],'questions':[]},'usage':[{'stage':'api_check'}]}
 monkeypatch.setattr(derived_availability,'check_availability',lambda *a:verified)
 result=r.plan('로그 지수')
 assert not result.get('unsupported') and result['availability']['sources'][0]['status']=='available'
 assert len(result['usage'])==2


def test_automatic_checked_inputs_open_missing_file_without_replanning(monkeypatch,setup):
 import bridge_api as api
 from authenticated_client import TestClient
 service,calls,slot,final=setup
 periods=[{'start':'202001','end':'202004','frequency':'M'}]
 verified={'status':'need_details','availability':{'status':'checked','questions':[], 'sources':[
  {'status':'available','selection':final['sources'][0],'periods':periods},
  {'status':'not_found','name':slot['required_data'],'reason':'missing','periods':periods}]}}
 monkeypatch.setattr(api.agent.workflow,'invoke',lambda **kw:verified)
 monkeypatch.setattr(api,'derived_supplements',service)
 r=TestClient(api.app).post('/api/query',json={'query':'2020년 1월부터 4월까지 경제심리지수를 다른 지수로 나눈 비율을 계산해줘'})
 assert r.status_code==200,r.text
 assert r.json()['supplement']['missing'] and len(calls)==1


def test_verified_source_metadata_skips_duplicate_model_lookup(setup):
 from derived_indicator_planner import DerivedIndicatorPlanner
 from test_dynamic_derived_indicators import Model,plan
 service,_,_,_=setup
 p=plan(service.base.catalog,'inverse')
 model=Model([{'action':'plan','plan':p.model_dump()},{'approved':True,'reason':'independent mathematical inverse'}])
 result=DerivedIndicatorPlanner(model,service.base.catalog).plan('2020년 1월부터 4월까지 경제심리지수의 역수를 계산해줘',verified_sources=[p.sources[0].model_dump()])
 assert result['status']=='planned' and len(result['usage'])==2
