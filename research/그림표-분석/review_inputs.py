#!/usr/bin/env python3
"""Display compact source packets and save human-visible vision contact sheets."""
import argparse,json,sys
from pathlib import Path
from enrichment.common import CACHE,OUT,load_json,save_json,digest,UNKNOWN
from enrichment.context import render_context

def text(start,count):
    groups=load_json(CACHE/'assistant_group_inputs.json',[])
    for group in groups[start-1:start-1+count]:
        e=group['examples'][0]
        fields=[group['group'],group['title']]
        if e['series']!=UNKNOWN:fields.append('계열='+e['series'][:90])
        if e['description']!=UNKNOWN:fields.append('본문='+e['description'][:170])
        if len(group['title'])<13:
            ctx=load_json(CACHE/'contexts.json',{})['items'].get(group['ids'][0],{})
            if ctx.get('text'):fields.append('영역='+ctx['text'][:260].replace('\n',' / '))
        print(' | '.join(fields))

def sheets(size):
    from PIL import Image,ImageDraw,ImageFont
    jobs=load_json(CACHE/'vision_jobs.json',[])
    target=CACHE/'review_sheets';target.mkdir(parents=True,exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',13)
    titlefont=ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf',15)
    cols=5;cell_w=340;cell_h=260
    for start in range(0,len(jobs),size):
        number=start//size+1;png=target/f'sheet_{number:03d}.png';meta=target/f'sheet_{number:03d}.json'
        if png.exists() and meta.exists():continue
        selected=jobs[start:start+size]
        sheet=Image.new('RGB',(cell_w*cols,cell_h*((len(selected)+cols-1)//cols)),'#e1e4e8')
        draw=ImageDraw.Draw(sheet);items=[]
        for j,job in enumerate(selected):
            index=start+j+1;key=digest(job);crop=CACHE/'vision_crops'/f'{key}.png'
            if not crop.exists():render_context(job['context'],crop)
            img=Image.open(crop).convert('RGB');img.thumbnail((cell_w-10,cell_h-54))
            x=(j%cols)*cell_w;y=(j//cols)*cell_h
            draw.rectangle((x,y,x+cell_w-2,y+cell_h-2),fill='white',outline='#666')
            draw.text((x+5,y+3),f'{index} | {job["number"]}',font=titlefont,fill='black')
            draw.text((x+5,y+23),job['title'][:26],font=font,fill='black')
            sheet.paste(img,(x+5,y+49))
            items.append({'index':index,'job':job,'crop':str(crop.relative_to(OUT))})
        sheet.save(png);save_json(meta,items)
        print(f'검토 이미지 {number}: {start+1}~{start+len(selected)}',flush=True)

OBS={'선그래프':'관측점을 잇는 연속 선과 수치 축이 보임','막대':'범주별 세로 또는 가로 막대가 보임','산점도':'두 수치 축 사이에 개별 관측점이 흩어져 있음','영역':'축 아래 또는 계열 사이의 채움 영역이 보임','pie':'원형을 비율별 부채꼴로 나눈 형태가 보임','혼합':'서로 다른 선·막대 또는 다른 그래프 형식이 함께 보임','사진·이미지':'정량 그래프가 아닌 사진·개념도·흐름도 등의 이미지','불명':'이 해상도와 캡션 연결로는 지정 그림을 확실히 판별할 수 없음'}

def record(sheet,decisions):
    items=load_json(CACHE/'review_sheets'/f'sheet_{sheet:03d}.json',[])
    by_index={x['index']:x['job'] for x in items}
    raw=json.loads(decisions);bank=load_json(CACHE/'assistant_vision_judgments.json',{})
    for item in raw:
        index,kind=item[:2];job=by_index.get(index)
        if not job or kind not in OBS:raise ValueError(f'잘못된 시트/판정: {index} {kind}')
        bank[job['id']]={'kind':kind,'confidence':0.95 if kind!=UNKNOWN else 0,'observation':item[2] if len(item)>2 else OBS[kind],'context_hash':digest(job),'response_hash':digest(item),'sheet':sheet,'sheet_index':index}
    save_json(CACHE/'assistant_vision_judgments.json',bank);print('저장된 직접 비전 판별',len(bank))

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True)
    t=sub.add_parser('text');t.add_argument('--start',type=int,default=1);t.add_argument('--count',type=int,default=100)
    s=sub.add_parser('sheets');s.add_argument('--size',type=int,default=30)
    r=sub.add_parser('record-vision');r.add_argument('--sheet',type=int,required=True);r.add_argument('--decisions',required=True)
    a=p.parse_args()
    if a.mode=='text':text(a.start,a.count)
    elif a.mode=='sheets':sheets(a.size)
    else:record(a.sheet,a.decisions)
if __name__=='__main__':main()
