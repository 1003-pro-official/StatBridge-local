"""Deterministic component probes. No API, model, server, auth, or product writes."""
from pathlib import Path
import os,sys,json,copy,re,hashlib
ROOT=Path(__file__).resolve().parents[1];P=ROOT.parent/'StatBridge'/'StatBridge-local1'
os.environ['LANGFUSE_TRACING_ENABLED']='false';os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ['MPLCONFIGDIR']=str(ROOT/'audit/validation/matplotlib_cache')
sys.path[:0]=[str(P/'src/agent'),str(P/'src/backend')]
from output_agent import OutputAgent
from output_schema import ChartEditCommand,ChartSpec
rows=[{'PRD_DE':period,'DT':str(value+i),'ITM_NM':f'계열{i}','UNIT_NM':'개','_SOURCE_SERIES_ID':'DT_TEST','_FREQUENCY':'M'} for i in range(2) for period,value in [('202401',10),('202402',20),('202403',30)]]
data={'api_plan':{'table_id':'DT_TEST','table_name':'synthetic renderer probe','org_id':'301','item_id':'ITEM','frequency':'M','start_period':'202401','end_period':'202403'},'execution':{'status':'success','rows':rows,'sources':[{'table_id':'DT_TEST','source':'synthetic component fixture','row_count':6}]}}
agent=OutputAgent();initial=agent.prepare(copy.deepcopy(data),{'chart_type':'line','title':'synthetic initial snapshot'})
observations={'scope':'local first-party pure OutputAgent/renderer, synthetic numbers, not API/UI reproduction of PC-1 run','model_called':False,'api_called':False,'checks':{}}
try:
    hidden=agent.apply_edits(data,initial,[ChartEditCommand(operation='hide_series',kind='DATA_EDIT',value='계열1')],generate_explanation=False)
    before=[s['label'] for s in initial['tableSeries']];after=[s['label'] for s in hidden['tableSeries']]
    observations['checks']['graph_table_independence']={'before_table_series':before,'after_table_series':after,'graph_series':[s['label'] for s in hidden['visualization']['series']],'defect_reproduced':before!=after,'case_ids':['E26','E39','F34']}
except Exception as exc:observations['checks']['graph_table_independence']={'error_type':type(exc).__name__,'defect_reproduced':None}
try:
    point=agent.apply_edits(data,initial,[ChartEditCommand(operation='set_point_style',kind='STYLE_EDIT',label='계열0',start='202403',params={'color':'#E53935'})],generate_explanation=False)
    traces=[t for t in point['plotlyFigure']['data'] if 'markers' in t.get('mode','') and t.get('meta',{}).get('seriesLabel')=='계열0']
    detail=[{'mode':t.get('mode'),'marker':t.get('marker'),'x':t.get('x')} for t in traces]
    visible=any(any(float(n)>0 for n in (t.get('marker',{}).get('size',[]) if isinstance(t.get('marker',{}).get('size'),list) else [t.get('marker',{}).get('size',0)])) for t in traces)
    observations['checks']['point_color_only_visibility']={'traces':detail,'any_nonzero_marker':visible,'defect_reproduced':not visible,'case_ids':['E28','E39','F27'],'limit':'Direct color-only edit command. Natural-language model command generation not repeated.'}
except Exception as exc:observations['checks']['point_color_only_visibility']={'error_type':type(exc).__name__,'defect_reproduced':None}
try:
    changed=agent.apply_edits(data,initial,[ChartEditCommand(operation='set_series_color',kind='STYLE_EDIT',label='계열0',value='#2563EB'),ChartEditCommand(operation='set_series_color',kind='STYLE_EDIT',label='계열1',value='#F97316'),ChartEditCommand(operation='set_segment_style',kind='STYLE_EDIT',label='계열0',start='202401',end='202402',params={'color':'#E53935','dash':'dash'})],generate_explanation=False)
    from report_export import render_file
    spec=ChartSpec.model_validate(changed['chartState']);series=changed['visualization']['series']
    blob=render_file(series,spec,data,'svg')
    if isinstance(blob,tuple):blob=blob[0]
    if isinstance(blob,str):blob=blob.encode()
    output=ROOT/'audit/validation/synthetic_renderer_probe.svg';output.write_bytes(blob)
    text=blob.decode('utf-8');colors=sorted(set(c.upper() for c in re.findall(r'#[0-9a-fA-F]{6}',text)))
    observations['checks']['svg_color_preservation']={'svg_file':str(output.relative_to(ROOT)),'svg_sha256':hashlib.sha256(blob).hexdigest(),'expected_base_colors':['#2563EB','#F97316'],'observed_colors':colors,'defect_reproduced':not all(c in colors for c in ['#2563EB','#F97316']),'case_ids':['F26','F37'],'limit':'Synthetic renderer data, actual export function; not the original 2026-10-29 downloaded SVG.'}
except Exception as exc:observations['checks']['svg_color_preservation']={'error_type':type(exc).__name__,'defect_reproduced':None}
(ROOT/'audit/evidence/local_component_probes.json').write_text(json.dumps(observations,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(observations,ensure_ascii=False))
