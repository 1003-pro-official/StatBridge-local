"""Bounded, ordered multi-query execution; no implicit replacement or data cache."""
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from threading import BoundedSemaphore
import copy,json,re,time
from typing import Any
POOL=ThreadPoolExecutor(max_workers=3,thread_name_prefix='statistics')
SLOTS=BoundedSemaphore(6)
FIELDS={'table_id','item_id','classifications','frequency','start_period','end_period','prefer_local','allow_fallback'}

def get_statistics_batch(service,requests:list[dict[str,Any]],timeout_seconds:float=20):
    if not 1<=len(requests)<=20:raise ValueError('배치 조회는 1~20개 요청을 지원합니다.')
    if not 0<timeout_seconds<=20:raise ValueError('배치 대기는 최대 20초입니다.')
    validated=[]
    for i,request in enumerate(requests):
        if not isinstance(request,dict) or set(request)-FIELDS-{'request_id'}:raise ValueError('지원하지 않는 조회 조건입니다.')
        args={k:v for k,v in request.items() if k in FIELDS}
        if not isinstance(args.get('table_id'),str) or not args['table_id'].strip():raise ValueError('통계표 ID가 필요합니다.')
        store=getattr(service,'store',None)
        if store and not store.get(args['table_id']):raise ValueError('지원 카탈로그에 없는 통계표입니다: '+args['table_id'])
        if args.get('classifications') is not None and (not isinstance(args['classifications'],dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in args['classifications'].items())):raise ValueError('분류는 코드 문자열 사전이어야 합니다.')
        for k in ['item_id','frequency','start_period','end_period']:
            if args.get(k) is not None and not isinstance(args[k],str):raise ValueError('조회 조건은 문자열이어야 합니다: '+k)
        for k in ['prefer_local','allow_fallback']:
            if k in args and not isinstance(args[k],bool):raise ValueError('조회 정책은 참/거짓이어야 합니다.')
        if args.get('start_period') and args.get('end_period') and args['start_period']>args['end_period']:raise ValueError('조회 시작 기간이 종료 기간보다 늦습니다.')
        meta=store.get(args['table_id']) if store else None
        if meta:
            from .metadata_store import normalize_frequency
            known={normalize_frequency(v) for v in getattr(meta,'frequencies',[])}
            if args.get('frequency') and known and normalize_frequency(args['frequency']) not in known:raise ValueError('해당 표에서 지원하지 않는 자료 주기입니다.')
            items={str(v['item_id']) for v in getattr(meta,'items',[]) if v.get('item_id')}
            if items and args.get('item_id') not in (None,'ALL') and any(v not in items for v in re.split(r'[+,]',args['item_id'])):raise ValueError('해당 표에 없는 통계 항목 코드입니다.')
            dims=getattr(meta,'dimensions',[])
            for key,value in (args.get('classifications') or {}).items():
                dim=next((d for d in dims if key in {d.get('mcp_param'),d.get('obj_id')}),None)
                if dim and value!='ALL':
                    codes={str(v['class_id']) for v in dim.get('values',[]) if v.get('class_id')}
                    if codes and any(v not in codes for v in re.split(r'[+,]',value)):raise ValueError('해당 표에 없는 분류 코드입니다: '+key)
        validated.append((str(request.get('request_id',i)),args,json.dumps(args,sort_keys=True,ensure_ascii=False)))
    def safe(value):
        if isinstance(value,dict):return {k:('[redacted]' if re.fullmatch(r'(?i)api[_-]?key|access_token|authorization',str(k)) else safe(v)) for k,v in value.items()}
        if isinstance(value,list):return [safe(v) for v in value]
        if not isinstance(value,str):return value
        text=re.sub(r'(?i)(api[_-]?key|access_token)=([^&\s]+)',r'\1=[redacted]',value)
        secret=getattr(getattr(service,'client',None),'api_key','')
        return text.replace(secret,'[redacted]') if isinstance(secret,str) and secret else text
    def execute(args):
        local=getattr(getattr(service,'client',None),'thread_sessions',None)
        previous=getattr(local,'deadline',None) if local is not None else None
        if local is not None:local.deadline=deadline
        try:
            data=service.get_statistics(**args)
            if data.get('status')!='success':
                return {'status':'busy' if data.get('status')=='busy' else 'error','data':safe(data),
                        'error':safe(data.get('error') or '조회 실패: '+args['table_id']),
                        **({'retry_after_seconds':data['retry_after_seconds']} if data.get('retry_after_seconds') else {})}
            if any(row.get('TBL_ID') and str(row['TBL_ID'])!=args['table_id'] for row in data.get('rows',[])):return {'status':'error','error':'응답 통계표가 요청과 다릅니다.'}
            return {'status':'success','data':safe(data)}
        except Exception as e:
            message=re.sub(r'(?i)(api[_-]?key|access_token)=([^&\s]+)',r'\1=[redacted]',str(e))
            key=getattr(getattr(service,'client',None),'api_key','')
            if isinstance(key,str) and key:message=message.replace(key,'[redacted]')
            return {'status':'error','error':message}
        finally:
            if local is not None:
                if previous is None:
                    try:del local.deadline
                    except AttributeError:pass
                else:local.deadline=previous
    futures={};queue={key:args for _,args,key in validated};deadline=time.monotonic()+timeout_seconds
    done=set()
    while queue or any(f is not None and not f.done() for f in futures.values()):
        while queue and SLOTS.acquire(blocking=False):
            key=next(iter(queue));args=queue.pop(key)
            try:future=POOL.submit(execute,args)
            except Exception:SLOTS.release();raise
            future.add_done_callback(lambda _:SLOTS.release());futures[key]=future
        remaining=deadline-time.monotonic()
        if remaining<=0:break
        active=[f for f in futures.values() if f is not None and not f.done()]
        if active:wait(active,timeout=remaining,return_when=FIRST_COMPLETED)
        elif queue:time.sleep(min(.01,remaining))
    done={f for f in futures.values() if f is not None and f.done()}
    for key in queue:futures[key]=None
    results=[]
    for request_id,args,key in validated:
        future=futures[key]
        outcome={'status':'busy','error':'조회 작업이 많습니다. 잠시 후 다시 시도해 주세요.'} if future is None else future.result() if future in done else {'status':'timeout','error':'20초 이내 조회를 완료하지 못했습니다. 해당 지표를 다시 시도해 주세요.'}
        results.append({'request_id':request_id,'table_id':args['table_id'],**copy.deepcopy(outcome)})
    for future in futures.values():
        if future is not None and future not in done:future.cancel()
    success=sum(r['status']=='success' for r in results)
    return {'status':'success' if success==len(results) else 'partial' if success else 'error','results':results,'unique_queries':len(futures)}
