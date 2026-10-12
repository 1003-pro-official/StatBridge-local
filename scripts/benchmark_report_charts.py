"""Offline measured report pipeline workload. All observations are synthetic."""
import json,sys,time,math,tracemalloc
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root/'src/agent'),str(root/'src/backend')]
from output_agent import OutputAgent
from output_schema import ChartSpec
from advanced_chart_spec import ReportOptions
from report_export import render_file

cases=[]
for name,n,count,kind in [('small',30,2,'forecast'),('medium',1000,2,'forecast'),('large',10000,2,'forecast'),('panels',250,4,'panels')]:
    rows=[{'PRD_DE':f'{2000+i//12:04d}{i%12+1:02d}','DT':str(10+math.sin(i/12)+i*.001+j),'ITM_NM':f'합성 계열{j}',
        'UNIT_NM':'%','_SOURCE_SERIES_ID':'DT_BENCH','_FREQUENCY':'M'} for j in range(count) for i in range(n)]
    result={'api_plan':{'table_id':'DT_BENCH','table_name':'합성 성능 검증','org_id':'301','item_id':'ITEM','frequency':'M','start_period':rows[0]['PRD_DE'],'end_period':rows[n-1]['PRD_DE']},'execution':{'rows':rows,'status':'success','sources':[{'table_id':'DT_BENCH','source':'synthetic benchmark','row_count':len(rows)}]}}
    spec=ChartSpec(title='합성 성능 검증',report=ReportOptions(kind=kind));agent=OutputAgent()
    tracemalloc.start();start=time.perf_counter();output=agent._build(result,spec,generate_explanation=False);build=time.perf_counter()-start
    start=time.perf_counter();svg=render_file(output['visualization']['series'],spec,result,'svg');export=time.perf_counter()-start
    peak=tracemalloc.get_traced_memory()[1]/1024**2;tracemalloc.stop()
    record={'case':name,'observations':len(rows),'build_seconds':round(build,3),'svg_seconds':round(export,3),'python_peak_mb':round(peak,2),'svg_bytes':len(svg)}
    cases.append(record);print(json.dumps(record),flush=True)
out=root/'evaluation_runs/advanced_chart_benchmark';out.mkdir(parents=True,exist_ok=True)
(out/'measurements.json').write_text(json.dumps(cases,indent=2),encoding='utf-8')
