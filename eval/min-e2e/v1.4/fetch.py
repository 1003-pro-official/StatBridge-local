import re,json,time
from pathlib import Path
from statbridge_mcp.kosis_client import KosisClient
text=Path('eval/min-e2e/v1.4/질의와_정답_50문항.md').read_text(encoding='utf-8')
requests={}
for part in text.split('\n## ')[1:]:
 lines=part.splitlines(); ident=lines[0].split()[0]; query=next(x for x in lines if x.startswith('**질의:**')); years=re.findall(r'(\d{4})년',query); y0,y1=int(years[0]),int(years[1]); freq='M' if '월별' in query else ('Q' if '분기별' in query else 'Y')
 for line in lines:
  if not line.startswith('- **원천'): continue
  table,item=re.search(r'\((DT_\w+)\); 항목 (\w+)',line).groups(); classifications=dict(re.findall(r'(objL\d)=[^;]*\(([0-9][^)]*)\)',line)); key=(table,item,freq,tuple(sorted(classifications.items())))
  x=requests.setdefault(key,{'start':y0,'end':y1,'cases':[]}); x['start']=min(x['start'],y0-1 if int(ident[-2:])>=21 else y0); x['end']=max(x['end'],y1); x['cases'].append(ident)
client=KosisClient(); cache=[]
for (table,item,freq,cla),info in requests.items():
 start=str(info['start'])+('01' if freq in ('M','Q') else ''); end=str(info['end'])+('12' if freq=='M' else '04' if freq=='Q' else '')
 try:
  rows=client.get_statistics('301',table,item,freq,start,end,dict(cla))
  cache.append(dict(table=table,item=item,frequency=freq,classification=dict(cla),start=start,end=end,cases=info['cases'],rows=rows))
  print(table,freq,len(rows),flush=True)
 except Exception as e:
  cache.append(dict(table=table,item=item,frequency=freq,classification=dict(cla),start=start,end=end,cases=info['cases'],error=type(e).__name__))
  print(table,freq,'ERROR',type(e).__name__,flush=True)
Path('.venv/cache/min-e2e-v14/observations.json').write_text(json.dumps(cache,ensure_ascii=False),encoding='utf-8')
print('requests:',len(requests),'ok:',sum('rows' in a for a in cache),'errors:',sum('error' in a for a in cache),flush=True)
