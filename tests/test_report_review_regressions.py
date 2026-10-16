"""Synthetic contract regressions for review #38; no provider or frozen gold."""
import io
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from canonical_request_planner import selections
from output_agent import OutputAgent
from output_schema import ChartSpec
from plotly_renderer import render_plotly
from report_summary import explain
from report_table import build_table, render_table_file, TableOptions
from request_period import explicit_period


def rate(label, values, unit='연리%', frequency='M'):
    return dict(label=label, unit=unit, sourceId='DT_TEST', frequency=frequency,
                color='#005e93', points=[dict(date=f'2024{i:02}', value=v) for i,v in enumerate(values,11)])


def test_bracket_variants_resolve_same_private_consumption():
    tables=json.loads((Path(__file__).resolve().parents[1]/'src/agent/stat_dictionary/stat_language_dictionary.json').read_text(encoding='utf-8'))['tables']
    query='국내총생산에 대한 지출(원계열 실질 분기 및 연간) {}의 민간소비를 2024년 1분기부터 2024년 4분기까지 분기별로 보여줘.'
    a=selections(query.format('(DT_200Y110)'),tables)
    b=selections(query.format('[DT_200Y110]'),tables)
    assert a==b and a and any(h['value_name']=='민간' for h in a[0]['dimension_hits'])


def test_rate_index_and_comparison_units():
    a,b=rate('가계',[4.79,4.72]),rate('기업',[4.76,4.62])
    out=explain([a,b],query='금리 비교')
    assert '0.07 %p 하락' in out['text'] and '0.14 %p 하락' in out['text']
    gap=next(f for f in out['facts'] if f['kind']=='gap')
    assert gap['result']=='0.10' and '0.03 %p' in gap['text'] and '0.07 %p 확대' in gap['text']
    ppi=explain([rate('물가',[119.1,119.52],'2020＝100')])
    assert '0.42 포인트 상승' in ppi['text'] and '0.42 2020' not in ppi['text']
    b['sourceId']='OTHER'
    assert not any(f['kind']=='gap' for f in explain([a,b],query='비교')['facts'])


def test_hidden_and_top_n_summary_follows_visible_original_observations():
    result={'query':'금리 비교','execution':{'rows':[
        {'PRD_DE':p['date'],'DT':p['value'],'ITM_NM':s['label'],'UNIT_NM':s['unit'],'_SOURCE_SERIES_ID':'DT_TEST','_FREQUENCY':'M'}
        for s in [rate('가계',[4.79,4.72]),rate('기업',[4.76,4.62])] for p in s['points']]}}
    agent=OutputAgent()
    initial=agent._series(result['execution']['rows'])
    hidden=initial[1]['label']
    out=agent._build(result,ChartSpec(chart_type='line',hidden_series=[hidden]),generate_explanation=False)
    assert hidden not in out['summary']
    assert len(out['explanation']['scope']['labels'])==1
    top=agent._build(result,ChartSpec(chart_type='line',top_n=1),generate_explanation=False)
    assert len(top['explanation']['scope']['labels'])==1
    from output_schema import ChartEditCommand
    original=agent._build(result,ChartSpec(chart_type='line'),generate_explanation=False)
    changed=agent.apply_edits(result,original,[ChartEditCommand(operation='set_transform',kind='DATA_EDIT',value='cumulative')],generate_explanation=False)
    assert changed['explanation']['scope']['transform']=='cumulative'
    assert '4.72' in changed['summary']


def test_mixed_panels_keep_independent_category_axes():
    m=rate('월',[1,2]);m['points']=[dict(date=f'2024{i:02}',value=i) for i in range(1,13)]
    q=rate('분기',[1,2],frequency='Q');q['points']=[dict(date=f'2024{i:02}',value=i) for i in range(1,5)]
    fig=render_plotly([m,q],ChartSpec(chart_type='line',layout='separate'))
    assert len(fig['layout']['xaxis']['categoryarray'])==12
    assert len(fig['layout']['xaxis2']['categoryarray'])==4
    assert not fig['layout']['xaxis'].get('matches')
    # Equal frequency alone does not imply the same category set (missing months).
    a=rate('A',[1,2]);a['points']=[dict(date='202401',value=1),dict(date='202501',value=2)]
    b=rate('B',[1,2]);b['points']=[dict(date='202401',value=1),dict(date='202402',value=2),dict(date='202501',value=3)]
    separate=render_plotly([a,b],ChartSpec(chart_type='line',layout='separate',highlights=[{'start':'202501','end':'202501','label':'검증'}]))
    assert not separate['layout']['xaxis'].get('matches')
    assert any(s['xref']=='x' and s['x0']==1 for s in separate['layout'].get('shapes',[]))
    assert any(s['xref']=='x2' and s['x0']==2 for s in separate['layout'].get('shapes',[]))


def test_short_and_relative_periods_have_explicit_basis():
    assert explicit_period('2024년 1월부터 12월까지 생산자물가')['end']=='2024-12-31'
    parsed=explicit_period('최근 5년 경제심리지수',latest='2025-12-31')
    assert parsed['start']=='2021-01-01' and parsed['source']=='latest_observation'


def test_twelve_month_table_one_pdf_page_and_shared_export_metadata():
    from pypdf import PdfReader
    a=rate('표명 · 가계',[4.79,4.72]);b=rate('표명 · 기업',[4.76,4.62])
    for s in [a,b]:s['points']=[dict(date=f'2024{i:02}',value=4+i/100) for i in range(1,13)]
    source={'tableId':'DT_TEST','tableName':'금리','organizationId':'301','source':'kosis_api'}
    doc=build_table([a,b],TableOptions(table_number='2'),title='금리 비교',sources=[source,source])
    assert len(doc['sources'])==1 and doc['options']['decimals']==2
    assert doc['sections'][0]['rows'][0][0]=='가계 (연리%)'
    pdf=PdfReader(io.BytesIO(render_table_file(doc,'pdf')))
    assert len(pdf.pages)==1
    assert '표 2.' in pdf.pages[0].extract_text()
    with zipfile.ZipFile(io.BytesIO(render_table_file(doc,'xlsx'))) as z:
        root=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
        ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        assert root.find('s:pageSetup',ns).get('fitToWidth')=='1'
        assert any('표 2.' in (t.text or '') for t in root.findall('.//s:t',ns))
        assert any('월별' in (t.text or '') for t in root.findall('.//s:t',ns))


def test_computed_table_cells_keep_units_and_require_actual_baselines():
    a,b=rate('가계',[4.79,4.72]),rate('기업',[4.76,4.62])
    doc=build_table([a,b],TableOptions(comparison='previous_change'))
    cells=doc['sections'][0]['computedCells']
    assert [c['value'] for c in cells]==[-.07,-.14]
    assert all(c['unit']=='%p' and len(c['observations'])==2 for c in cells)
    missing=build_table([a],TableOptions(comparison='yearly_change'))
    assert missing['sections'][0]['computedCells'][0]['value'] is None
    assert missing['sections'][0]['rows'][0][-1] is None
