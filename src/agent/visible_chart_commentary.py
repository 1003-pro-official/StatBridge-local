"""Report-shaped descriptions calculated exclusively from the displayed series."""
from decimal import Decimal,InvalidOperation
import re
from report_summary import difference_unit,period
from report_summary import display_number
from narrative_labels import narrative_name
from datetime import datetime,timedelta


def report_names(series):
    short=[narrative_name(s['label'],table_name=s.get('tableName','')) for s in series]
    result=[]
    for i,s in enumerate(series):
        if short.count(short[i])==1:
            result.append(short[i]);continue
        # Keep distinguishing classifications, remove only redundant unit tokens.
        parts=[p.strip() for p in re.split(r'[·ㆍ]',s['label'])]
        parts=[p for p in parts if not re.fullmatch(r'(?:비중|구성비)?\s*\([%％]\)|[%％]',p)]
        result.append(' '.join(parts) or s['label'])
    return result


def topic(name):
    clean=re.sub(r'[^가-힣A-Za-z0-9]+$','',name)
    end=ord(clean[-1]) if clean else 0
    return name+('은' if 0xAC00<=end<=0xD7A3 and (end-0xAC00)%28 else '는')


def report_period(value,frequency):
    if frequency=='D' and re.fullmatch(r'\d{8}',str(value)):
        return f'{value[:4]}년 {int(value[4:6])}월 {int(value[6:])}일'
    return period(value,frequency)


def previous_period(value,frequency):
    if frequency in {'Y','A'}:return str(int(value)-1)
    if frequency=='D':return (datetime.strptime(value,'%Y%m%d')-timedelta(days=1)).strftime('%Y%m%d')
    cycle={'M':12,'Q':4,'H':2}.get(frequency)
    if cycle and len(value)==6:
        year,part=int(value[:4]),int(value[4:]);return f'{year if part>1 else year-1}{part-1 if part>1 else cycle:02d}'
    return None


def refers_to_visible_chart(question):
    text=re.sub(r'[\s?.!。？]','',question)
    if re.fullmatch(r'(?:변화율|증감률|변화|추이|흐름)(?:을|를)?(?:설명해줘|설명해주세요|알려줘|요약해줘)',text):return True
    return bool(re.fullmatch(r'(?:현재|해당|이|그|지금|조회한|표시된|화면의)?(?:그래프|표|자료|데이터)(?:의|에서|에있는|를|을)?(?:한국은행|보고서|간행물|처럼|문체로|특징|정리|자세히|간단히|구체적으로|상세히|전체|최근|전년동기|전년대비|전월대비|전기대비|시작대비|변화율|증감률|변화|추이|흐름|추세|요약|설명|해석|분석|을|를|와|및|하고|해서|좀|해줘|해줘봐|알려줘|해줄래|해주세요|보여줘|부탁해)+',text))


def describe_visible_chart(question,series):
    result={'question':question,'status':'answered','paragraphs':[],'claims':[],'facts':[],
            'method':'displayed_data_server_calculated','scope':{'basis':'displayed_observations','series':[]},'limitations':[],'requiredData':[]}
    sentences=[];recent=[];missing=[]
    names=report_names(series)
    yearly=bool(re.search(r'전년동기|전년대비',question))
    previous_comparison=bool(re.search(r'전월대비|전기대비',question))
    for index,s in enumerate(series):
        checked={}
        for p in s.get('points') or []:
            try:value=Decimal(str(p['value']))
            except (InvalidOperation,ValueError,KeyError):continue
            if not value.is_finite():continue
            if p['date'] in checked and Decimal(str(checked[p['date']]['value']))!=value:
                result.update(status='insufficient_data',paragraphs=[f"{s['label']}의 {p['date']}에 서로 다른 값이 중복돼 있어. 같은 시점의 값을 하나로 확정해 줘."])
                return result
            checked[p['date']]=p
        points=sorted(checked.values(),key=lambda p:p['date'])
        if not points:continue
        name=names[index]
        last=points[-1];frequency=s.get('frequency','');lookup={p['date']:p for p in points}
        if frequency=='category':
            missing.append(f'{name}는 항목별 비교 자료라 동일 항목의 두 시점이 없어. 변화율 = (종료 시점 ÷ 시작 시점 − 1) × 100을 계산하려면 어느 두 시점을 비교할지 알려줘.')
            continue
        if '전월대비' in re.sub(r'\s+','',question) and frequency!='M':
            missing.append(f'{name}는 월별 자료가 아니야. 전월대비 = (이번 달 ÷ 지난달 − 1) × 100 계산에는 같은 지표의 월별 두 시점 자료가 필요해. 월별 자료를 비교할지 알려줘.')
            continue
        target=last['date'];baseline=(str(int(target[:4])-1)+target[4:]) if yearly else previous_period(target,frequency) if previous_comparison else points[0]['date']
        before=lookup.get(baseline);unit=s.get('unit','');is_rate=('%' in unit or '％' in unit)
        result['scope']['series'].append({'label':s['label'],'unit':unit,'frequency':frequency,'sourceId':s.get('sourceId'),'start':points[0]['date'],'end':target})
        if not before or len(points)<2:
            missing.append(f"{name}의 {'전년 같은 시점인 '+baseline if yearly else '직전 비교 시점인 '+str(baseline) if previous_comparison else '표시 기간 내 비교 기준 시점'} 값이 없어. {'변화폭 = 현재 − 비교 기준' if is_rate else '증감률 = (현재 ÷ 비교 기준 − 1) × 100'} 계산에 쓸 이 기준 시점 자료를 추가해 줘.")
            continue
        a,b=Decimal(str(before['value'])),Decimal(str(last['value']))
        if not is_rate and a<=0:
            missing.append(f'{name}의 비교 기준 {baseline} 값이 0 이하라 비율 증감률의 분모로 쓸 수 없어. 절대 변화폭으로 비교할지 알려줘.')
            continue
        change=b-a if is_rate else (b/a-1)*100
        change_unit=difference_unit(unit) if is_rate else '%'
        direction='상승' if change>0 else '하락' if change<0 else '보합'
        basis='전년 같은 시점' if yearly else '직전 기간' if previous_comparison else '표시 기간 시작 시점'
        sentence=f"{topic(name)} {report_period(baseline,frequency)} 대비 {report_period(target,frequency)}에 {display_number(abs(change))}{change_unit} {direction}했어." if change else f'{topic(name)} {report_period(baseline,frequency)} 대비 {report_period(target,frequency)}에 변화가 없어.'
        values=[Decimal(str(p['value'])) for p in points]
        steps=[v-u for u,v in zip(values,values[1:])]
        turns=sum(x*y<0 for x,y in zip(steps,steps[1:]))
        if not (yearly or previous_comparison) and turns>=2:sentence+=' 중간에 등락을 반복했지만 전체적으로는 '+('높아졌어.' if change>0 else '낮아졌어.' if change<0 else '시작 수준으로 돌아왔어.')
        elif not (yearly or previous_comparison) and any(steps) and (all(x>=0 for x in steps) or all(x<=0 for x in steps)):sentence+=' 기간 중 같은 방향의 흐름을 이어갔어.'
        sentences.append(sentence)
        previous=points[-2];old=Decimal(str(previous['value']))
        if is_rate or old>0:
            delta=b-old if is_rate else (b/old-1)*100
            line=f"{topic(name)} {report_period(previous['date'],frequency)} 대비 {display_number(abs(delta))}{change_unit} {'상승했어' if delta>0 else '하락했어'}." if delta else f"{topic(name)} {report_period(previous['date'],frequency)} 대비 변동이 없어."
            if len(values)>=3 and (is_rate or values[-3]>0):
                prior=values[-2]-values[-3] if is_rate else (values[-2]/values[-3]-1)*100
                if prior*delta<0:line+=' 이전 시점과 비교해 변화 방향이 바뀌었어.'
                elif prior*delta>0 and abs(prior)!=abs(delta):line+=f" {'상승폭' if delta>0 else '하락폭'}은 직전보다 {'확대' if abs(delta)>abs(prior) else '축소'}됐어."
            recent.append(line)
        result['facts'].append({'id':f'visible-{index}','text':sentence,'formula':'target - baseline' if is_rate else '(target / baseline - 1) * 100','result':str(change),'unit':change_unit,'observations':[dict(before,label=s['label']),dict(last,label=s['label'])], 'recent':{'baseline':dict(previous),'target':dict(last),'change':str(delta),'unit':change_unit} if is_rate or old>0 else None})
    if sentences:
        facts=result['facts'];up=sum(Decimal(f['result'])>0 for f in facts);down=sum(Decimal(f['result'])<0 for f in facts);flat=len(facts)-up-down
        overview='요청한 비교 기준에서' if yearly or previous_comparison else '표시된 전체 기간을 비교하면'
        if len(facts)>1:
            counts=' · '.join(text for n,text in [(up,f'{up}개 지표 상승'),(down,f'{down}개 지표 하락'),(flat,f'{flat}개 지표 보합')] if n)
            result['paragraphs'].append(f'{overview} {counts}으로 나타났어.')
        result['paragraphs']+=sentences
        if recent and not yearly and not previous_comparison:
            result['paragraphs'].append('마지막 관측 시점의 움직임을 따로 보면 다음과 같아.')
            result['paragraphs']+=recent
        if any('%' in s.get('unit','').replace('％','%') for s in series):
            result['paragraphs'].append('비중·금리는 종료 값에서 비교 기준 값을 뺀 %p 변화폭이야. 지수·금액은 (종료 값 ÷ 비교 기준 값 − 1) × 100으로 계산했어.' if any('%' not in s.get('unit','').replace('％','%') for s in series) else '비중·금리의 변화는 종료 값 − 비교 기준 값으로 계산한 %p 변화폭이야. 상대 증감률(%)과 구분해서 읽으면 돼.')
        else:
            result['paragraphs'].append('증감률 = (종료 값 ÷ 비교 기준 값 − 1) × 100으로 계산했어.')
    if missing:
        result['paragraphs']+=missing;result['requiredData']=missing
        result['status']='partially_answered' if sentences else 'insufficient_data'
    if not sentences and not missing:
        result.update(status='insufficient_data',paragraphs=['표시 중인 시계열이 없어. 그래프나 표의 데이터를 먼저 조회해 줘.'])
    return result
