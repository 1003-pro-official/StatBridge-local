"""Parse explicit user date ranges independently of model-generated periods."""
import calendar
from datetime import date
import re

TOKEN=re.compile(r"(?<![\da-z_])(?P<year>(?:19|20)\d{2})(?:-(?P<im>\d{1,2})(?!\d)(?:-(?P<iday>\d{1,2})(?!\d))?|\s*년(?:\s*(?P<quarter>[1-4])\s*분기|\s*(?P<month>\d{1,2})\s*월(?:\s*(?P<day>\d{1,2})\s*일)?)?)?",re.I)


def _boundary(match,end=False):
    year=int(match['year']); month=int(match['im'] or match['month'] or (12 if end else 1))
    if match['quarter']: month=(int(match['quarter'])-1)*3+(3 if end else 1)
    day=int(match['iday'] or match['day'] or (calendar.monthrange(year,month)[1] if end else 1))
    return date(year,month,day).isoformat()


def explicit_period(query, latest=None):
    text=str(query or '');matches=list(TOKEN.finditer(text))
    relative = re.search(r'최근\s*(\d{1,2})\s*년', text)
    if relative and not matches and latest:
        end = date.fromisoformat(latest)
        count = int(relative[1])
        if count < 1: return None
        month_index = end.year * 12 + end.month - count * 12
        year, month = divmod(month_index, 12)
        return {'start': date(year, month+1, 1).isoformat(), 'end': end.isoformat(),
                'source': 'latest_observation', 'expression': relative[0],
                'basis': '최신 제공 관측 시점 기준'}
    if len(matches) == 1:
        tail = text[matches[0].end():]
        short = re.match(r'\s*(?:부터|~|～|–)\s*(\d{1,2})\s*월\s*까지', tail)
        if short and (matches[0]['month'] or matches[0]['im']):
            start = _boundary(matches[0])
            year, month = int(matches[0]['year']), int(short[1])
            end = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
            if start > end: raise ValueError('텍스트의 시작일이 종료일보다 늦습니다.')
            return {'start': start, 'end': end, 'source': 'text', 'expression': text[matches[0].start():matches[0].end()+short.end()]}
    if not matches:return None
    if len(matches)>2:return None
    if len(matches)==2:
        between=text[matches[0].end():matches[1].start()]
        connected=re.search(r'부터|에서|~|～|–|—|-|\bto\b',between,re.I)
        through=re.fullmatch(r'\s*(?:과|와)\s*',between) and re.match(r'\s*(?:까지|사이)',text[matches[1].end():])
        if not connected and not through:return None
        start,end=_boundary(matches[0]),_boundary(matches[1],True)
    elif re.search(r'현재|지금|최신|오늘',text) and re.search(r'부터|이후',text):
        if not latest:return None
        start,end=_boundary(matches[0]),latest
    elif re.search(r'부터|이후|까지|이전',text):
        return None  # One open bound must not become an invented closed range.
    else:
        start,end=_boundary(matches[0]),_boundary(matches[0],True)
    if start>end:raise ValueError('텍스트의 시작일이 종료일보다 늦습니다.')
    return {'start':start,'end':end,'source':'text','expression':text[matches[0].start():matches[-1].end()]}
