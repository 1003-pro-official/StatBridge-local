import {useAutoEdit} from './useAutoEdit';
import { useEffect, useRef, useState, type RefObject, type PointerEvent } from "react";
import { createPortal } from "react-dom";
import type { ChartEditInput, ChartSticker, StickerAsset } from "./api/types";
import { clamp, moveSticker, rotationAt, stickerCenter, type PlotBox } from "./stickerTransform";
import "./StickerEditor.css";

type Props = {stage:RefObject<HTMLDivElement|null>;items:ChartSticker[];initialDraft?:()=>ChartSticker[]|undefined;revision:object;disabled:boolean;drawing:boolean;onActivate:()=>void;onDraftChange:(items:ChartSticker[])=>void;onEdit:(input:ChartEditInput)=>Promise<boolean>};
type Plot = HTMLElement & {_fullLayout?:{_size?:{l:number;t:number;w:number;h:number}};on?:(name:string,callback:()=>void)=>void;removeListener?:(name:string,callback:()=>void)=>void};
type Gesture = {id:string;kind:"move"|"size"|"rotate";startX:number;startY:number;original:ChartSticker};

export default function StickerEditor({stage,items,initialDraft,revision,disabled,drawing,onActivate,onDraftChange,onEdit}:Props) {
  const auto=useAutoEdit(onEdit);
  const [catalog,setCatalog]=useState<StickerAsset[]>([]);
  const [draft,setDraft]=useState<ChartSticker[]>(()=>initialDraft?.()??items);
  const lastRevision=useRef(revision);
  const [selected,setSelected]=useState<string|null>(null);
  const [active,setActive]=useState(false);
  const [category,setCategory]=useState("전체");
  const [search,setSearch]=useState("");
  const [error,setError]=useState("");
  const busy=false;
  const [box,setBox]=useState<PlotBox|null>(null);
  const gesture=useRef<Gesture|null>(null);

  const current=draft.find(s=>s.id===selected);
  const asset=catalog.find(a=>a.id===current?.asset_id);
  const dirty=JSON.stringify(draft)!==JSON.stringify(items);
  const locked=disabled||busy;
  useEffect(()=>{onDraftChange(draft);},[draft,onDraftChange]);

  useEffect(()=>{const controller=new AbortController();
    fetch("/stickers/catalog.json",{signal:controller.signal}).then(r=>{if(!r.ok)throw new Error("주석 기호 목록을 불러오지 못했습니다.");return r.json();}).then(setCatalog).catch(e=>{if(!controller.signal.aborted)setError(String(e.message));});
    return()=>controller.abort();
  },[]);
  useEffect(()=>{if(lastRevision.current===revision&&!auto.settled)return;lastRevision.current=revision;if(!auto.pending('stickers')&&JSON.stringify(items)!==JSON.stringify(draft)){setDraft(items);setSelected(null);setActive(false);gesture.current=null;}setError("");},[revision,auto.settled]);
  useEffect(()=>{if(drawing)setActive(false);},[drawing]);
  useEffect(()=>{
    const host=stage.current,plot=host?.querySelector<Plot>(".plotly-chart");
    if(!host||!plot)return;
    const measure=()=>{const size=plot._fullLayout?._size;if(!size||!size.w||!size.h)return;
      const p=plot.getBoundingClientRect(),h=host.getBoundingClientRect();setBox({left:p.left-h.left+size.l,top:p.top-h.top+size.t,width:size.w,height:size.h});};
    const observer=new ResizeObserver(measure);observer.observe(host);observer.observe(plot);
    plot.on?.("plotly_afterplot",measure);measure();
    return()=>{observer.disconnect();plot.removeListener?.("plotly_afterplot",measure);};
  },[stage,revision,active]);
  useEffect(()=>{const host=stage.current;host?.classList.toggle("sticker-preview-active",active);return()=>host?.classList.remove("sticker-preview-active");},[active,stage]);

  const patch=(values:Partial<ChartSticker>)=>setDraft(rows=>rows.map(s=>s.id===selected?{...s,...values}:s));
  const activate=()=>{setActive(true);onActivate();};
  const add=(a:StickerAsset)=>{if(locked||draft.length>=40)return;const s:ChartSticker={id:crypto.randomUUID(),asset_id:a.id,x:.5,y:.5,size:.3,angle:0,opacity:1};setDraft(rows=>[...rows,s]);setSelected(s.id);activate();};
  const remove=()=>{setDraft(rows=>rows.filter(s=>s.id!==selected));setSelected(null);};
  const start=(e:PointerEvent<HTMLDivElement>,s:ChartSticker,kind:Gesture["kind"])=>{if(locked||!box)return;e.preventDefault();e.stopPropagation();e.currentTarget.setPointerCapture(e.pointerId);setSelected(s.id);gesture.current={id:s.id,kind,startX:e.clientX,startY:e.clientY,original:{...s}};};
  const move=(e:PointerEvent<HTMLDivElement>)=>{const g=gesture.current;if(!g||!box||locked)return;
    let next={...g.original};const bounds=stage.current!.getBoundingClientRect();const p={x:e.clientX-bounds.left,y:e.clientY-bounds.top},center=stickerCenter(next,box);
    if(g.kind==="move")next=moveSticker(next,e.clientX-g.startX,e.clientY-g.startY,box);
    else if(g.kind==="rotate")next.angle=rotationAt(p.x,p.y,center);
    else next.size=clamp(Math.hypot(p.x-center.x,p.y-center.y)*Math.SQRT2/Math.min(box.width,box.height),.02,1);
    setDraft(rows=>rows.map(s=>s.id===g.id?next:s));
  };
  const finish=(e:PointerEvent<HTMLDivElement>)=>{gesture.current=null;if(dirty)auto.schedule({instruction:'',stickers:draft},'stickers');if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);};
  const cancel=()=>{const g=gesture.current;if(g)setDraft(rows=>rows.map(s=>s.id===g.id?g.original:s));gesture.current=null;};
  useEffect(()=>{if(dirty&&!gesture.current)auto.schedule({instruction:'',stickers:draft},'stickers');},[draft]);
  const overlay=active&&box&&stage.current?createPortal(<div className="sticker-overlay" aria-label="주석 기호 배치 영역"
    onPointerDown={e=>{if(e.target===e.currentTarget&&!locked){gesture.current=null;setSelected(null);}}}
    >{draft.map(s=>{const a=catalog.find(a=>a.id===s.asset_id);if(!a)return null;const center=stickerCenter(s,box),side=s.size*Math.min(box.width,box.height),envelope=Math.ceil(Math.hypot(a.width,a.height));
      return <div key={s.id} role="button" tabIndex={0} aria-label={`${a.name} 주석 기호 선택·이동`} aria-pressed={selected===s.id}
        className={`sticker-object ${selected===s.id?"selected":""}`} style={{left:center.x,top:center.y,width:side,height:side}}
        onPointerDown={e=>start(e,s,"move")} onPointerMove={move} onPointerUp={finish} onPointerCancel={cancel}
        onKeyDown={e=>{if(locked)return;setSelected(s.id);const d:Record<string,[number,number]>={ArrowLeft:[-5,0],ArrowRight:[5,0],ArrowUp:[0,-5],ArrowDown:[0,5]};if(d[e.key]){e.preventDefault();setDraft(rows=>rows.map(row=>row.id===s.id?moveSticker(row,...d[e.key],box):row));}else if(e.key==="Delete"){e.preventDefault();setDraft(rows=>rows.filter(row=>row.id!==s.id));}else if(e.key==="Enter"||e.key===" "){e.preventDefault();setSelected(s.id);}}}>
        <img src={`/stickers/${a.file}`} alt="" draggable={false} style={{width:`${100*a.width/envelope}%`,height:`${100*a.height/envelope}%`,opacity:s.opacity,transform:`translate(-50%,-50%) rotate(${s.angle}deg)`}}/>
        {selected===s.id&&<><div className="sticker-handle rotate" aria-label="회전 조절점" title="끌어서 회전" onPointerDown={e=>start(e,s,"rotate")}>↻</div><div className="sticker-handle resize" aria-label="크기 조절점" title="끌어서 크기 조절" onPointerDown={e=>start(e,s,"size")}>↔</div></>}
      </div>;
    })}</div>,stage.current):null;

  return <><details className="sticker-editor" onToggle={e=>{if(e.currentTarget.open)activate();else setActive(false);}}><summary>보고서 주석 기호 <span>{catalog.length}종</span></summary>
    <p>한국은행 통화신용정책보고서(2026년 9월) 그림 I-4의 상승·하락 표시를 참고한 기본 화살표입니다. 공식 배포 이미지가 아닙니다.</p><p>이미지를 고른 뒤 그래프에서 끌어 이동하세요. 조절점이나 아래 설정으로 크기와 각도를 바꿀 수 있습니다.</p>
    <input type="search" aria-label="주석 기호 검색" value={search} onChange={e=>setSearch(e.target.value)} placeholder="주석 기호 검색"/>
    <div className="sticker-categories">{["전체",...new Set(catalog.map(a=>a.category))].map(c=><button key={c} type="button" aria-pressed={category===c} onClick={()=>setCategory(c)}>{c}</button>)}</div>
    <div className="sticker-gallery">{catalog.filter(a=>(category==="전체"||category===a.category)&&a.name.includes(search.trim())).map(a=><button key={a.id} type="button" title={a.name} aria-label={`${a.name} 추가`} disabled={locked||draft.length>=40} onClick={()=>add(a)}><img src={`/stickers/${a.file}`} alt="" loading="lazy"/><span>{a.name}</span></button>)}</div>
    {!!draft.length&&<label className="sticker-choice">배치한 주석 기호<select aria-label="배치한 주석 기호 선택" value={selected||""} onChange={e=>{setSelected(e.target.value);activate();}}><option value="">선택하세요</option>{draft.map((s,i)=><option key={s.id} value={s.id}>{i+1}. {catalog.find(a=>a.id===s.asset_id)?.name}</option>)}</select></label>}
    {current&&asset&&<div className="sticker-settings"><strong>{asset.name}</strong>
      <label>크기 <input type="range" aria-label="주석 기호 크기" min="2" max="100" value={Math.round(current.size*100)} disabled={locked} onChange={e=>patch({size:Number(e.target.value)/100})}/><input type="number" aria-label="주석 기호 크기 수치" min="2" max="100" value={Math.round(current.size*100)} disabled={locked} onChange={e=>patch({size:clamp(Number(e.target.value),2,100)/100})}/> %</label>
      <label>각도 <input type="range" aria-label="주석 기호 각도" min="-360" max="360" value={current.angle} disabled={locked} onChange={e=>patch({angle:Number(e.target.value)})}/><input type="number" aria-label="주석 기호 각도 수치" min="-360" max="360" value={current.angle} disabled={locked} onChange={e=>patch({angle:clamp(Number(e.target.value),-360,360)})}/> °</label>
      <label>투명도 <input type="range" aria-label="주석 기호 투명도" min="0" max="100" value={Math.round((1-current.opacity)*100)} disabled={locked} onChange={e=>patch({opacity:1-Number(e.target.value)/100})}/><span>{Math.round((1-current.opacity)*100)}%</span></label>
      <div className="sticker-actions"><button type="button" disabled={locked} onClick={remove}>선택 삭제</button><a href={`/stickers/${asset.file}`} download={`${asset.id}.png`}>PNG 다운로드</a></div>
    </div>}
    <div className="sticker-actions"><button type="button" disabled={locked} onClick={()=>{setDraft(items);setSelected(null);setActive(false);}}>저장한 배치로 복원</button><button type="button" disabled={locked} onClick={()=>{if(active)setActive(false);else activate();}}>{active?"배치 미리보기 종료":"배치 조정"}</button></div>
    {dirty&&!active&&<small>변경한 배치는 자동 저장됩니다.</small>}{(error||auto.error)&&<p role="alert">{error||auto.error}</p>}
  </details>{overlay}</>;
}
