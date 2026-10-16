"""Position axis titles in each axis domain, independently of observations."""
from html import escape

def position_axis_titles(fig,spec):
    for name,style in spec.axes.items():
        if style.title_position is None and not style.title_standoff and style.title_orientation=='auto' and style.title_placement=='side':continue
        for key in list(fig.layout):
            if name=='x':matches=key.startswith('xaxis')
            elif name=='y2':matches=key=='yaxis2'
            else:matches=key.startswith('yaxis') and (not spec.secondary_axis_series or key!='yaxis2')
            if not matches:continue
            axis=fig.layout[key];text=style.title if style.title is not None else axis.title.text
            if not text:continue
            axis.title.text=''
            ref=key.replace('axis','');pos=style.title_position if style.title_position is not None else .5
            shift=60+style.title_standoff
            common=dict(name='statbridge-axis-title:'+key,text=text if style.title is None else escape(text),showarrow=False,captureevents=True,font=dict(size=spec.presentation.font_size),)
            if name=='x':
                fig.add_annotation(**common,x=pos,y=0,xref=ref+' domain',yref=(axis.anchor if axis.anchor and axis.anchor!='free' else 'y')+' domain',yshift=-shift,xanchor='left' if pos==0 else 'right' if pos==1 else 'center',yanchor='top')
            else:
                right=name=='y2';anchor=axis.anchor if axis.anchor and axis.anchor!='free' else 'x'
                angle=0 if style.title_orientation=='horizontal' else (90 if right else -90)
                if style.title_placement!='side':
                    x=style.title_x if style.title_placement=='custom' else (1 if right else 0)
                    y=style.title_y if style.title_placement=='custom' else (1 if style.title_placement=='top' else 0)
                    fig.add_annotation(**common,x=x,y=y,xref=anchor+' domain',yref=ref+' domain',textangle=angle if style.title_orientation!='auto' else 0,xanchor='right' if right else 'left',yanchor='bottom' if style.title_placement!='bottom' else 'top',yshift=(18+style.title_standoff)*( -1 if style.title_placement=='bottom' else 1))
                    field='t' if style.title_placement!='bottom' else 'b';setattr(fig.layout.margin,field,max(getattr(fig.layout.margin,field) or 0,70+style.title_standoff))
                    if spec.show_legend and spec.legend_position=='top':
                        fig.layout.legend.y=max(fig.layout.legend.y or 0,1.15)
                        fig.layout.margin.t=max(fig.layout.margin.t or 0,160)
                    continue
                fig.add_annotation(**common,x=1 if right else 0,y=pos,xref=anchor+' domain',yref=ref+' domain',xshift=shift if right else -shift,textangle=angle)
                field='r' if right else 'l';setattr(fig.layout.margin,field,max(getattr(fig.layout.margin,field) or 0,shift+25))
