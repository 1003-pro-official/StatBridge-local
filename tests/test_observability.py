"""Real timing and isolated SDK export contracts, no paid model/provider calls."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from threading import RLock
import pytest
from fastapi import FastAPI,HTTPException
from fastapi.responses import Response
from fastapi.testclient import TestClient
from statbridge_mcp import observability as obs
from observability_middleware import ObservabilityMiddleware,get_trace,STORE

@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv('LANGFUSE_ENABLED','false');STORE.clear()


def test_nested_actual_timings_parenting_and_privacy():
    trace=obs.Trace('request.query');token=obs.CURRENT.set(trace)
    @obs.observed('source.fetch')
    def work(table_id,secret):
        time.sleep(.002);return {'rows':[1,2],'password':secret}
    try:
        with trace.span('request.query'):
            work('DT_ABC','secret-cannot-leak')
    finally:obs.CURRENT.reset(token)
    result=trace.snapshot();assert result['steps'][1]['parentId']==result['steps'][0]['id']
    assert result['durationMs']>=2 and result['steps'][1]['metadata']['row_count']==2
    assert 'secret-cannot-leak' not in json.dumps(result) and result['steps'][1]['metadata']['table_id']=='DT_ABC'

@pytest.mark.parametrize('status,expected',[('need_clarification','awaiting_input'),('data_unavailable','missing_data'),('no_match','unsupported_scope'),('request_failed','failed')])
def test_outcomes_are_not_all_errors(status,expected):assert obs.outcome({'status':status})==expected


def test_caught_failure_still_has_error_without_message_secret():
    trace=obs.Trace('request.query');token=obs.CURRENT.set(trace)
    @obs.observed('plan.validate')
    def validate():
        try:raise ValueError('apiKey=secret-cannot-leak')
        except ValueError as exc:obs.record_failure(exc);return {'status':'data_unavailable'}
    try:validate()
    finally:obs.CURRENT.reset(token)
    result=trace.snapshot();assert result['status']=='failed';assert result['steps'][0]['error']['code']=='validation_failed'
    assert 'secret-cannot-leak' not in json.dumps(result)


def test_parallel_context_does_not_mix_requests():
    def request():
        trace=obs.Trace('request.query');token=obs.CURRENT.set(trace)
        @obs.observed('source.fetch')
        def fetch():return {'rows':[1]}
        try:
            with trace.span('request.query'):
                with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda ctx:ctx.run(fetch),[copy_context(),copy_context()]))
        finally:obs.CURRENT.reset(token)
        return trace.snapshot()
    with ThreadPoolExecutor(max_workers=2) as pool:a,b=pool.map(lambda _:request(),range(2))
    assert a['traceId']!=b['traceId'];assert len(a['steps'])==len(b['steps'])==3
    assert {s['parentId'] for s in a['steps'][1:]}=={a['steps'][0]['id']}


def test_bounded_steps_and_snapshot_is_immutable():
    trace=obs.Trace('request.query');token=obs.CURRENT.set(trace)
    try:
        for _ in range(200):
            with trace.span('step'):pass
    finally:obs.CURRENT.reset(token)
    snapshot=trace.snapshot();assert len(snapshot['steps'])==128 and snapshot['droppedSteps']==72
    trace.steps[0]['metadata']['row_count']=99;assert 'row_count' not in snapshot['steps'][0]['metadata']


def make_app():
    app=FastAPI();app.add_middleware(ObservabilityMiddleware,owner=lambda:{'id':1},sessions={},session_lock=lambda:RLock())
    @app.post('/api/query')
    @obs.observed('request.resolve')
    def query():return {'status':'need_clarification','query':'not-exported-user-question'}
    @app.post('/api/output/edit')
    @obs.observed('edit.apply')
    def edit():raise HTTPException(422,'original validation message')
    @app.post('/api/output/fail')
    @obs.observed('output.build')
    def fail():raise RuntimeError('apiKey=secret-cannot-leak')
    @app.post('/api/table/export')
    @obs.observed('export.table')
    def export():return Response(b'\x00file bytes',media_type='application/pdf',headers={'Content-Disposition':'attachment; filename=x.pdf'})
    return app


def test_asgi_timings_and_existing_response_remain_intact():
    with TestClient(make_app()) as client:
        result=client.post('/api/query');assert result.status_code==200
        data=result.json();assert data['query']=='not-exported-user-question'
        trace=data['observability'][0];assert trace['status']=='awaiting_input'
        assert [s['name'] for s in trace['steps']]==['request.query','request.resolve']
        assert get_trace(trace['traceId'],1)==trace and get_trace(trace['traceId'],2) is None
        assert 'not-exported-user-question' not in json.dumps(trace)
        error=client.post('/api/output/edit');assert error.status_code==422 and error.json()['detail']=='original validation message'
        assert error.json()['observability'][0]['steps'][-1]['error']['code']=='validation_failed'
        fail=client.post('/api/output/fail');assert fail.status_code==500
        assert 'secret-cannot-leak' not in fail.text and fail.json()['observability'][0]['status']=='failed'
        exported=client.post('/api/table/export');assert exported.content==b'\x00file bytes'
        assert exported.headers['content-disposition']=='attachment; filename=x.pdf'
        assert get_trace(exported.headers['x-statbridge-trace-id'],1)['steps'][-1]['name']=='export.table'


def test_exporter_failure_does_not_change_computation(monkeypatch):
    class Broken:
        def start_observation(self,**kwargs):raise OSError('secret-cannot-leak')
    monkeypatch.setattr(obs,'exporter',lambda:(Broken(),'configured'))
    trace=obs.Trace('request.query');token=obs.CURRENT.set(trace)
    try:
        with trace.span('root'):
            with trace.span('calculate'):value=2+2
    finally:obs.CURRENT.reset(token)
    result=trace.snapshot();assert value==4 and result['langfuse']=='unavailable'
    assert len(result['steps'])==2 and 'secret-cannot-leak' not in json.dumps(result)


def test_real_sdk_exports_parenting_usage_and_safe_metadata_in_memory(monkeypatch):
    from langfuse import Langfuse
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    exporter=InMemorySpanExporter()
    sdk=Langfuse(public_key='pk-lf-isolated-test',secret_key='sk-lf-isolated-test',base_url='http://127.0.0.1:1',tracer_provider=TracerProvider(),span_exporter=exporter,environment='isolated-test')
    monkeypatch.setattr(obs,'exporter',lambda:(sdk,'configured'))
    trace=obs.Trace('request.query');token=obs.CURRENT.set(trace)
    try:
        with trace.span('request.query'):
            with trace.span('model.openai','generation'):
                obs.generation_usage('gpt-5.4',{'input_tokens':10,'output_tokens':2,'total_tokens':12})
    finally:obs.CURRENT.reset(token)
    sdk.flush()
    spans=exporter.get_finished_spans();assert len(spans)==2
    parent=next(s for s in spans if s.name=='request.query');child=next(s for s in spans if s.name=='model.openai')
    assert child.parent.span_id==parent.context.span_id
    assert format(parent.context.trace_id,'032x')==trace.id
    assert child.attributes['langfuse.observation.usage_details']
    sdk.shutdown()


def test_model_calls_count_http_attempts_not_missing_configuration():
    from openai_chart_client import OpenAIChartClient,OpenAIChartError
    trace=obs.Trace('request.query');token=obs.CURRENT.set(trace)
    try:
        with pytest.raises(OpenAIChartError):OpenAIChartClient(api_key='').request('secret-question','secret-output')
        assert trace.model_calls==0
        class NetworkFailure:
            def post(self,*a,**kw):
                import requests
                raise requests.ConnectionError('secret-provider-url')
        with pytest.raises(OpenAIChartError):OpenAIChartClient(api_key='test-only',session=NetworkFailure()).request('secret-question','secret-output')
        assert trace.model_calls==1
    finally:obs.CURRENT.reset(token)
    assert 'secret-question' not in json.dumps(trace.snapshot())


def test_real_batch_workers_have_source_timings():
    from statbridge_mcp.statistics_batch import get_statistics_batch
    class FakeService:
        @obs.observed('source.fetch')
        def get_statistics(self,table_id):return {'status':'success','rows':[]}
    trace=obs.Trace('request.query');token=obs.CURRENT.set(trace)
    try:
        with trace.span('sources.fetch'):
            result=get_statistics_batch(FakeService(),[{'table_id':'DT_A'},{'table_id':'DT_B'}])
    finally:obs.CURRENT.reset(token)
    assert len(result['results'])==2
    assert len([s for s in trace.snapshot()['steps'] if s['name']=='source.fetch'])==2
