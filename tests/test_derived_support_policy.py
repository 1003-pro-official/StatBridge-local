"""Policy tests use synthetic observations, never claimed as API verification."""
from types import SimpleNamespace as NS
import pytest
from derived_support_policy import assessment_scope,require_api_dependency
from expression_tree_validator import DerivedValidationError
from test_derived_supplement import setup

@pytest.mark.parametrize('statuses,expected',[
 (['available'],'api_only'),(['available','not_found'],'mixed'),
 (['not_found'],'unsupported'),(['not_found','not_found'],'unsupported'),
 (['api_error','not_found'],'verification_pending'),(['selection_required'],'verification_pending'),
 (['data_absent'],'verification_pending'),([], 'verification_pending'),
])
def test_scope_distinguishes_absence_from_failed_verification(statuses,expected):
 assert assessment_scope({'status':'checked','sources':[{'status':s} for s in statuses]})==expected

@pytest.mark.parametrize('connected',[False,True])
def test_only_api_inputs_reaching_an_output_count(connected):
 p=NS(sources=[NS(alias='api',table_id='DT_APPROVED'),NS(alias='file',table_id='USER_FILE:f')],
      nodes=[NS(id='n',inputs=['api','file'] if connected else ['file'])],outputs=[NS(node='n')])
 seen=[];cat=NS(validate_source_selection=lambda s:seen.append(s.alias))
 if connected:
  require_api_dependency(p,cat);assert seen==['api']
 else:
  with pytest.raises(DerivedValidationError,match='最終|최종'):require_api_dependency(p,cat)


def test_invalid_api_selection_does_not_count_as_an_anchor():
 p=NS(sources=[NS(alias='api',table_id='DT_OUTSIDE')],nodes=[],outputs=[NS(node='api')])
 def invalid(source):raise DerivedValidationError('outside')
 with pytest.raises(DerivedValidationError,match='outside'):require_api_dependency(p,NS(validate_source_selection=invalid))


def test_confirmed_api_with_missing_file_keeps_upload_flow(setup):
 service,calls,_,_=setup
 result=service.start(1,'2020년 1월부터 2020년 4월까지 경제심리지수를 사용자 비용지수로 나누어 계산해 주세요.')
 assert len(calls)==1 and len(result['supplement']['available'])==1
 assert result['supplement']['missing'] and not result.get('unsupported')


def test_api_timeout_never_opens_upload_or_reports_unsupported(setup):
 service,_,_,_=setup
 def timeout(**kw):raise TimeoutError()
 service.base.gateway.get_statistics=timeout
 result=service.start(1,'2020년 1월부터 2020년 4월까지 경제심리지수를 파일 지수로 나누어 계산해 주세요.')
 assert result['recovery']['issue']=='source_verification'
 assert not result.get('supplement') and not result.get('unsupported')
 assert not list(service.directory.glob('user-*/*/workspace.json'))


def test_model_file_request_without_api_is_rejected_before_workspace(setup):
 service,_,_,_=setup
 # Independent of planner prompt compliance: service rejects such a proposal.
 runtime=NS(plan=lambda *a,**kw:{'status':'inputs_required','available_sources':[],
   'missing':[{'alias':'external'}],'start_period':'202001','end_period':'202004'})
 service.runtime=lambda w:runtime
 result=service.start(1,'외부 자료만 나누어 계산해줘')
 assert result['unsupported'] and not result.get('supplement')
 assert not list(service.directory.glob('user-*/*/workspace.json'))


def test_api_metadata_or_partial_check_cannot_open_uploads(tmp_path):
 from derived_supplement import DerivedSupplementService
 service=DerivedSupplementService(None,tmp_path)
 for status in ['selection_required','api_error','data_absent']:
  result=service.from_assessment(1,'요청',{'status':'checked','sources':[{'status':status}]})
  assert not result.get('supplement') and not result.get('unsupported')


def test_publication_catalog_is_unverified_search_hints_only():
 from derived_publication_reference import candidates,search_hints
 rows=candidates();assert len(rows)==1766
 assert len({r['id'] for r in rows})==1766
 hints=search_hints('생산자물가 전년동월 상승률',{'DT_404Y014'})
 assert hints and all(set(h['table_ids'])<={'DT_404Y014'} for h in hints)
 assert all('미검증' in h['verification'] for h in hints)
 assert all('formula' not in h and 'plan' not in h for h in hints)


def test_verified_partial_plan_is_reused_without_a_second_model_call(setup):
 service,calls,slot,final=setup
 original=service.runtime
 def runtime(w):
  r=original(w)
  def forbidden(*a,**kw):raise AssertionError('must reuse server partial plan')
  r.plan=forbidden
  return r
 service.runtime=runtime
 partial={'status':'inputs_required','start_period':'202001','end_period':'202004',
          'available_sources':[final['sources'][0]],'missing':[slot], 'usage':[]}
 result=service.start(1,'기존 API 계획과 파일 입력 연결',planning=partial)
 assert len(calls)==1 and result['supplement']['available'] and result['supplement']['missing']


def test_actual_assessment_reuses_selections_without_model_calls(setup):
 service,calls,slot,final=setup
 original=service.runtime
 def runtime(w):
  r=original(w)
  r.plan=lambda *a,**kw:(_ for _ in ()).throw(AssertionError('must not replan'))
  return r
 service.runtime=runtime
 periods=[{'start':'202001','end':'202004','frequency':'M'}]
 checked={'status':'checked','sources':[
  {'status':'available','selection':final['sources'][0],'periods':periods},
  {'status':'not_found','name':'외부 지수','reason':'승인 범위에서 없음','periods':periods}]}
 result=service.from_assessment(1,'경제심리와 외부 지수의 비율',checked)
 assert result['supplement']['missing'] and len(calls)==1
