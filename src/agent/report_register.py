"""Deterministic report register; figures and user quotations are never rewritten."""
import re
from copy import deepcopy

REPLACEMENTS=[('단정하지 않았어','단정하지 않았다'),('계산하지 않아','계산하지 않는다'),('이전 수치를 표시하지 않아','이전 수치를 표시하지 않는다'),('확정할 수 없어','확정할 수 없다'),('판단할 수 없어','판단할 수 없다'),('확인할 수 있어','확인할 수 있다'),('사용할 수 없어','사용할 수 없다'),('나타났어','나타났다'),('확대됐어','확대되었다'),('축소됐어','축소되었다'),('유지됐어','유지되었다'),('바뀌었어','바뀌었다'),('변동이 없어','변동이 없다'),('변화가 없어','변화가 없다'),('가장 커','가장 크다'),('따로 보면 다음과 같아','구분하여 살펴보면 다음과 같다'),('다음과 같아','다음과 같다'),('높아졌어','높아졌다'),('낮아졌어','낮아졌다'),('돌아왔어','돌아왔다'),('이어갔어','이어갔다'),('내려갔어','하락하였다'),('올라갔어','상승하였다'),('없어','없다'),('필요해','필요하다'),('읽으면 돼','해석해야 한다'),('다시 적용해','다시 적용한다'),('추가해 줘','추가하기 바란다'),('알려줘','알려 주기 바란다'),('알려 줘','알려 주기 바란다'),('변경해 줘','변경하기 바란다'),('포함해 다시 조회해 줘','포함하여 다시 조회하기 바란다'),('후 같은 질문을 다시 보내줘','후 같은 질문을 다시 보내기 바란다'),('질문해 줘','질문하기 바란다'),('했어','하였다'),('이야','이다')]

def report_text(text):
    for before,after in REPLACEMENTS:text=text.replace(before,after)
    text=re.sub(r'야(?=[.!?]|$)','이다',text)
    text=re.sub(r'돼(?=[.!?]|$)','된다',text)
    return text


def report_answer(answer):
    result=deepcopy(answer)
    for field in ['paragraphs','requiredData','limitations']:result[field]=[report_text(s) for s in result.get(field,[])]
    for fact in result.get('facts',[]):
        if 'text' in fact:fact['text']=report_text(fact['text'])
    result['register']='report'
    return result
