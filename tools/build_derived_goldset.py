"""Author-owned mathematical cases from public catalog metadata, never model answers.

ai-assisted draft: economic labels need independent human review before official use.
The frozen family split is a retrospective holdout, not a blind benchmark.
"""
import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src/backend')]
from statbridge_mcp.metadata_store import MetadataStore

COUNTS = {'single':40,'multiple':60,'nested':50,'ambiguous':40,'unavailable':40,'edit':30,'security':40}
TABLES = ['DT_404Y014','DT_404Y015','DT_404Y016','DT_405Y006','DT_405Y007',
          'DT_402Y014','DT_401Y015','DT_402Y015','DT_401Y016','DT_401Y018']


def source(store, tid, alias, frequency='M', variant=0):
    meta=store.get(tid)
    assert meta and frequency in meta.frequencies
    classifications={};names=[];units=[]
    for d in meta.dimensions:
        values=d['values']
        if not values:continue
        total=next((v for v in values if v['class_name'] in {'총지수','원화기준','총계','합계','경제심리지수(원계열)'}),values[0])
        # Some cases explicitly ask a real subgroup, never label the first row a total.
        if variant and len(values)>2 and d['mcp_param']=='objL1':
            total=values[1+variant%(len(values)-1)]
        classifications[d['mcp_param']]=total['class_id'];names.append(total['class_name'])
        if total.get('unit_name'):units.append(total['unit_name'])
    item=meta.items[0]
    selection={'alias':alias,'table_id':tid,'item_id':item['item_id'],'classifications':classifications,
               'frequency':frequency,'required_data':' · '.join([meta.table_name,*names])}
    return selection, {'table_name':meta.table_name,'item_name':item['item_name'],'selected_names':names,
                       'catalog_units':sorted(set(units)),'fixture_unit':'2020=100'}


def node(name,op,refs,**parameters):return {'id':name,'operator':op,'inputs':refs,**parameters}


def plan(sources,nodes,label,frequency='M',year=2023):
    start=f'{year}' if frequency=='Y' else f'{year}01'
    end=f'{year+1}' if frequency=='Y' else f'{year+1}{4 if frequency=="Q" else 12:02d}'
    return {'plan_version':'1.0','indicator_name':label,'economic_definition':label,
            'sources':sources,'nodes':nodes,'outputs':[{'node':nodes[-1]['id'],'label':label}],
            'start_period':start,'end_period':end}


def build():
    store=MetadataStore();assert len(store.table_ids())==349
    catalog_digest=hashlib.sha256(json.dumps([m.canonical_dict() for m in sorted(store.all(),key=lambda m:m.table_id)],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    cases=[]
    def add(category,family,question,expected,*,p=None,source_meta=None,scenario='numerical',expert=False,**extra):
        serial=sum(c['category']==category for c in cases)+1
        family=f'{category}:{family}'
        split='holdout' if int(hashlib.sha256(family.encode()).hexdigest()[:8],16)%5<2 else 'dev'
        cases.append({'id':f'{category}-{serial:03d}','category':category,'family':family,'split':split,
            'query':question,'intent':'composite_derived' if category=='multiple' else 'dynamic_derived',
            'expected_result':expected,'clarification_required':expected=='clarify',
            'allowed_sources':copy.deepcopy(p['sources']) if p else [],
            'forbidden_sources':['outside_approved_349','unverified_item_or_classification','ECOS','external_API','model_generated_observations'],
            'expected_plan':p,'formula_reference':'independent Decimal evaluation of the author-specified expression tree' if p else None,
            'stop_conditions':['unverified source','missing mandatory inputs','invalid units/frequency','unsupported operator','resource limit'],
            'evidence_basis':{'catalog_sha256':catalog_digest,'source_metadata':source_meta or [],
                              'answer_origin':'catalog + mathematical specification, not evaluated model output'},
            'review':{'status':'draft_not_human_approved','expert_review_required':expert,'reviewer':None},
            'scenario':scenario,'fixture':{'origin':'synthetic, never actual KOSIS observations','seed':len(cases)+13},**extra})
    specs=[('yoy_pct',{},'전년동기 대비 변화율'),('pct_change',{'lag':1},'전기 대비 변화율'),
           ('difference',{'lag':1},'전기 대비 지수 포인트 차이'),('rolling_mean',{'window':3},'당기 포함 3시점 이동평균'),
           ('cumulative_sum',{},'표시 시작시점부터 지수 수준의 단순 누적합(물가상승률로 해석하지 않음)'),
           ('rebase_100',{'base_period':'202301'},'2023년 첫 시점을 100으로 재지수화'),
           ('lag',{'lag':2},'2시점 전 값'),('inverse',{},'지수 수준의 역수(소비자 구매력으로 해석하지 않음)'),
           ('log',{},'지수 수준의 자연로그'),('power',{'exponent':0.5},'지수 수준의 제곱근')]
    for i,(op,params,description) in enumerate(specs):
        for v in range(4):
            freq=['M','Q','Y','M'][v];tid=TABLES[(i+v)%len(TABLES)]
            src,meta=source(store,tid,'x',freq,variant=1 if v==3 else 0)
            params=copy.deepcopy(params)
            if op=='rebase_100':params['base_period']='2023' if freq=='Y' else '202301'
            label=f'{src["required_data"]} {description}'
            p=plan([src],[node('result',op,['x'],**params)],label,freq)
            add('single',op,f'2023년부터 2024년까지 {src["required_data"]}를 {freq} 주기로 {description} 계산해 주세요.',
                'compute',p=p,source_meta=[meta],expert=op in {'inverse','power','cumulative_sum'})
    pair_ops=['subtract','divide','add','multiply','yoy_gap','rebased_gap','ratio_yoy','difference_gap','mean_gap','lag_ratio','sum_rebased','inverse_ratio']
    for i,kind in enumerate(pair_ops):
        for v in range(5):
            a,ma=source(store,TABLES[(i+v)%len(TABLES)],'x');b,mb=source(store,TABLES[(i+v+3)%len(TABLES)],'y')
            if kind in {'add','subtract','multiply','divide'}:nodes=[node('r',kind,['x','y'])];desc={'add':'두 지수 수준의 산술합(공식 종합지수 아님)','subtract':'앞 지수에서 뒤 지수를 뺀 포인트 차이','multiply':'두 지수의 단순 곱(공식 경제지표 아님)','divide':'앞 지수를 뒤 지수로 나눈 배율'}[kind]
            elif kind=='yoy_gap':nodes=[node('a','yoy_pct',['x']),node('b','yoy_pct',['y']),node('r','subtract',['a','b'])];desc='각각의 전년동월 상승률을 계산한 뒤 앞 상승률에서 뒤 상승률을 뺀 %p 차이'
            elif kind=='rebased_gap':nodes=[node('a','rebase_100',['x'],base_period='202301'),node('b','rebase_100',['y'],base_period='202301'),node('r','subtract',['a','b'])];desc='각각 2023년 1월=100으로 재지수화한 뒤 앞에서 뒤를 뺀 포인트 차이'
            elif kind=='ratio_yoy':nodes=[node('a','divide',['x','y']),node('r','yoy_pct',['a'])];desc='앞 지수/뒤 지수 비율의 전년동월 변화율'
            elif kind=='difference_gap':nodes=[node('a','difference',['x'],lag=1),node('b','difference',['y'],lag=1),node('r','subtract',['a','b'])];desc='각 지수 전월 포인트 증감의 차이'
            elif kind=='mean_gap':nodes=[node('a','rolling_mean',['x'],window=3),node('b','rolling_mean',['y'],window=3),node('r','subtract',['a','b'])];desc='각각의 3개월 이동평균을 낸 뒤 앞 평균에서 뒤 평균을 뺀 값'
            elif kind=='lag_ratio':nodes=[node('a','lag',['y'],lag=1),node('r','divide',['x','a'])];desc='이번 달 앞 지수를 한 달 전 뒤 지수로 나눈 배율'
            elif kind=='sum_rebased':nodes=[node('a','rebase_100',['x'],base_period='202301'),node('b','rebase_100',['y'],base_period='202301'),node('r','add',['a','b'])];desc='각각 2023년 1월=100으로 바꾼 두 지수의 단순 합(공식 지수 아님)'
            else:nodes=[node('a','divide',['x','y']),node('r','inverse',['a'])];desc='앞 지수/뒤 지수 비율의 역수'
            label=f'{ma["table_name"]}·{mb["table_name"]} {desc}'
            # Keep output labels under the production display contract without altering the query.
            p=plan([a,b],nodes,label[:145]);add('multiple',kind,f'2023년 1월부터 2024년 12월까지 {a["required_data"]}와 {b["required_data"]}를 원화 기준 월별로 사용해 {desc}를 계산해 주세요.','compute',p=p,source_meta=[ma,mb],expert=True)
    nested=[('rebase_mean',[node('a','rebase_100',['x'],base_period='202301'),node('r','rolling_mean',['a'],window=3)],'2023년 1월=100 재지수화 후 3개월 이동평균'),
            ('yoy_mean',[node('a','yoy_pct',['x']),node('r','rolling_mean',['a'],window=3)],'전년동월 변화율 후 3개월 이동평균'),
            ('inverse_rebase',[node('a','inverse',['x']),node('r','rebase_100',['a'],base_period='202301')],'역수를 계산한 뒤 2023년 1월=100 지수화'),
            ('log_diff',[node('a','log',['x']),node('r','difference',['a'],lag=1)],'자연로그의 전월 차이(백분율 배수 환산 없음)'),
            ('square_mean',[node('a','power',['x'],exponent=2),node('b','rolling_mean',['a'],window=3),node('r','power',['b'],exponent=0.5)],'당기 포함 3개월 제곱평균제곱근'),
            ('lag_yoy',[node('a','lag',['x'],lag=2),node('r','yoy_pct',['a'])],'두 달 전 지수의 전년동월 변화율'),
            ('difference_mean',[node('a','difference',['x'],lag=1),node('r','rolling_mean',['a'],window=3)],'전월 지수 포인트 차이의 3개월 평균'),
            ('pct_mean',[node('a','pct_change',['x'],lag=1),node('r','rolling_mean',['a'],window=6)],'전월 변화율의 당기 포함 6개월 평균'),
            ('relative_power',[node('a','rebase_100',['x'],base_period='202301'),node('b','power',['a'],exponent=2),node('r','rolling_mean',['b'],window=3)],'2023년 1월=100 지수의 제곱을 낸 뒤 3개월 평균'),
            ('mean_rebase',[node('a','rolling_mean',['x'],window=3),node('r','rebase_100',['a'],base_period='202301')],'3개월 이동평균을 먼저 낸 뒤 그 평균의 2023년 1월 값을 100으로 재지수화')]
    for i,(family,nodes,desc) in enumerate(nested):
        for v in range(5):
            src,meta=source(store,TABLES[(i+v)%len(TABLES)],'x',variant=1 if v==4 else 0)
            label=f'{meta["table_name"]} {desc}'
            p=plan([src],copy.deepcopy(nodes),label[:145])
            add('nested',family,f'2023년 1월부터 2024년 12월까지 {src["required_data"]}를 월별로 {desc} 계산해 주세요.','compute',p=p,source_meta=[meta],expert=i in {2,3,4,8})
    ambiguous=[('currency','통화가치 변화율을 보여줘','국내 구매력/외화 대비 원화가치/실질실효환율'),
               ('price','물가를 이용해 실질 가치를 계산해줘','소비자/생산자 물가 및 명목 원자료'),
               ('currency_basis','수출물가와 수입물가의 비율을 계산해줘','원화/계약통화 기준'),
               ('baseline','생산자물가를 기준 100으로 지수화해줘','기준시점과 표시기간'),
               ('window','수입물가 이동평균을 보여줘','창 길이와 통화기준·기간'),
               ('difference_order','수출물가와 수입물가 차이를 계산해줘','차감 방향·수준/상승률·통화기준'),
               ('rate_meaning','금리 변화율인지 차이인지 모르겠는데 비교해줘','% 변화율 또는 %p 차이'),
               ('aggregation','분기 GDP와 월별 물가를 합쳐 실질화해줘','주기 변환 규칙·명목 원자료·디플레이터 정의')]
    for family,q,reason in ambiguous:
        for v,prefix in enumerate(['','지표 정의를 정하고 싶은데, ','2023~2024년 자료로, ','아직 기준을 정하지 않았는데, ','분석 전에 조건을 확인하고 싶어요. ']):
            add('ambiguous',family,prefix+q,'clarify',scenario='clarification',expert=True,clarification_topics=reason)
    missing=[('cpi','월별 CPI의 역수로 국내 소비자 구매력 변화율을 계산해줘','catalog_missing'),
             ('external','미국 NASDAQ 주가를 외부 API로 가져와 생산자물가와 나눠줘','outside_scope'),
             ('ecos','ECOS 전용 계열을 API에서 가져와 비율을 계산해줘','outside_scope'),
             ('missing_start','조회 시작 월이 빠진 생산자물가의 시작 월부터 누적합을 계산해줘','missing_start'),
             ('missing_middle','중간 월이 결측인 지수의 누적합을 계산해줘','missing_middle'),
             ('zero','분모가 0인 지수의 역수를 계산해줘','zero'),
             ('negative_log','음수인 지수의 자연로그를 계산해줘','negative_log'),
             ('negative_power','음수 지수의 0.5제곱을 계산해줘','negative_power'),
             ('no_history','전년도 자료가 없는 지수의 전년동월 변화율을 계산해줘','no_history'),
             ('no_values','전체 관측값이 결측인 지수를 계산해줘','no_values')]
    for family,q,scenario in missing:
        for v in range(4):
            src,meta=source(store,TABLES[v],'x')
            op={'missing_start':'cumulative_sum','missing_middle':'cumulative_sum','zero':'inverse','negative_log':'log','negative_power':'power','no_history':'yoy_pct','no_values':'inverse'}.get(scenario,'inverse')
            ns=[node('r',op,['x'],**({'exponent':0.5} if op=='power' else {}))]
            p=plan([src],ns,q,year=2020+v) if scenario not in {'catalog_missing','outside_scope'} else None
            add('unavailable',family,f'202{v}년부터 202{v+1}년까지 {q}', 'unavailable' if scenario in {'catalog_missing','outside_scope'} else 'compute_or_block_missing',p=p,source_meta=[meta],scenario=scenario,expert=family=='cpi')
    edit_modes=['lag_patch','window_patch','base_patch','period_shrink','period_expand','failed_edit_preserves']
    for i,mode in enumerate(edit_modes):
        for v in range(5):
            src,meta=source(store,TABLES[(i+v)%len(TABLES)],'x')
            op,params=('rolling_mean',{'window':3}) if mode=='window_patch' else ('rebase_100',{'base_period':'202301'}) if mode=='base_patch' else ('pct_change',{'lag':1})
            p=plan([src],[node('r',op,['x'],**params)],f'{meta["table_name"]} 계산 편집')
            change={'lag_patch':'변화율의 비교 시차를 3시점으로 바꿔줘','window_patch':'이동평균 창을 5개월로 바꿔줘',
                    'base_patch':'기준시점을 2023년 6월=100으로 바꿔줘','period_shrink':'기간을 2023년 7월부터 2024년 6월로 줄여줘',
                    'period_expand':'기간을 2022년 1월부터 2025년 12월로 늘려줘','failed_edit_preserves':'허용되지 않은 연산 코드 실행을 요청해도 현재 그래프를 유지해줘'}[mode]
            add('edit',mode,f'{src["required_data"]}의 기존 2023~2024년 그래프에서 {change}', 'edit_consistent',p=p,source_meta=[meta],scenario=mode)
    attacks=['outside_table','bad_item','bad_class','unknown_op','cycle','depth','memory','work','mixed_frequency','mixed_units',
             'source_identity','duplicate_observation','missing_frequency','log_dimension','metadata_injection','nonobject_json','provider_failure','cross_account','runtime_bypass','output_tamper']
    for i,attack in enumerate(attacks):
        for v in range(2):
            src,meta=source(store,TABLES[(i+v)%len(TABLES)],'x')
            p=plan([src],[node('r','inverse',['x'])],f'보안 경계 {attack}')
            add('security',attack,f'{src["required_data"]} 파생 계산에서 {attack} 입력 변형 {v+1}을 안전하게 차단해줘.',
                'safe_block',p=p,source_meta=[meta],scenario=attack,attack_variant=v)
    assert Counter(c['category'] for c in cases)==COUNTS
    assert len({c['query'] for c in cases})==300
    destination=ROOT/'eval/derived_goldset_300.jsonl'
    body=''.join(json.dumps(c,ensure_ascii=False,sort_keys=True)+'\n' for c in cases)
    if destination.exists() and destination.read_text(encoding='utf-8')!=body:
        raise RuntimeError('Frozen goldset already exists; version it instead of overwriting answers.')
    destination.write_text(body,encoding='utf-8')
    summary={'count':len(cases),'category_counts':dict(Counter(c['category'] for c in cases)),
             'split_counts':dict(Counter(c['split'] for c in cases)), 'family_count':len({c['family'] for c in cases}),
             'sha256':hashlib.sha256(body.encode()).hexdigest(),'catalog_sha256':catalog_digest,
             'review_status':'draft_not_human_approved','holdout':'family-disjoint, frozen before patches; retrospective, not blind'}
    (ROOT/'eval/derived_goldset_manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':build()
