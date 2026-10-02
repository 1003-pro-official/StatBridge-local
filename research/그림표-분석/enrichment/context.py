"""Local PDF coordinates and body references, without nearest-sentence matching."""
from __future__ import annotations
import json
import re
import sys
from collections import Counter,defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from .common import OUT,ROOT,ARCHIVE,CACHE,BACKUP,UNKNOWN,BLACKLIST,normalize,compact,number,ref_pattern,bad_sentence,load_json,save_json,digest

sys.path.insert(0,str(OUT/'.runtime'))
try:
    import pymupdf as fitz
    if not hasattr(fitz,'open'):fitz=None
except ImportError: fitz=None

NUM = r'(?:[IVX]+\s*[-.]\s*\d+(?:\s*[-.]\s*\d+)*|(?:개요|참고)\s*\d+(?:[-.]\d+)*|\d+(?:[-.]\d+)*)'
MARKER = re.compile(r'(그림|표)\s*[\[<(]?\s*('+NUM+r')(?!\d)',re.I)

def series_from_markdown():
    found={}
    for path in BACKUP.glob('*/*.md'):
        current=None
        for line in path.read_text(encoding='utf-8').splitlines():
            m=re.match(r'- 결과물ID: `([^`]+)`',line)
            if m: current=m.group(1)
            if current and line.startswith('- **데이터 요약:** '):
                value=line.split('**데이터 요약:** ',1)[1]
                found[current]=re.split(r'; (?:시계열|단면|데이터 구조|불명)',value,maxsplit=1)[0].strip()
    return found

def refs(text):
    result=[]
    for m in MARKER.finditer(normalize(text)):
        # Reject prose numeric fragments, e.g. "표 1" in "표 1개".
        result.append((m.group(1),number(m.group(2))))
    return result

def split_sentences(block):
    lines=[]
    for line in block.splitlines():
        line=normalize(line)
        if not line or BLACKLIST.search(line) or re.fullmatch(r'\d{1,3}',line): continue
        if re.match(r'^(?:자료|주|단위)\s*:',line): continue
        if re.match(r'^(?:그림|표)\s*'+NUM+r'\s*[.>\]]',line,re.I):continue
        lines.append(line)
    text=' '.join(lines)
    if not text:return []
    # Korean declarative prose, not axis labels or a TOC caption.
    parts=re.split(r'(?<=[.!?])\s+(?=[^\d])',text)
    return [s.strip() for s in parts if refs(s) and not bad_sentence(s) and re.search(r'(?:다|됨|임)(?:\s*\([^()]{0,180}\))?[.)]*\s*$',s)]

def pdf_index(path):
    sha=digest(path.read_bytes());target=CACHE/'pdf_index'/f'{sha}.json'
    cached=load_json(target)
    if cached and cached.get('version')==4: return cached
    if fitz is None: raise RuntimeError('PyMuPDF가 필요합니다: 번들 Python -m pip install --target research/그림표-분석/.runtime PyMuPDF')
    doc=fitz.open(path);pages=[];captions=[];sentences=[]
    for i,page in enumerate(doc):
        lines=[]
        for block in page.get_text('dict')['blocks']:
            if block.get('type')!=0:continue
            block_lines=[]
            for line in block.get('lines',[]):
                text=normalize(''.join(span['text'] for span in line.get('spans',[])))
                if not text: continue
                box=[round(float(v),2) for v in line['bbox']]
                lines.append({'text':text,'bbox':box});block_lines.append(text)
                for match in MARKER.finditer(text):
                    prefix=text[:match.start()].strip()
                    suffix=text[match.end():]
                    is_caption=(not prefix or prefix.endswith('[')) and bool(re.match(r'^\s*[.>\]: ]',suffix))
                    if not is_caption: continue
                    title=suffix.strip(' .:>][ ')
                    captions.append({'kind':match.group(1),'number':number(match.group(2)),'title':title,'page':i+1,'bbox':box})
            for sentence in split_sentences('\n'.join(block_lines)):
                sentences.append({'text':sentence,'page':i+1,'refs':[list(x) for x in refs(sentence)]})
        pages.append({'page':i+1,'width':round(page.rect.width,2),'height':round(page.rect.height,2),'lines':lines})
    doc.close()
    result={'version':4,'sha256':sha,'pages':pages,'captions':captions,'sentences':sentences}
    save_json(target,result);return result

def clip_context(index, caption):
    page=index['pages'][caption['page']-1];box=caption['bbox'];width=page['width'];height=page['height']
    x0=box[0]-4
    # Financial Stability uses two columns; Monetary often has a chart to the right.
    right=x0>width*0.40
    x1=width-12 if right or box[2]>width*0.75 else width*0.51
    if box[2]>x1: x1=min(width-12,box[2]+4)
    y0=max(0,box[1]-2);y1=height-20
    for other in index['captions']:
        if other['page']!=caption['page'] or other['bbox'][1]<=box[3]+8: continue
        if abs(other['bbox'][0]-box[0])<width*0.15: y1=min(y1,other['bbox'][1]-4)
    # Stop at repeated copyright/footer text.
    for line in page['lines']:
        if line['bbox'][1]>box[3]+8 and BLACKLIST.search(line['text']): y1=min(y1,line['bbox'][1]-2)
    region=[round(x0,2),round(y0,2),round(x1,2),round(max(y0+40,y1),2)]
    lines=[line['text'] for line in page['lines'] if line['bbox'][0]>=x0-6 and line['bbox'][0]<x1 and line['bbox'][1]>=y0 and line['bbox'][1]<region[3] and not BLACKLIST.search(line['text'])]
    return region,lines

def build_context(rows, summary):
    existing=load_json(CACHE/'contexts.json',{})
    baseline_hash=digest([{k:r.get(k) for k in ('결과물ID','근거','제목','번호')} for r in rows])
    if existing.get('version')==6 and existing.get('baseline_hash')==baseline_hash:return existing['items']
    series=series_from_markdown();result={}
    by_report=defaultdict(list)
    for row in rows:by_report[row['보고서']].append(row)
    for report in summary['reports']:
        folder=ARCHIVE/report['folder'];docs=[]
        for src in report.get('pdf_sources',[]):
            path=folder/src['file']
            if not path.exists():continue
            idx=pdf_index(path);docs.append((path,idx))
        print(f"문맥 색인: {report['report']}, PDF {len(docs)}개",flush=True)
        for row in by_report[report['report']]:
            identifier=row['결과물ID'];num=number(row['번호']);title=compact(row['제목']);kind=row['구분']
            preferred=[(p,idx) for p,idx in docs if p.name in row['근거']]
            candidates=[]
            for path,idx in (preferred or docs):
                for cap in idx['captions']:
                    if cap['kind']!=kind:continue
                    cap_title=compact(cap['title'])
                    sim=SequenceMatcher(None,title,cap_title).ratio() if title and cap_title else 0
                    exact=cap['number']==num and num!=UNKNOWN
                    if exact or (len(title)>=8 and (title in cap_title or sim>=0.83)):
                        page_lines=idx['pages'][cap['page']-1]['lines']
                        is_toc=any(re.search(r'(?:그림|통계표|표)\s*차례',x['text']) for x in page_lines[:30])
                        if is_toc:continue
                        candidates.append((3*exact+sim,path,idx,cap))
            context={'series':series.get(identifier,UNKNOWN),'direct_sentences':[],'reason':'본문 캡션 좌표와 연결되지 않음'}
            if candidates:
                _,path,idx,cap=max(candidates,key=lambda x:(x[0],-x[3]['page']))
                region,lines=clip_context(idx,cap)
                context.update({'pdf':str(path.relative_to(ROOT)).replace('\\','/'),'page':cap['page'],'clip':region,'caption':cap['title'],'lines':lines,'text':'\n'.join(lines)[:6500],'reason':''})
                scope_docs=[(path,idx)]
            else:scope_docs=preferred or docs[:1]
            if num!=UNKNOWN:
                pat=ref_pattern(kind,row['번호'])
                for path,idx in scope_docs:
                    for sentence in idx['sentences']:
                        if pat and pat.search(normalize(sentence['text'])):
                            if candidates:
                                # Same numeric labels can recur in independent BOX/appendix
                                # sections of a combined book. Bind the direct reference to
                                # its matched caption scope, never a different section.
                                same_number=[c for c in idx['captions'] if c['kind']==kind and c['number']==num]
                                competing=[c for c in same_number if compact(c['title'])!=compact(cap['title']) and abs(c['page']-cap['page'])>2]
                                if competing:
                                    distance=abs(sentence['page']-cap['page'])
                                    if distance>3 or any(abs(sentence['page']-c['page'])<distance for c in competing):continue
                            context['direct_sentences'].append({'text':sentence['text'],'source':f'PDF:{path.name} p.{sentence["page"]}; 번호 직결 문장'})
            context['direct_sentences']=sorted(context['direct_sentences'],key=lambda s:(len(s['text']),s['source']))
            result[identifier]=context
    save_json(CACHE/'contexts.json',{'version':6,'baseline_hash':baseline_hash,'items':result})
    return result

def render_context(context, target):
    if fitz is None: raise RuntimeError('PyMuPDF 없음')
    doc=fitz.open(ROOT/context['pdf']);page=doc[context['page']-1]
    clip=fitz.Rect(context['clip']) & page.rect
    if clip.is_empty: raise ValueError('빈 그림 영역')
    scale=min(2.1,1500/max(clip.width,clip.height))
    pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),clip=clip,alpha=False)
    target.parent.mkdir(parents=True,exist_ok=True);pix.save(target);doc.close()
    return target
