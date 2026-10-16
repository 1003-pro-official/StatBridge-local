import asyncio,time,threading
from types import SimpleNamespace
import pytest
from statbridge_mcp.statistics_batch import get_statistics_batch
from mcp_gateway import McpToolGateway

def test_public_tools_are_four_business_operations():
 from statbridge_mcp.server import mcp
 assert {t.name for t in asyncio.run(mcp.list_tools())}=={'search_tables','get_table_metadata','get_statistics','get_statistics_batch'}

class Fake:
 def __init__(self):self.calls=[];self.active=0;self.peak=0;self.lock=threading.Lock()
 def get_statistics(self,**kw):
  with self.lock:self.calls.append(kw);self.active+=1;self.peak=max(self.peak,self.active)
  time.sleep(.06)
  with self.lock:self.active-=1
  if kw['table_id']=='BAD':raise ValueError('failed apiKey=private-secret')
  return {'status':'success','source':'fixture','rows':[{'TBL_ID':kw['table_id'],'DT':'12.5'}]}

def test_order_dedup_bounded_parallel_and_failure():
 f=Fake();r=McpToolGateway(f).get_statistics_batch([{'table_id':v,'request_id':str(i)} for i,v in enumerate(['A','B','A','BAD'])])
 assert r['status']=='partial' and len(f.calls)==3 and f.peak<=3
 assert [x['request_id'] for x in r['results']]==['0','1','2','3']
 assert r['results'][0]['data']==r['results'][2]['data']
 assert 'private-secret' not in str(r)
 assert r['results'][0]['data']['rows'][0]['DT']=='12.5'

def test_invalid_batch_is_rejected_before_any_fetch_and_timeout_returns():
 f=Fake()
 with pytest.raises(ValueError):get_statistics_batch(f,[{'table_id':'A'},{'table_id':'B','start_period':'2025','end_period':'2020'}])
 assert not f.calls
 started=time.monotonic();r=get_statistics_batch(f,[{'table_id':'A'}],timeout_seconds=.01)
 assert time.monotonic()-started<.05 and r['results'][0]['status']=='timeout'
 time.sleep(.07)

@pytest.mark.parametrize('query',['compare','두 지표 원자료를 비교해줘','전년동기 대비 증가율 말고 잔액 비교'])
def test_runtime_uses_gateway_batch_without_dropping_series(query):
 from agent_runtime import StatBridgeAgent
 f=Fake();a=object.__new__(StatBridgeAgent);a.service=McpToolGateway(f);a.ncp=SimpleNamespace(configured=False)
 a.validate_resolution=lambda q,r,**kwargs:r
 plans=[{'table_id':x,'table_name':x,'item_id':'I','classifications':{},'frequency':'M','start_period':'202401','end_period':'202402','exact_params':{}} for x in ['A','B']]
 r=a.execute_resolution(query,{'status':'resolved','api_plans':plans},generate_answer=False)
 assert r['execution']['status']=='success',r['execution']
 assert len(r['execution']['sources'])==2 and f.peak==2
 assert len(r['execution']['rows'])==2
 assert all(call['start_period']=='202401' for call in f.calls)
 assert 'calculations' not in r['execution']


def test_twenty_requests_complete_with_bounded_workers():
 f=Fake();r=get_statistics_batch(f,[{'table_id':str(i)} for i in range(20)])
 assert r['status']=='success' and len(r['results'])==20
 assert f.peak<=3 and len(f.calls)==20


def test_catalog_preflight_rejects_invalid_item_before_fetch():
 f=Fake();f.store=SimpleNamespace(get=lambda _:SimpleNamespace(frequencies=['M'],items=[{'item_id':'VALID'}],dimensions=[]))
 with pytest.raises(ValueError,match='항목'):
  get_statistics_batch(f,[{'table_id':'A','item_id':'VALID'},{'table_id':'B','item_id':'INVALID'}])
 assert f.calls==[]


def test_rate_limit_wait_cannot_exceed_batch_deadline():
 from statbridge_mcp.kosis_client import RateLimiter,KosisRequestDeferred
 limiter=RateLimiter(1,min_delay=0,max_delay=0)
 limiter.calls.append(time.monotonic())
 start=time.monotonic()
 with pytest.raises(KosisRequestDeferred) as result:limiter.wait(deadline=start+20)
 assert time.monotonic()-start<.1
 assert 59<=result.value.retry_after_seconds<=61
 assert len(limiter.calls)==1


def test_batch_preserves_retry_guidance_and_clears_worker_deadline():
 class Deferred:
  def __init__(self):self.client=SimpleNamespace(thread_sessions=threading.local());self.seen=[]
  def get_statistics(self,**kwargs):
   self.seen.append(self.client.thread_sessions.deadline)
   return {'status':'busy','error':'약 60초 후 다시 시도해 주세요.','retry_after_seconds':60,'rows':[]}
 f=Deferred();r=get_statistics_batch(f,[{'table_id':'A'}])
 assert r['results'][0]['status']=='busy'
 assert r['results'][0]['retry_after_seconds']==60
 assert '60초' in r['results'][0]['error'] and f.seen[0]>time.monotonic()
 from statbridge_mcp.statistics_batch import POOL
 # A reused worker must never inherit a prior request deadline.
 checks=[POOL.submit(lambda:hasattr(f.client.thread_sessions,'deadline')) for _ in range(3)]
 assert all(not future.result() for future in checks)
