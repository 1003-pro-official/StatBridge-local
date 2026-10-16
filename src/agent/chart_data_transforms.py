"""Calendar-aligned transformations over copies of canonical observations."""
import re


def previous_year_period(period,frequency):
    if frequency in {'A','Y'} and re.fullmatch(r'\d{4}',period):return str(int(period)-1).zfill(4)
    if frequency in {'M','Q','H','S'} and re.fullmatch(r'\d{6}',period):
        limit=4 if frequency=='Q' else 2 if frequency in {'H','S'} else 12
        if 1<=int(period[4:])<=limit:return str(int(period[:4])-1).zfill(4)+period[4:]
    if frequency=='Q' and re.fullmatch(r'\d{4}Q[1-4]',period):return str(int(period[:4])-1).zfill(4)+period[4:]
    if frequency=='D' and re.fullmatch(r'\d{8}',period):return str(int(period[:4])-1).zfill(4)+period[4:]
    raise ValueError('전년 대비 계산에는 확인된 연간·분기·월간 주기와 정본 시점 형식이 필요합니다.')


def year_over_year(points,frequency):
    by_period={p['date']:p['value'] for p in points}
    result=[]
    for point in points:
        previous=previous_year_period(point['date'],frequency)
        if previous in by_period and by_period[previous]!=0:
            result.append({'date':point['date'],'value':(point['value']/by_period[previous]-1)*100})
    return result
