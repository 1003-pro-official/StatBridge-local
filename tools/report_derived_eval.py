"""Generate scoped reports from recorded runs, never turn missing runs into PASS."""
import hashlib,json,math,re,statistics,xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'eval'

def read(name):
    p=OUT/name
    return json.loads(p.read_text(encoding='utf8')) if p.exists() else None

def write(name,text):(OUT/name).write_text(text.rstrip()+'\n',encoding='utf8')
def percentile(values,p):
    if not values:return None
    values=sorted(values);return values[max(0,math.ceil(len(values)*p)-1)]

def perf(report):
    if report is None:return {'status':'SKIPPED'}
    rows=[r for r in report['records'] if r['status']!='SKIPPED'];lat=[r['latency_seconds'] for r in rows]
    calls=[len(r.get('calls',[])) for r in rows]
    stages={}
    for r in rows:
        for c in r.get('calls',[]):
            name=c.get('action') if c.get('stage')=='planning' else c.get('stage')
            b=stages.setdefault(name or 'unknown',{'calls':0,'seconds':0.,'input_tokens':0,'output_tokens':0})
            b['calls']+=1;b['seconds']+=c['seconds']
            for key in ('input_tokens','output_tokens'):b[key]+=c.get('usage',{}).get(key,0)
    return {'n':len(rows),'latency_p50_seconds':percentile(lat,.5),'latency_p95_seconds':percentile(lat,.95),
        'gpt_calls_total':sum(calls),'gpt_calls_mean':statistics.mean(calls) if calls else None,
        'tokens_total':sum(r.get('tokens',{}).get('total_tokens',0) for r in rows),
        'tokens_mean':statistics.mean([r.get('tokens',{}).get('total_tokens',0) for r in rows]) if rows else None,
        'stages':stages,'cost':{'status':'NOT_ESTIMATED','reason':'Official unit prices not verified in this run'}}

def regression(name, directory=None):
    folder=Path(directory) if directory is not None else OUT
    p=folder/(name+'.xml');metadata=folder/(name+'.json')
    meta=json.loads(metadata.read_text(encoding='utf8')) if metadata.exists() else None
    if not p.exists():return {'status':'RUNNING_OR_SKIPPED','meta':meta}
    root=ET.parse(p).getroot();cases=root.findall('.//testcase')
    failed=sum(c.find('failure') is not None or c.find('error') is not None for c in cases)
    skipped=sum(c.find('skipped') is not None for c in cases)
    log=(folder/(name+'.txt')).read_text(encoding='utf8') if (folder/(name+'.txt')).exists() else ''
    subtests=re.search(r'(\d+) subtests passed',log)
    return {'status':'PASS' if not failed and meta and meta['returncode']==0 else 'FAIL','tests':len(cases),
            'passed_subtests':int(subtests.group(1)) if subtests else 0,
            'passed':len(cases)-failed-skipped,'failed':failed,'skipped':skipped,'meta':meta}

def paired(before,after):
    if not before or not after:return {'status':'SKIPPED'}
    old={r['id']:r for r in before['records']};rows=after['records'];result={}
    for split in ('all','dev','holdout'):
        selected=[r for r in rows if split=='all' or r['split']==split]
        result[split]={'n':len(selected),'before_pass':sum(old[r['id']]['status']=='PASS' for r in selected),
            'after_pass':sum(r['status']=='PASS' for r in selected),
            'regressions':[r['id'] for r in selected if old[r['id']]['status']=='PASS' and r['status']!='PASS'],
            'fixed':[r['id'] for r in selected if old[r['id']]['status']!='PASS' and r['status']=='PASS']}
    return result

def main():
    before=read('derived_before_offline_all.json');after=read('derived_after_offline_all.json')
    live_before=read('derived_before_live_all.json');live=read('derived_after_live_all.json');kosis=read('derived_after_kosis_all.json')
    manifest=read('derived_goldset_manifest.json');e2e=read('derived_e2e_results.json');injection=read('derived_metadata_injection_live.json')
    offpair=paired(before,after);livepair=paired(live_before,live)
    regression_results={name:regression(name) for name in ('derived_regression_full','derived_regression_targeted')}
    failures=[]
    for name,run in [('before_offline',before),('before_live',live_before),('after_live_round1',read('derived_after_live_round1.json')),
                     ('after_kosis_round1',read('derived_after_kosis_round1.json')),('after_offline',after),('after_live',live),('after_kosis',kosis)]:
        if not run:continue
        final={r['id']:r for r in (after if 'offline' in name else kosis if 'kosis' in name else live)['records']}
        for r in run['records']:
            if r['status']!='FAIL':continue
            fixed=final.get(r['id'],{}).get('status')=='PASS'
            failures.append({'run':name,'id':r['id'],'category':r['category'],'split':r['split'],
                'type':r.get('failure_type'),'detail':r.get('detail'),'error':r.get('error'),
                'final_status':'FIXED_OR_NOT_REPRODUCED' if fixed else 'OPEN_REVIEW_REQUIRED',
                'note':'Live model nondeterminism: a later pass alone does not prove a code fix.'})
    final_failures=[r for r in (live or {}).get('records',[]) if r['status']=='FAIL']
    checks={
        'approved_sources_only':{'status':'PASS_WITH_SCOPE','scope':'40 adversarial component cases, selected live plans and real KOSIS queries only','observed_unauthorized_accesses':0},
        'no_arbitrary_execution':{'status':'PASS_WITH_SCOPE','scope':'enum-only executor, schema rejection and one browser malicious edit; no complete sandbox proof'},
        'numerical_accuracy':{'status':'PASS' if after and after['summary']['failed']==0 and kosis and kosis['summary']['failed']==0 else 'FAIL',
            'synthetic_points':after['summary']['checked_synthetic_points'] if after else 0,'real_points':sum(r.get('numerical_check',{}).get('checked_points',0) for r in (kosis or {}).get('records',[]))},
        'economic_semantic_correctness':{'status':'LIMITATION','reason':'All author labels lack independent human expert approval; formula structural agreement is not semantic proof'},
        'general_query_regression':regression_results['derived_regression_full'],
        'graph_edit_and_restore':{'status':(e2e or {}).get('status','SKIPPED'),'detail':e2e},
        'holdout_no_regressions':{'status':'FAIL' if livepair.get('holdout',{}).get('regressions') else 'PASS',
            'offline':offpair.get('holdout'),'live':livepair.get('holdout'),'blind':False},
        'all_failures_recorded':{'status':'PASS','count':len(failures)},
        'all_300_live_planning':{'status':'LIMITATION','executed':(live or {}).get('summary',{}).get('executed',0),'unexecuted':300-(live or {}).get('summary',{}).get('executed',0)}}
    report={'schema_version':'1.0','date':'2026-10-19','overall_status':'LIMITATION_WITH_RECORDED_FAILURE',
        'ai_assisted':True,'official_benchmark':False,'goldset':manifest,
        'offline_before':(before or {}).get('summary'),'offline_after':(after or {}).get('summary'),
        'live_before':(live_before or {}).get('summary'),'live_after':(live or {}).get('summary'),'kosis_after':(kosis or {}).get('summary'),
        'paired_offline':offpair,'paired_live':livepair,'regression':regression_results,'completion_checks':checks,
        'performance_before':perf(live_before),'performance_after':perf(live),
        'unmeasured_metrics':['expert Formula Semantic Accuracy','broad naturalistic Intent Accuracy','OS peak RSS','blind holdout generalization'],
        'failures':failures}
    lm=(live or {}).get('summary',{}).get('metrics',{})
    provenance=[bool(r.get('receipt',{}).get('sha256') and r.get('receipt',{}).get('plan') and r.get('raw_sources') and r.get('record_file') and (OUT.parent/r['record_file']).exists()) for r in (kosis or {}).get('records',[]) if r.get('receipt')]
    report['requested_metrics']={
        'Intent Accuracy':{'status':'LIMITATION','proxy':lm.get('Intent Result Agreement'),'reason':'result-class agreement for drafted labels, not independent expert intent annotation'},
        **{name:lm.get(name,{'status':'NOT_MEASURED'}) for name in ('Table Selection Precision','Table Selection Recall','Item Selection Accuracy','DAG Validity Rate','Safe Refusal Rate','Clarification Appropriateness')},
        'Formula Semantic Accuracy':{'status':'LIMITATION','expert_approved_n':0,'structural_proxy':lm.get('Formula Structural Agreement')},
        'Numerical Accuracy':{'synthetic':(after or {}).get('summary',{}).get('metrics',{}).get('Numerical Accuracy'),'actual':(kosis or {}).get('summary',{}).get('metrics',{}).get('Numerical Accuracy')},
        'Edit Consistency':{'component':(after or {}).get('summary',{}).get('metrics',{}).get('Edit Consistency'),'e2e_status':(e2e or {}).get('status','SKIPPED')},
        'Provenance Completeness':{'status':'measured' if provenance else 'NOT_MEASURED','n':len(provenance),'value':sum(provenance)/len(provenance) if provenance else None,'scope':'actual KOSIS subset receipts, source data and persisted node records'},
        'Latency p50/p95':perf(live),
        'GPT Calls per Request':perf(live).get('gpt_calls_mean'),
        'Tokens per Request':perf(live).get('tokens_mean'),
        'Estimated Cost':{'status':'NOT_ESTIMATED','reason':'official prices not verified'},
        'conditional_selection_denominator':'Table/item scores only apply to returned planned requests; failed/refused computations remain in result agreement denominator',
        'safe_stop_rate':{'value':sum(r.get('planning',{}).get('status') in {'unavailable','need_details'} for r in (live or {}).get('records',[]) if r['category']=='unavailable')/6 if live else None,'n':6 if live else 0,'scope':'no computation attempted for unavailable/outside subset; distinct from exact unavailable response-class score'}}
    target=read('derived_target_verification.json')
    if target:report['target_verification']=target
    write('derived_evaluation_results.json',json.dumps(report,ensure_ascii=False,indent=2))
    evidence={'actual_provider_reports':['derived_before_live_all.json','derived_after_live_round1.json','derived_after_live_all.json'],
        'actual_kosis_reports':['derived_after_kosis_round1.json','derived_after_kosis_all.json'],'raw_calculations':'derived_live_records/',
        'live_planner':(live or {}).get('summary'),'kosis':(kosis or {}).get('summary'),'e2e':e2e,
        'metadata_injection':injection,'keys_exposed':False,'mock_counts_as_live':False,
        'limitations':['30/300 selected planning questions','4/300 representative real KOSIS queries','one browser scenario','expert labels pending'],
        'api_failure_taxonomy':['model_provider_error','source_api_error','source_data_absent','validation_error','analysis_error']}
    write('derived_live_evidence.json',json.dumps(evidence,ensure_ascii=False,indent=2))
    rows=['# 파생지표 패치 전후 비교','', 'ai-assisted · 정답 초안 · 비공개 블라인드 성능이 아닙니다.','',
        '| 평가 | 분할 | 패치 전 통과 | 패치 후 통과 | 회귀 |','|---|---|---:|---:|---|']
    for mode,pair in [('오프라인',offpair),('실제 GPT-5.4',livepair)]:
        for split,v in pair.items():
            if isinstance(v,dict):rows.append(f'| {mode} | {split} ({v["n"]}) | {v["before_pass"]} | {v["after_pass"]} | {", ".join(v["regressions"]) or "0"} |')
    rows+=['','오프라인 통과는 모델 의도 해석 성능이 아닙니다. 모호한 질문 40건은 라우팅만, 자료 부재 안내 일부는 scripted contract만 검사합니다.',
           '최종 live 표본은 저온 단일 실행이며 모델 비결정성이 있습니다. round1(24/30), 최종(29/30)을 모두 보존했습니다. 반복 통계적 유의성은 측정하지 않았습니다.',
           'live unavailable-011은 외부 ECOS 사용을 거부하고 분자·분모를 되묻습니다. 안전하게 중단했지만 정답의 명시적 unavailable 분류와 달라 FAIL이며 회귀로 유지합니다.',
           '기준선 소스와 manifest는 derived_baseline_20261019/에 보존되어 있습니다. 정답 SHA는 두 평가에서 동일합니다.']
    write('derived_before_after_comparison.md','\n'.join(rows))
    rows=['# 실패 원인 및 처리 상태','','ai-assisted · 모든 최종 실패를 숨기지 않고 유지합니다.','',
          '기준선의 초기 실행 21개 실패 중 memory 2개는 평가기 문제였습니다. 원래 입력은 500,000 셀에 못 미쳤습니다. 격리된 1,000 셀 시험 한도로 경계를 검사하도록 고친 공통 평가기로 기준선을 다시 실행해 19개 실패를 확정했습니다. 정답은 바꾸지 않았습니다.',
          '초기 targeted 실행의 PYTHONPATH 누락으로 collection error 2개가 있었으며 실행기에 경로를 지정해 재실행했습니다. 제품 결함으로 집계하지 않습니다.','',
          '| 실행 | 사례 | 실패 유형 | 최종 처리 |','|---|---|---|---|']
    for f in failures:rows.append(f'| {f["run"]} | {f["id"]} | {f["type"] or f.get("error") or "specification disagreement"} | {f["final_status"]} |')
    rows+=['','개발셋의 시작 결측 누적합, 주기 누락, 100원 로그, 비객체 JSON, 직접 fetch 승인 경계, 출력 주기·라벨 변조를 최소 패치했습니다.',
           '감사에서 재지수화 지수 차이 단위(포인트), 실제 연간 주기 A 및 전각 ＝100 호환성도 별도 재현·회귀로 확인했습니다.',
           '초기 실제 GPT 실패는 과거 이력 조회 범위를 못 받은 의미 검토, 반복 검색 한도 소진, 지수의 원화 기준과 금액 혼동, 수식/응답 분류 불일치입니다.',
           '최종 실패 unavailable-011은 홀드아웃이므로 이를 통과시키는 문항별 규칙을 추가하지 않았습니다. 정답 분류 적정성 및 명시적 거부+추가질문의 처리 정책은 전문가 재판정이 필요합니다.',
           'FIXED_OR_NOT_REPRODUCED는 해당 입력이 최종 실행에서 통과했다는 뜻입니다. 실모델의 모든 변화가 코드 패치 때문이라는 인과 주장은 하지 않습니다.']
    write('derived_failure_analysis.md','\n'.join(rows))
    rows=['# GPT 호출 및 성능','','실제 요청 지연은 네트워크·병렬 실행·프롬프트 캐시 영향을 포함합니다. 추정 가격은 공식 단가를 확인하지 않아 산출하지 않았습니다.','',
          '| 구간 | n | 지연 p50 초 | p95 초 | GPT 호출/요청 | 토큰/요청 |','|---|---:|---:|---:|---:|---:|']
    for name,run in [('패치 전',live_before),('패치 후 최종',live)]:
        p=perf(run)
        if p.get('n'):rows.append(f'| {name} | {p["n"]} | {p["latency_p50_seconds"]:.3f} | {p["latency_p95_seconds"]:.3f} | {p["gpt_calls_mean"]:.3f} | {p["tokens_mean"]:.1f} |')
    rows+=['','| 단계/반환 action | 전 호출수 | 후 호출수 | 전 초 합계 | 후 초 합계 | 전 입력/출력 토큰 | 후 입력/출력 토큰 |','|---|---:|---:|---:|---:|---|---|']
    a=perf(live_before).get('stages',{});b=perf(live).get('stages',{})
    for name in sorted(set(a)|set(b)):
        x=a.get(name,{});y=b.get(name,{})
        rows.append(f'| {name} | {x.get("calls",0)} | {y.get("calls",0)} | {x.get("seconds",0):.3f} | {y.get("seconds",0):.3f} | {x.get("input_tokens",0)}/{x.get("output_tokens",0)} | {y.get("input_tokens",0)}/{y.get("output_tokens",0)} |')
    rows+=['','검색·메타데이터 action은 그 다음 도구를 요청하는 GPT 호출의 시간입니다. 로컬 카탈로그 CPU 검색만의 p50/p95는 별도 계측하지 않았습니다.',
           '남은 검색 호출 수와 종료 지침을 전달했습니다. CPI 부재 질문은 여전히 최대 9회 수준이므로 추가 최적화가 필요합니다. 일반 계산에서도 메타데이터 조회→계획→의미 검토로 약 3회가 필요합니다.',
           '검증된 그래프의 숫자 매개변수 수정과 기간 변경은 기존 결정론적 revise 경로를 사용해 GPT 호출 0회가 가능합니다. 연산·입력 변경은 자연어 계획과 의미 검토를 다시 거칩니다.',
           '세션 내 원자료/중간 노드 캐시와 부족한 과거 구간만 조회하는 동작을 회귀 검사했습니다. 다른 사용자 사이의 공용 결과 캐시는 구현하지 않았습니다. 계정·카탈로그 버전·원자료 개정·기간·단위를 키에 포함하고 자료 신선도 정책을 정한 뒤 검토해야 합니다.',
           '유효 DAG의 셀·연산 수 제한은 Python 객체의 실제 RSS/CPU 시간 하드 격리가 아닙니다. 메모리 시험은 낮춘 논리 셀 예산을 사용했으며 OS 메모리 상한을 검증했다고 주장하지 않습니다.']
    write('derived_performance_report.md','\n'.join(rows))
    print(json.dumps({'offline_after':(after or {}).get('summary',{}).get('passed'),'live_after':(live or {}).get('summary',{}).get('passed'),'regression':regression_results},ensure_ascii=False))

if __name__=='__main__':
    if (OUT/'derived_v7_related_holdout_150_live.json').exists():
        from report_derived_v7 import main as v7_main
        v7_main()
    elif (OUT/'derived_v6_live_api_300.json').exists():
        from report_derived_v6 import main as v6_main
        v6_main()
    elif (OUT/'derived_v5_live_300.json').exists():
        from report_derived_followup import main as followup_main
        followup_main()
    else:
        main()
