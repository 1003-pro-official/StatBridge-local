from types import SimpleNamespace as NS
import pytest
from derived_private_inputs import private_metric, require_private_input
from derived_indicator_planner import is_derived_request, DerivedIndicatorPlanner
from expression_tree_validator import DerivedValidationError

@pytest.mark.parametrize('query',[
 '우리 회사의 월별 원재료 구매비용을 생산자물가지수로 조정한 실질 비용을 계산해줘',
 '당사 매출액을 물가로 조정해줘','자사 인건비 실질화',
 '실질 비용을 계산해줘',
])
def test_routes_private_and_real_costs_to_derived(query):
 assert is_derived_request(query)

def test_private_missing_short_circuits_provider():
 class Client:
  def request(self,*a,**kw):raise AssertionError('unnecessary GPT call')
 planner=DerivedIndicatorPlanner(Client(),NS())
 result=planner.plan('2023년 우리 회사 원재료 구매비용을 조정해줘')
 assert result['unsupported'] and result['usage']==[]
 assert 'missing' not in result
 assert '다시 작성' in result['question']
 assert result['status']=='need_details'

@pytest.mark.parametrize('query',['한국은행 생산자물가지수 조회','우리 회사 자료는 제외하고 생산자물가지수만 보여줘'])
def test_no_false_private_requirements(query):
 assert private_metric(query) is None

@pytest.mark.parametrize('tid,name,connected',[
 ('DT_404Y014','회사 원재료구매비용',True),
 ('USER_FILE:unrelated','회사 매출액',True),
 ('USER_FILE:cost','회사 원재료구매비용',False),
])
def test_model_cannot_substitute_api_unrelated_or_unused_file(tid,name,connected):
 source=NS(alias='cost',table_id=tid)
 plan=NS(sources=[source],nodes=[NS(id='result',inputs=['cost'] if connected else ['ppi'])],outputs=[NS(node='result')])
 catalog=NS(get_table_metadata=lambda _: {'table_name':name})
 with pytest.raises(DerivedValidationError,match='지원하지 않습니다'):
  require_private_input('우리 회사 원재료 구매비용 실질화',plan,catalog)

def test_even_uploaded_private_file_is_not_supported():
 plan=NS(sources=[NS(alias='cost',table_id='USER_FILE:cost')],nodes=[NS(id='deflated',inputs=['cost','ppi'])],outputs=[NS(node='deflated')])
 with pytest.raises(DerivedValidationError,match='지원하지 않습니다'):
  require_private_input('우리 회사 원재료 구매비용 실질화',plan,NS(get_table_metadata=lambda _:{'table_name':'우리 회사 원재료 구매비용'}))


def test_http_private_request_never_creates_graph_or_upload_workspace(monkeypatch):
 import bridge_api as api
 from authenticated_client import TestClient
 def forbidden(*args,**kwargs):raise AssertionError('unsupported private data must not call supplements')
 monkeypatch.setattr(api.derived_supplements,'start',forbidden)
 client=TestClient(api.app)
 r=client.post('/api/query',json={'query':'2023년부터 2025년까지 우리 회사 원재료 구매비용을 생산자물가지수로 조정한 실질 비용을 계산해줘'})
 assert r.status_code==200,r.text
 data=r.json()
 assert data['recovery']['issue']=='unsupported'
 assert data['recovery']['choices'][0]['label']=='질문 다시 작성'
 assert not data['chart'] and not data.get('supplement') and not data.get('outputSessionId')
 assert data['state']=={}


@pytest.mark.parametrize('query',[
 '사내 매출을 보여줘','우리 회사 급여를 월별로 보여줘','당사 재고를 구해줘',
 '개인 구매비용을 조정해줘','특정 기업 영업이익을 구해줘',
 '우리 회사 매출에서 비용을 빼고 보여줘','원재료 구매비용(우리 회사)을 계산해줘',
])
def test_private_business_inputs_always_require_rewrite(query):
 assert private_metric(query)
 assert is_derived_request(query)

@pytest.mark.parametrize('query',[
 '우리 회사 매출은 제외하고 생산자물가지수만 보여줘',
 '개인소비지출 통계를 보여줘','기업경영분석 매출액증가율을 조회해줘',
])
def test_public_statistics_not_confused_with_private_ownership(query):
 assert private_metric(query) is None
