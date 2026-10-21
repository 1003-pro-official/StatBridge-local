"""Build exposed source contracts from authorized research; keep numeric oracles local."""
import argparse
import copy
import csv
import json
from pathlib import Path

from core import BASE, ROOT, RUBRIC, FrozenProvider, calculate, number, digest_value, digest_file, identity, period, read, write, write_rows


SUPPLEMENTS = {
    'derived': [
        ('전년비 선행기간', '생산자물가 보도자료 갱신용으로 2025년 총지수 전년동월비를 확인해줘.', '12개월 전 같은 달의 실제 관측값을 사용하고 선행기간은 표시하지 않는다.'),
        ('금리차', '금융기관 가중평균금리 표에 넣을 수 있도록 2025년 신규취급액 기준 대출금리와 저축성 수신금리의 월별 차이를 계산해줘.', '같은 기간의 대출금리-수신금리이며 단위는 %p이다.'),
        ('단위 변환', '국제수지 보도자료에 반영할 2025년 경상수지를 월별 억달러로 정리해줘.', '백만달러 원자료를 100으로 나누고 기간·출처를 유지한다.'),
        ('결측과 0 분모', '첨부한 검증용 시계열의 전기비를 계산해 표에 반영하고, 결측과 0 분모는 구분해줘.', '별도 합성 입력에서 결측·0 분모 결과는 null이며 임의 보간하지 않는다.'),
    ],
    'followup': [
        ('기간 변경', '이 그림의 계열과 단위는 유지하고 기간만 2024년으로 바꿔서 자료를 다시 반영해줘.', '기존 계열·주기·단위를 보존하고 기간 자료를 다시 조회한다.'),
        ('비교 계열 변경', '대출금리 비교표에서 중소기업 대신 대기업 금리를 넣어 비교해줘.', '비교 대상만 변경하고 신규취급액 기준을 유지한다.'),
        ('지시어 참조', '보고서 설명에 넣으려는데, 현재 그림에 표시된 계열 가운데 마지막 표시 시점의 값이 가장 높은 항목을 알려줘.', '현재 표시된 계열과 마지막 표시 시점으로 판단한다.'),
        ('재계산', '표시 기간을 바꿨어. 방금 비교한 금리 차이도 바뀐 기간 기준으로 다시 계산해줘.', '기존 답변 수치를 복사하지 않고 최신 표시 자료로 재계산한다.'),
    ],
    'reference_edit': [
        ('이미지 참조', '첨부한 한국은행 그림을 이번 보도자료 도표 서식 참고로 삼아 제목과 범례 위치를 맞춰줘.', '참조 이미지 스타일만 반영하고 조회 계열·수치·출처를 보존한다.'),
        ('PDF 참조', '첨부 PDF 3페이지의 그림을 참고해 현재 보도자료용 그래프 배치를 정리해줘.', '명시한 PDF 페이지를 참조하고 기존 데이터를 보존한다.'),
        ('자료 보존', '참고 이미지의 색상 체계만 적용해줘. 발표 자료에 쓸 수치와 출처는 그대로 유지해줘.', '시점·값·단위·출처와 계산 근거가 편집 전후 동일하다.'),
        ('불명확한 참조', '첨부한 자료와 같은 형식으로 바꿔서 보고서에 넣어줘.', '복수 그림의 대상이 불명확하면 필요한 확인을 하고 숫자를 추측하지 않는다.'),
    ],
    'summary_style': [
        ('단일 사실 선택', '보도자료 문안 검토용으로 현재 금리 그림의 최신 수준과 전월 대비 변화를 요약해줘.', '독립 계산으로 확인한 최신 수치와 변화만 설명한다.'),
        ('복수 사실 선택', '금융기관 가중평균금리 자료 설명에 쓰게 대기업과 중소기업 대출금리의 최신 수준 및 같은 달 차이를 요약해줘.', '두 대출금리 계열의 같은 시점 수치와 대기업-중소기업 차이를 설명한다.'),
        ('스타일 지정', '금리 비교 그림을 보도자료에 넣으려고 해. 제목은 금리 비교로 하고 범례는 아래쪽에 배치해줘.', '제목·범례 요구를 반영하고 수치를 바꾸지 않는다.'),
        ('안전한 폴백', '보고서 초안에 넣을 수 있도록 현재 자료에서 확인되는 사실만 요약해줘.', '모델이 유효하지 않은 fact ID를 반환해도 검증된 기본 요약을 사용한다.'),
    ],
    'report': [
        ('수준과 변화', '금리 동향 보도자료 초안에 쓸 수 있게 현재 그림의 최신 수준과 전월 대비 변화를 포함해 설명문을 작성해줘.', '실제 표시 수치와 %p 변화가 근거와 일치한다.'),
        ('변환값 설명', '생산자물가 전년동월비 그림을 보고서에 설명할 문장으로 정리해줘.', '변환된 증감률을 원지수 수준으로 설명하지 않는다.'),
        ('부분 답변', '금리 동향 보고서에 넣을 금리 변화와 대출액 구성을 각각 설명해줘.', '금리는 답하고 미조회 대출금액 구성은 필요한 자료로 구분한다.'),
        ('인과·전망 요구', '최근 두 달 값이 같은데 하락 원인과 다음 달 값을 보도자료에 확정적으로 써줘.', '두 값이 같아 하락이 아님을 바로잡고 원자료만으로 원인·미래 값을 확정할 수 없다고 안내한다.'),
    ],
    'recovery': [
        ('모델 장애', '생산자물가 보도자료 갱신에 필요한 전년동월비 계산을 이어서 진행해줘.', '모델 장애는 자료 부재로 바꾸지 않고 입력을 유지하며 재시도를 안내한다.'),
        ('API 장애', '국제수지 보도자료 표에 넣을 경상수지를 조회해줘.', '조회 API 장애를 통계 미존재로 단정하지 않는다.'),
        ('자료 부재', '표의 누락 여부를 확인하려고 합니다. 저축성 수신금리의 2026년 7~8월 관측값을 보여줘.', '조회 성공·관측값 부재를 API 장애와 구분한다.'),
        ('잘못된 파일', '보고서에 반영할 자료인데 형식과 단위를 확인해 이 파일을 연결해줘.', '잘못된 형식·단위 파일이 기존 작업을 덮어쓰지 않는다.'),
    ],
}


def pilot_query(original_id, periods):
    """Human task wording; deliberately avoids source catalog labels and output prescriptions."""
    start, end = periods
    start_text = f'{start[:4]}년 {int(start[4:])}월' if 'Q' not in start else f'{start[:4]}년 {start[-1]}분기'
    end_text = f'{end[:4]}년 {int(end[4:])}월' if 'Q' not in end else f'{end[:4]}년 {end[-1]}분기'
    wording = {
        '01-G': f'원계열 경제심리지수 보도자료 그림을 갱신하려고 합니다. {start_text}부터 {end_text}까지 흐름을 확인해줘.',
        '02-G': f'전체 소비자심리지수 표 검토용으로 {start_text} 대비 {end_text} 수치를 비교해줘.',
        '06-T': f'금리 동향 보도자료 갱신을 위해 {start_text}부터 {end_text}까지 저축성 수신금리를 확인해줘.',
        '24-T': f'금융기관 가중평균금리 표에 반영할 대출금리를 {start_text}부터 {end_text}까지 확인해줘.',
        '07-T': f'생산자물가 보도자료 갱신용으로 {start_text}부터 {end_text}까지 흐름을 확인해줘.',
        '08-T': f'원화 기준 수출물가 보도자료 그림을 갱신하려고 합니다. {start_text}부터 {end_text}까지 변화를 확인해줘.',
        '13-T': f'가계신용 동향 표 검토용으로 {start_text}부터 {end_text}까지 규모를 확인해줘.',
        '11-G2-M': f'월중 국제수지 보도자료 그림에 넣을 상품 수출 흐름을 {start_text}부터 {end_text}까지 확인해줘.',
        '11-G3-M': f'국제수지 보고서 설명을 위해 {start_text}부터 {end_text}까지 증권투자 자산 흐름을 확인해줘.',
        '15-G1': f'금융기관 대출행태 자료의 대기업 대출태도 표를 갱신하려고 합니다. {start_text} 대비 {end_text} 수준을 비교해줘.',
        '15-G2': f'금융기관 대출행태 표 갱신용으로 가계 주택대출 태도를 확인하려고 합니다. {start_text}부터 {end_text}까지 비교해줘.',
        '20-G': f'기업경기 조사 보도자료 그림 갱신용으로 제조업 경기 흐름을 {start_text}부터 {end_text}까지 확인해줘.',
    }
    return wording[original_id]


def build(cache, destination=BASE):
    from core import rows
    for name in ('pilot.jsonl','supplemental.jsonl'):
        existing=destination/name
        if existing.exists() and any(c.get('review',{}).get('human_approved') for c in rows(existing)):
            raise ValueError('refusing to overwrite human-approved cases; create a new version')
    verification = cache / 'original-gallery/verification'
    objects_path = verification / 'object-audit.json'
    objects = read(objects_path)
    if len(objects) != 46 or len({o['id'] for o in objects}) != 46:
        raise ValueError('expected 46 unique researched originals')
    sources = {s['bundle_page']: s for s in read(cache / 'original-gallery/original-source-index.json')}
    with (ROOT / 'research/kosis-bok-reproduction/원본목록.csv').open(encoding='utf-8-sig', newline='') as f:
        releases = {r['SHA256']: r for r in csv.DictReader(f)}
    with (ROOT / 'data/processed/bok_classifications.csv').open(encoding='utf-8-sig', newline='') as f:
        labels = {(r['TBL_ID'],r['ITM_ID']):r['ITM_NM'] for r in csv.DictReader(f)}
    with (cache / 'graph19-results/20261020/46개_최신판정.csv').open(encoding='utf-8-sig', newline='') as f:
        previous = {r['ID']: r for r in csv.DictReader(f)}
    index_path = verification / 'live-only/20261019T023917Z/observation-index.json'
    index = read(index_path)
    registry = {}
    for encoded, observations in index.items():
        s = json.loads(encoded)
        key = identity(s)
        entry = registry.setdefault(key, {**{k:s[k] for k in ('table_id','item_id','classifications','frequency','label')},
                                           'unit': '', 'points': {}, 'source_sha256': digest_file(index_path)})
        for p, point in observations.items():
            if point.get('source') != 'kosis_api':
                raise ValueError('only independently cached API observations are allowed')
            p = period(p, s['frequency'])
            if p in entry['points'] and entry['points'][p] != point['value']:
                raise ValueError('conflicting source vintage; explicit selection required')
            entry['points'][p] = point['value']
            if point.get('unit'):
                if entry['unit'] and entry['unit'] != point['unit']:
                    raise ValueError('conflicting units')
                entry['unit'] = point['unit']
    registry_values = [{**s, 'points': [dict(period=p, value=v) for p,v in sorted(s['points'].items())]} for s in registry.values()]
    for s in registry_values:
        s['label'] = ' / '.join(labels.get((s['table_id'],code),code) for code in s['classifications'].values())
    for s in registry.values():
        s['label'] = ' / '.join(labels.get((s['table_id'],code),code) for code in s['classifications'].values())
    FrozenProvider(registry_values)
    local = cache / 'evaluation-v1'
    write(local / 'provider.json', {'source': index_path.relative_to(ROOT).as_posix(), 'source_sha256': digest_file(index_path), 'series': registry_values})
    audit, cases, oracle = [], [], {}
    pilot_targets = ['01-G','02-G','06-T','24-T','07-T','08-T','13-T','11-G2-M','11-G3-M','15-G1','15-G2','20-G']
    for obj in objects:
        source = sources[obj['page']]
        release = releases.get(source['sha256'], {})
        required = []
        for s in obj['required_series']:
            available = registry.get(identity(s))
            required.append({**s, 'unit': available['unit'] if available else None,
                             'snapshot_available': available is not None,
                             'missing_periods': sorted(set(period(p,s['frequency']) for p in s['periods']) - set(available['points'] if available else {}))})
        audit.append(dict(id=obj['id'], title=obj['title'], kind=obj['kind'], group_id='source-'+source['sha256'][:16],
            source={'url':source['url'], 'publication_date':release.get('발간일'), 'sha256':source['sha256'],
                    'pdf_page':source['page'], 'bundle_page':obj['page'], 'path':source['original_pdf']},
            required_series=required, calculation=obj['calculation'], exposed_regression=True,
            evidence={'path':objects_path.relative_to(ROOT).as_posix(), 'sha256':digest_file(objects_path),
                      'cache_snapshot_sha256':digest_file(index_path), 'prior_base_commit':'478d3d5dd9c2bfc2c313bf5148784fd2c2fca6ae'},
            historical={'status':'pending','reason':'공표 당시 전체 수치·자료 버전의 독립 사람 검수 필요'},
            current={'status':'pending','reason':obj.get('known_gap') or '전체 계열·산식·단위 독립 검수 필요; 파일럿은 일부 원자료 확인'},
            previous_verdict=previous[obj['id']]['생산자 검증 판정'],
            review={'human_approved':False,'reviewer':None}))
        if obj['id'] not in pilot_targets:
            continue
        s = obj['required_series'][3 if obj['id']=='24-T' else 0]
        available = registry.get(identity(s))
        if not available or len(available['points']) < 2:
            raise ValueError('pilot source unavailable: '+obj['id'])
        periods = sorted(available['points'])[-2:]
        ref = {k:s[k] for k in ('table_id','item_id','classifications','frequency')}
        ref.update(unit=available['unit'], label=available['label'], periods=periods)
        start, end = periods
        def iso(p, end=False):
            import calendar
            if s['frequency']=='Q':
                month=int(p[-1])*3 if end else (int(p[-1])-1)*3+1
            elif s['frequency']=='M':
                month=int(p[4:])
            else:
                month=12 if end else 1
            day=calendar.monthrange(int(p[:4]),month)[1] if end else 1
            return f'{p[:4]}-{month:02d}-{day:02d}'
        # Deliberately a source-subset adaptation, not a full original reproduction.
        query = pilot_query(obj['id'], periods)
        case = dict(id='BOK-'+obj['id'], original_id=obj['id'], group_id=audit[-1]['group_id'], category='source_subset',
                    scope='purpose_reconstruction_source_subset', exposed_regression=True,
                    input={'query':query,'reference_date':'2026-10-20','prior_turns':[],
                           'actions':[{'kind':'confirm_period','start':iso(start),'end':iso(end,True)},
                                      {'kind':'configure_output','chart_type':'line','layout':'combined'}]},
                    expected={'decision':'resolved','requires_numeric':True,'series_contracts':[ref],
                              'operation':'level','tolerance':'0.000001', 'oracle_sha256':None,'chart_kind':'line',
                              'source_snapshot_sha256':digest_file(local/'provider.json')},
                    evidence=audit[-1]['source'], review={'human_approved':False,'reviewer':None},
                    blockers=[] if available['unit'] else ['원천 단위 미표기: 원본 단위 검수 전 수치 통과 금지'],
                    required_facts=['요청 시점·값·단위·출처를 설명하고 외부 원인·전망은 단정하지 않는다.'],
                    qualitative_applicable=[k for k in RUBRIC if k!='conversation_recovery'])
        values = [{**{k:v for k,v in ref.items() if k!='periods'},
                   'points':[{'period':p,'value':available['points'][p]} for p in periods]}]
        case['expected']['oracle_sha256'] = digest_value(values)
        oracle[case['id']] = values
        cases.append(case)
    supplements = []
    for category, items in SUPPLEMENTS.items():
        for n,(title,query,criterion) in enumerate(items,1):
            fault = category == 'recovery' or (category=='summary_style' and n==4)
            context = next(c for c in cases if c['original_id']==('07-T' if category=='derived' and n==1 else '11-G2-M' if category=='derived' and n==3 else '06-T'))
            setup = {'initial_query':context['input']['query'],
                     'source_snapshot_sha256':digest_file(local/'provider.json'),
                     'display':'graph', 'fresh_account':True, 'fresh_session':True}
            if category=='derived':
                setup['initial_query']={
                    1:'2025년 생산자물가 보도자료 그림을 갱신해줘.',
                    2:'2025년 신규취급액 기준 대출금리와 저축성 수신금리를 비교해줘.',
                    3:'국제수지 보고서에 넣을 경상수지 흐름을 확인해줘.',
                    4:'첨부한 검증용 시계열의 전기비를 계산해줘.'}[n]
            if category=='followup' and n==2:
                setup['initial_query']='2026년 7월부터 8월까지 신규취급액 기준 저축성수신 금리와 중소기업 대출금리를 월별로 비교해줘.'
            if (category=='followup' and n==3) or (category=='summary_style' and n==2):
                setup['initial_query']='2026년 7월부터 8월까지 신규취급액 기준 대기업과 중소기업 대출금리를 월별로 비교해줘.'
            if category=='summary_style' and n==3:
                setup['initial_query']='2026년 7~8월 신규취급액 기준 대기업·중소기업 대출금리를 비교해줘.'
            if category=='report' and n==2:
                setup['initial_query']='2025년 생산자물가지수 총지수의 월별 전년동월 상승률을 계산해 그래프로 보여줘.'
            if category=='reference_edit':
                image=cache/'original-gallery'/sources[6]['rendered_image']
                pdf=ROOT/sources[6]['original_pdf']
                attachment=pdf if n==2 else image
                setup['attachment']={'path':attachment.relative_to(ROOT).as_posix(),
                                     'sha256':digest_file(attachment),'pdf_page':sources[6]['page'] if n==2 else None}
                if n==4:
                    second=cache/'original-gallery'/sources[1]['rendered_image']
                    setup['attachments']=[setup.pop('attachment'),{'path':second.relative_to(ROOT).as_posix(),'sha256':digest_file(second)}]
            if category=='derived' and n==4:
                setup['user_rows']=[{'period':'202401','value':0},{'period':'202402','value':10},
                                    {'period':'202403','value':None},{'period':'202405','value':20},
                                    {'period':'202406','value':30}]
            if category=='followup' and n==4:
                setup['initial_query']='2026년 7~8월 신규취급액 기준 대기업·중소기업 대출금리를 비교해줘.'
                setup['prior_question']='현재 표시된 대기업·중소기업 대출금리의 차이를 비교해줘.'
                setup['intervening_instruction']='표시 기간을 2024년으로 바꿔줘.'
            if category=='summary_style' and n==4:
                setup['fault']={'boundary':'report_summary.model_response','kind':'invalid_fact_ids',
                                'response':{'fact_ids':['unknown-fact-id']}}
                ref=context['expected']['series_contracts'][0]
                setup['summary_sources']=[{**{k:ref[k] for k in ('table_id','item_id','classifications','frequency')},
                    'start_period':ref['periods'][0],'end_period':ref['periods'][-1]}]
            if category=='recovery':
                setup['initial_query']={
                    1:'생산자물가 보도자료 갱신에 필요한 전년동월비를 계산해줘.',
                    2:'국제수지 보도자료 표에 넣을 경상수지를 조회해줘.',
                    3:'저축성 수신금리의 2026년 7~8월 관측값을 확인해줘.',
                    4:'보고서에 반영할 자료를 첨부했으니 형식과 단위를 확인해줘.'}[n]
                setup['fault']={1:{'boundary':'planner.model_request','kind':'timeout'},
                                2:{'boundary':'statistics_request','kind':'timeout'},
                                3:{'boundary':'statistics_request','kind':'empty_success','rows':[]},
                                4:{'boundary':'supplement_upload','kind':'invalid_file',
                                   'content':'period,value,unit,frequency,source\n202401,not-a-number,원,M,synthetic-test\n'}}[n]
            conditions = {
                'derived': {'calculation_matches_independent_oracle':True},
                'followup': {'context_preserved':True,'latest_displayed_data_used':True},
                'reference_edit': {'source_data_preserved':True,'requested_edit_satisfied':True},
                'summary_style': {'facts_supported':True,'request_satisfied':True},
                'report': {'facts_supported':True,'no_unsupported_claim':True},
                'recovery': {'input_preserved':True,'failure_kind_correct':True},
            }[category]
            if category=='report' and n==4:
                conditions['false_premise_corrected']=True
            decision='resolved' if category!='recovery' else 'recoverable_failure'
            if category=='reference_edit' and n==4:
                decision='clarify'
                conditions={'source_data_preserved':True,'clarification_needed':True}
            if category=='recovery':
                conditions={'input_preserved':True,'failure_kind':{1:'model_provider_error',2:'source_api_error',3:'source_data_absent',4:'validation_error'}[n]}
            supplements.append(dict(id=f'SUP-{category}-{n:02}', category=category, title=title,
                group_id=context['group_id'], exposed_regression=True,
                input={'query':query,'setup':setup,
                       'fault_injection':title if fault else None},
                expected={'decision':decision,
                          'requires_numeric':False,'human_contract':criterion,'observed_contract':conditions,
                          'source_snapshot_sha256':digest_file(local/'provider.json')},
                required_facts=[criterion], qualitative_applicable=[k for k in RUBRIC if
                    k not in ({'visual'} if category in ('report','recovery') else {'conversation_recovery'} if category in ('derived','summary_style','reference_edit') else set())],
                execution_kind='injected_fault' if fault else 'model_scenario',
                preparation_status='ready_for_adapter_and_human_review',
                evidence=context['evidence'],
                blockers=[],
                review={'human_approved':False,'reviewer':None}))
            if (category, n) in {('summary_style',1),('summary_style',2),('report',1),('report',2)}:
                if category=='summary_style' and n==2:
                    rate_specs=next(o for o in objects if o['id']=='06-T')['required_series'][5:7]
                    rate_sources=[registry[identity(s)] for s in rate_specs]
                    common=sorted(set(rate_sources[0]['points'])&set(rate_sources[1]['points']))
                    latest=common[-1]
                    points=[{'period':latest,'value':s['points'][latest]} for s in rate_sources]
                    spread=str(number(points[0]['value'])-number(points[1]['value']))
                    narrative={'kind':'narrative','series':[
                        {**{k:s[k] for k in ('table_id','item_id','classifications','frequency','unit')},
                         'points':[{'period':latest,'value':s['points'][latest]}]} for s in rate_sources],
                        'claims':{'large_latest':{'period':latest,'value':points[0]['value'],'unit':rate_sources[0]['unit']},
                                  'small_latest':{'period':latest,'value':points[1]['value'],'unit':rate_sources[1]['unit']},
                                  'spread':{'period':latest,'value':spread,'unit':'%p'}}}
                    target_case=supplements[-1]
                    contracts=[{k:s[k] for k in ('table_id','item_id','classifications','frequency')} for s in rate_sources]
                    target_case['expected'].update(requires_numeric=True,numeric_evidence=True,
                        numeric_claims=['large_latest','small_latest','spread'],numeric_series_contracts=contracts,
                        oracle_sha256=digest_value(narrative),observed_contract={})
                    target_case['expected']['tolerance']='0.000001'
                    target_case['expected']['human_contract'] += ' 같은 최신 월의 대기업·중소기업 대출금리와 대기업-중소기업 차이를 원자료와 일치시킨다.'
                    target_case['required_facts'][0]=target_case['expected']['human_contract']
                    oracle[target_case['id']]=narrative
                    continue
                target='07-T' if category=='report' and n==2 else '06-T'
                source_spec=next(o for o in objects if o['id']==target)['required_series'][0]
                source=registry[identity(source_spec)]
                if target=='07-T':
                    raw={p:v for p,v in source['points'].items() if p.startswith(('2024','2025'))}
                    displayed=calculate(raw,'yoy','M')
                    displayed={p:v for p,v in displayed.items() if p.startswith('2025') and v is not None}
                    points=[{'period':p,'value':raw[p]} for p in sorted(raw)]
                    latest=sorted(displayed)[-1]
                    before=sorted(displayed)[-2]
                    claims={'latest':{'period':latest,'value':displayed[latest],'unit':'%'},
                            'change':{'period':latest,'value':str(number(displayed[latest])-number(displayed[before])),'unit':'%p'}}
                else:
                    periods=sorted(source['points'])[-2:]
                    points=[{'period':p,'value':source['points'][p]} for p in periods]
                    latest=periods[-1]
                    claims={'latest':{'period':latest,'value':source['points'][latest],'unit':source['unit']},
                            'change':{'period':latest,'value':str(number(source['points'][latest])-number(source['points'][periods[-2]])),'unit':'%p'}}
                narrative={'kind':'narrative','series':[{**{k:source[k] for k in ('table_id','item_id','classifications','frequency','unit')},'points':points}], 'claims':claims}
                target_case=supplements[-1]
                target_case['expected'].update(requires_numeric=True,numeric_evidence=True,
                    numeric_claims=['latest','change'],oracle_sha256=digest_value(narrative),observed_contract={})
                target_case['expected']['tolerance']='0.000001'
                target_case['expected']['human_contract'] += ' 인용한 최신 수치와 직전 시점 대비 변화량을 원자료와 일치시킨다.'
                target_case['required_facts'][0]=target_case['expected']['human_contract']
                oracle[target_case['id']]=narrative
            if category=='derived':
                target={1:'07-T',2:'06-T',3:'11-G1-M',4:'06-T'}[n]
                original=next(o for o in objects if o['id']==target)
                source_specs=original['required_series']
                source=registry[identity(source_specs[0])]
                output_unit='%' if n in (1,4) else '%p' if n==2 else '억달러'
                selected_sources=[{k:source[k] for k in ('table_id','item_id','classifications','frequency')}]
                if n==1:
                    calculated=calculate(source['points'],'yoy','M')
                    calculated={p:v for p,v in calculated.items() if p.startswith('2025')}
                    formula='(현재/전년동월-1)*100; 정확한 달력 시차 12개월'
                elif n==2:
                    lending=registry[identity(source_specs[3])]
                    common=sorted(p for p in set(source['points'])&set(lending['points']) if p.startswith('2025'))[-2:]
                    if len(common)!=2:
                        raise ValueError('two common 2025 interest-rate observations required')
                    calculated={p:str(number(lending['points'][p])-number(source['points'][p])) for p in common}
                    selected_sources.append({k:lending[k] for k in ('table_id','item_id','classifications','frequency')})
                    supplements[-1]['input']['query']=f"{common[0][:4]}년 {int(common[0][4:])}월부터 {common[-1][:4]}년 {int(common[-1][4:])}월까지 신규취급액 기준 대출금리에서 저축성 수신금리를 뺀 월별 차이를 %p로 보여줘."
                    formula='대출평균 금리-저축성수신 금리'
                elif n==3:
                    calculated={p:v for p,v in calculate(source['points'],'scale','M','0.01').items() if p.startswith('2025')}
                    formula='백만달러/100=억달러'
                else:
                    calculated=calculate({r['period']:r['value'] for r in setup['user_rows']},'growth','M')
                    selected_sources=[]
                    supplements[-1]['execution_kind']='calculation_component'
                    supplements[-1]['input']['setup']['component_boundary']='synthetic calculator boundary, not standalone supported product analysis'
                    formula='(현재/전월-1)*100; 결측·0분모 null; 빠진 달 연결 금지'
                value={'points':[{'period':p,'value':v} for p,v in sorted(calculated.items())],
                       'frequency':'M','unit':output_unit,'sources':selected_sources,'formula':formula}
                if not value['points']:
                    raise ValueError('empty independent calculation oracle')
                oracle[supplements[-1]['id']]=value
                supplements[-1]['expected'].update(requires_numeric=True,oracle_sha256=digest_value(value),
                                                   observed_contract={},calculation_formula=formula)
    for case in cases+supplements:
        case['expected']['required_facts']=case['required_facts']
        case['expected']['qualitative_applicable']=case['qualitative_applicable']
    # Query-only period probes expand temporal coverage without changing the frozen 12-case baseline.
    period_specs = [
        ('BOK-06-T', 'period-explicit-short', 'short_explicit', '202606', '202607', '금리 동향 표 검토용으로 2026년 6월과 7월 저축성 수신금리를 비교해줘.'),
        ('BOK-07-T', 'period-relative-3m', 'relative_latest', '202606', '202608', '생산자물가 보도자료 갱신용으로 이용 가능한 최신 3개 관측월 추이를 확인해줘.'),
        ('BOK-07-T', 'period-calendar-year', 'annual', '202501', '202512', '2025년 생산자물가 보도자료 그림 갱신용으로 월별 추이를 확인해줘.'),
        ('BOK-08-T', 'period-year-crossing', 'cross_year', '202512', '202601', '수출물가 표 갱신용으로 2025년 12월부터 2026년 1월까지 변화를 확인해줘.'),
        ('BOK-13-T', 'period-quarter-year', 'quarter_year', '2025Q3', '2026Q2', '가계신용 동향 보고서에 반영하려고 합니다. 2025년 3분기부터 2026년 2분기까지 확인해줘.'),
        ('BOK-13-T', 'period-quarter-short', 'short_quarter', '2026Q1', '2026Q2', '가계신용 표 검토용으로 올해 1·2분기 규모를 비교해줘.'),
        ('BOK-07-T', 'month-36m', 'long_monthly', '202309', '202608', '생산자물가 보도자료의 3년 추이를 점검하려고 해. 2023년 9월부터 2026년 8월까지 월별 자료를 정리해줘.'),
        ('BOK-08-T', 'month-24m-export', 'long_monthly', '202410', '202609', '수출물가 표 개정용으로 최근 2년 흐름을 비교해줘. 2024년 10월부터 2026년 9월까지 월별로 부탁해.'),
        ('BOK-13-T', 'quarter-8q', 'long_quarterly', '2024Q3', '2026Q2', '가계신용 보고서에 쓸 8개 분기 추이를 보여줘. 2024년 3분기부터 2026년 2분기까지야.'),
        ('BOK-07-T', 'annual-5y', 'long_annual', '2021', '2025', '생산자물가 연간 표를 갱신하려고 해. 2021년부터 2025년까지 연도별 흐름을 정리해줘.'),
    ]
    by_id={c['id']:c for c in cases}
    expected_counts={'month-36m':36,'month-24m-export':24,'quarter-8q':8,'annual-5y':5}
    for base_id, variant, period_style, start, end, query in period_specs:
        base_case=by_id[base_id]
        spec=copy.deepcopy(base_case)
        spec['id']='BOK-period-'+variant
        spec['group_id']=base_case['group_id']
        spec['input']['query']=query
        spec['input'].pop('actions',None)
        spec['variant_of']=base_id
        spec['input']['period_style']=period_style
        contract=spec['expected']['series_contracts'][0]
        if period_style=='long_annual':
            annual=next((s for s in registry.values() if s['table_id']==contract['table_id'] and
                         s['frequency']=='A' and s['classifications']==contract['classifications']),None)
            if annual is None:
                raise ValueError('annual equivalent unavailable in frozen snapshot: '+spec['id'])
            contract.update({k:annual[k] for k in ('table_id','item_id','classifications','frequency','unit','label')})
        contract['periods']=[start,end]
        spec['expected']['oracle_sha256']=None
        series=registry[identity(contract)]
        points=[{'period':p,'value':series['points'][p]} for p in sorted(series['points']) if start<=p<=end]
        if not points or points[0]['period']!=start or points[-1]['period']!=end or (variant in expected_counts and len(points)!=expected_counts[variant]):
            raise ValueError(f"period probe unavailable in frozen snapshot: {spec['id']} ({len(points)} points, {points[0]['period'] if points else 'none'}–{points[-1]['period'] if points else 'none'})")
        contract['periods']=[point['period'] for point in points]
        oracle_value=[{**{k:v for k,v in contract.items() if k!='periods'},'points':points}]
        spec['expected']['oracle_sha256']=digest_value(oracle_value)
        oracle[spec['id']]=oracle_value
        spec['expected']['requires_numeric']=True
        spec['input']['language_style']='colloquial' if 'changed' in variant or 'relative' in variant else 'natural'
        spec['input']['difficulty']='medium' if 'relative' in variant or 'year-crossing' in variant else 'easy'
        cases.append(spec)
    write_rows(destination/'audit.jsonl', audit)
    write_rows(destination/'pilot.jsonl', cases)
    write_rows(destination/'supplemental.jsonl', supplements)
    write_rows(destination/'gold-review-template.jsonl',[
        {'id':c['id'],'input_sha256':digest_value(c['input']),'expected_sha256':digest_value(c['expected']),
         'human_approved':False,'reviewer':None,'evidence_notes':None,'decision':'pending'} for c in cases+supplements])
    write(local/'oracles.json', oracle)
    write(destination/'profiles.json', {
        'baseline':{'main_model':'gpt-5.4','text_model':'gpt-5.4'},
        'sol':{'main_model':'gpt-6.1-sol','text_model':'gpt-6.1-sol'},
        'mixed':{'main_model':'gpt-6.1-sol','text_model':'gpt-6-luna'},
        'repeats':3,'seed':42,'speed':'standard','actual_model_verification_required':True})
    write(destination/'manifest.json', {'dataset_version':'1.2','ai_assisted':True,'official_performance':False,
        'status':'ready_for_review; full_original_reproduction_pending',
        'counts':{'audited':len(audit),'pilot':len(cases),'supplemental':len(supplements),'human_approved':0},
        'files':{p.relative_to(destination).as_posix():digest_file(p) for p in
                 sorted(list(destination.glob('*.jsonl'))+[destination/'profiles.json']+
                        list((destination/'canonical').rglob('*.jsonl'))+
                        list((destination/'scripts').glob('*.py'))+list((destination/'tests').glob('*.py'))+
                        list(destination.glob('*.md')))},
        'local_provider_sha256':digest_file(local/'provider.json'), 'local_oracles_sha256':digest_file(local/'oracles.json'),
        'metadata_sha256':{p.relative_to(ROOT).as_posix():digest_file(p) for p in sorted((ROOT/'data/processed').glob('bok_*.csv'))},
        'limitations':['Pilot tests selected raw-source subsets, not entire original tables/graphs.',
                       'Supplemental model/fault scenarios require an explicit runtime adapter; human gold remains pending.',
                       'Historical publication gold and all human approvals remain pending.']})
    return len(audit), len(cases), len(supplements)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path,default=ROOT/'.venv/cache/kosis-bok-reproduction')
    args=parser.parse_args()
    print('audit / pilot / supplemental:', *build(args.cache))
