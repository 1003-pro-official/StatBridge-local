"""Ordered, immutable report answer selections; no model calls and no raw levels."""
from copy import deepcopy
from uuid import uuid4
import re

MAX_ENTRIES=50


def append_answer(state,turn_id,revision):
    turn=next((t for t in state.get('turns',[]) if t['id']==turn_id),None)
    if not turn or turn.get('verifiedRevision')!=revision:raise ValueError('최신 대화를 다시 불러온 뒤 답변을 추가해 주세요.')
    if turn['answer']['status'] not in {'answered','partially_answered'}:raise ValueError('분석 결과가 있는 답변만 보고서에 추가할 수 있습니다.')
    entries=deepcopy(state.get('markdown_entries',[]))
    if any(e['turnId']==turn_id and e['revision']==revision for e in entries):return entries
    if len(entries)>=MAX_ENTRIES:raise ValueError('한 보고서는 최대 50개 답변을 담을 수 있습니다.')
    answer=turn['answer']
    entries.append({'id':uuid4().hex,'turnId':turn_id,'revision':revision,'question':turn['question'],'paragraphs':deepcopy(answer['paragraphs']),'table':deepcopy(answer.get('table')),'sources':sorted({str(s.get('sourceId')) for s in answer.get('scope',{}).get('series',[]) if s.get('sourceId')})})
    if len(markdown(entries).encode('utf-8'))>1_000_000:raise ValueError('보고서 텍스트 크기가 1MB를 초과합니다.')
    return entries


def cell(value):return str(value).replace('\\','\\\\').replace('|','\\|').replace('\n',' ')


def markdown(entries):
    lines=['# 통계 분석 보고서','']
    for index,entry in enumerate(entries,1):
        lines.extend([f'## {index}. 분석 결과','',*sum(([p,''] for p in entry['paragraphs']),[])])
        table=entry.get('table')
        if table:
            lines+=['| '+' | '.join(cell(v) for v in table['columns'])+' |','| '+' | '.join('---' for _ in table['columns'])+' |']
            lines+=['| '+' | '.join(cell(v) for v in row)+' |' for row in table['rows']]
            lines+=['']
        lines+=[f"자료 기준: 편집 {entry['revision']}회 시점의 검산 결과."]
        if entry.get('sources'):lines+=['자료: 한국은행 · KOSIS / '+', '.join(entry['sources'])]
        lines+=['']
    return '\n'.join(lines)
