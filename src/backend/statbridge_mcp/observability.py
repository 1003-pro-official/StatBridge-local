"""Bounded request-local timings and optional Langfuse export; no prompt/data capture."""
from contextvars import ContextVar
from contextlib import contextmanager
from functools import wraps
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4
from threading import RLock
import inspect
import os
import re

CURRENT = ContextVar('statbridge_observation_trace', default=None)
PARENT = ContextVar('statbridge_observation_parent', default=None)
_client = None
_client_state = None
_client_lock = RLock()
MAX_STEPS = 128


def exporter():
    global _client, _client_state
    if os.getenv('LANGFUSE_ENABLED', 'true').lower() in {'0','false','off'}:
        return None, 'disabled'
    if not all(os.getenv(k, '').strip() for k in ('LANGFUSE_PUBLIC_KEY','LANGFUSE_SECRET_KEY','LANGFUSE_BASE_URL')):
        return None, 'not_configured'
    with _client_lock:
        if _client_state is not None:return _client, _client_state
        try:
            from langfuse import Langfuse
            from opentelemetry.sdk.trace import TracerProvider
            _client = Langfuse(public_key=os.environ['LANGFUSE_PUBLIC_KEY'], secret_key=os.environ['LANGFUSE_SECRET_KEY'],
                base_url=os.environ['LANGFUSE_BASE_URL'], environment=os.getenv('STATBRIDGE_TRACE_ENVIRONMENT') or ('statbridge1' if 'statbridge1' in os.getcwd().lower() else 'local1'), timeout=2, tracer_provider=TracerProvider())
            _client_state = 'configured'
        except Exception:
            _client_state = 'unavailable'
        return _client, _client_state


def shutdown_exporter():
    if _client is not None:
        try:_client.shutdown()
        except Exception:pass


def error_info(exc):
    kind = getattr(exc, 'failure_kind', '')
    status = getattr(exc, 'status_code', None)
    if status is None:status = getattr(getattr(exc, 'response', None), 'status_code', None)
    name = type(exc).__name__
    code = ('model_response_error' if kind=='model_response_error' else 'model_provider_error' if kind=='model_provider_error' else
            'missing_data' if kind=='source_input_required' else 'validation_failed' if kind=='validation_error' else
            'timeout' if 'timeout' in name.lower() else 'revision_conflict' if status==409 else
            'access_denied' if status in (401,403) else 'validation_failed' if status in (400,422) or isinstance(exc,(ValueError,TypeError,KeyError)) else 'operation_failed')
    # Never send str(exc): provider exceptions can contain URLs, keys, prompts or file content.
    messages={'missing_data':'계산에 필요한 추가 원자료를 기다리고 있습니다.','model_response_error':'모델 출력 형식 검증에 실패했습니다.','model_provider_error':'모델 공급자 요청을 완료하지 못했습니다.',
        'timeout':'처리 제한 시간을 초과했습니다.','revision_conflict':'최신 편집 버전과 충돌했습니다.',
        'access_denied':'이 작업의 접근 권한을 확인해 주세요.','validation_failed':'입력·계산 계획·표시 설정 검증에서 중단했습니다.',
        'operation_failed':'이 단계의 처리를 완료하지 못했습니다.'}
    return {'code':code,'type':name,'message':messages[code],**({'httpStatus':status} if isinstance(status,int) else {})}


def outcome(value):
    if not isinstance(value,dict):return 'completed'
    current=value.get('result') if isinstance(value.get('result'),dict) else value
    if current.get('failure_kind') in ('model_provider_error','model_response_error','validation_error','analysis_error'):return 'failed'
    status=current.get('status')
    if status in ('need_clarification','need_details','need_period','need_output_config','needs_input','planned_only'):return 'awaiting_input'
    if status in ('no_match','unsupported_scope'):return 'unsupported_scope'
    if status in ('data_unavailable','missing_data','missing_inputs'):return 'missing_data'
    if status in ('request_failed','failed','error'):return 'failed'
    execution=current.get('execution')
    if isinstance(execution,dict) and execution.get('status') in ('failed','error'):return 'failed'
    return 'completed'


def safe_metadata(value):
    allowed={'row_count','source_count','node_count','input_count','cache_hit','cached_nodes','changed_nodes','missing_count','issue_count',
             'table_id','org_id','item_id','frequency','operation','format','model','attempt','http_status','json_valid','catalog_version','bytes','unit','start_period','end_period','classification_count','classification_ids','calculation_id','source','candidate_count','route','work_units','cells','plan_cache_hit','semantic_review_reused'}
    result={}
    for key,v in value.items():
        if key not in allowed:continue
        if isinstance(v,(bool,int,float)) and (not isinstance(v,float) or __import__('math').isfinite(v)):result[key]=v
        elif isinstance(v,str) and len(v)<=100 and re.fullmatch(r'[\w .%/()=:+,-]+',v):
            if re.search(r'(?i)(?:sk-|pk-lf-|bearer|api.?key|password|secret)',v):continue
            if key=='table_id' and not re.fullmatch(r'(?:DT_|REFERENCE_|FILE_)[A-Za-z0-9_]+',v):continue
            if key=='org_id' and not re.fullmatch(r'[0-9]{1,8}',v):continue
            result[key]=v
    return result


class Trace:
    def __init__(self, name):
        self.id=uuid4().hex;self.name=name;self.steps=[];self.dropped=0;self.lock=RLock();self.client,self.export_state=exporter()
        self.root=None;self.closed=False;self.model_calls=0

    @contextmanager
    def span(self,name,kind='span'):
        parent=PARENT.get();started=perf_counter()
        with self.lock:
            if self.closed or len(self.steps)>=MAX_STEPS:
                self.dropped+=1;record=None
            else:
                record={'id':uuid4().hex[:16],'parentId':parent['id'] if parent else None,'name':name,'type':kind,
                    'startedAt':datetime.now(timezone.utc).isoformat(),'durationMs':0,'status':'running','metadata':{}}
                self.steps.append(record)
        if record is None:
            yield None;return
        remote=None
        if self.client is not None:
            try:
                remote=self.client.start_observation(name=name,as_type=kind,trace_context={'trace_id':self.id,**({'parent_span_id':parent['id']} if parent else {})})
                # Use SDK span IDs for explicit parenting; never invent remote parent IDs.
                record['id']=remote.id
            except Exception:self.export_state='unavailable';self.client=None
        token=PARENT.set(record)
        try:yield record
        except BaseException as exc:
            record['status']='cancelled' if isinstance(exc,(KeyboardInterrupt,SystemExit)) or type(exc).__name__=='CancelledError' else 'failed'
            record['error']=error_info(exc)
            if kind=='generation' and record['error']['code'] not in ('model_response_error','timeout'):
                record['error'].update(code='model_provider_error',message='모델 공급자 요청을 완료하지 못했습니다.')
            if name.startswith('kosis.') and record['error']['code']=='operation_failed':record['error'].update(code='source_api_error',message='KOSIS 원자료 요청을 완료하지 못했습니다.')
            raise
        finally:
            with self.lock:
                record['durationMs']=round(max(0,(perf_counter()-started)*1000),3)
                record['endedAt']=datetime.now(timezone.utc).isoformat()
                if record['status']=='running':record['status']='completed'
            PARENT.reset(token)
            if remote is not None:
                try:
                    remote.update(metadata={**record['metadata'],'status':record['status'],**({'error_code':record['error']['code']} if record.get('error') else {})},
                        level='ERROR' if record['status']=='failed' else 'DEFAULT',
                        **({'model':record['model'],'usage_details':record.get('usage',{})} if kind=='generation' and record.get('model') else {}))
                    remote.end()
                except Exception:self.export_state='unavailable'

    def snapshot(self):
        with self.lock:
            import copy
            self.closed=True
            for step in self.steps:
                if step['status']=='running':step['status']='timeout';step['error']={'code':'timeout','type':'PendingTask','message':'응답 완료 시점까지 끝나지 않은 작업입니다.'}
            return copy.deepcopy( {'traceId':self.id,'name':self.name,'time':self.steps[0]['startedAt'] if self.steps else datetime.now(timezone.utc).isoformat(),
                    'durationMs':self.steps[0]['durationMs'] if self.steps else 0,'status':self.steps[0]['status'] if self.steps else 'completed',
                    'langfuse':self.export_state,'modelCalls':self.model_calls,'droppedSteps':self.dropped,'steps':self.steps})


def annotate(**metadata):
    record=PARENT.get()
    trace=CURRENT.get()
    if record is not None and trace is not None:
        with trace.lock:record['metadata'].update(safe_metadata(metadata))


def observed(name, kind='span'):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            trace=CURRENT.get()
            if trace is None:return fn(*args,**kwargs)
            with trace.span(name,kind) as record:
                if record is not None:
                    try:
                        bound=inspect.signature(fn).bind(*args,**kwargs).arguments
                        record['metadata'].update(safe_metadata(bound))
                        payload=bound.get('payload')
                        identifier=bound.get('edit_session_id') or getattr(payload,'edit_session_id',None)
                        if isinstance(identifier,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}',identifier):trace.session_id=identifier
                        if isinstance(bound.get('classifications'),dict):
                            classes=bound['classifications'];annotate(classification_count=len(classes))
                            if all(isinstance(k,str) and re.fullmatch(r'[A-Za-z0-9_]{1,12}',k) and isinstance(v,str) and re.fullmatch(r'[A-Z0-9_+.-]{1,40}',v) for k,v in classes.items()):annotate(classification_ids=','.join(k+':'+v for k,v in sorted(classes.items())))
                        plan=bound.get('plan')
                        if plan is not None and hasattr(plan,'nodes'):annotate(node_count=len(plan.nodes),input_count=len(plan.sources))
                    except (ValueError,TypeError,AttributeError):pass
                result=fn(*args,**kwargs)
                with trace.lock:
                    if record is not None:
                        record['status']=('missing_data' if record['error']['code']=='missing_data' else 'failed') if record.get('error') else outcome(result)
                        if isinstance(result,list):record['metadata']['candidate_count' if name=='catalog.search' else 'row_count']=len(result)
                        if name=='intent.route' and result in ('resolve_request','classify_analysis_intent','plan_derived_indicator'):record['metadata']['route']=result
                        if isinstance(result,dict):
                            for key in ('cache_hit','plan_cache_hit'):
                                if key in result:record['metadata']['cache_hit']=bool(result[key])
                            if isinstance(result.get('rows'),list):record['metadata']['row_count']=len(result['rows'])
                            if result.get('source') in ('kosis_api','local_csv','user_file','cache'):annotate(source=result['source'])
                            if re.fullmatch(r'[a-f0-9]{32}',str(result.get('calculationId',''))):annotate(calculation_id=result['calculationId'])
                        if kind=='generation' and isinstance(result,tuple) and len(result)>1 and isinstance(result[1],dict) and result[1].get('model'):
                            info=result[1];generation_usage(info.get('model'),info.get('usage') or {})
                return result
        try:wrapped.__signature__=inspect.signature(fn,eval_str=True)
        except (NameError,TypeError,ValueError):pass
        return wrapped
    return decorate


@contextmanager
def span(name,kind='span'):
    trace=CURRENT.get()
    if trace is None:yield None
    else:
        with trace.span(name,kind) as record:yield record


def generation_usage(model,usage):
    trace=CURRENT.get()
    if trace is None:return
    with trace.lock:
        record=PARENT.get()
        if record is None or record['type']!='generation':return
        if isinstance(model,str) and re.fullmatch(r'[\w.:-]{1,100}',model) and not re.search(r'(?i)(?:sk-|pk-lf-|secret|password)',model):record['model']=model
        if not isinstance(usage,dict):return
        record['usage']={key:usage[key] for key in ('input_tokens','output_tokens','total_tokens','prompt_tokens','completion_tokens') if isinstance(usage.get(key),int) and usage[key]>=0}
        cached=(usage.get('input_tokens_details') or {}).get('cached_tokens')
        if isinstance(cached,int) and cached>=0:record['usage']['input_cached_tokens']=cached


def record_failure(exc):
    trace=CURRENT.get()
    if trace is None:return
    with trace.lock:
        record=PARENT.get()
        if record is not None and isinstance(exc,BaseException):
            record['error']=error_info(exc)
            record['status']='missing_data' if record['error']['code']=='missing_data' else 'failed'


def generation_started(model=None):
    trace=CURRENT.get();record=PARENT.get()
    if trace is None:return
    with trace.lock:
        trace.model_calls+=1
        if record is not None and record['type']=='generation':
            record['metadata']['http_attempted']=True
            generation_usage(model,{})
