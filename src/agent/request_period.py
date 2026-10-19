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
    original=str(query or '')
    # Index base years are metadata, not a second observation endpoint.
    text=re.sub(r'(?<!\d)(?:19|20)\d{2}\s*(?:년\s*)?[=＝]\s*100(?!\d)',lambda m:' '*len(m[0]),original)
    matches=list(TOKEN.finditer(text))
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
    inherited=[]
    for match in matches:
        tail=text[match.end():]
        connector=r'\s*(?:부터|에서|~|～|–|—|to)\s*'
        short=re.match(connector+r'(\d{1,2})\s*월(?:\s*(\d{1,2})\s*일)?\s*(?:까지|동안|사이)',tail,re.I)
        if short and (match['month'] or match['im']):
            year,month=int(match['year']),int(short[1])
            day=int(short[2]) if short[2] else calendar.monthrange(year,month)[1]
            end=date(year,month,day).isoformat()
        else:
            short=re.match(connector+r'(\d{1,2})\s*일\s*(?:까지|동안|사이)',tail,re.I)
            if short and (match['day'] or match['iday']):
                end=date(int(match['year']),int(match['month'] or match['im']),int(short[1])).isoformat()
            else:
                short=re.match(connector+r'([1-4])\s*분기\s*(?:까지|동안|사이)',tail,re.I)
                if not short or not match['quarter']:continue
                year,month=int(match['year']),int(short[1])*3
                end=date(year,month,calendar.monthrange(year,month)[1]).isoformat()
        start=_boundary(match)
        if start>end:raise ValueError('텍스트의 시작일이 종료일보다 늦습니다.')
        inherited.append({'start':start,'end':end,'source':'text',
                          'expression':original[match.start():match.end()+short.end()]})
    if inherited:
        # Several comparison periods must not collapse into a single interval.
        full_pairs=sum(bool(re.fullmatch(connector,text[a.end():b.start()],re.I))
                       for a,b in zip(matches,matches[1:]))
        if len(inherited)>1 or full_pairs:return None
        return inherited[0]
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
