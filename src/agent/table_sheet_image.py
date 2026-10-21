"""Render arbitrary validated cell spans; project spans at page boundaries."""
import io
import textwrap

def render_sheet_image(doc,kind):
    from report_export import EXPORT_LOCK,_font
    from table_layout_export import footnotes
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from matplotlib.backends.backend_pdf import PdfPages
    from PIL import Image
    preset=doc['options']['print_preset'];capacity=720 if preset=='a4_portrait' else 1000 if preset=='a4_landscape' else 1400
    limit=min(doc['options']['layout']['rows_per_page'],12 if preset=='a4_landscape' else 20 if preset=='a4_portrait' else 60)
    pages=[]
    for s in doc['layoutSections']:
        panels=[];indices=[0];used=s['columns'][0]['width']
        for ci,c in enumerate(s['columns'][1:],1):
            if len(indices)>1 and used+c['width']>capacity:panels.append(indices);indices=[0];used=s['columns'][0]['width']
            indices.append(ci);used+=c['width']
        panels.append(indices)
        head=[i for i,r in enumerate(s['sheetRows']) if r['kind']=='header'];body=[i for i,r in enumerate(s['sheetRows']) if r['kind']!='header']
        for panel in panels:
            for start in range(0,max(1,len(body)),limit):
                selected=([*head] if start==0 or doc['options']['layout']['repeat_headers'] else [])+body[start:start+limit]
                if selected:pages.append((s,panel,selected))
    if not pages or len(pages)>120:raise ValueError('표 출력은 최대 120쪽입니다. 표시 범위를 줄여 주세요.')
    target_w=doc['options'].get('export_width');target_h=doc['options'].get('export_height')
    if bool(target_w)!=bool(target_h):raise ValueError('출력 너비와 높이를 함께 지정해 주세요.')
    out=io.BytesIO();images=[];pixels=0
    with EXPORT_LOCK:
        font=_font();pdf=PdfPages(out) if kind=='pdf' else None
        try:
            for pi,(s,cols,rows) in enumerate(pages):
                widths=[s['columns'][i]['width'] for i in cols];heights=[s['sheetRows'][i]['height'] for i in rows]
                xs=[0];ys=[82]
                for w in widths:xs.append(xs[-1]+w)
                for h in heights:ys.append(ys[-1]+h)
                foot=[line for t in footnotes(doc) for line in textwrap.wrap(t,100)]
                height=ys[-1]+len(foot)*17+42;total=xs[-1]
                if total>2400 or height>3000:raise ValueError('표가 인쇄 범위를 넘습니다. 크기나 페이지당 행 수를 줄여 주세요.')
                figsize=(8.27,11.69) if preset=='a4_portrait' else (11.69,8.27) if preset=='a4_landscape' else (max(850,total+60)/100,height/100)
                fig=plt.figure(figsize=figsize);ax=fig.add_axes([.03,.02,.94,.96]);ax.set_xlim(0,total);ax.set_ylim(height,0);ax.axis('off')
                ax.text(0,12,doc['caption'].replace('−','-'),fontproperties=font,fontsize=15,va='top')
                ax.text(0,45,f"{s['periodCaption']} · {pi+1}/{len(pages)}",fontproperties=font,fontsize=9,va='top')
                fig.canvas.draw();renderer=fig.canvas.get_renderer()
                for sr in s['sheetRows']:
                    for cell in sr['cells']:
                        hitr=[r for r in rows if cell['row']<=r<cell['row']+cell['rowSpan']];hitc=[c for c in cols if cell['column']<=c<cell['column']+cell['colSpan']]
                        if not hitr or not hitc:continue
                        ri,ci=rows.index(hitr[0]),cols.index(hitc[0]);x,y=xs[ci],ys[ri];w=sum(widths[cols.index(c)] for c in hitc);h=sum(heights[rows.index(r)] for r in hitr);f=cell['format']
                        ax.add_patch(Rectangle((x,y),w,h,facecolor=f.get('background','#ffffff'),edgecolor='none',linewidth=0))
                        for edge,coords in {'top':([x,x+w],[y,y]),'bottom':([x,x+w],[y+h,y+h]),'left':([x,x],[y,y+h]),'right':([x+w,x+w],[y,y+h])}.items():
                            style=f.get(edge,'none')
                            if style!='none':
                                from table_borders import border_spec
                                width,kind=border_spec(style)
                                ax.plot(*coords,color=f.get(edge+'_color','#577088'),linewidth=.7 if kind=='double' else width*.7,linestyle=':' if kind=='dotted' else '--' if kind=='dashed' else '-')
                                if kind=='double':
                                    shift=3 if edge in {'top','left'} else -3
                                    second=([v+shift for v in coords[0]],coords[1]) if edge in {'left','right'} else (coords[0],[v+shift for v in coords[1]])
                                    ax.plot(*second,color=f.get(edge+'_color','#577088'),linewidth=.7)
                        text=cell['text']
                        if cell['mergeId'].startswith('merge:') and (len(hitr)!=cell['rowSpan'] or len(hitc)!=cell['colSpan']):
                            visible=[p['text'] for p in cell.get('parts',[]) if p['row'] in hitr and p['column'] in hitc]
                            if visible:text='\n'.join(visible)
                        text=text.replace('−','-');size=f.get('font_size',11)
                        available=abs(ax.transData.transform((w-12,0))[0]-ax.transData.transform((0,0))[0]);vertical=abs(ax.transData.transform((0,h-8))[1]-ax.transData.transform((0,0))[1])
                        while True:
                            prop=font.copy();prop.set_size(size);prop.set_weight('bold' if f.get('bold') else 'normal');prop.set_style('italic' if f.get('italic') else 'normal');lines=[];line=''
                            for ch in text:
                                if ch=='\n' or (f.get('wrap',True) and line and renderer.get_text_width_height_descent(line+ch,prop,False)[0]>available):lines.append(line);line=''
                                if ch!='\n':line+=ch
                            lines.append(line);width=max(renderer.get_text_width_height_descent(l,prop,False)[0] for l in lines)
                            if (width<=available and len(lines)*size*fig.dpi/72*1.2<=vertical) or size<=6:break
                            size-=.5
                        if width>available or len(lines)*size*fig.dpi/72*1.2>vertical:
                            plt.close(fig);raise ValueError('병합 셀 내용이 인쇄 공간을 넘습니다. 행 높이·열 너비를 늘려 주세요.')
                        align=f.get('align','right');valign=f.get('vertical_align','middle');tx=x+(6 if align=='left' else w/2 if align=='center' else w-6);ty=y+4 if valign=='top' else y+h-4 if valign=='bottom' else y+h/2
                        ax.text(tx,ty,'\n'.join(lines),fontproperties=prop,color=f.get('color','#17324d'),ha=align,va='center' if valign=='middle' else valign)
                        if f.get('underline'):
                            scale=abs(ax.transData.inverted().transform((1,1))[1]-ax.transData.inverted().transform((0,0))[1]);lineh=size*fig.dpi/72*1.2*scale;start=ty if valign=='top' else ty-len(lines)*lineh if valign=='bottom' else ty-len(lines)*lineh/2
                            xscale=abs(ax.transData.inverted().transform((1,0))[0]-ax.transData.inverted().transform((0,0))[0])
                            for li,line in enumerate(lines):
                                length=renderer.get_text_width_height_descent(line,prop,False)[0]*xscale;lo=tx if align=='left' else tx-length if align=='right' else tx-length/2;ax.plot([lo,lo+length],[start+(li+1)*lineh]*2,color=f.get('color','#17324d'),linewidth=.6)
                for j,line in enumerate(foot):ax.text(0,ys[-1]+12+j*17,line.replace('−','-'),fontproperties=font,fontsize=8,va='top')
                try:
                    if pdf:
                        if target_w and target_h:
                            buf=io.BytesIO();fig.savefig(buf,format='png',dpi=100);buf.seek(0)
                            with Image.open(buf) as source:
                                from PIL import ImageOps
                                fitted=ImageOps.pad(source.convert('RGB'),(target_w,target_h),color='white')
                            page=plt.figure(figsize=(target_w/100,target_h/100))
                            page.add_axes([0,0,1,1]).imshow(fitted);page.axes[0].axis('off')
                            try:pdf.savefig(page)
                            finally:plt.close(page);fitted.close()
                        else:pdf.savefig(fig)
                    else:
                        buf=io.BytesIO();fig.savefig(buf,format='png',dpi=120);buf.seek(0);im=Image.open(buf).convert('RGB')
                        if target_w and target_h:
                            from PIL import ImageOps
                            original=im;im=ImageOps.pad(im,(target_w,target_h),color='white');original.close()
                        pixels+=im.width*im.height
                        if pixels>40_000_000:im.close();raise ValueError('이미지가 너무 큽니다. PDF로 내보내 주세요.')
                        images.append(im)
                finally:plt.close(fig)
            if pdf:pdf.close();return out.getvalue()
            combined=Image.new('RGB',(max(im.width for im in images),sum(im.height for im in images)),'white');offset=0
            for im in images:combined.paste(im,(0,offset));offset+=im.height
            combined.save(out,format='PNG');combined.close();return out.getvalue()
        finally:
            if pdf:pdf.close()
            for im in images:im.close()
