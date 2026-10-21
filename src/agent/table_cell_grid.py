"""Presentation-only sheet cells shared by direct editing and every exporter."""
from pydantic import BaseModel,ConfigDict,Field

class CellMerge(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str=Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    rows:list[str]=Field(min_length=1,max_length=640)
    columns:list[str]=Field(min_length=1,max_length=120)

def header_row_ids(sections,layout):
    return {f'sheet-header:{si}:{hi}' for si,s in enumerate(sections) for hi in range(2+max((b.level for b in s.get('_effective_bands',layout.header_bands) if set(b.columns)<={c['id'] for c in s['columns']}),default=-1))}

def header_keys(sections,layout):
    ids=header_row_ids(sections,layout)
    return {f'{rid}|{c["id"]}' for si,s in enumerate(sections) for rid in ids if rid.startswith(f'sheet-header:{si}:') for c in s['columns']}

def build_sheet(section,layout,index):
    columns=section['columns'];cids=[c['id'] for c in columns];cells={};base=[]
    rows=[{'id':f'sheet-header:{index}:{i}','height':42,'kind':'header'} for i in range(len(section['headerRows']))]
    rows.extend({'id':r['id'],'height':r.get('height',34),'kind':'group' if r.get('group') else 'body'} for r in section['layoutRows'])
    rids=[r['id'] for r in rows];nh=len(section['headerRows'])
    def add(ri,ci,text,fmt,rs=1,cs=1,merge_id='',editable=False):
        key=rids[ri]+'|'+cids[ci]
        cell={'row':ri,'column':ci,'rowSpan':rs,'colSpan':cs,'key':key,'text':text,'format':dict(fmt),'mergeId':merge_id if rs>1 or cs>1 else '', 'editable':editable}
        for dr in range(rs):
            for dc in range(cs):
                cells[(ri+dr,ci+dc)]={'row':ri+dr,'column':ci+dc,'rowSpan':1,'colSpan':1,'key':rids[ri+dr]+'|'+cids[ci+dc], 'text':text if dr==dc==0 else '', 'format':dict(fmt),'mergeId':'','editable':editable}
        if rs>1 or cs>1:base.append(cell)
        else:cells[(ri,ci)]=cell
    for ri,headers in enumerate(section['headerRows']):
        for h in headers:add(ri,h['column'],h['text'],h['format'],h['rowSpan'],h['colSpan'],f'base:{index}:'+h['id'],True)
    for offset,row in enumerate(section['layoutRows'],nh):
        if row.get('group'):
            add(offset,0,row['label'],{**{k:getattr(layout.base,k) for k in type(layout.base).model_fields},'bold':True,'background':'#edf3f7','align':'left','font_size':11},1,len(columns),row['id'],True)
        else:
            for ci,c in enumerate(columns):
                text=row['display'][c['id']];markers=row['markers'].get(c['id'],[])
                if markers:text+=' '+','.join(str(n)+')' for n in markers)
                add(offset,ci,text,row['formats'][c['id']],editable=c['id']=='label')
                if c['id']!='label':cells[(offset,ci)].update(_value=row['cells'].get(c['id']),_comparison=row.get('comparisons',{}).get(c['id']),_markers=markers)
    if len(cells)!=len(rows)*len(columns):raise ValueError('표의 셀 격자가 완전하지 않습니다.')
    active=[b for b in base if b['mergeId'] not in layout.split_cells]
    for m in layout.cell_merges:
        if not set(m.rows)<=set(rids) or not set(m.columns)<=set(cids):continue
        rr=sorted(rids.index(r) for r in m.rows);cc=sorted(cids.index(c) for c in m.columns)
        if len(set(rr))!=len(rr) or rr!=list(range(rr[0],rr[-1]+1)) or len(set(cc))!=len(cc) or cc!=list(range(cc[0],cc[-1]+1)):
            raise ValueError('병합은 중복 없는 직사각형 범위로 선택해 주세요.')
        if len(rr)*len(cc)<2:raise ValueError('병합할 셀을 두 개 이상 선택해 주세요.')
        selected={(r,c) for r in rr for c in cc}
        for b in active:
            covered={(r,c) for r in range(b['row'],b['row']+b['rowSpan']) for c in range(b['column'],b['column']+b['colSpan'])}
            if selected&covered and not covered<=selected:raise ValueError('기존 병합 셀 전체를 포함하거나 먼저 병합을 해제해 주세요.')
            if selected&covered and b['mergeId'].startswith('merge:'):raise ValueError('사용자 병합 범위가 겹칩니다. 먼저 병합을 해제해 주세요.')
        active=[b for b in active if not (b['row'],b['column']) in selected]
        first=cells[(rr[0],cc[0])]
        text='\n'.join(cells[(r,c)]['text'] for r in rr for c in cc if cells[(r,c)]['text'])
        if len(text)>6000:raise ValueError('병합 셀의 내용이 너무 깁니다. 선택 범위를 줄여 주세요.')
        active.append({**first,'rowSpan':len(rr),'colSpan':len(cc),'text':text,'mergeId':'merge:'+m.id,'editable':all(cells[p]['editable'] for p in selected)})
    hidden=set();anchors={}
    for b in active:
        anchors[(b['row'],b['column'])]=b
        hidden.update((r,c) for r in range(b['row'],b['row']+b['rowSpan']) for c in range(b['column'],b['column']+b['colSpan']) if (r,c)!=(b['row'],b['column']))
    rules=[(set(r.rows),set(r.columns),r.format.model_dump()) for r in layout.range_formats]
    for pos,cell in cells.items():
        fmt=layout.formats.get(cell['key'])
        if fmt:cell['format'].update(fmt.model_dump())
        if cell['key'] in layout.cell_text:
            if not cell['editable']:raise ValueError('관측 수치는 직접 수정할 수 없습니다. 계산식 또는 원자료 연결을 수정해 주세요.')
            cell['text']=layout.cell_text[cell['key']]
        for rr,cc,fmt in rules:
            if rids[pos[0]] in rr and cids[pos[1]] in cc:cell['format'].update(fmt)
        if '_value' in cell:
            from table_layout import display
            cell['text']=display(cell['_value'],cell['format'],section.get('_decimals',1))
            if cell.get('_comparison') and cell['_comparison']['operation']=='difference_growth':cell['text']+=' ('+display(cell['_comparison']['secondary'],cell['format'],section.get('_decimals',1))+')'
            if cell.get('_markers'):cell['text']+=' '+','.join(str(n)+')' for n in cell['_markers'])
    result=[]
    for ri,row in enumerate(rows):
        content=[]
        for ci in range(len(columns)):
            if (ri,ci) in hidden:continue
            cell=dict(anchors.get((ri,ci),cells[(ri,ci)]))
            if cell['mergeId']:
                cell['parts']=[{'row':r,'column':c,'text':cells[(r,c)]['text']} for r in range(ri,ri+cell['rowSpan']) for c in range(ci,ci+cell['colSpan']) if cells[(r,c)]['text']]
                cell['text']='\n'.join(p['text'] for p in cell['parts'])
                cell['format']=dict(cells[(ri,ci)]['format'])
                for edge,pos in [('bottom',(ri+cell['rowSpan']-1,ci)),('right',(ri,ci+cell['colSpan']-1))]:
                    cell['format'][edge]=cells[pos]['format'][edge]
                    cell['format'][edge+'_color']=cells[pos]['format'][edge+'_color']
            content.append({k:v for k,v in cell.items() if not k.startswith('_')})
        result.append({**row,'height':layout.heights.get(row['id'],row['height']),'cells':content})
    section['sheetRows']=result
    return {b['mergeId'] for b in base},set(rids),{c['key'] for c in cells.values()}

def apply_sheets(sections,layout):
    if sum(len(r.rows)*len(r.columns) for r in layout.range_formats)>100000:raise ValueError('범위 서식의 계산 한도를 넘었습니다. 이전 서식을 정리해 주세요.')
    if len({m.id for m in layout.cell_merges})!=len(layout.cell_merges):raise ValueError('셀 병합 ID가 중복되었습니다.')
    if len({r.id for r in layout.range_formats})!=len(layout.range_formats):raise ValueError('범위 서식 ID가 중복되었습니다.')
    base_ids=set();keys=set();all_rows=set()
    for si,s in enumerate(sections):
        b,r,k=build_sheet(s,layout,si);base_ids.update(b);all_rows.update(r);keys.update(k)
    for m in layout.cell_merges:
        if not any(set(m.rows)<={r['id'] for r in s['sheetRows']} and set(m.columns)<={c['id'] for c in s['columns']} for s in sections):raise ValueError('병합 대상이 없거나 서로 다른 표 구역입니다.')
    if not set(layout.split_cells)<=base_ids:raise ValueError('분할할 원본 병합 셀이 없습니다.')
    if not set(layout.cell_text)<=keys:raise ValueError('표시 문구를 바꿀 셀이 없습니다.')
    if sum(len(r.rows)*len(r.columns) for r in layout.range_formats)>100000:raise ValueError('범위 서식의 계산 한도를 넘었습니다. 이전 서식을 정리해 주세요.')
    for rule in layout.range_formats:
        if len(set(rule.rows))!=len(rule.rows) or len(set(rule.columns))!=len(rule.columns):raise ValueError('서식 범위에 중복 셀이 있습니다.')
        if not any(set(rule.rows)<={r['id'] for r in s['sheetRows']} and set(rule.columns)<={c['id'] for c in s['columns']} for s in sections):raise ValueError('서식을 적용할 범위가 현재 표에 없습니다.')
