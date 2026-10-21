"""Report styles applied before user overrides, including the editable sheet."""
import re

def effective_bands(section,layout,options):
    from table_layout import HeaderBand,_order
    cols=section['columns'];ids={c['id'] for c in cols}
    custom=[b for b in layout.header_bands if set(b.columns)<=ids]
    if custom or options['template'] not in {'BOK-T02','BOK-T03'} or options['orientation']!='indicators' or layout.matrix_columns or layout.bindings:return sorted(custom,key=lambda b:b.level)
    byid={c['id']:c for c in cols};order=_order(list(byid),[x for x in layout.column_order if x in byid]);groups=[]
    for cid in order[1:]:
        match=re.match(r'^(\d{4})(?:-|년|$)',byid[cid]['label'])
        if not match:continue
        year=match[1]+'년'
        if groups and groups[-1]['label']==year:groups[-1]['columns'].append(cid)
        else:groups.append({'label':year,'columns':[cid]})
    return [HeaderBand(**g) for g in groups]

def theme_format(options,*,header,label,row_index,last_row,latest,emphasized):
    t=options['template'];f={}
    if header:
        f={'bold':True,'align':'center','background':'#eaf2f8','bottom':'thin'}
        if t!='default':f.update(background='#ffffff',color='#222222',top='medium',bottom='thin')
        if t=='BOK-T02':f.update(background='#edf3f8',top='medium')
        if t=='BOK-T03':f.update(background='#ddebf7',top='medium',bottom='medium')
        if t=='BOK-T04':f.update(background='#f4f6f7',font_size=10)
        if t=='BOK-T05':f.update(background='#e2f0d9')
        if t=='BOK-T06':f.update(background='#fff2cc',top='double')
    else:
        if t!='default':f.update(color='#222222')
        if t=='BOK-T03' and row_index%2:f['background']='#f4f8fc'
        if t=='BOK-T04':f['font_size']=10
        if t=='BOK-T05' and emphasized:f.update(background='#e2f0d9',bold=True,top='thin')
        if t=='BOK-T06' and label:f.update(align='left',italic=True)
        if last_row and t!='default':f['bottom']='medium'
        if options.get('highlight_latest') and latest:f.update(background='#edf7f3',bold=True)
    return f


def latest_columns(row):
    references={cid:ref for cid,ref in row.get('references',{}).items() if ref.get('period') and cid not in row.get('comparisons',{}) and cid!='legacy_comparison'}
    latest=max((str(ref['period']) for ref in references.values()),default='')
    return {cid for cid,ref in references.items() if str(ref['period'])==latest}
