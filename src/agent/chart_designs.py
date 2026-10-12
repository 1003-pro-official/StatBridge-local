"""Presentation presets only: never generate or change statistical values."""
DESIGNS={
 'report':{'name':'한국은행 경제보고서형','palette':['#2255a4','#d87832','#337f65'],'font':13,'title':20,'width':2,'grid':'#e3e8ee','markers':False,'dash':['solid'],'legend':'top','margin':90},
 'stability':{'name':'금융안정 분석형','palette':['#163e66','#bb4141','#398b83'],'font':13,'title':19,'width':2.5,'grid':'#d4dfe7','markers':True,'dash':['solid','dash'],'legend':'bottom','margin':105},
 'outlook':{'name':'경제전망 분석형','palette':['#246ba8','#dc8634','#638a76'],'font':14,'title':21,'width':2.5,'grid':'#e9edf1','markers':False,'dash':['solid','dash','dot'],'legend':'top','margin':105},
 'slides':{'name':'발표자료형','palette':['#005b96','#e56528','#168768'],'font':18,'title':28,'width':4,'grid':'#ffffff','markers':True,'dash':['solid'],'legend':'bottom','margin':100},
 'academic':{'name':'논문·학술형','palette':['#202020','#777777','#aaaaaa'],'font':12,'title':17,'width':1.5,'grid':'#ededed','markers':True,'dash':['solid','dash','dot'],'legend':'top','margin':85},
 'explore':{'name':'데이터 탐색형','palette':['#176ab2','#e58431','#299879'],'font':14,'title':20,'width':3,'grid':'#ccdbe7','markers':True,'dash':['solid'],'legend':'top','margin':90},
}

def palette(spec):
    return DESIGNS.get(spec.presentation.design_template,{}).get('palette')

def apply_design(spec, key):
    from output_schema import PresentationStyle
    if key not in DESIGNS:raise ValueError('등록된 그래프 디자인을 선택해 주세요.')
    d=DESIGNS[key]
    p={**spec.presentation.model_dump(),'design_template':key,'font_family':'Malgun Gothic, Noto Sans CJK KR, sans-serif',
       'font_size':d['font'],'title_size':d['title'],'legend_size':d['font'],'background':'#ffffff',
       'grid_color':d['grid'],'title_x':.5,'margin_top':d['margin'],'margin_bottom':d['margin'],
       'number_decimals':2 if key=='academic' else 1}
    # Explicit per-series overrides, annotations, data and title survive.
    updates={'presentation':PresentationStyle.model_validate(p),'line_width':d['width'],'legend_position':d['legend']}
    if spec.report is None and spec.chart_type in {'auto','line'}:
        from advanced_chart_spec import ReportOptions
        updates['report']=ReportOptions(kind='forecast' if spec.layout=='combined' else 'panels')
    return spec.model_copy(update=updates)

def materialize(spec, labels):
    """Resolve defaults without overwriting stored user overrides."""
    from output_schema import SeriesStyle
    d=DESIGNS.get(spec.presentation.design_template)
    if not d:return spec
    styles={}
    for i,label in enumerate(labels):
        styles[label]=SeriesStyle.model_validate({'markers':d['markers'],'marker_symbol':['circle','square','diamond'][i%3],
            'dash':d['dash'][i%len(d['dash'])],**(spec.series_styles[label].model_dump(exclude_none=True) if label in spec.series_styles else {})})
    return spec.model_copy(update={'series_styles':styles})
