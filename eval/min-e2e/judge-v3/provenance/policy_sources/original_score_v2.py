"""Post-freeze scorer; reference data never enters the product process."""
import json,re,hashlib,math,collections
from pathlib import Path
from html.parser import HTMLParser
RUN=Path(__file__).resolve().parent;GOLD=RUN/'scoring-only'
freeze=json.loads((RUN/'prediction-freeze.json').read_text(encoding='utf8'))
assert freeze['cases']==50
for name,sha in freeze['files'].items():assert hashlib.sha256((RUN/name).read_bytes()).hexdigest()==sha
class Tables(HTMLParser):
 def __init__(self):super().__init__();self.cases={};self.ident=None;self.h2=False;self.row=None;self.cell=None;self.head=''
 def handle_starttag(self,tag,attrs):
  if tag=='h2':self.h2=True;self.head=''
  if tag=='tr':self.row=[]
  if tag in ['td','th']:self.cell=''
 def handle_data(self,data):
  if self.h2:self.head+=data
  if self.cell is not None:self.cell+=data
 def handle_endtag(self,tag):
  if tag=='h2':
   self.h2=False;self.ident=self.head.strip();self.cases[self.ident]=[]
  if tag in ['td','th'] and self.cell is not None:
   self.row.append(self.cell.strip());self.cell=None
  if tag=='tr' and self.ident and self.row is not None:self.cases[self.ident].append(self.row);self.row=None
parser=Tables();parser.feed((GOLD/'reference.html').read_text(encoding='utf-8-sig'))
answers=(GOLD/'answers.md').read_text(encoding='utf-8-sig')
sections={m[1]:m[0] for m in re.finditer(r'^## (ME14-\d+).*?(?=^## |\Z)',answers,re.M|re.S)}
questions=[json.loads(s) for s in (RUN/'execution-input/questions.jsonl').read_text(encoding='utf8').splitlines()]
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def number(x):
 text=str(x).strip().replace(',','').replace('−','-')
 if text in ['','—','–','-','null','None','결측']:return None
 try:return float(text)
 except ValueError:return None
def period(x,frequency):
 text=str(x).replace('period:','').strip()
 q=re.fullmatch(r'(\d{4})(?:년\s*|[- ]?Q)([1-4])(?:\s*분기)?',text,re.I)
 if q:return q[1]+'0'+q[2]
 text=re.sub(r'년\s*|월|[- /]','',text)
 return text
def normalized_unit(x):return str(x).replace('＝','=').replace(' ','')
def signature(p):
 return (str(p.get('org_id','301')),p.get('table_id'),p.get('item_id'),tuple(sorted(p.get('classifications',{}).items())),('Y' if p.get('frequency')=='A' else p.get('frequency')))
def sources(section):
 out=[]
 for line in section.splitlines():
  m=re.search(r'\((DT_\w+)\); 항목 (\w+)',line)
  if not m:continue
  classes=dict(re.findall(r'(objL\d+)=[^;]*?\(([0-9][^)]*)\)',line))
  freq=re.search(r'주기 ([A-Z])',line)[1]
  unit=re.search(r'단위 ([^.;]+)',line)[1]
  out.append({'org_id':'301','table_id':m[1],'item_id':m[2],'classifications':classes,'frequency':freq,'unit':unit})
 return out
def match_vectors(expected,observed,tol=1e-6):
 matches=[];available=set(range(len(observed)))
 for e in expected:
  found=None
  for i in sorted(available):
   v=observed[i]
   if len(v)!=len(e):continue
   if all((a is None and b is None) or (a is not None and b is not None and abs(float(a)-float(b))<=tol+1e-10) for a,b in zip(e,v)):
    found=i;break
  if found is None:return False,matches
  available.remove(found);matches.append(found)
 return True,matches

def required_columns(i,headers):
 if i<=20:return list(range(1,len(headers))),list(range(1,len(headers)))
 if 21<=i<=38:return [1,4],[4]
 if i in [39,40]:return [1,2,3,5],[3]
 if i==41:return [1,2,4,5],[4]
 if i==42:return [1,3,5,6,7],[5,6]
 if 43<=i<=48:return [1,4],[1,4]
 return [1,3,4],[3]

def unit_key(unit):
 unit=normalized_unit(unit)
 if unit in ['지수(기준=100)','기준=100']:return '기준=100'
 return unit

def columns(rows,indices):
 return [[number(r[i]) for r in rows[1:]] for i in indices]

def header_unit(header):
 return re.search(r'\(([^()]*)\)$',header)[1]

def aligned(series,periods,frequency):
 out=[]
 for s in series:
  values={period(p['date'],frequency):p['value'] for p in s['points']}
  out.append([values.get(p) for p in periods])
 return out

def source_history(result,expected_sources,ident):
 internal=result.get('_derived') or {}
 if not internal:return True,0,[]
 p=internal['record']['plan'];bounds=internal['record']['bounds'];compared=0;issues=[]
 for source in p['sources']:
  sig=signature({'table_id':source['table_id'],'item_id':source['item_id'],
                 'classifications':source['classifications'],'frequency':source['frequency']})
  reference=next((s for s in oracle if ident in s['cases'] and signature({
      'table_id':s['table'],'item_id':s['item'],'classifications':s['classification'],
      'frequency':s['frequency']})==sig),None)
  if reference is None:issues.append('원자료 참조 없음');continue
  actual=internal['series'][source['alias']]
  for row in reference['rows']:
   key=period(row['PRD_DE'],source['frequency'])
   if not bounds['fetch_start']<=key<=bounds['fetch_end']:continue
   a=actual['values'].get(key);e=number(row['DT'])
   compared+=1
   if a is None or e is None or abs(a-e)>1e-6+1e-10:issues.append(f'{source["alias"]}:{key} 원자료/이력 불일치')
   if unit_key(actual['unit'])!=unit_key(row['UNIT_NM']):issues.append('원자료 단위 불일치')
 return not issues and compared>0,compared,list(dict.fromkeys(issues))[:5]

oracle=json.loads((GOLD/'observations.json').read_text(encoding='utf-8-sig'))
results=[]
for q in questions:
 ident=q['id'];i=int(ident[-2:]);directory=RUN/'predictions'/ident
 obs=json.loads((directory/'observation.json').read_text(encoding='utf8'))
 section=sections[ident];category=re.search(r'^## ME14-\d+ · (.+)',section)[1]
 weights=dict(zip('ABCDE',[25,20,20,20,15] if i<=20 else [20,15,30,20,15]))
 expected_sources=sources(section);frequency=expected_sources[0]['frequency']
 rows=parser.cases[ident];periods=[period(r[0],frequency) for r in rows[1:]]
 tc,gc=required_columns(i,rows[0]);tv=columns(rows,tc);gv=columns(rows,gc)
 record={'id':ident,'category':category,'query':q['query'],'weights':weights,
         'required_table_columns':[rows[0][c] for c in tc],'required_graph_columns':[rows[0][c] for c in gc],
         'required_sources':expected_sources,'expected_periods':len(periods),
         'ui_seconds':obs['elapsed_seconds'],'levels':{},'checks':{},'evidence':str(directory.relative_to(RUN))}
 if not obs.get('workspace_visible'):
  last=next((r['body'] for r in reversed(obs['responses']) if 'body' in r),{})
  record.update(status='fail',total=None,product_status=last.get('status','ui_timeout'),
                failure_message=last.get('summary','UI 출력 없음'),levels={'A':None,'B':None,'C':None,'D':0,'E':0})
 else:
  snap=json.loads((directory/'product-snapshot.json').read_text(encoding='utf8'));result=snap['result'];output=snap['output']
  plans=result.get('api_plans') or [result.get('api_plan',{})]
  ts=output.get('tableSeries') or output['visualization']['series'];gs=output['visualization']['series']
  a_ok=collections.Counter(signature(p) for p in plans)==collections.Counter(signature(p) for p in expected_sources)
  b_ok=all([period(p['date'],frequency) for p in s['points']]==periods for s in ts+gs)
  c_values,tm=match_vectors(tv,aligned(ts,periods,frequency))
  units_ok=c_values and all(unit_key(header_unit(rows[0][col]))==unit_key(ts[j]['unit']) for col,j in zip(tc,tm))
  history_ok,history_count,history_issues=source_history(result,expected_sources,ident)
  c_ok=c_values and units_ok and history_ok
  dom=[];dom_labels=[]
  for table in obs.get('tables',[]):
   for row in table['rows'][1:]:
    if len(row)==len(periods)+1:
     dom.append([number(c) for c in row[1:]]);dom_labels.append(row[0])
  d_values,dm=match_vectors(tv,dom)
  d_units=d_values and c_values and all(normalized_unit(ts[t]['unit']) in normalized_unit(dom_labels[d]) for t,d in zip(tm,dm))
  d_source=bool(re.search(r'자료|출처',obs.get('table_ui_text','')))
  d_ok=d_values and d_units
  traces=[t for graph in obs.get('graphs',[]) if graph.get('visible') for t in graph['data']
          if t.get('type')=='scatter' and t.get('hoverinfo')!='skip' and t.get('y')]
  e_values,em=match_vectors(gv,[t['y'] for t in traces])
  e_series,gm=match_vectors(gv,aligned(gs,periods,frequency))
  e_units=e_series and all(unit_key(header_unit(rows[0][col]))==unit_key(gs[j]['unit']) for col,j in zip(gc,gm))
  x_ok=bool(traces) and all([period(x,frequency) for x in t.get('x',[])]==periods for t in traces)
  e_source=bool(re.search(r'자료|출처',obs.get('graph_ui_text','')))
  separated=output['chartState']['layout']=='separate' or bool(output['chartState'].get('secondary_axis_series'))
  e_layout=(len({unit_key(s['unit']) for s in gs})<=1 or separated) and (i!=17 or output['chartState']['layout']=='separate')
  e_ok=e_values and e_series and e_units and x_ok and len(traces)==len(gc) and len(gs)==len(gc) and e_layout
  record['levels']={'A':int(a_ok),'B':int(b_ok and history_ok),'C':int(c_ok),
                    'D':1 if d_ok and d_source else .5 if d_ok else 0,
                    'E':1 if e_ok and e_source else .5 if e_ok else 0}
  record['checks']={'source_signatures':a_ok,'all_display_periods':b_ok,'all_table_values':c_values,
                    'table_units':units_ok,'source_and_history_values':history_ok,'source_values_compared':history_count,
                    'history_issues':history_issues,'actual_dom_values':d_values,'actual_dom_units':d_units,'table_source':d_source,
                    'actual_plotly_values':e_values,'graph_units':e_units,'graph_periods':x_ok,'graph_source':e_source,
                    'graph_layout':e_layout,'table_mapping':tm,'graph_mapping':gm}
  record['total']=sum(weights[k]*v for k,v in record['levels'].items())
  record['status']='pass' if record['total']>=80 and all([a_ok,b_ok,c_ok,d_ok,e_ok]) else 'fail'
 if i==41:
  record.update(status='pending',total=None,review_issue='질의에 비율의 배율과 전월 변화의 정의가 미확정이며 전달 README도 검토 대상으로 명시함. 제품의 확인 질문을 오답으로 확정하지 않음.')
 results.append(record)
summary={'mode':'Actual UI; questions only; post-freeze independent scoring','cases':len(results),
         'counts':dict(collections.Counter(r['status'] for r in results)),
         'categories':{g:dict(collections.Counter(r['status'] for r in results if r['category']==g)) for g in ['일반','복수 지표 일반','단순 파생','복잡 파생']},
         'source_history_values_compared':sum(r['checks'].get('source_values_compared',0) for r in results),
         'required_output_values_compared':sum((len(parser.cases[r['id']])-1)*len(r['required_table_columns']) for r in results if r['checks'].get('all_table_values')),
         'human_final_approval':'pending','results':results}
write(RUN/'scores-v2.json',summary)
print(json.dumps({k:v for k,v in summary.items() if k!='results'},ensure_ascii=False,indent=2))
for r in results:
 if r['status']=='fail':print(r['id'],r['total'],[k for k,v in r['checks'].items() if v is False],r.get('failure_message',''))
