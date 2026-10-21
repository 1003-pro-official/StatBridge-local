"""Validate, execute, score and prepare blind review packets. No paid calls by default."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import math
import os
import random
import statistics
import sys
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from core import (BASE, ROOT, RUBRIC, FrozenProvider, compare_series, digest_file, digest_value,
                  read, review_packet, review_valid, rows, score_case, summary, write, write_rows)


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def validate():
    manifest = read(BASE/'manifest.json')
    for name, digest in manifest['files'].items():
        if digest_file(BASE/name) != digest:
            raise ValueError('stale manifest: '+name)
    audit, pilot, supplements = (rows(BASE/name) for name in ('audit.jsonl','pilot.jsonl','supplemental.jsonl'))
    if len(audit)!=46 or len(pilot)!=12 or len(supplements)!=24:
        raise ValueError('unexpected dataset counts')
    if len({c['id'] for c in audit})!=46:
        raise ValueError('duplicate audit ID')
    all_cases = pilot+supplements
    if len({c['id'] for c in all_cases}) != len(all_cases):
        raise ValueError('duplicate case ID')
    for c in audit:
        if not c['source']['url'].startswith('https://www.bok.or.kr/') or not c['source']['publication_date']:
            raise ValueError('missing official source/date')
        if len(c['source']['sha256'])!=64 or not c['historical']['reason'] or not c['current']['reason']:
            raise ValueError('missing evidence/status')
    for c in all_cases:
        if not c['input']['query'] or not c['expected'] or not c.get('required_facts'):
            raise ValueError('missing input/expected/facts')
        if c['expected'].get('required_facts')!=c['required_facts'] or c['expected'].get('qualitative_applicable')!=c['qualitative_applicable']:
            raise ValueError('rubric/facts must be bound into the expected-contract hash')
        if {'expected','evidence','review'} & c['input'].keys():
            raise ValueError('gold leakage into input')
        if c['review']['human_approved'] and not c['review'].get('reviewer'):
            raise ValueError('approval without human reviewer')
    for kind in ('derived','followup','reference_edit','summary_style','report','recovery'):
        if sum(c['category']==kind for c in supplements)!=4:
            raise ValueError('supplemental strata mismatch')
    print('VALIDATION OK: audit=46, pilot=12, supplements=24; exposed regression; human approval pending')


def offline(cases, provider_file):
    """Reuse real v2 FastAPI path, replacing only the external source and test login."""
    os.environ.update(PYTHON_DOTENV_DISABLED='1', STATBRIDGE_HYBRID_RETRIEVAL='0',
                      STATBRIDGE_JEV_ENABLED='0', LANGFUSE_TRACING_ENABLED='false',
                      MPLCONFIGDIR=str(Path(tempfile.gettempdir())/'statbridge-bok-mpl'))
    for key in ('OPENAI_API_KEY','KOSIS_API_KEY','NCP_CLOVA_API_KEY','NCP_API_KEY','CLOVA_STUDIO_API_KEY','LANGFUSE_PUBLIC_KEY','LANGFUSE_SECRET_KEY'):
        os.environ[key]=''
    for rel in ('src/backend','src/agent','tests','eval/statbridge-golden/v2/scripts'):
        sys.path.insert(0,str(ROOT/rel))
    legacy = module(ROOT/'eval/statbridge-golden/v2/scripts/run.py','bok_legacy_runner')
    data = read(provider_file)['series']
    class Source(FrozenProvider):
        def __init__(self, metadata):
            super().__init__(data)
            self.metadata = metadata
        def __getattr__(self, name):
            return getattr(self.metadata, name)
    import io
    real_open = io.open
    def guarded_open(file, *args, **kwargs):
        if isinstance(file,(str,Path)):
            normalized = str(file).replace('\\','/').casefold()
            if '/data/tables/' in normalized or normalized.endswith('/.env') or 'holdout_answers' in normalized or 'statbridge-evaluation-private' in normalized:
                raise PermissionError('evaluation source boundary: forbidden file')
        return real_open(file,*args,**kwargs)
    with tempfile.TemporaryDirectory(prefix='bok-eval-auth-') as temp, ExitStack() as stack:
        os.environ['STATBRIDGE_AUTH_DB'] = str(Path(temp)/'accounts.sqlite3')
        stack.enter_context(patch('io.open',guarded_open))
        stack.enter_context(patch('builtins.open',guarded_open))
        def no_network(*args, **kwargs):
            raise RuntimeError('offline external access blocked')
        stack.enter_context(patch('requests.sessions.Session.request',no_network))
        stack.enter_context(patch('httpx.HTTPTransport.handle_request',no_network))
        stack.enter_context(patch('urllib.request.urlopen',no_network))
        import bridge_api
        from authenticated_client import TestClient
        from agent_runtime import StatBridgeAgent
        from mcp_gateway import McpToolGateway
        from ncp_clova_client import NcpClovaClient, NcpSettings
        from statbridge_mcp.statistics_service import StatisticsService
        provider=Source(StatisticsService(client=legacy.NoNetwork()))
        agent=StatBridgeAgent(McpToolGateway(provider),ncp_client=NcpClovaClient(NcpSettings(api_key='')))
        stack.enter_context(patch.object(bridge_api,'service',provider))
        stack.enter_context(patch.object(bridge_api,'agent',agent))
        predictions=[]
        with TestClient(bridge_api.app) as client:
            for c in cases:
                # Keep the dictionaries installed in authentication middleware by identity.
                bridge_api.OUTPUT_SESSIONS.clear()
                bridge_api.EDIT_SESSIONS.clear()
                provider.calls.clear()
                started=time.perf_counter()
                trace=[]
                p=dict(id=c['id'],input_sha256=digest_value(c['input']),execution_status='observed')
                def post(path,body):
                    response=client.post(path,json=body)
                    value=response.json()
                    trace.append({'stage':path,'http_status':response.status_code,'response':value})
                    response.raise_for_status()
                    return value
                print('Executing '+c['id']+' (real offline query/output)',flush=True)
                try:
                    response=post('/api/query',{'query':c['input']['query'],'execute':True})
                    p['first_attempt_success']=bool(response.get('outputSessionId'))
                    p['user_confirmation_count']=0
                    for action in c['input'].get('actions',[]):
                        if action['kind']=='confirm_period' and response.get('status')=='need_period':
                            p['user_confirmation_count']+=1
                            response=post('/api/query',{'query':c['input']['query'],'state':response.get('state'),
                                'execute':True,'period_start':action['start'],'period_end':action['end']})
                    resolution=legacy.observed_resolution(response)
                    if response.get('status') in ('need_details','need_period','need_clarification'):
                        resolution['decision']='clarify'
                    p['decision']=resolution['decision']
                    p['resolution']=resolution
                    session=response.get('outputSessionId')
                    if session:
                        output=post('/api/output',{'session_ids':[session],'chart_type':'line','chart_mode':'combined'})
                        identities=[]
                        for call in provider.calls:
                            identity={k:call[k] for k in ('provider','table_id','item_id','classifications','frequency')}
                            if identity not in identities:
                                identities.append(identity)
                        p.update(legacy.observed_output(output.get('outputSpec',{}),identities))
                    elif response.get('status') not in ('need_clarification','need_details','need_period','no_match','catalog_only'):
                        p.update(execution_status='unobserved',error='query did not issue an output session: '+str(response.get('status')))
                except Exception as exc:
                    p.update(execution_status='error',error=str(exc),error_type=type(exc).__name__)
                p.update(elapsed_ms=(time.perf_counter()-started)*1000,trace=trace,statistics_requests=copy.deepcopy(provider.calls))
                predictions.append(p)
    for p in predictions:
        p['decision'] = p.get('resolution',{}).get('decision')
        p['environment']='offline_fixed_provider'
        p['model_called']=False
        p['usage']=None
        p['cost']=None
        p['observed_contract']={'chart_type':p.get('chart_type'),'layout':p.get('layout')}
        p['implementation_sha256']=legacy.implementation_hashes()
        p['observation_sha256']=legacy.observation_hash(p)
    return predictions


def run(cases, provider_file, run_mode, adapter=None, profile='baseline', repeats=1, allow_paid=False):
    if run_mode!='offline' and (not allow_paid or not adapter):
        raise ValueError('model/live execution requires explicit --allow-paid and --adapter; never falls back to offline')
    if run_mode=='offline' and adapter:
        raise ValueError('custom adapters require model_fixed/live mode')
    profiles=read(BASE/'profiles.json')
    manifest=read(BASE/'manifest.json')
    for name,digest in manifest.get('files',{}).items():
        if digest_file(BASE/name)!=digest:
            raise ValueError('dataset/tool changed after manifest: '+name)
    for name,digest in manifest.get('metadata_sha256',{}).items():
        if digest_file(ROOT/name)!=digest:
            raise ValueError('metadata snapshot changed: '+name)
    if digest_file(provider_file)!=manifest['local_provider_sha256']:
        raise ValueError('source snapshot differs from the fixed dataset manifest')
    if profile not in ('baseline','sol','mixed'):
        raise ValueError('unknown model profile')
    work=[]
    for repeat in range(repeats):
        batch=copy.deepcopy(cases)
        random.Random(profiles['seed']+repeat).shuffle(batch)
        executable=[c for c in batch if not c.get('preparation_status') or run_mode!='offline']
        pending=[c for c in batch if c not in executable]
        if run_mode=='offline':
            predictions=offline(executable,provider_file) if executable else []
        else:
            implementation=module(adapter,'bok_explicit_adapter')
            predictions=[]
            for c in executable:
                start=time.perf_counter()
                p=implementation.run_input(copy.deepcopy(c['input']),
                    FrozenProvider(read(provider_file)['series']) if run_mode=='model_fixed' else None,
                    copy.deepcopy(profiles[profile]))
                p.update(id=c['id'],input_sha256=digest_value(c['input']),elapsed_ms=(time.perf_counter()-start)*1000)
                actual=p.get('actual_models')
                controlled=bool(c['input'].get('fault_injection') or c['input'].get('setup',{}).get('component_boundary'))
                verified_control=controlled and p.get('model_called') is False and bool(p.get('controlled_execution_evidence'))
                model_verified=isinstance(actual,list) and bool(actual) and all(isinstance(m,dict) and m.get('purpose') and
                    m.get('model') == profiles[profile]['text_model' if m.get('purpose') in ('summary','style') else 'main_model'] for m in actual)
                if not model_verified and not verified_control:
                    p.update(execution_status='unobserved',error='actual model/purpose evidence missing')
                p['environment']=run_mode
                predictions.append(p)
        for c in pending:
            predictions.append(dict(id=c['id'],execution_status='not_executed',input_sha256=digest_value(c['input']),
                                    error='offline does not emulate natural-language/model or fault adapters',environment=run_mode))
        for p in predictions:
            p['repeat']=repeat
            p['profile']=profile if run_mode!='offline' else 'disabled'
            p['provider_sha256']=(p.get('live_source_sha256') or 'unobserved') if run_mode=='live' else digest_file(provider_file)
            p['evaluation_code_sha256']={path.name:digest_file(path) for path in (BASE/'scripts').glob('*.py')}
        work.extend(predictions)
    return work


def blind_packets(cases, predictions):
    by_id={c['id']:c for c in cases}
    packets, mapping=[],[]
    for n,p in enumerate(predictions):
        if p.get('execution_status')!='observed':
            continue
        c=by_id[p['id']]
        packet=review_packet(c,p)
        token=digest_value({'prediction':p,'index':n})[:20]
        # Allowlist user-facing content; raw traces may contain model/profile names.
        packet.update(review_id=token,group_id=c['group_id'],input=c['input'],
                      response={k:p.get(k) for k in ('series','explanation','plotly_figure','resolution')},
                      required_facts=c.get('required_facts',[]),source=c.get('evidence'),
                      second_review_required=False)
        mapping.append({'review_id':token,'id':p['id'],'repeat':p.get('repeat'),'profile':p.get('profile')})
        packets.append(packet)
    groups={}
    for packet in packets:
        groups.setdefault((packet['group_id'],by_id[packet['id']].get('category')),[]).append(packet)
    for group in groups.values():
        for packet in sorted(group,key=lambda p:p['review_id'])[:math.ceil(len(group)*.2)]:
            packet['second_review_required']=True
    return packets,mapping


def score(cases, predictions, oracle, reviews):
    if len({(p['id'],p.get('repeat',0)) for p in predictions})!=len(predictions):
        raise ValueError('duplicate predictions in same repeat')
    if set(p['id'] for p in predictions)-set(c['id'] for c in cases):
        raise ValueError('unknown prediction case')
    if len({(p.get('environment'),p.get('profile')) for p in predictions})>1:
        raise ValueError('score each environment/profile separately')
    review_map={r['prediction_sha256']:r for r in reviews}
    sample_packets,_=blind_packets(cases,predictions)
    sampled={r['prediction_sha256'] for r in sample_packets if r['second_review_required']}
    scored=[]
    for c in cases:
        matches=[p for p in predictions if p['id']==c['id']]
        if not matches:
            scored.append(score_case(c,None))
        for p in matches:
            r=review_map.get(digest_value(p))
            values=oracle.get(c['id'])
            if values is not None and digest_value(values)!=c['expected'].get('oracle_sha256'):
                raise ValueError('stale local oracle: '+c['id'])
            result=score_case(c,p,values,r)
            result['critical_error']=None
            if c.get('blockers'):
                result.update(quantitative_pass=False,blockers=c['blockers'])
                if p.get('execution_status')=='observed':
                    result['status']='unobserved'
            if r and review_valid(c,p,r):
                second=r.get('second_review')
                needs_second=bool(second) or digest_value(p) in sampled or r.get('critical_error') is True or any(v==0 for v in r['scores'].values())
                agreement=(review_valid(c,p,second) and second['reviewer']!=r['reviewer'] and second['scores']==r['scores']
                           and second.get('critical_error')==r.get('critical_error'))
                if needs_second and not agreement:
                    result['status']='pending_second_review'
                    result['qualitative_scores']=None
                else:
                    result['critical_error']=r.get('critical_error')
                if r.get('critical_error') is True or any(v==0 for v in r['scores'].values()):
                    result['status']='failed' if agreement else 'pending_second_review'
            result.update(category=c['category'],group_id=c['group_id'],repeat=p.get('repeat'),profile=p.get('profile'))
            scored.append(result)
    totals=summary(cases,predictions,scored)
    categories={}
    for category in sorted({c['category'] for c in cases}):
        selected=[r for r in scored if r.get('category')==category]
        categories[category]={'attempts':len(selected),'quantitative_pass':sum(r['quantitative_pass'] for r in selected)}
    qualitative={k:{'n':len(v:=[r['qualitative_scores'][k] for r in scored if r.get('qualitative_scores') and r['qualitative_scores'][k] is not None]),
                    'mean':statistics.mean(v) if v else None,'distribution':{str(i):v.count(i) for i in (0,1,2)}} for k in RUBRIC}
    return dict(summary=totals,categories=categories,quantitative=scored,qualitative=qualitative,
                case_contracts_sha256=digest_value([{k:c[k] for k in ('id','input','expected')} for c in cases]),
                provider_sha256=sorted({p.get('provider_sha256','unobserved') for p in predictions}),
                adoption='pending_human_gold_and_response_review',combined_score=None)


def compare(baseline,candidate):
    if baseline['case_contracts_sha256']!=candidate['case_contracts_sha256'] or baseline['provider_sha256']!=candidate['provider_sha256']:
        raise ValueError('different case contracts/source snapshots cannot isolate model effects')
    def indexed(report):
        result={}
        for row in report['quantitative']:
            result.setdefault(row['id'],[]).append(row)
        return result
    before,after=indexed(baseline),indexed(candidate)
    if before.keys()!=after.keys() or any(len(before[k])!=len(after[k]) for k in before):
        raise ValueError('compare the same cases and repeat count')
    if baseline['categories'].keys()!=candidate['categories'].keys() or any(
        baseline['categories'][k]['attempts']!=candidate['categories'][k]['attempts'] for k in baseline['categories']):
        raise ValueError('different category coverage cannot establish quality maintenance')
    regressions=[]
    for key,attempts in before.items():
        threshold=len(attempts)//2+1
        if sum(x['quantitative_pass'] for x in attempts)>=threshold and sum(x['quantitative_pass'] for x in after[key])<threshold:
            regressions.append(key)
    category_drops=[]
    for category,b in baseline['categories'].items():
        a=candidate['categories'].get(category)
        if not a or not b['attempts'] or not a['attempts']:
            continue
        if a['quantitative_pass']/a['attempts'] < b['quantitative_pass']/b['attempts']:
            category_drops.append(category)
    qualitative_drops=[k for k in RUBRIC if baseline['qualitative'][k]['mean'] is not None and candidate['qualitative'][k]['mean'] is not None
                       and candidate['qualitative'][k]['mean']<baseline['qualitative'][k]['mean']]
    case_qualitative_drops=[]
    for key in before:
        for dimension in RUBRIC:
            b=[r['qualitative_scores'][dimension] for r in before[key] if r.get('qualitative_scores') and r['qualitative_scores'][dimension] is not None]
            a=[r['qualitative_scores'][dimension] for r in after[key] if r.get('qualitative_scores') and r['qualitative_scores'][dimension] is not None]
            if b and a and (statistics.mean(a)<statistics.mean(b) or (0 in a and 0 not in b)):
                case_qualitative_drops.append({'id':key,'dimension':dimension})
    critical=any(r.get('critical_error') is True for r in candidate['quantitative'])
    unreviewed=any(r['status'] in ('pending_review','pending_second_review','not_executed','unobserved') or r.get('critical_error') is None
                   for report in (baseline,candidate) for r in report['quantitative'])
    return {'adoption':'blocked_quality_regression' if regressions or category_drops or qualitative_drops or case_qualitative_drops or critical else
            'pending_review_or_execution' if unreviewed else 'eligible_for_human_decision',
            'regressions':regressions,'category_drops':category_drops,'qualitative_drops':qualitative_drops,
            'case_qualitative_drops':case_qualitative_drops,
            'critical_error':critical,'combined_score':None,'official_performance':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['validate','manifest','run','score','review','compare'])
    parser.add_argument('--cases',type=Path,default=BASE/'pilot.jsonl')
    parser.add_argument('--cache',type=Path,default=ROOT/'.venv/cache/kosis-bok-reproduction/evaluation-v1')
    parser.add_argument('--observations',type=Path)
    parser.add_argument('--reviews',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--mode',choices=['offline','model_fixed','live'],default='offline')
    parser.add_argument('--profile',choices=['baseline','sol','mixed'],default='baseline')
    parser.add_argument('--repeats',type=int,choices=[1,3],default=1)
    parser.add_argument('--adapter',type=Path)
    parser.add_argument('--allow-paid',action='store_true')
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--candidate',type=Path)
    args=parser.parse_args()
    if args.command=='manifest':
        manifest=read(BASE/'manifest.json')
        manifest['files']={name:digest_file(BASE/name) for name in manifest['files']}
        cases=rows(BASE/'pilot.jsonl')+rows(BASE/'supplemental.jsonl')
        manifest['counts']['human_approved']=sum(c['review']['human_approved'] is True for c in cases)
        write(BASE/'manifest.json',manifest)
        validate()
        return
    if args.command=='validate':
        validate();return
    cases=rows(args.cases)
    output=args.output or args.cache/(args.command+'.json')
    allowed=(ROOT/'.venv/cache').resolve()
    if not output.resolve().is_relative_to(allowed):
        raise ValueError('numeric/output/review artifacts must stay in ignored .venv/cache/')
    if output.exists():
        raise ValueError('refusing to overwrite prior run/review: choose a new output')
    if args.command=='compare':
        if not args.baseline or not args.candidate:
            parser.error('--baseline and --candidate score reports are required')
        write(output,compare(read(args.baseline),read(args.candidate)))
        print('Saved comparison:',output)
        return
    if args.command=='run':
        predictions=run(cases,args.cache/'provider.json',args.mode,args.adapter,args.profile,args.repeats,args.allow_paid)
        write_rows(output,predictions)
    else:
        if not args.observations:
            parser.error('--observations is required')
        predictions=rows(args.observations)
        if args.command=='review':
            packets,mapping=blind_packets(cases,predictions)
            write_rows(output,packets)
            write(output.with_suffix('.mapping.json'),mapping)
        else:
            write(output,score(cases,predictions,read(args.cache/'oracles.json'),rows(args.reviews) if args.reviews else []))
    print('Saved local artifact:',output)


if __name__=='__main__':
    main()
