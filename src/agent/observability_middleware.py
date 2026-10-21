"""Authenticated ASGI tracing, bounded response metadata and owner-scoped trace lookup."""
import json
import re
from collections import OrderedDict
from threading import RLock
from time import monotonic
from statbridge_mcp.observability import CURRENT, Trace, outcome, error_info

MAX_BUFFER=8*1024*1024
STORE=OrderedDict()
LOCK=RLock()


def get_trace(identifier, owner):
    with LOCK:
        value=STORE.get(identifier)
        if value is None or value[0]!=owner or monotonic()-value[1]>3600:return None
        return value[2]


def request_name(scope):
    path=scope['path']
    if '/export' in path:return 'request.export'
    if '/save' in path:return 'request.save'
    if '/workspace/' in path:return 'request.restore'
    if '/supplement/' in path or path.endswith('/supplement'):return 'request.file'
    if path.endswith('/edit'):return 'request.edit'
    if '/output' in path:return 'request.output'
    return 'request.query'


class ObservabilityMiddleware:
    def __init__(self,app,owner,sessions,session_lock):
        self.app,self.owner,self.sessions,self.session_lock=app,owner,sessions,session_lock

    async def __call__(self,scope,receive,send):
        path=scope.get('path','')
        selected=path.startswith(('/api/query','/api/output','/api/workspace/','/api/table/export','/api/report/','/api/derived/'))
        if scope['type']!='http' or not selected or scope['method']=='OPTIONS':
            return await self.app(scope,receive,send)
        user=self.owner()
        if not user:return await self.app(scope,receive,send)
        trace=Trace(request_name(scope));token=CURRENT.set(trace);messages=[];size=0;streaming=False;start=None
        async def capture(message):
            nonlocal size,streaming,start
            if message['type']=='http.response.start':
                start=message;return
            if message['type']!='http.response.body':return await send(message)
            if streaming:return await send(message)
            size+=len(message.get('body',b''));messages.append(message)
            if size>MAX_BUFFER:
                streaming=True
                await send({**start,'headers':[*start.get('headers',[]),(b'x-statbridge-trace-id',trace.id.encode())]})
                for item in messages:await send(item)
                messages.clear()
        try:
            with trace.span(trace.name) as root:
                await self.app(scope,receive,capture)
                status=start['status'] if start else 500
                body=b''.join(item.get('body',b'') for item in messages)
                headers=dict(start.get('headers',[])) if start else {}
                is_json=headers.get(b'content-type',b'').startswith(b'application/json') and b'content-disposition' not in headers
                data=None
                if is_json and not streaming:
                    try:data=json.loads(body)
                    except (ValueError,UnicodeDecodeError):pass
                if root is not None:
                    root['metadata']['http_status']=status
                    root['metadata']['model_calls']=trace.model_calls
                    root['status']=outcome(data) if status<400 else 'failed'
                    if status>=400:
                        problem=type('RequestFailure',(Exception,),{'status_code':status})()
                        root['error']=error_info(problem)
                identifier=(data.get('editSessionId') if isinstance(data,dict) else None) or getattr(trace,'session_id',None)
                if not identifier:
                    match=re.fullmatch(r'/api/workspace/([A-Za-z0-9_-]+)/?(?:save)?',path)
                    identifier=match.group(1) if match else None
            snapshot=trace.snapshot()
            if identifier:snapshot['sessionId']=identifier
            with LOCK:
                STORE[trace.id]=(user['id'],monotonic(),snapshot)
                while len(STORE)>200:STORE.popitem(last=False)
            history=[snapshot]
            if identifier:
                with self.session_lock():
                    session=self.sessions.get(identifier)
                    if session and session.get('account_id')==user['id']:
                        history=[*session.get('observability',[]),snapshot][-30:]
                        session['observability']=history
            if not streaming and start is not None:
                if isinstance(data,dict) and is_json:
                    data['observability']=history
                    body=json.dumps(data,ensure_ascii=False,allow_nan=False).encode('utf-8')
                outgoing=[(k,v) for k,v in start.get('headers',[]) if k.lower()!=b'content-length']
                outgoing.extend([(b'content-length',str(len(body)).encode()),(b'x-statbridge-trace-id',trace.id.encode())])
                await send({**start,'headers':outgoing})
                await send({'type':'http.response.body','body':body,'more_body':False})
        except Exception:
            snapshot=trace.snapshot()
            with LOCK:
                STORE[trace.id]=(user['id'],monotonic(),snapshot)
                while len(STORE)>200:STORE.popitem(last=False)
            if streaming:raise
            body=json.dumps({'detail':'요청 처리 중 오류가 발생했습니다. 기존 분석은 유지됩니다.','observability':[snapshot]},ensure_ascii=False).encode('utf-8')
            await send({'type':'http.response.start','status':500,'headers':[(b'content-type',b'application/json'),(b'content-length',str(len(body)).encode()),(b'x-statbridge-trace-id',trace.id.encode())]})
            await send({'type':'http.response.body','body':body,'more_body':False})
        finally:
            CURRENT.reset(token)


def install_shutdown(app,shutdown):
    from contextlib import asynccontextmanager
    original=app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(application):
        async with original(application) as state:
            try:yield state
            finally:
                import anyio
                await anyio.to_thread.run_sync(shutdown)
    app.router.lifespan_context=lifespan
