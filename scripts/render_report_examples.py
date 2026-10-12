"""Reproducible synthetic visual/format QA, never a reconstruction of BOK values."""
from pathlib import Path
import io,json,sys,time
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'src/agent'),str(root/'src/backend'),str(root/'tests')]
from pypdf import PdfReader,PdfWriter
from test_advanced_reports import fixture,options
from output_agent import OutputAgent
from output_schema import ChartSpec
from advanced_chart_spec import TEMPLATES,ReportOptions
from report_export import render_file

out=root/'output/pdf';out.mkdir(parents=True,exist_ok=True)
images=root/'evaluation_runs/advanced_chart_visuals';images.mkdir(parents=True,exist_ok=True)
writer=PdfWriter();records=[]
for key,template in TEMPLATES.items():
    kind=template['kind'];data=fixture(1 if kind=='waterfall' else 2)
    if kind=='dual_axis':
        for row in data['execution']['rows']:
            if row['ITM_NM']=='미국':row['UNIT_NM']='조원'
    opt=options(kind).model_copy(update={'template':key,'footnotes':['주: 모든 값과 구간은 기능 검증용 합성 자료. 한국은행 수치 또는 공식 제작물이 아닙니다.']})
    if kind=='events':
        from advanced_chart_spec import Event
        opt.events=[Event(period='202101',text='합성 이벤트',source='QA fixture')]
    if kind in {'forecast','scenario'}:opt.forecast_start='202101'
    spec=ChartSpec(title=template['name']+' | StatBridge',subtitle='사용자 제작 보고서형 그래프 · 합성 검증 자료',report=opt)
    start=time.perf_counter();rendered=OutputAgent()._build(data,spec,generate_explanation=False)
    series=rendered['visualization']['series']
    pdf=render_file(series,spec,data,'pdf');writer.append(PdfReader(io.BytesIO(pdf)))
    for format in ['png','svg']:(images/f'{key}.{format}').write_bytes(render_file(series,spec,data,format))
    (images/f'{key}.json').write_text(json.dumps(rendered['reportDocument'],ensure_ascii=False,indent=2),encoding='utf-8')
    records.append({'template':key,'kind':kind,'seconds':round(time.perf_counter()-start,3),'rows':len(data['execution']['rows']),'echarts_available':'echartsOption' in rendered})
target=out/'statbridge-report-template-examples.pdf'
with target.open('wb') as f:writer.write(f)
(images/'measurements.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'pdf':str(target),'templates':len(records),'measurements':records},ensure_ascii=False))
