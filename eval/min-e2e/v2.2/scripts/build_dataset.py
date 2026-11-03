raise SystemExit("Legacy v1 generator disabled in vNext; use patch_reviewed_dataset.py and render_reviewed.py. Original files are preserved at baseline_reference/source_hashes.json references.")
"""ai-assisted authoring. Never infer an oracle from product predictions."""
from pathlib import Path
from copy import deepcopy
import csv, json, re, hashlib, zipfile

ROOT=Path(__file__).resolve().parents[1]
CATALOG=ROOT.parent/'StatBridge'/'StatBridge-local1'/'data'/'processed'
def write(path,data):
    p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(data if isinstance(data,str) else json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def csvrows(name):return list(csv.DictReader((CATALOG/name).open(encoding='utf-8-sig')))
MASTER={r['TBL_ID']:r for r in csvrows('bok_table_master.csv')}
ITEMS=csvrows('bok_items.csv');CLASSES=csvrows('bok_classifications.csv')
def source(tid,freq,start,end,*selectors):
    its=[r for r in ITEMS if r['TBL_ID']==tid];assert len(its)==1,(tid,len(its))
    cl={}
    for dimension,suffix in enumerate(selectors,1):
        candidates=[r for r in CLASSES if r['TBL_ID']==tid and r['OBJ_ID_SN']==str(dimension) and r['ITM_ID'].endswith('.'+suffix)]
        assert len(candidates)==1,(tid,dimension,suffix,len(candidates))
        cl['objL'+str(dimension)]=candidates[0]['ITM_ID']
    return dict(org_id='301',table_id=tid,item_id=its[0]['ITM_ID'],classifications=cl,frequency=freq,start_period=start,end_period=end)

# Independently authored from the question, checked against the approved catalog.
DA=[
 source('DT_161Y006','M','202401','202403','BBHA00'),
 source('DT_161Y007','M','202401','202403','BBGS00'),
 source('DT_121Y006','M','202401','202403','BECBLA03'),
 source('DT_121Y015','M','202401','202403','BECBLB0202'),
 source('DT_121Y002','M','202401','202403','BEABAA1'),
 source('DT_131Y018','Q','202401','202404','1103000','E20'),
 source('DT_151Y003','M','202401','202403','1111000','B00'),
 source('DT_200Y104','Q','202401','202404','1400'),
 source('DT_200Y105','Y','2023','2024','1400'),
 source('DT_301Y013','M','202401','202403','000000'),
 source('DT_301Y015','Y','2023','2024','REG0000','CN'),
 source('DT_311Y001','Q','202401','202404','1000000'),
 source('DT_401Y015','M','202401','202403','*AA','W'),
 source('DT_402Y014','M','202401','202403','*AA','D'),
 source('DT_403Y001','M','202401','202403','*AA'),
 source('DT_403Y002','M','202401','202403','*AA'),
 source('DT_403Y005','M','202401','202403','A'),
 source('DT_501Y005','Y','2023','2024','C','A','506'),
 source('DT_284Y001','Y','2023','2024','A1000','T10000'),
 source('DT_284Y002','Y','2023','2024','A1000','T10000')]
ALTERNATIVES={'DA21-08':source('DT_200Y108','Q','202401','202404','10601'),'DA21-09':source('DT_200Y109','Y','2023','2024','10601')}
write('oracle/da_sources.json',{**{f'DA21-{i:02}':s for i,s in enumerate(DA,1)},**{cid+'-equivalent':s for cid,s in ALTERNATIVES.items()}})

CQ_MISSING=['loan_rate_basis','balance_basis','seasonal_adjustment','price_basis','seasonal_adjustment','currency_basis','esi_component','start_and_end_month','comparison_lag','annual_aggregation']
CQ_PROMPTS=[
 '신규취급액/잔액 중 금리 기준','평잔/말잔 중 잔액 기준','원계열/계절조정 여부','명목/실질 중 가격 기준','실질을 유지하고 원계열/계절조정 중 기준', '원화/달러/계약통화 중 어느 기준인지', '경제심리지수 원계열/순환변동치 중 어느 계열인지', '이번 조회의 시작월과 종료월', '전월 대비/전년 동월 대비 중 비교 기준', '월별 12값의 단순평균/12월 값 등 대표값 산출 방식']
CQ_KNOWN=[
 ['가계대출','월별','202401~202403'],['M2 총액','계절조정','202401~202403','구 M2 제외'],['M2 총액','평잔','월별','202401~202403','구 M2 제외'],
 ['GDP 지출 총액','계절조정','분기별','2024Q1~Q4'],['GDP 지출 총액','실질','분기별','2024Q1~Q4'],['수입물가','기본분류 총지수','월별','202401~202403'],
 ['경제심리지수','월별','202401~202403','기업/소비자심리지수 제외'],['가계대출','신규취급액','월별','양식 작성 연도는 조회기간 아님'],['수입물가 총지수','원화','백분율 변화','202401~202403'],['가계대출','신규취급액','2024년 12개월','연간 대표값 1개']]
CQ_RESOLVED=[
 '가계대출 신규취급액 월별 202401~202403. 잔액 금리 제외.',
 'M2 총액 평잔·원계열 월별 202401~202403. 폐기된 말잔·계절조정안 제외.',
 '수입물가 기본분류 총지수 원화 월별 202401~202403. 참고 문헌의 달러는 선택 아님.',
 'DT_200Y108이 제공하는 GDP 지출 총액·가격·계절조정·분기 기준 적용. 2024Q1~Q4.',
 '경제심리지수 원계열과 순환변동치 두 계열 모두 월별 202401~202403.',
 '경제심리지수 원계열 월별 202401부터 실제 마지막 유효 관측월까지. 순환변동치·달력 현재월 채움 금지.',
 '원화 수입물가 총지수의 전년 동월 대비 증가율. 표시 202401~202403; 선행 202301~202303 허용. 전월 대비로 변경 금지.',
 'M2 총액 말잔·계절조정 월별 202401~202403. 색상·제목 후보 때문에 확인 질문하지 않음.',
 '수입물가 기본분류 총지수 달러 월별 202401~202403. 명시 예외가 원화 기본값을 대체.',
 '신규취급액 가계대출 금리 2024년 12개월의 동일 가중 산술평균 1개. 12월 단독·금액 가중평균 금지.']
QT_DERIVED={2,3,6,7,10,12,13,16,17,19}
QT_REASON={1:'제목의 변화율은 연산 지시가 아니며 원지수 6개 조회',2:'6개월 값의 산술평균',3:'1월 기준 2월 상대 증감률',4:'증가율은 후속 작업이며 원지수 2개 조회',5:'월별 공표 금리 3개 조회',6:'2월 금리−1월 금리(%p)',7:'가계대출/판매신용 비율',8:'구성비는 제목이며 잔액 2개 조회',9:'전월 변화는 다음 작업이며 원잔액 조회',10:'부산+대구 합계',11:'원계열 월별 3값 조회',12:'세 값의 최댓값−최솟값',13:'1월=100 재기준화',14:'평잔은 공표 계열 기준이며 3개월 평균 아님',15:'실질화는 절 제목이며 공표된 실질값 조회',16:'1분기 기준 2분기 상대 증감률',17:'3개월 경상수지 합계',18:'누계 제외, 월별 원자료 조회',19:'6개 값 정렬 후 3·4번째 평균(중앙값)',20:'이동평균·재기준화 제외, 월별 원값 조회'}

v2=json.loads((ROOT/'fixtures/v2_source_contract.json').read_text(encoding='utf-8-sig'))
v21=[json.loads(l) for l in (ROOT/'fixtures/v21_queries_source.jsonl').read_text(encoding='utf-8-sig').splitlines() if l.strip()]
base={'title':'2025년 상반기 금리 비교','title_size':20,'legend_visible':True,'legend_position':'top','periods':v2['fixture']['months'],'series':{}}
for alias,color in [('a','#2563EB'),('b','#F97316')]:
    base['series'][alias]={'visible':True,'color':color,'width':2,'dash':'solid','type':'line','unit':'연리%','values':dict(zip(v2['fixture']['months'],v2['fixture'][alias])),'segments':[],'points':{}}
base.update(annotations=[],reference_lines=[],table_series=['a','b'])
write('fixtures/baseline.json',base)
write('fixtures/api_fixture.json',{'origin':'inherited_fixed_public_API_fixture','source_snapshot_date':'2026-10-27 package; original capture date not independently verified','sources':v2['sources'],'data':v2['fixture'],'note':'Provider response boundary only. Never inject plans/answers into product.'})

# A separate reference state model: expected operations are scorer-only.
def op(kind,**kw):return {'op':kind,**kw}
def style(alias,**attrs):return op('style',alias=alias,attrs=attrs)
def title(text):return op('global',attrs={'title':text})
def glob(**attrs):return op('global',attrs=attrs)
def period(a,b):return glob(periods=[f'2025{i:02}' for i in range(a,b+1)])
def seg(alias,a,b,**attrs):return op('segment',alias=alias,start=f'2025{a:02}',end=f'2025{b:02}',attrs=attrs)
def point(alias,m,color):return op('point',alias=alias,period=f'2025{m:02}',color=color)
def file(*formats):return op('download',formats=list(formats))
R='#E53935';G='#16A34A';B='#2563EB'
O={
'E21':[[style('a',color=R,width=4)],[style('a',color=B),style('b',color=R)],[glob(legend_position='bottom')]],
'E22':[[title('대출금리−수신금리: 월별 비교')],[glob(title_size=26)],[style('a',dash='dash')]],
'E23':[[glob(legend_visible=False)],[glob(legend_position='bottom'),style('a',width=4)],[glob(legend_visible=True)]],
'E24':[[title('편집 이력 검증')],[style('a',color=R)],[style('b',dash='dash')],[op('undo',count=2)],[op('redo',count=1)]],
'E25':[[period(2,5)],[style('a',type='bar'),style('b',type='line')],[title('2∼5월 혼합 금리')]],
'E26':[[style('b',color=G,dash='dash',width=4)],[style('b',visible=False)],[title('대출 계열 복원')],[style('b',visible=True)]],
'E27':[[op('selection')],[seg('a',2,4,color=R)],[op('selection')],[style('a',width=4)]],
'E28':[[op('selection')],[point('a',6,R)],[op('selection')],[point('b',6,G)]],
'E29':[[op('selection')],[seg('a',1,2,color=R,dash='dash'),seg('b',5,6,color=G,dash='solid')],[title('두 구간 비교')]],
'E30':[[style('a',width=4)],[period(3,6)],[title('필터 취소 전')],[op('undo',count=2)]],
'E31':[[style('a',type='bar')],[style('a',type='line')],[style('a',dash='dash',width=4),glob(legend_position='bottom')]],
'E32':[[title('빨간색 선과 파란색 선의 비교')],[style('b',color=G)],[glob(title_size=24)]],
'E33':[[op('clarify',slots=['series','range','emphasis_method'])],[seg('a',2,3,color=R,dash='dash')],[glob(legend_position='bottom')]],
'E34':[[style('b',color=G)],[style('b',dash='dash',width=4)],[style('a',width=3)]],
'E35':[[glob(legend_visible=False)],[period(2,6)],[glob(legend_visible=True,legend_position='bottom')],[title('2∼6월 금리')]],
'E36':[[style('a',color=G)],[style('b',color=R)],[op('undo',count=1)],[style('a',dash='dash')]],
'E37':[[op('selection')],[seg('a',3,4,color=R)],[op('selection')],[seg('a',3,4,dash='dash')],[op('clear_segments',alias='a'),style('a',color=B,dash='solid')]],
'E38':[[style('a',type='bar')],[style('b',width=5)],[op('undo',count=1)],[op('redo',count=1)]],
'E39':[[op('selection')],[point('a',4,R)],[op('selection')],[style('b',visible=False)],[style('b',visible=True)]],
'E40':[[style('a',color=R,dash='dash'),glob(legend_position='bottom')],[title('복원 전 금리')],[op('save_resume')],[op('reset')]],
'F21':[[title('금리 비교: 2025 상반기'),glob(title_size=24)],[style('a',color=R,dash='dash',width=4),glob(legend_position='bottom')],[file('png','svg')]],
'F22':[[period(2,5)],[style('a',type='bar')],[file('png','pdf')]],
'F23':[[glob(legend_visible=False)],[file('png')],[glob(legend_visible=True,legend_position='bottom')],[file('png')]],
'F24':[[title('임시 제목')],[style('a',color=R)],[op('undo',count=1)],[file('svg','csv')]],
'F25':[[style('a',width=4)],[style('b',dash='dash')],[op('undo',count=1),op('redo',count=1)],[file('png','pdf')]],
'F26':[[op('selection')],[seg('a',2,3,color=R,dash='dash')],[op('selection')],[style('b',color=G,dash='solid')],[file('svg','png')]],
'F27':[[op('selection')],[point('b',6,R)],[op('selection')],[period(4,6)],[file('png','svg')]],
'F28':[[title('수신·대출 / 상반기 비교')],[op('annotation',text='검토용: 2025.01~06',x=0.90,y=0.10)],[file('png','pdf')]],
'F29':[[op('reference_line',period='202504')],[glob(legend_position='bottom')],[file('svg','pdf')]],
'F30':[[period(2,5)],[glob(table_series=['a'])],[file('csv','xlsx')]],
'F31':[[period(3,6)],[glob(table_series=['b'])],[file('csv','xlsx')]],
'F32':[[style('a',color=R,dash='dash'),title('데이터 불변 확인')],[file('csv','xlsx')]],
'F33':[[style('a',width=4)],[period(4,6)],[op('undo',count=1)],[file('csv','png')]],
'F34':[[style('a',color=R),style('b',visible=False)],[title('초기화 대상')],[op('reset'),file('png','csv')]],
'F35':[[period(2,6)],[style('a',color=R,dash='dash'),glob(legend_position='bottom')],[op('save_resume'),file('svg','png')]],
'F36':[[period(1,4)],[style('a',type='bar'),style('b',type='line')],[title('1∼4월 혼합 비교')],[file('png'),file('xlsx')]],
'F37':[[op('selection')],[seg('a',2,3,color=R,dash='dash'),seg('b',5,6,color=G,dash='solid')],[file('pdf','svg')]],
'F38':[[title('B−A는 계산하지 않은 원금리 비교')],[glob(legend_position='bottom')],[file('png','csv')]],
'F39':[[title('1차 검토')],[file('svg')],[title('2차 검토'),style('a',color=G)],[file('svg')]],
'F40':[[title('저장된 금리 분석')],[op('save_resume')],[period(4,6)],[glob(table_series=['a']),file('csv','xlsx')]]}

def state_contract(operations):
    state=deepcopy(base);undo=[];redo=[];checkpoints=[];downloads=[];revision=0
    for idx,step in enumerate(operations,1):
        mutable=any(o['op'] in {'style','global','segment','point','annotation','reference_line','clear_segments'} for o in step)
        if mutable:undo.append(deepcopy(state));redo.clear();revision+=1
        clarify=None
        for o in step:
            kind=o['op']
            if kind=='style':state['series'][o['alias']].update(o['attrs'])
            elif kind=='global':state.update(o['attrs'])
            elif kind=='segment':
                segments=state['series'][o['alias']]['segments']; found=next((s for s in segments if s['start']==o['start'] and s['end']==o['end']),None)
                if found:found['attrs'].update(o['attrs'])
                else:segments.append({k:deepcopy(o[k]) for k in ['start','end','attrs']})
            elif kind=='point':state['series'][o['alias']]['points'][o['period']]={'color':o['color']}
            elif kind=='clear_segments':state['series'][o['alias']]['segments']=[]
            elif kind=='annotation':state['annotations'].append({k:o[k] for k in ['text','x','y']})
            elif kind=='reference_line':state['reference_lines'].append({'period':o['period']})
            elif kind in {'undo','redo'}:
                src,dst=(undo,redo) if kind=='undo' else (redo,undo)
                for _ in range(o['count']):assert src;dst.append(deepcopy(state));state=src.pop();revision+=1
            elif kind=='reset':state=deepcopy(base);revision+=1
            elif kind=='clarify':clarify={'required':True,'slots':o['slots'],'revision_unchanged':True}
            elif kind=='download':
                for fmt in o['formats']:downloads.append({'ordinal':len(downloads)+1,'step':idx,'format':fmt,'expected_state':deepcopy(state),'reference_revision':revision})
            elif kind in {'selection','save_resume'}:pass
            else:raise ValueError(kind)
        checkpoints.append({'step':idx,'expected_state':deepcopy(state),'clarification':clarify})
    return {'checkpoints':checkpoints,'downloads':downloads,'final_state':state,'require_all_checkpoints':True,'numeric_tolerance':'0.000001','annotation_tolerance':0.03,'pixel_exact_match':False}

cases=[]
for q in sorted(v21,key=lambda q:({'QT':0,'CQ':1,'DA':2}[q['id'][:2]],q['id'])):
    cid=q['id'];g=cid[:2];n=int(cid[-2:])
    common=dict(id=cid,group=g,query=q['query'],source='v2.1 query-only ZIP',oracle_origin='independent_reauthoring_from_query_and_catalog',human_review='pending',product_evaluation_executed=False)
    if g=='QT':
        exp={'label':'derived' if n in QT_DERIVED else 'general','rationale':QT_REASON[n]};metrics=['intent_accuracy']
    elif g=='CQ':
        exp={'clarification_required':n<=10,'missing_slots':[CQ_MISSING[n-1]] if n<=10 else [],'question_target':CQ_PROMPTS[n-1] if n<=10 else None,'preserve_conditions':CQ_KNOWN[n-1] if n<=10 else [CQ_RESOLVED[n-11]],'no_execution_before_answer':n<=10,'not_ambiguity':['metadata_verifying','provider_error'],'semantic_judge_required':True}
        if n==16:exp['latest_policy']={'end':'max_valid_observed_period_of_selected_original_series','never_current_month_default':True,'freeze_reference_before_predictions':True}
        metrics=['clarification_decision','clarification_target','condition_preservation','groundedness']
    else:
        exp={'sources':[DA[n-1]],'periods':([str(y) for y in range(2023,2025)] if DA[n-1]['frequency']=='Y' else [f'2024{i:02}' for i in range(1,5 if DA[n-1]['frequency']=='Q' else 4)]),'extra_series_allowed':False,'extra_periods_allowed':False,'snapshot_file':f'oracle/source_snapshots/{cid}.json','numeric_tolerance':'0.000001','raw_values_only':True,'requires_table':True,'requires_chart':False}
        metrics=['source_exact_match','period_frequency_match','numeric_unit_match','output_contract','groundedness']
    if g=='DA' and cid in ALTERNATIVES:
        exp['allowed_source_sets']=[[DA[n-1]],[ALTERNATIVES[cid]]]
        exp['equivalence_snapshot_file']=f'oracle/source_snapshots/{cid}-equivalent.json'
        exp['equivalence_policy']='Alternative only accepted after full requested-period value/unit equivalence validation; human review pending.'
    common.update(expected=exp,metrics=metrics);cases.append(common)
for c in v2['cases']:
    g={'edit':'E','screen_file':'F','derived':'D'}[c['group']]
    common=dict(id=c['id'],group=g,query=c['query'],purpose=c['purpose'],source='v2 ZIP',oracle_origin='inherited_v2_contract_with_structured_reference_model',reference_text=c['answer'],human_review='pending',product_evaluation_executed=False)
    if g=='D':
        common['expected']={k:deepcopy(c[k]) for k in ['expected','unit','plan','history']}
        common['expected'].update(tolerance=v2['absolute_tolerance'],fixture_file='fixtures/api_fixture.json',source_identity_policy='complete source set, not table_id only',plan_equivalence='equivalent numerical/economic operations accepted; node names not required')
        common['metrics']=['source_exact_match','period_frequency_match','numeric_unit_match','groundedness']
    else:
        common['expected']=state_contract(O[c['id']]);common['reference_operations']=O[c['id']]
        common['metrics']=['edit_contract','output_contract']+(['screen_file_consistency'] if g=='F' else [])
    cases.append(common)
assert len(cases)==120
write('oracle/cases.jsonl',''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in cases))
write('runner/questions.jsonl',''.join(json.dumps({'id':c['id'],'query':c['query']},ensure_ascii=False)+'\n' for c in cases))
steps={}
for c in cases:
    chunks=[s.strip().strip('→').strip() for s in re.split('[①②③④⑤⑥⑦⑧⑨⑩]',c['query']) if s.strip().strip('→').strip()]
    if c['group'] in ['E','F']:assert len(chunks)==len(c['expected']['checkpoints']),(c['id'],len(chunks),len(c['expected']['checkpoints']))
    steps[c['id']]={'setup':'baseline_graph' if c['group'] in ['E','F'] else 'fresh_chat','ordered_steps':[{'step':i,'kind':'ui_or_mixed' if '[UI' in s else 'query','instruction':s} for i,s in enumerate(chunks,1)]}
write('runner/scenarios.json',steps)
write('oracle/authoring_manifest.json',{'date':'2026-10-28','cases':120,'groups':{g:sum(c['group']==g for c in cases) for g in ['QT','CQ','DA','D','E','F']},'source_zip_hashes':{name:hashlib.sha256(Path(path).read_bytes()).hexdigest() for name,path in [('v2',r'C:\Users\<user>\Downloads\v2.zip'),('v2.1',r'C:\Users\<user>\Downloads\v2.1_고난도60_질의전용평가_20261027.zip')]},'v21_original_gold_missing':True,'reconstructed_oracle_not_original_gold':True,'human_review':'pending','product_evaluation_executed':False,'ragas_judge_executed':False})
all_sources=DA+v2['sources']+list(ALTERNATIVES.values())
write('oracle/catalog_excerpt.json',{'origin':'approved_local1_processed_catalog','files_sha256':{n:hashlib.sha256((CATALOG/n).read_bytes()).hexdigest() for n in ['bok_table_master.csv','bok_items.csv','bok_classifications.csv']},'tables':{tid:MASTER[tid] for tid in sorted({s['table_id'] for s in all_sources})},'items':[r for r in ITEMS if r['TBL_ID'] in {s['table_id'] for s in all_sources}],'classifications':[r for r in CLASSES if r['ITM_ID'] in {v for s in all_sources for v in s['classifications'].values()}]})
print(json.dumps({'authored':len(cases),'groups':{g:sum(c['group']==g for c in cases) for g in ['QT','CQ','DA','D','E','F']}},ensure_ascii=False))
