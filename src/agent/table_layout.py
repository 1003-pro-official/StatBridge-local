"""Server-validated report layout. Presentation references immutable observations."""
import hashlib,math,re
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_serializer
from table_borders import BorderStyle
from table_cell_grid import CellMerge,apply_sheets,header_keys,header_row_ids

class Closed(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)

class CellFormat(Closed):
    font_size:int=Field(default=11,ge=8,le=24)
    bold:bool=False
    color:str=Field(default='#17324d',pattern=r'^#[0-9A-Fa-f]{6}$')
    background:str=Field(default='#ffffff',pattern=r'^#[0-9A-Fa-f]{6}$')
    align:Literal['left','center','right']='right'
    decimals:int|None=Field(default=None,ge=0,le=6)
    signed:bool=False
    zero_dash:bool=False
    wrap:bool=True
    top:BorderStyle='none'
    bottom:BorderStyle='none'
    left:BorderStyle='none'
    right:BorderStyle='none'
    top_color:str=Field(default='#577088',pattern=r'^#[0-9A-Fa-f]{6}$')
    bottom_color:str=Field(default='#577088',pattern=r'^#[0-9A-Fa-f]{6}$')
    left_color:str=Field(default='#577088',pattern=r'^#[0-9A-Fa-f]{6}$')
    right_color:str=Field(default='#577088',pattern=r'^#[0-9A-Fa-f]{6}$')
    vertical_align:Literal['top','middle','bottom']='middle'
    italic:bool=False
    underline:bool=False

    @model_serializer
    def sparse(self):
        return {key:getattr(self,key) for key in self.model_fields_set}

class HeaderBand(Closed):
    label:str=Field(min_length=1,max_length=120)
    columns:list[str]=Field(min_length=1,max_length=100)
    level:int=Field(default=0,ge=0,le=3)

class RangeFormat(CellMerge):
    format:CellFormat=Field(default_factory=CellFormat)

class RowGroup(Closed):
    label:str=Field(min_length=1,max_length=120)
    rows:list[str]=Field(min_length=1,max_length=100)
    level:int=Field(default=0,ge=0,le=3)

class Comparison(Closed):
    id:str=Field(pattern=r'^[a-z][a-z0-9_]{0,31}$')
    label:str=Field(min_length=1,max_length=100)
    baseline:str=Field(min_length=1,max_length=40)
    current:str=Field(min_length=1,max_length=40)
    operation:Literal['difference','growth','ratio','difference_growth']='difference'

class Annotation(Closed):
    id:str=Field(pattern=r'^[a-z][a-z0-9_]{0,31}$')
    text:str=Field(min_length=1,max_length=500)
    target:str=Field(default='',max_length=180)

class Binding(Closed):
    id:str=Field(pattern=r'^[a-z][a-z0-9_]{0,31}$')
    label:str=Field(min_length=1,max_length=150)
    series:list[str]=Field(min_length=1,max_length=8)

class Reference(Closed):
    series:str=Field(min_length=1,max_length=200)
    period:str=Field(min_length=1,max_length=40)
    baseline:str|None=Field(default=None,max_length=40)
    operation:Literal['difference','growth']='difference'

class MatrixRow(Closed):
    id:str=Field(pattern=r'^[a-z][a-z0-9_]{0,31}$')
    label:str=Field(min_length=1,max_length=150)
    cells:dict[str,Reference]=Field(max_length=100)

class MatrixColumn(Closed):
    id:str=Field(pattern=r'^[a-z][a-z0-9_]{0,31}$')
    label:str=Field(min_length=1,max_length=120)

class TableLayout(Closed):
    enabled:bool=False
    base:CellFormat=Field(default_factory=CellFormat)
    formats:dict[str,CellFormat]=Field(default_factory=dict,max_length=500)
    widths:dict[str,int]=Field(default_factory=dict,max_length=120)
    heights:dict[str,int]=Field(default_factory=dict,max_length=600)
    aliases:dict[str,str]=Field(default_factory=dict,max_length=600)
    header_bands:list[HeaderBand]=Field(default_factory=list,max_length=40)
    row_groups:list[RowGroup]=Field(default_factory=list,max_length=30)
    comparisons:list[Comparison]=Field(default_factory=list,max_length=12)
    annotations:list[Annotation]=Field(default_factory=list,max_length=40)
    column_order:list[str]=Field(default_factory=list,max_length=120)
    row_order:list[str]=Field(default_factory=list,max_length=600)
    bindings:list[Binding]=Field(default_factory=list,max_length=40)
    matrix_columns:list[MatrixColumn]=Field(default_factory=list,max_length=100)
    matrix_rows:list[MatrixRow]=Field(default_factory=list,max_length=100)
    show_gridlines:bool=True
    repeat_headers:bool=True
    rows_per_page:int=Field(default=24,ge=5,le=60)
    cell_merges:list[CellMerge]=Field(default_factory=list,max_length=100)
    split_cells:list[str]=Field(default_factory=list,max_length=150)
    cell_text:dict[str,str]=Field(default_factory=dict,max_length=500)
    range_formats:list[RangeFormat]=Field(default_factory=list,max_length=100)

def stable(prefix,value):
    return prefix+hashlib.sha256(str(value).encode()).hexdigest()[:16]

def _order(ids,requested):
    if len(requested)!=len(set(requested)) or not set(requested)<=set(ids):raise ValueError('표 순서에 중복되거나 존재하지 않는 ID가 있습니다.')
    return [*requested,*[x for x in ids if x not in requested]]

def _headers(columns,bands):
    ids=[c['id'] for c in columns];depth=1+max((b.level for b in bands),default=-1)
    grid=[[False]*len(ids) for _ in range(depth+1)];rows=[[] for _ in grid]
    groups=[]
    for b in bands:
        if len(set(b.columns))!=len(b.columns) or not set(b.columns)<=set(ids):raise ValueError('머리글은 현재 열을 중복 없이 선택해 주세요.')
        positions=sorted(ids.index(i) for i in b.columns)
        if positions!=list(range(positions[0],positions[-1]+1)):raise ValueError('머리글 병합은 인접한 열만 가능합니다.')
        start,end=positions[0],positions[-1]
        if any(grid[b.level][i] for i in positions):raise ValueError('같은 단계의 머리글 병합이 겹칩니다.')
        if b.level and not any(level==b.level-1 and lo<=start<=end<=hi for level,lo,hi in groups):
            raise ValueError('하위 머리글은 바로 위 상위 그룹 안에 있어야 합니다.')
        for i in positions:grid[b.level][i]=True
        rows[b.level].append({'column':start,'colSpan':len(positions),'rowSpan':1,'text':b.label,'id':stable('header:',str(b.level)+b.label+'|'.join(b.columns))})
        groups.append((b.level,start,end))
    for ci,c in enumerate(columns):
        start=next((r for r in range(depth+1) if not grid[r][ci]),depth)
        if any(grid[r][ci] for r in range(start,depth)):raise ValueError('머리글 계층이 연속되지 않습니다.')
        rows[start].append({'column':ci,'colSpan':1,'rowSpan':depth-start+1,'text':c['label'],'id':c['id']})
    return [sorted(row,key=lambda c:c['column']) for row in rows]

def _format(layout,row,col,theme=None):
    result={key:getattr(layout.base,key) for key in CellFormat.model_fields}
    if col=='label':result['align']='left'
    result.update(theme or {});result.update(layout.base.model_dump())
    for key in [col,row,row+'|'+col]:
        if key in layout.formats:result.update(layout.formats[key].model_dump(exclude_unset=True))
    return result

def display(value,fmt,decimals):
    if value is None:return '—'
    if not isinstance(value,(int,float)):return str(value)
    if not math.isfinite(value):raise ValueError('유한하지 않은 표 값입니다.')
    if value==0 and fmt.get('zero_dash'):return '−'
    from report_table import text_value
    text=text_value(value,fmt.get('decimals') if fmt.get('decimals') is not None else decimals)
    if fmt.get('signed') and value>0:text='+'+text
    return text

def _mixed(series,bindings):
    columns=[{'id':'label','label':'연·분기 / 단위'}];rows={};seen=set()
    if len({b.id for b in bindings})!=len(bindings):raise ValueError('기간 결합 열 ID가 중복되었습니다.')
    known={s['label']:s for s in series}
    for b in bindings:
        if not set(b.series)<=set(known):raise ValueError('기간 결합에는 조회된 계열만 선택해 주세요.')
        if seen.intersection(b.series):raise ValueError('하나의 계열을 여러 기간 결합 열에 중복 배치할 수 없습니다.')
        seen.update(b.series);units={known[s]['unit'] for s in b.series}
        if len(units)!=1:raise ValueError('기간을 함께 배치할 계열의 단위가 다릅니다.')
        cid='binding:'+b.id;columns.append({'id':cid,'label':b.label+' ('+next(iter(units))+')'})
        occupied=set()
        for label in b.series:
            s=known[label];freq={'A':'Y','H':'S'}.get(s.get('frequency'),s.get('frequency'))
            if freq not in {'D','M','Q','S','Y'}:raise ValueError('지원하지 않는 결합 주기입니다.')
            for p in s['points']:
                rid='period:'+freq+':'+str(p['date'])
                if rid in occupied:raise ValueError('기간 결합 열의 같은 주기·시점에 값이 중복됩니다.')
                occupied.add(rid)
                from report_table import period_label
                row=rows.setdefault(rid,{'id':rid,'label':period_label(str(p['date']),freq)+' ['+freq+']','frequency':freq,'cells':{},'references':{}})
                row['cells'][cid]=p['value'];row['references'][cid]={'series':label,'frequency':freq,'period':p['date'],'unit':s['unit']}
    ordered=sorted(rows.values(),key=lambda r:(str(r['label'])[:4],{'Y':0,'S':1,'Q':2,'M':3,'D':4}[r['frequency']],str(r['label'])))
    return {'frequency':'mixed','periods':[],'periodCaption':'제공된 연·분기·월 관측값 직접 배치 · 자동 집계 없음','columns':columns,'layoutRows':ordered}

def apply_layout(doc,series,layout):
    if not layout.enabled:return doc
    if len({s['label'] for s in series})!=len(series):raise ValueError('표 편집에는 서로 구분되는 계열 이름이 필요합니다.')
    if layout.matrix_columns or layout.matrix_rows:
        if not layout.matrix_columns or not layout.matrix_rows or layout.bindings or layout.comparisons:
            raise ValueError('참조 배치는 행·열을 함께 지정하고 다른 결합·비교 설정을 해제해 주세요.')
        columns=[{'id':'label','label':'항목 · 원자료 단위'},*[{'id':'matrix:'+c.id,'label':c.label} for c in layout.matrix_columns]]
        if len({c.id for c in layout.matrix_columns})!=len(layout.matrix_columns) or len({r.id for r in layout.matrix_rows})!=len(layout.matrix_rows):raise ValueError('참조 배치 ID가 중복되었습니다.')
        known={s['label']:s for s in series};allowed={c.id for c in layout.matrix_columns};rows=[]
        for r in layout.matrix_rows:
            if not set(r.cells)<=allowed:raise ValueError('참조 배치의 열이 없습니다.')
            cells={};refs={};comparisons={}
            for cid,ref in r.cells.items():
                item=known.get(ref.series)
                if not item:raise ValueError('참조 배치에는 조회된 계열만 사용할 수 있습니다.')
                matches=[p for p in item['points'] if str(p['date'])==ref.period]
                if len(matches)!=1:raise ValueError('참조 시점이 없거나 중복됩니다.')
                value=matches[0]['value'];unit=item['unit']
                if ref.baseline:
                    bases=[p for p in item['points'] if str(p['date'])==ref.baseline]
                    if len(bases)!=1 or ref.baseline==ref.period:raise ValueError('참조 비교에는 서로 다른 실제 A/B 시점이 필요합니다.')
                    va=bases[0]['value'];vb=value;value=None
                    if va is not None and vb is not None:
                        aa,bb=Decimal(str(va)),Decimal(str(vb))
                        value=float(bb-aa) if ref.operation=='difference' else float((bb/aa-1)*100) if aa>0 else None
                    from report_summary import difference_unit
                    unit='%' if ref.operation=='growth' else difference_unit(unit)
                    comparisons['matrix:'+cid]={'value':value,'secondary':None,'unit':unit,'secondaryUnit':'%','baseline':ref.baseline,'current':ref.period,'operation':ref.operation,'observations':[va,vb],'reason':None if value is not None else '비교 원자료가 없거나 증가율 기준값이 0 이하입니다.'}
                cells['matrix:'+cid]=value;refs['matrix:'+cid]={'series':ref.series,'period':ref.period,'unit':unit,'frequency':item.get('frequency')}
            rows.append({'id':'matrix-row:'+r.id,'label':r.label,'cells':cells,'references':refs,'comparisons':comparisons})
        sections=[{'frequency':'reference','periods':[],'periodCaption':'조회된 관측값 직접 참조 · 각 셀의 단위·주기는 계산 근거 참조','columns':columns,'layoutRows':rows}]
    elif layout.bindings:
        if doc['options']['orientation']!='periods' or layout.comparisons:raise ValueError('연·분기 결합은 시점을 행으로 배치하고 비교 열을 해제해 주세요.')
        sections=[_mixed(series,layout.bindings)]
    else:
        sections=[]
        by_label={s['label']:s for s in series}
        for section in doc['sections']:
            if len(section['headers'])>120 or len(section['rows'])>600:raise ValueError('자유 표 편집은 120열·600행 이내로 줄여 주세요.')
            freq=section['frequency'];items=[s for s in series if (s.get('frequency') or '원자료 주기')==freq]
            if doc['options']['labels']:items=sorted([s for s in items if s['label'] in doc['options']['labels']],key=lambda s:doc['options']['labels'].index(s['label']))
            columns=[{'id':'label','label':section['headers'][0]}]
            if doc['options']['orientation']=='indicators':
                columns += [{'id':'period:'+str(p),'label':h,'period':str(p)} for p,h in zip(section['periods'],section['headers'][1:])]
                if len(section['headers'])>len(columns):columns.append({'id':'legacy_comparison','label':section['headers'][-1]})
                rows=[{'id':stable('series:',s['label']),'label':raw[0],
                       'cells':{c['id']:v for c,v in zip(columns[1:],raw[1:])},'sourceLabel':s['label'],
                       'references':{c['id']:{'series':s['label'],'period':c.get('period'),'frequency':freq,'unit':s['unit']} for c in columns[1:]}} for s,raw in zip(items,section['rows'])]
                for comp in layout.comparisons:
                    if freq=='category':raise ValueError('항목 비교 값에는 시점 비교 열을 추가할 수 없습니다.')
                    if comp.baseline not in section['periods'] or comp.current not in section['periods']:raise ValueError('비교 기간은 표에 표시된 실제 시점에서 선택해 주세요.')
                    if comp.baseline==comp.current:raise ValueError('비교할 A와 B는 서로 다른 시점을 선택해 주세요.')
                    cid='comparison:'+comp.id;columns.append({'id':cid,'label':comp.label,'computed':True})
                    for row,s in zip(rows,items):
                        va=row['cells'].get('period:'+comp.baseline);vb=row['cells'].get('period:'+comp.current)
                        result=growth=None;reason=None
                        if va is not None and vb is not None:
                            aa,bb=Decimal(str(va)),Decimal(str(vb))
                            if comp.operation=='ratio':result=float(bb/aa) if aa else None
                            elif comp.operation=='growth':result=float((bb/aa-1)*100) if aa>0 else None
                            else:result=float(bb-aa)
                            if comp.operation=='difference_growth' and aa>0:growth=float((bb/aa-1)*100)
                            if result is None or (comp.operation=='difference_growth' and growth is None):reason='분모가 0이거나 증가율 기준값이 0 이하입니다.'
                        else:reason='A 또는 B의 원자료가 없습니다.'
                        from report_summary import difference_unit
                        unit='%' if comp.operation=='growth' else '배' if comp.operation=='ratio' else difference_unit(s['unit'])
                        row['cells'][cid]=result
                        row.setdefault('comparisons',{})[cid]={'value':result,'secondary':growth,'unit':unit,'secondaryUnit':'%',
                          'baseline':comp.baseline,'current':comp.current,'operation':comp.operation,'observations':[va,vb],'reason':reason}
            else:
                columns += [{'id':stable('series:',s['label']),'label':h} for s,h in zip(items,section['headers'][1:])]
                rows=[{'id':'period:'+freq+':'+str(p),'label':raw[0],'cells':{c['id']:v for c,v in zip(columns[1:],raw[1:])},
                       'references':{c['id']:{'series':s['label'],'period':p,'frequency':freq,'unit':s['unit']} for c,s in zip(columns[1:],items)}} for p,raw in zip(section['periods'],section['rows'])]
                if layout.comparisons:raise ValueError('비교 열은 지표를 행으로 배치한 표에서 추가해 주세요.')
            sections.append({**section,'columns':columns,'layoutRows':rows})
    from table_sheet_theme import theme_format,effective_bands,latest_columns
    for section in sections:section['_effective_bands']=effective_bands(section,layout,doc['options'])
    valid=set();cell_keys=set();row_ids=set();col_ids=set()
    for s in sections:
        if len(s['columns'])>120 or len(s['layoutRows'])>600:raise ValueError('자유 표 편집은 120열·600행 이내로 줄여 주세요.')
        ids=[r['id'] for r in s['layoutRows']];cids=[c['id'] for c in s['columns']]
        valid.update(ids+cids);cell_keys.update(r+'|'+c for r in ids for c in cids)
        row_ids.update(ids);col_ids.update(cids)
    valid.update(stable('header:',str(b.level)+b.label+'|'.join(b.columns)) for section in sections for b in section['_effective_bands'])
    cell_keys.update(header_keys(sections,layout))
    row_ids.update(header_row_ids(sections,layout))
    for si,s in enumerate(sections):
        present={r['id'] for r in s['layoutRows']}
        groups=[g for g in layout.row_groups if set(g.rows)<=present]
        row_ids.update(stable('group:',str(si)+str(gi)+g.label) for gi,g in enumerate(groups))
    valid.update(row_ids)
    for mapping in [layout.formats,layout.widths,layout.heights,layout.aliases]:
        if not set(mapping)<=valid|cell_keys:raise ValueError('서식 대상이 현재 표에 없습니다. 기간·항목 변경 후 대상 선택을 다시 확인해 주세요.')
    if any(not 45<=v<=500 for v in layout.widths.values()):raise ValueError('열 너비는 45~500px입니다.')
    if any(not 22<=v<=140 for v in layout.heights.values()):raise ValueError('행 높이는 22~140px입니다.')
    if not set(layout.widths)<=col_ids or not set(layout.heights)<=row_ids:raise ValueError('너비는 열, 높이는 행에만 적용할 수 있습니다.')
    if any(len(v)>150 or not v.strip() for v in layout.aliases.values()):raise ValueError('표시 이름은 1~150자입니다.')
    if len({c.id for c in layout.comparisons})!=len(layout.comparisons):raise ValueError('계산 열 ID가 중복되었습니다.')
    if len({n.id for n in layout.annotations})!=len(layout.annotations):raise ValueError('각주 ID가 중복되었습니다.')
    if any(n.target and n.target not in valid|cell_keys for n in layout.annotations):raise ValueError('각주 대상이 현재 표에 없습니다.')
    if not set(layout.column_order)<=col_ids or not set(layout.row_order)<=row_ids:raise ValueError('표 순서의 대상이 없습니다.')
    if len(set(layout.column_order))!=len(layout.column_order) or len(set(layout.row_order))!=len(layout.row_order):raise ValueError('표 순서가 중복됩니다.')
    if any(not set(b.columns)<=valid for b in layout.header_bands):raise ValueError('머리글의 대상 열이 없습니다.')
    if any(not set(g.rows)<=valid for g in layout.row_groups):raise ValueError('행 그룹의 대상이 없습니다.')
    if any(not any(set(b.columns)<={c['id'] for c in s['columns']} for s in sections) for b in layout.header_bands):raise ValueError('서로 다른 표 구역의 머리글을 병합할 수 없습니다.')
    if any(not any(set(g.rows)<={r['id'] for r in s['layoutRows']} for s in sections) for g in layout.row_groups):raise ValueError('서로 다른 표 구역의 행을 묶을 수 없습니다.')
    for si,s in enumerate(sections):
        cols={c['id']:c for c in s['columns']};rows={r['id']:r for r in s['layoutRows']}
        order=_order(list(cols),[x for x in layout.column_order if x in cols]);rorder=_order(list(rows),[x for x in layout.row_order if x in rows])
        if order[0]!='label':raise ValueError('항목 이름 열은 표의 첫 열에 유지해야 합니다.')
        s['columns']=[{**cols[c],'label':layout.aliases.get(c,cols[c]['label']),'width':layout.widths.get(c,240 if c=='label' else 110)} for c in order]
        groups=[g for g in layout.row_groups if set(g.rows)<=set(rows)]
        for group in groups:
            positions=sorted(rorder.index(r) for r in group.rows)
            if len(positions)!=len(set(positions)) or positions!=list(range(positions[0],positions[-1]+1)):raise ValueError('행 그룹은 인접한 행을 중복 없이 선택해 주세요.')
            if any(other is not group and other.level==group.level and set(other.rows)&set(group.rows) for other in groups):raise ValueError('같은 단계의 행 그룹이 겹칩니다.')
            if group.level and not any(parent.level==group.level-1 and set(group.rows)<=set(parent.rows) for parent in groups):raise ValueError('하위 행 그룹은 상위 그룹 안에 있어야 합니다.')
        final=[]
        for rid in rorder:
            for gi,g in sorted(enumerate(groups),key=lambda p:p[1].level):
                if rid==next(r for r in rorder if r in g.rows):
                    final.append({'id':stable('group:',str(si)+str(gi)+g.label),'label':g.label,'group':True,'level':g.level,'cells':{}})
            row={**rows[rid],'label':layout.aliases.get(rid,rows[rid]['label']),'height':layout.heights.get(rid,34)}
            row['level']=sum(1 for g in groups if rid in g.rows)
            row['display']={};row['formats']={};row['markers']={}
            for c in order:
                theme=theme_format(doc['options'],header=False,label=c=='label',row_index=rorder.index(rid),last_row=rid==rorder[-1],latest=(c in latest_columns(row) if doc['options']['orientation']=='indicators' else rid==rorder[-1] and c!='label'),emphasized=row.get('sourceLabel',row['label']) in doc['options'].get('emphasized_labels',[]))
                fmt=_format(layout,rid,c,theme);row['formats'][c]=fmt
                value=row['label'] if c=='label' else row['cells'].get(c)
                text=display(value,fmt,doc['options']['decimals'])
                info=row.get('comparisons',{}).get(c)
                if info and info['operation']=='difference_growth':text+=' ('+display(info['secondary'],fmt,doc['options']['decimals'])+')'
                row['display'][c]=text
                row['markers'][c]=[i+1 for i,n in enumerate(layout.annotations) if n.target in {rid if c=='label' else '',c,rid+'|'+c} and n.target]
            final.append(row)
        bands=s['_effective_bands']
        s['headerRows']=_headers(s['columns'],bands);s['layoutRows']=final
        for header_row in s['headerRows']:
            for cell in header_row:
                fmt=theme_format(doc['options'],header=True,label=cell['column']==0,row_index=0,last_row=False,latest=False,emphasized=False)
                fmt.update(layout.base.model_dump())
                if cell['id'] in layout.formats:fmt.update(layout.formats[cell['id']].model_dump())
                cell['format']={**{key:getattr(layout.base,key) for key in CellFormat.model_fields},**fmt}
                cell['text']=layout.aliases.get(cell['id'],cell['text'])
                cell['markers']=[i+1 for i,n in enumerate(layout.annotations) if n.target==cell['id']]
    if any(len(t)>500 for t in layout.cell_text.values()):raise ValueError('셀 표시 문구는 500자 이내입니다.')
    for section in sections:section['_decimals']=doc['options']['decimals']
    apply_sheets(sections,layout)
    for section in sections:section.pop('_effective_bands',None);section.pop('_decimals',None)
    doc['layoutSections']=sections
    doc['annotations']=[n.model_dump()|{'number':i+1} for i,n in enumerate(layout.annotations)]
    return doc
