"""Route explicit external providers before waiting for a global API census.

Local metadata only finds candidates. Availability still needs live metadata,
exact selection validation and successful observation IO. No external imports.
"""
import copy
import hashlib
import json
import re
import time
from datetime import datetime, timezone

from expression_tree_validator import DerivedValidationError


def explicit_provider_check(runtime, query):
    if not re.search(r'세계\s*은행|world\s*bank', query, re.I):
        return None
    from derived_availability import AvailabilityRequest, SYSTEM, _search, _resolve_candidate
    from derived_request_period import requested_display_period
    from derived_catalog_tools import DerivedCatalogTools
    from derived_input_guidance import input_guidance
    from derived_support_policy import unsupported

    # Requirements only: never cache API observations or negative API decisions.
    key=hashlib.sha256(query.encode()).hexdigest()
    cache=getattr(runtime, '_provider_requirement_cache', {})
    cached=cache.get(key)
    usage=[]
    if cached and time.monotonic()-cached[0]<300:
        request=AvailabilityRequest.model_validate(copy.deepcopy(cached[1]))
    else:
        options={'json_mode':True, 'max_tokens':3000}
        if getattr(runtime.planner.client, 'supports_json_schema', False):
            schema=AvailabilityRequest.model_json_schema()
            schema['required']=list(schema['properties'])
            schema['properties']['calculation_guide'].pop('default',None)
            definition=schema['$defs']['RequiredInput']
            definition['required']=list(definition['properties'])
            definition['properties']['requested_provider'].pop('default',None)
            options['response_schema']=schema
        raw, info=runtime.planner.client.request(SYSTEM, json.dumps({
            'query':query, 'server_display_period':requested_display_period(query)}, ensure_ascii=False), **options)
        usage.append(info)
        try:
            request=AvailabilityRequest.model_validate_json(raw)
        except ValueError as exc:
            raise DerivedValidationError('원자료와 요청 출처를 읽지 못했습니다. 같은 요청을 다시 시도해 주세요.', failure_kind='model_response_error') from exc
        if len(cache)>=32:cache.pop(next(iter(cache)))
        cache[key]=(time.monotonic(),request.model_dump())
        runtime._provider_requirement_cache=cache

    providers={r.requested_provider for r in request.inputs}
    # Ambiguous requirements retain the normal verification path, never reject
    # a request merely because its wording mentions a third-party institution.
    if 'unspecified' in providers or 'external' not in providers:
        return None
    if providers=={'external'}:
        if re.search(r'한국\s*은행|KOSIS|\bBOK\b',query,re.I):
            return None
        return {**unsupported(query, '이 요청은 지원하지 않는 범위입니다. 요청하신 원자료가 모두 외부기관 자료이므로, 한국은행 KOSIS API 원자료가 실제 계산에 하나 이상 포함되는 질문으로 다시 작성해 주세요.'),
                'usage':usage}

    # Only shortlist approved local catalog candidates. Do not start 1,047
    # metadata calls or treat a bounded search as proof of global absence.
    local={'tables':[DerivedCatalogTools.get_table_metadata(runtime.catalog,t)
                     for t in sorted(runtime.catalog.approved)]}
    checked={}; sources=[]
    for req in request.inputs:
        source={**req.model_dump(), 'candidateTables':[], 'guidance':None}
        if req.requested_provider=='external':
            source.update(status='not_found', reason='사용자가 명시한 외부기관의 원자료입니다. 승인 한국은행 KOSIS 자료로 대체하거나 자동 조회하지 않습니다.',
                          guidance=input_guidance({'required_data':req.name,'reason':''},query))
            sources.append(source)
            continue
        local_matches=_search(local,req.search_terms)
        ranked=runtime.catalog.search_approved_tables(req.name+' '+' '.join(req.search_terms),limit=6)
        wanted={p.frequency for p in req.periods if p.frequency!='pending'}
        eligible={m['table_id']:m for m,_ in local_matches if wanted<=set(m['frequencies'])}
        ids=[r['table_id'] for r in ranked if r['table_id'] in eligible]
        if not ids:ids=list(eligible)[:6]
        ids.sort(key=lambda tid: set(eligible[tid]['frequencies'])!=wanted)
        ids=ids[:2]
        matches=[]
        try:
            for tid in ids:
                meta=runtime.catalog.get_table_metadata(tid)
                if meta.get('metadata_origin')!='actual_KOSIS_metadata_API':
                    raise DerivedValidationError('실제 KOSIS 메타데이터 확인이 필요합니다.', failure_kind='source_api_error')
                checked[tid]=meta
                matches.append((meta,req.search_terms))
            source.update(status='selection_required', reason='필요한 한국은행 후보 표만 실제 API로 확인합니다. 후보 검색 실패를 자료 부재로 단정하지 않습니다.')
            if matches:
                outcome=_resolve_candidate(runtime,req,matches,usage)
                # Shortlisted mismatches do not prove an exhaustive absence.
                if outcome['status']=='not_found':outcome['status']='selection_required'
                source.update(outcome)
                source['candidateTables']=[{'tableId':m['table_id'],'name':m['table_name'],
                    'frequencies':m['frequencies'],'periods':m['periods'],'matchedTerms':hits} for m,hits in matches]
        except DerivedValidationError as exc:
            source.update(status='api_error' if exc.failure_kind=='source_api_error' else 'selection_required', reason=str(exc))
        sources.append(source)
    return {'status':'need_details','question':'한국은행 원자료 확인 결과와 추가로 필요한 외부 자료를 안내합니다. 아직 계산하지 않았습니다.',
            'usage':usage,'searches':[], 'availability':{
                'status':'checked','origin':'actual_KOSIS_metadata_API_targeted',
                'checkedAt':datetime.now(timezone.utc).isoformat(),
                'sha256':hashlib.sha256(json.dumps(list(checked.values()),sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                'checkedTables':len(checked),'requiredTables':len(runtime.catalog.approved),
                'apiRequests':len(checked)*3,'sources':sources,'questions':request.questions,
                'calculationGuide':request.calculation_guide,'calculationExecuted':False,
                'metadataOnly':not any(s.get('observationChecks') for s in sources),
                'acceptedFormats':['CSV','JSON','TSV','XLSX']}}
