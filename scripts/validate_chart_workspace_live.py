"""Real loopback API acceptance run. No mock data, keys or private evaluation input."""
import argparse,hashlib,json,time,os
from pathlib import Path
import requests

parser=argparse.ArgumentParser();parser.add_argument('--username',default='test1');parser.add_argument('--base-url',default='http://127.0.0.1:8005/api');parser.add_argument('--output',default='evaluation_runs/chart_workspace_live');args=parser.parse_args()
session=requests.Session();login=session.post(args.base_url+'/auth/login',json={'username':args.username,'password':os.environ.get('STATBRIDGE_TEST_PASSWORD','1234')},timeout=30);login.raise_for_status()
out=Path(args.output);out.mkdir(parents=True,exist_ok=True);records=[]
def call(path,payload):
 started=time.perf_counter();response=session.post(args.base_url+path,json=payload,timeout=120)
 if response.status_code!=200:
  detail=response.json().get('detail','요청 실패');records.append({'endpoint':path,'status':'FAIL','http_status':response.status_code,'detail':detail,'operation':(payload.get('commands') or [{}])[0].get('operation'),'instruction':payload.get('instruction')});(out/'failure.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8');raise RuntimeError(f'{path}: HTTP {response.status_code}; {detail}')
 data=response.json();(out/'current-response.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');records.append({'endpoint':path,'status':'PASS','seconds':round(time.perf_counter()-started,3),'session_id':data.get('editSessionId'),'revision':data.get('outputSpec',{}).get('editVersion')});(out/'progress.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8');return data
def signature(data):return hashlib.sha256(json.dumps(data['outputSpec']['table']['rows'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
query='차주당 주택담보대출 신규취급액 (DT_181Y011)'
result=call('/query',{'query':query,'execute':True,'period_start':'2020-01-01','period_end':'2025-12-31'})
if not result.get('outputSessionId'):raise RuntimeError('조회 조건 확인이 필요합니다. 실제 조회를 성공으로 간주하지 않습니다.')
result=call('/output',{'session_ids':[result['outputSessionId']],'chart_type':'line','chart_mode':'combined','show_legend':True,'title':'워크스페이스 실제 조회 검증'})
identifier=result['editSessionId'];initial=signature(result);label=result['chart'][0]['label'];dates=[p['date'] for p in result['chart'][0]['points']]
def command(operation,value=None,**fields):return {'operation':operation,'kind':'STYLE_EDIT','value':value,**fields}
def edit(**payload):
 global result
 result=call('/output/edit',{'edit_session_id':identifier,'revision':result['outputSpec']['editVersion'],**payload})
 if signature(result)!=initial:raise AssertionError('스타일 변경이 관측값을 바꿨습니다.')
 return result
designs={}
for key in ['report','stability','outlook','slides','academic','explore']:
 edit(commands=[command('set_presentation',params={'design_template':key})])
 figure=result['outputSpec']['plotlyFigure'];designs[key]={'font':figure['layout']['font'],'line':figure['data'][0]['line'],'grid':figure['layout']['xaxis'].get('gridcolor'),'data_hash':initial}
steps=[command('set_title','연속 편집 제목'),command('set_series_color','#112233',label=label),
 command('highlight_period',start=dates[-8],end=dates[-1],params={'color':'#b9cddb','opacity':.2}),
 command('add_guide',params={'value':1800,'text':'기준 1800'}),command('set_legend','bottom'),
 command('set_presentation',params={'design_template':'slides'}),command('add_note',params={'text':'실제 조회 검증','x':.5,'y':.9}),
 command('set_series_style',label=label,params={'width':5}),command('set_axis_style',label='x',params={'show_grid':False}),command('set_subtitle','이전 설정 유지')]
for step in steps:edit(commands=[step])
last=result['outputSpec']['chartState'];edit(action='undo');assert result['outputSpec']['chartState']['subtitle']!=last['subtitle'];edit(action='redo');assert result['outputSpec']['chartState']==last
docresponse=session.post(args.base_url+'/report/export',json={'edit_session_id':identifier,'revision':result['outputSpec']['editVersion'],'format':'json'},timeout=60);docresponse.raise_for_status();doc=docresponse.json();(out/'saved-chart.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
edit(document=doc);edit(commands=[command('set_title','저장 후 재편집')]);assert result['outputSpec']['chartState']['highlights']==last['highlights']
edit(instruction='제목을 실제 자연어 편집 검증으로 바꿔줘')
assert result['outputSpec']['chartState']['title']=='실제 자연어 편집 검증'
natural_checks=[]
for instruction,field,expected in [
 ('2024년 1분기부터 2025년 4분기까지 회색으로 강조해줘','highlights',None),
 ('가장 최근 강조 영역의 색을 #777777로 바꿔줘','color','#777777'),
 ('가장 최근 강조 영역의 불투명도를 35%로 바꿔줘','opacity',.35),
 (label+' 선 색상을 #334455로 바꿔줘','series_colors','#334455')]:
 edit(instruction=instruction)
 state=result['outputSpec']['chartState']
 if field=='highlights':assert state['highlights']
 elif field=='series_colors':assert state[field][label]==expected
 else:assert state['highlights'][-1][field]==expected
 natural_checks.append({'instruction':instruction,'status':'PASS'})

formats={}
for format in ['png','svg','pdf']:
 r=session.post(args.base_url+'/report/export',json={'edit_session_id':identifier,'revision':result['outputSpec']['editVersion'],'format':format},timeout=60);r.raise_for_status();(out/f'actual-chart.{format}').write_bytes(r.content);formats[format]={'bytes':len(r.content),'content_type':r.headers['content-type']}
saved_workspace=call('/workspace/'+identifier+'/save',{'edit_session_id':identifier,'revision':result['outputSpec']['editVersion'],'format':'json'})
evidence={'status':'PASS','query':query,'session_id':identifier,'series':label,'source':result['tables'],'observations':len(dates),'data_hash':initial,'designs':designs,'consecutive_edits':len(steps),'undo_redo':'PASS','save_reedit':'PASS','natural_language':'PASS','natural_checks':natural_checks,'edit_agent':result['outputSpec'].get('editAgent'),'formats':formats,'records':records,'saved_workspace':saved_workspace,'final_revision':result['outputSpec']['editVersion']}
(out/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:evidence[k] for k in ['status','observations','consecutive_edits','undo_redo','save_reedit','natural_language','final_revision']},ensure_ascii=False))
