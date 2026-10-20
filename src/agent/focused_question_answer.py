"""Presentation policy for current-data Q&A; retain audit facts, omit raw levels."""
from copy import deepcopy
from decimal import Decimal


def casual(text):
    for formal, plain in [('입력해 주세요','입력해 줘'),('조회해 주세요','조회해 줘'),('나누어 주세요','나누어 줘'),('확인해 주세요','확인해 줘'),('할 수 없습니다','할 수 없어'),('되지 않았습니다','되지 않았어'),('나타났습니다','나타났어'),('하였습니다','했어'),('바뀌었습니다','바뀌었어'),('되었습니다','됐어'),('필요합니다','필요해'),('없습니다','없어'),('있습니다','있어'),('같습니다','같아'),('다릅니다','달라'),('미달합니다','미달해'),('뜻하지는 않습니다','뜻하지는 않아'),('추정하지 않습니다','추정하지 않아'),('합니다','해'),('입니다','이야'),('됩니다','돼')]:
        text=text.replace(formal,plain)
    return text


def focused_answer(answer):
    result=deepcopy(answer)
    if result.get('sections'):
        sections=[]
        for index,section in enumerate(result['sections']):
            ids={f['id'] for f in result['facts'] if f['id'].startswith(f's{index}:')}
            part={**section,'facts':[f for f in result['facts'] if f['id'] in ids], 'claims':[c for c in result['claims'] if c['fact_ids'] and set(c['fact_ids'])<=ids]}
            sections.append({**section,'paragraphs':focused_answer(part)['paragraphs']})
        result['sections']=sections;result['paragraphs']=[p for s in sections for p in s['paragraphs']]
    elif result.get('status')=='answered':
        facts=result.get('facts',[]);deltas=[f for f in facts if f.get('formula')=='target - baseline']
        question=result.get('question','')
        lines=[]
        if any(f.get('formula')=='observation' for f in facts):
            lines=['개별 관측값은 이 답변에 표시하지 않아. 그래프나 원자료 표에서 확인해 줘.']
        elif any(word in question for word in ['속도','빠르','빠르게']) and deltas:
            magnitude=max(abs(Decimal(f['result'])) for f in deltas)
            leaders=[f for f in deltas if abs(Decimal(f['result']))==magnitude]
            names=[f['observations'][-1]['label'] for f in leaders]
            values=[Decimal(f['result']) for f in deltas]
            lines=[]
            if len(values)>1:
                if len(set(values))==1:lines.append('같은 비교 기간의 변화폭이 같아.')
                elif all(v<0 for v in values):lines.append('모두 하락했으나 하락 속도에는 차이가 나타났어.')
                elif all(v>0 for v in values):lines.append('모두 상승했으나 상승 속도에는 차이가 나타났어.')
                else:lines.append('같은 비교 기간의 변화 방향 또는 변화폭이 달라.')
            if len(leaders)<len(deltas) or len(deltas)==1:lines.append(', '.join(names)+'의 변화 속도가 가장 빨라.')
            for f in deltas:
                value=Decimal(f['result']);label=f['observations'][-1]['label']
                lines.append(f"{label}는 비교 기준보다 {abs(value):f} {f['unit']} {'줄었어' if value<0 else '늘었어' if value>0 else '변하지 않았어'}.")
        else:
            raw_ids={f['id'] for f in deltas}
            for c in result.get('claims',[]):
                if len(c.get('fact_ids',[]))==1 and c['fact_ids'][0] in raw_ids:continue
                lines.append(casual(c['text']))
            if not lines:
                for f in deltas:
                    value=Decimal(f['result']);label=f['observations'][-1]['label']
                    lines.append(f"{label}는 비교 기준보다 {abs(value):f} {f['unit']} {'줄었어' if value<0 else '늘었어' if value>0 else '변하지 않았어'}.")
        result['paragraphs']=lines or ['이 질문에 답할 비교 조건을 더 구체적으로 입력해 줘.']
    else:result['paragraphs']=[casual(p) for p in result.get('paragraphs',[])]
    result['limitations']=[casual(p) for p in result.get('limitations',[])]
    return result
