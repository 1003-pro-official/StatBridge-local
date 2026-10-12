import {apiFetch,accountKey} from './accountApi';
import { PointerEvent, ReactNode, useEffect, useRef, useState } from "react";
import Plotly from "plotly.js-dist-min";
import type { ChartEditInput, ChartSeries, SketchMark, EditSelection } from "./api/types";
import { graphHitPoints, resolveMarkSelection, resolveMarkRegion } from "./chartSelection";
import { isDrawingStroke, periodLabel, sketchLabel } from "./sketchLabels";
import { markBounds,moveMark,resizeMark } from "./sketchTransform";
import type { EditableMark,Corner } from "./sketchTransform";
import { bindMarks, changeMarkTarget, elementTargets, inferMarkTarget } from "./sketchRequest";
import { Sujeongi } from "./Sujeongi";
import editHelp from "./chartEditHelp.json";
import StickerEditor from "./StickerEditor";
import ReportPanel from "./ReportPanel";
import {reportExportIntent} from './reportExportIntent';
import {exportReportFile} from './api/client';
import type { ChartSticker } from "./api/types";
import WorkspaceProperties from './WorkspaceProperties';
import type {GraphSelection} from './WorkspaceProperties';
import WorkspaceData from './WorkspaceData';
import {historyIntent} from './historyIntent';
import './ChartWorkspace.css';

type Props = {
  children: ReactNode;
  warnings?:string[];
  series: ChartSeries[];
  sessionId: string;
  revision: object;
  loading: boolean;
  model?: { model: string; supportsImages: boolean };
  canUndo?: boolean;
  canRedo?: boolean;
  onEdit: (input: ChartEditInput) => Promise<boolean>;
};

function Mark({ mark }: { mark: EditableMark }) {
  const first = mark.points[0], last = mark.points[mark.points.length - 1];
  const x = first.x * 1000, y = first.y * 1000;
  const bounds=markBounds(mark);
  return <g data-mark-id={mark.id} stroke="#d62c43" strokeWidth="3" fill="none" style={{pointerEvents:"auto",cursor:"move"}}>
    {mark.tool==='text'?<rect x={bounds.left*1000} y={bounds.top*1000} width={(bounds.right-bounds.left)*1000} height={(bounds.bottom-bounds.top)*1000} fill="transparent" stroke="none"/>:mark.tool==='rectangle'?<rect x={bounds.left*1000} y={bounds.top*1000} width={(bounds.right-bounds.left)*1000} height={(bounds.bottom-bounds.top)*1000} fill="transparent" stroke="transparent" strokeWidth="16"/>:<polyline points={mark.points.map(p=>`${p.x*1000},${p.y*1000}`).join(' ')} stroke="transparent" strokeWidth="18"/>}
    {mark.tool === "pen" && <polyline points={mark.points.map(p => `${p.x * 1000},${p.y * 1000}`).join(" ")}/>}
    {mark.tool === "arrow" && <line x1={x} y1={y} x2={last.x * 1000} y2={last.y * 1000} markerEnd="url(#sketch-arrow)"/>}
    {mark.tool === "ellipse" && <ellipse cx={(bounds.left+bounds.right)*500} cy={(bounds.top+bounds.bottom)*500} rx={(bounds.right-bounds.left)*500} ry={(bounds.bottom-bounds.top)*500}/>}
    {mark.tool === "rectangle" && <rect x={Math.min(x,last.x*1000)} y={Math.min(y,last.y*1000)} width={Math.abs(x-last.x*1000)} height={Math.abs(y-last.y*1000)}/>}
    {mark.tool==="text" && mark.text && <text x={x} y={Math.max(20,y-8)} fill="#a81830" stroke="none" fontSize={mark.textSize||22}>{mark.text}</text>}
  </g>;
}

async function readImage(src: string): Promise<HTMLImageElement> {
  const image = new Image();
  await new Promise<void>((resolve,reject) => { image.onload=()=>resolve(); image.onerror=()=>reject(new Error("그래프 이미지 생성에 실패했습니다.")); image.src=src; });
  return image;
}

export default function ChartSketchEditor({ children, series, sessionId, revision, loading, onEdit, model, canUndo, canRedo, warnings=[] }: Props) {
  const state=(revision as {chartState?:Record<string,unknown>}).chartState||{};
  const [selection,setSelection]=useState<GraphSelection>({kind:'chart'});
  const [dataOpen,setDataOpen]=useState(true),[propertiesOpen,setPropertiesOpen]=useState(true);
  const [searchQuery,setSearchQuery]=useState('');
  const [fileBusy,setFileBusy]=useState(false);
  const stickerDraft=useRef<{revision:object;items:ChartSticker[]}|null>(null);
  const editWithDraft=(input:ChartEditInput)=>{
    const pending=stickerDraft.current?.revision===revision?stickerDraft.current.items:null;
    const saved=(revision as {chartState?:{stickers?:ChartSticker[]}}).chartState?.stickers||[];
    return onEdit({...input,...(!input.document&&(!input.action||input.action==='edit')&&input.stickers===undefined&&pending&&JSON.stringify(pending)!==JSON.stringify(saved)?{stickers:pending}:{})});
  };
  const [enabled,setEnabled] = useState(false);
  const [tool,setTool] = useState<SketchMark["tool"]>("pen");
  const [marks,setMarks] = useState<EditableMark[]>([]);
  const [selectedMark,setSelectedMark] = useState<string|null>(null);
  const [selectMode,setSelectMode] = useState(false);
  const transform=useRef<{mark:EditableMark;origin:{x:number;y:number};corner?:Corner;current:EditableMark;changed:boolean}|null>(null);
  const [draft,setDraft] = useState<SketchMark | null>(null);
  const active = useRef<SketchMark | null>(null);
  const [target,setTarget] = useState("chart");
  const [scope,setScope] = useState<EditSelection["scope"]>("segment");
  const [start,setStart] = useState("");
  const [end,setEnd] = useState("");
  const chosen=series.find(s=>s.label===target);
  const periods=chosen?.points.map(p=>p.date)||[];
  const manual:EditSelection|undefined=chosen&&scope==="series" ? {label:target,scope} : chosen&&start&&(scope==="point"||end) ? {label:target,scope,start,end:scope==="point"?start:end} : undefined;
  const [note,setNote] = useState("");
  const [textAnchor,setTextAnchor] = useState<SketchMark["points"][number]|null>(null);
  const [editingMark,setEditingMark] = useState<string|null>(null);
  const textInput = useRef<HTMLTextAreaElement>(null);
  const [instruction,setInstruction] = useState("");
  const [busy,setBusy] = useState(false);
  const applying = useRef(false);
  const [error,setError] = useState("");
  const stage = useRef<HTMLDivElement>(null);
  const overlay = useRef<SVGSVGElement>(null);
  useEffect(() => { setMarks([]);setSelectedMark(null);transform.current=null;setDraft(null);active.current=null;setInstruction("");setNote("");setTextAnchor(null);setTarget("chart");setStart("");setEnd("");setError(""); },[sessionId,revision]);
  useEffect(()=>{if(enabled&&tool==="text")textInput.current?.focus();},[enabled,tool,textAnchor]);

  const point = (event: PointerEvent<SVGSVGElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    return { x:Math.max(0,Math.min(1,(event.clientX-bounds.left)/bounds.width)), y:Math.max(0,Math.min(1,(event.clientY-bounds.top)/bounds.height)) };
  };
  const down = (event: PointerEvent<SVGSVGElement>) => {
    if(loading||busy||active.current||transform.current)return;
    const element=event.target as Element;
    const hit=element.closest('[data-mark-id]');
    const existing=marks.find(m=>m.id===hit?.getAttribute('data-mark-id'));
    if(existing){
      if(!enabled||(!selectMode&&tool==='text')){event.preventDefault();setSelectedMark(existing.id);setSelectMode(true);setEnabled(true);return;}
      event.preventDefault();event.currentTarget.setPointerCapture(event.pointerId);
      setSelectedMark(existing.id);setSelectMode(true);setEnabled(true);
      transform.current={mark:existing,origin:point(event),corner:(element.closest('[data-corner]')?.getAttribute('data-corner')||undefined) as Corner|undefined,current:existing,changed:false};
      return;
    }
    if(selectMode){setSelectedMark(null);return;}
    if(!enabled||marks.length>=40)return;
    if(tool==="text") {event.preventDefault();setTextAnchor(point(event));return;}
    event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId);
    const mark: SketchMark = { id:crypto.randomUUID(),tool,points:[point(event)],text:note.trim(),target };
    active.current=mark;setDraft(mark);
  };
  const move = (event: PointerEvent<SVGSVGElement>) => {
    if(transform.current){
      const t=transform.current,p=point(event),bounds=event.currentTarget.getBoundingClientRect();
      if(Math.hypot((p.x-t.origin.x)*bounds.width,(p.y-t.origin.y)*bounds.height)<3&&!t.changed)return;
      if(!t.changed){setStart("");setEnd("");}
      const next=t.corner?resizeMark(t.mark,t.corner,p.x,p.y):moveMark(t.mark,p.x-t.origin.x,p.y-t.origin.y);
      t.current=next;t.changed=true;setMarks(current=>current.map(m=>m.id===next.id?next:m));return;
    }
    if (!active.current) return;
    const mark=active.current;
    const sampled=mark.points.length>=299 ? mark.points.filter((_,index)=>index%2===0) : mark.points;
    const points=mark.tool==="pen" ? [...sampled,point(event)] : [mark.points[0],point(event)];
    active.current={...mark,points};setDraft(active.current);
  };
  const saveMark = (input:EditableMark,replace=false) => {
    const stageBox=stage.current?.getBoundingClientRect();
    const legendBox=stage.current?.querySelector('.legend')?.getBoundingClientRect();
    const legend=stageBox&&legendBox&&stageBox.width&&stageBox.height?{left:(legendBox.left-stageBox.left)/stageBox.width,right:(legendBox.right-stageBox.left)/stageBox.width,top:(legendBox.top-stageBox.top)/stageBox.height,bottom:(legendBox.bottom-stageBox.top)/stageBox.height}:undefined;
    let mark=inferMarkTarget(input,legend);
    setNote("");
    try {
      if(scope!=="series"&&(mark.target==="chart"||series.some(s=>s.label===mark.target))){
        const plot=stage.current?.querySelector<HTMLElement>(".plotly-chart");
        const bounds=stage.current?.getBoundingClientRect();
        if(!manual&&(!plot||!bounds))throw new Error("실제 그래프 위치를 확인하지 못했습니다. 시점을 직접 선택해 주세요.");
        mark={...mark,selection:(!replace&&manual)||resolveMarkSelection(mark,graphHitPoints(plot!,stage.current!),bounds!.width,bounds!.height,scope)};
      } else if(manual&&!replace&&!elementTargets.has(mark.target))mark={...mark,selection:manual};
      setMarks(current=>replace?current.map(m=>m.id===mark.id?mark:m):[...current,mark]);setError("");
    }catch(err){
      // Keep the user's drawing even when its statistical target is unresolved.
      setMarks(current=>replace?current.map(m=>m.id===mark.id?mark:m):[...current,mark]);
      setError((err instanceof Error?err.message:"부분 선택을 확인하지 못했습니다.")+" 표시는 보존했습니다. 대상을 선택하고 실제 시점을 지정해 주세요.");
    }
  };
  const up = (event: PointerEvent<SVGSVGElement>) => {
    if(transform.current){const t=transform.current;transform.current=null;if(t.changed)saveMark(t.current,true);if(event.currentTarget.hasPointerCapture(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);return;}
    if (!active.current) return;
    const bounds=event.currentTarget.getBoundingClientRect();
    if(isDrawingStroke(active.current,bounds.width,bounds.height))saveMark(active.current);
    active.current=null;setDraft(null);
    if(event.currentTarget.hasPointerCapture(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);
  };
  const apply = async (requestedInstruction=instruction, conversation: Array<{role:"user"|"assistant";text:string}>=[]): Promise<boolean> => {
    if(applying.current||loading)return false;
    applying.current=true;
    setBusy(true);setError("");
    try {
      const action=historyIntent(requestedInstruction);
      if(action)return await onEdit({instruction:'',action});
      const exportFormat=reportExportIntent(requestedInstruction);
      if(exportFormat&&!marks.some(mark=>mark.text.trim())){
        let version=(revision as {editVersion?:number}).editVersion;
        const pending=stickerDraft.current?.revision===revision?stickerDraft.current.items:null;
        const saved=(revision as {chartState?:{stickers?:ChartSticker[]}}).chartState?.stickers||[];
        if(pending&&JSON.stringify(pending)!==JSON.stringify(saved)){
          if(!await onEdit({instruction:'',stickers:pending}))return false;
          if(version!==undefined)version+=1;
        }
        const blob=await exportReportFile(sessionId,version,exportFormat),url=URL.createObjectURL(blob),link=document.createElement('a');
        link.href=url;link.download=`statbridge-report.${exportFormat}`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
        return true;
      }
      const plotForRegion=stage.current?.querySelector<HTMLElement>(".plotly-chart");
      const boundMarks=bindMarks(marks,manual).map(mark=>({...mark,region:plotForRegion&&stage.current?resolveMarkRegion(mark,plotForRegion,stage.current):undefined}));
      const visual = { marks:boundMarks, selected_target:target, selection:manual, graph_image:undefined as string|undefined, marked_image:undefined as string|undefined };
      if (marks.length && model?.supportsImages) {
        const plot = stage.current?.querySelector<HTMLElement>(".plotly-chart");
        if (plot && overlay.current) {
          const bounds=stage.current!.getBoundingClientRect();
          const width=900, height=Math.min(1600,Math.max(250,Math.round(width*bounds.height/bounds.width)));
          const src=await Plotly.toImage(plot,{format:"png",width,height});
          const canvas=document.createElement("canvas");canvas.width=width;canvas.height=height;
          const context=canvas.getContext("2d");
          if(!context)throw new Error("편집 이미지 생성 기능을 사용할 수 없습니다.");
          context.drawImage(await readImage(src),0,0,width,height);
          const clone=overlay.current.cloneNode(true) as SVGSVGElement;
          clone.querySelectorAll('.sketch-selection').forEach(node=>node.remove());
          clone.setAttribute("xmlns","http://www.w3.org/2000/svg");clone.setAttribute("width",String(width));clone.setAttribute("height",String(height));
          const url=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)],{type:"image/svg+xml;charset=utf-8"}));
          try { context.drawImage(await readImage(url),0,0,width,height); } finally { URL.revokeObjectURL(url); }
          const marked=canvas.toDataURL("image/png");
          if(src.length<=2_000_000 && marked.length<=2_000_000){visual.graph_image=src;visual.marked_image=marked;}
        }
      }
      const savedStickers=(revision as {chartState?:{stickers?:ChartSticker[]}}).chartState?.stickers||[];
      const stickers=stickerDraft.current?.revision===revision?stickerDraft.current.items:null;
      const success=await onEdit({instruction:requestedInstruction.trim(),visual,conversation,
        ...(stickers&&JSON.stringify(stickers)!==JSON.stringify(savedStickers)?{stickers}:{} )});
      if(success){setMarks([]);setInstruction("");setNote("");}
      return success;
    } catch(err){setError(err instanceof Error?err.message:"수정 요청을 준비하지 못했습니다.");throw err;}
    finally{applying.current=false;setBusy(false);}
  };
  const historyAction = async (action:"undo"|"redo") => {
    try { await onEdit({instruction:"",action}); }
    catch(err) { setError(err instanceof Error?err.message:"편집을 되돌리지 못했습니다."); }
  };
  useEffect(()=>{
    const node=stage.current;if(!node)return;
    const select=(event:Event)=>setSelection((event as CustomEvent<GraphSelection>).detail);
    const hitShape=(event:MouseEvent)=>{
      if(enabled||(event.target as Element).closest('.gtitle,.xtick,.ytick,.xtitle,.ytitle,.annotation,.legend,.workspace-plot-heading,.workspace-plot-legend'))return;
      const plot=node.querySelector<HTMLElement>('.plotly-chart');if(!plot)return;
      const bounds=node.getBoundingClientRect(),x=event.clientX-bounds.left,y=event.clientY-bounds.top;
      try{const hit=resolveMarkSelection({id:'click',tool:'arrow',target:'chart',text:'',points:[{x:x/bounds.width,y:y/bounds.height}]},graphHitPoints(plot,node),bounds.width,bounds.height,'segment');setSelection({kind:'series',label:hit.label});return;}catch{/* Empty chart space may select a highlighted time region. */}
      const graph=plot as unknown as {_fullLayout?:Record<string,any>},axis=graph._fullLayout?.xaxis,frame=graph._fullLayout?._size;
      if(!axis?.l2p||!Array.isArray(axis._categories)||!frame)return;
      const pb=plot.getBoundingClientRect(),px=event.clientX-pb.left,py=event.clientY-pb.top;
      if(py<frame.t||py>frame.t+frame.h)return;
      const category=(date:string)=>axis._categories.findIndex((v:string)=>String(v).replace(/^period:/,'')===date);
      const selected=(state.highlights as Array<{id:string;start:string;end:string}>||[]).find(h=>{const a=category(h.start),b=category(h.end);return a>=0&&b>=0&&px>=axis.l2p(a)+axis._offset&&px<=axis.l2p(b)+axis._offset;});
      if(selected)setSelection({kind:'highlight',id:selected.id});
    };
    node.addEventListener('statbridge:graph-select',select);node.addEventListener('click',hitShape);return()=>{node.removeEventListener('statbridge:graph-select',select);node.removeEventListener('click',hitShape);};
  },[revision,enabled]);
  useEffect(()=>{if(selection.kind==='series'&&selection.label)setTarget(selection.label);else if(selection.kind==='title')setTarget('title');else if(selection.kind==='x')setTarget('x_axis');else if(selection.kind==='y')setTarget('y_axis');},[selection,revision]);
  const file=async(format:string)=>{
    setFileBusy(true);setError('');try{
      let version=(revision as {editVersion?:number}).editVersion;
      const pending=stickerDraft.current?.revision===revision?stickerDraft.current.items:null;
      if(pending&&JSON.stringify(pending)!==JSON.stringify(state.stickers||[])){if(!await onEdit({instruction:'',stickers:pending}))return;if(version!==undefined)version+=1;}
      if(format==='json'){const response=await apiFetch(`${import.meta.env.VITE_API_BASE_URL??'http://127.0.0.1:8000/api'}/workspace/${encodeURIComponent(sessionId)}/save`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({edit_session_id:sessionId,revision:version,format:'json'})});if(!response.ok){const reason=await response.json();throw new Error(reason.detail||'서버 저장에 실패했습니다.');}window.dispatchEvent(new Event('statbridge:graph-saved'));}
      const csvValue=(value:unknown)=>JSON.stringify(String(value));
      const blob=format==='csv'?new Blob(['\ufeff'+[['데이터','시점','값','단위'].join(','),...series.flatMap(s=>s.points.map(p=>[s.label,p.date,p.value,s.unit].map(csvValue).join(',')))].join('\r\n')],{type:'text/csv;charset=utf-8'}):await exportReportFile(sessionId,version,format);
      if(format==='json')try{localStorage.setItem(accountKey('statbridge.workspace.saved'),await blob.text());}catch{setError('브라우저 저장 공간이 부족합니다. 다운로드한 파일로 복원하세요.');}
      const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=`statbridge-chart.${format}`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }catch(e){setError(e instanceof Error?e.message:String(e));}finally{setFileBusy(false);}
  };
  const restoreFile=async(file?:File)=>{if(!file)return;try{if(file.size>8_000_000)throw new Error('설정 파일은 최대 8MB입니다.');await onEdit({instruction:'',document:JSON.parse(await file.text())});}catch(e){setError(e instanceof Error?e.message:String(e));}};
  const controls = <>
    <StickerEditor stage={stage} items={(revision as {chartState?:{stickers?:ChartSticker[]}}).chartState?.stickers||[]} initialDraft={()=>stickerDraft.current?.revision===revision?stickerDraft.current.items:undefined} revision={revision} disabled={loading||busy} drawing={enabled} onActivate={()=>setEnabled(false)} onDraftChange={items=>{stickerDraft.current={revision,items};}} onEdit={onEdit}/>
    <div className="sketch-toolbar">
      <button type="button" disabled={!canUndo||loading||busy} onClick={()=>void historyAction("undo")}>편집 취소</button>
      <button type="button" disabled={!canRedo||loading||busy} onClick={()=>void historyAction("redo")}>편집 다시 적용</button>
      <button type="button" aria-pressed={enabled} disabled={loading||busy} onClick={()=>setEnabled(!enabled)}>{enabled?"그림 편집 종료":"그림판 편집 켜기"}</button>
      {enabled && <>
        <button type="button" className="sketch-tool" aria-pressed={selectMode} disabled={loading||busy} onClick={()=>{setSelectMode(true);setTextAnchor(null);}}><span aria-hidden="true">↖</span>선택·이동</button>
        {([ ["pen","펜","✎"],["arrow","화살표","↗"],["rectangle","사각형","□"],["ellipse","원","○"],["text","텍스트","T"] ] as const).map(([value,label,icon])=><button type="button" className="sketch-tool" key={value} aria-pressed={!selectMode&&tool===value} disabled={loading||busy} onClick={()=>{setTool(value);setSelectMode(false);setSelectedMark(null);setTextAnchor(null);setNote("");}}><span aria-hidden="true">{icon}</span>{label}</button>)}
        <button type="button" disabled={!marks.length||loading||busy} onClick={()=>setMarks(current=>current.slice(0,-1))}>표시 되돌리기</button>
        <button type="button" disabled={!marks.length||loading||busy} onClick={()=>setMarks([])}>표시 지우기</button>
      </>}
    </div>
    {marks.some(mark=>!mark.selection&&!elementTargets.has(mark.target))&&<details className="sketch-unresolved"><summary>표시 범위를 확인해 주세요</summary>
    <div className="sketch-fields">
      <label>수정 대상<select value={target} disabled={loading||busy} onChange={e=>{setTarget(e.target.value);setStart("");setEnd("");}}>
        <option value="chart">그래프 전체 / 확인 필요</option><option value="title">제목</option><option value="legend">범례</option><option value="x_axis">가로축</option><option value="y_axis">세로축</option>
        {Array.from(new Set(series.map(s=>s.label))).map(label=><option key={label} value={label}>{label}</option>)}
      </select></label>
      <label>적용 범위<select value={scope} disabled={loading||busy||elementTargets.has(target)} onChange={e=>setScope(e.target.value as EditSelection["scope"])}><option value="segment">선분 / 관측 구간</option><option value="point">관측점 / 막대 하나</option><option value="series">계열 전체</option></select>{elementTargets.has(target)&&<small>제목·축·범례는 시점 선택 없이 수정합니다.</small>}</label>
      {chosen&&scope!=="series"&&<><label>시작 시점<select value={start} onChange={e=>setStart(e.target.value)}><option value="">그림으로 선택</option>{periods.map(p=><option key={p}>{p}</option>)}</select></label>{scope==="segment"&&<label>종료 시점<select value={end} onChange={e=>setEnd(e.target.value)}><option value="">그림으로 선택</option>{periods.map(p=><option key={p}>{p}</option>)}</select></label>}</>}
      {manual&&<span>선택: {manual.label} · {manual.scope} · {manual.start} ~ {manual.end}</span>}
    </div>
    </details>}
    {enabled&&!selectMode&&tool==="text"&&<div className="setup-block sketch-text-panel" role="group" aria-label="그래프 텍스트 표시 입력">
      <label>표시할 텍스트<textarea ref={textInput} value={note} maxLength={300} disabled={loading||busy} onChange={e=>setNote(e.target.value)} placeholder="그래프 위에 배치할 수정 설명을 입력하세요"/></label>
      <p>{textAnchor?"배치 위치를 선택했습니다. 텍스트 배치를 눌러 주세요.":"텍스트를 입력한 뒤 그래프에서 배치할 위치를 클릭하세요."} 최종 그래프 주석이 아닌 수정 지시용 표시입니다.</p>
      <button type="button" disabled={!textAnchor||!note.trim()||loading||busy||marks.length>=40} onClick={()=>{if(textAnchor){saveMark({id:crypto.randomUUID(),tool:"text",points:[textAnchor],text:note.trim(),target});setTextAnchor(null);setNote("");setEnabled(false);setTool("pen");}}}>텍스트 배치</button>
    </div>}
    {!!marks.length&&<p className="sketch-help">표시를 클릭해 선택한 뒤 끌어서 이동하세요. 파란 모서리 조절점을 끌면 크기를 바꿀 수 있습니다. 이동 후 수정 위치는 다시 확인합니다.</p>}
    <details className="chart-edit-help"><summary>편집 가능한 항목과 예시</summary><p>그림을 그리지 않고 아래 입력칸에 여러 변경을 한 번에 적어도 됩니다. 여러 계열은 계열 이름을, 부분 수정은 실제 날짜나 분기를 함께 적어 주세요. 기존 메모·도형은 내용이나 위치로 지정해 주세요.</p>{editHelp.map(group=><section key={group.title}><strong>{group.title}</strong><ul>{group.examples.map(example=><li key={example}>{example}</li>)}</ul></section>)}</details>
    {error&&<p role="alert" className="error-banner">{error}</p>}
  </>;
  return <div className="sketch-editor chart-workspace" data-workspace-session={sessionId} aria-label="그래프 편집 워크스페이스">
    <header className="workspace-top"><div><small>STATBRIDGE 분석 작업{(revision as {cachedSnapshot?:boolean}).cachedSnapshot?' · 저장 당시 자료':''}</small><strong>{String(state.title||'통계 그래프 편집')}</strong></div><label className="workspace-search"><span className="sr-only">편집 항목 찾기</span><input aria-label="편집 항목 찾기" placeholder="제목, 축, 데이터 항목 찾기" value={searchQuery} onChange={e=>{const text=e.target.value;setSearchQuery(text);const found=series.find(s=>s.label.includes(text));if(text.includes('제목'))setSelection({kind:'title'});else if(text.includes('축'))setSelection({kind:'y'});else if(found)setSelection({kind:'series',label:found.label});}}/></label><div className="workspace-actions"><button type="button" disabled={!canUndo||loading} onClick={()=>void historyAction('undo')} title="마지막 편집 되돌리기">↶ 되돌리기</button><button type="button" disabled={!canRedo||loading} onClick={()=>void historyAction('redo')} title="취소한 편집 다시 실행">↷ 다시 실행</button><button type="button" disabled={loading||fileBusy} onClick={()=>void file('json')}>설정 저장</button><details><summary>다운로드 · 열기</summary><div>{['png','svg','pdf','csv'].map(format=><button key={format} type="button" disabled={loading||fileBusy} onClick={()=>void file(format)}>{format.toUpperCase()} 다운로드</button>)}<label>저장한 그래프 열기<input aria-label="저장한 그래프 열기" type="file" accept=".json" onChange={e=>void restoreFile(e.target.files?.[0])}/></label><button type="button" disabled={loading} onClick={async()=>{try{const saved=localStorage.getItem(accountKey('statbridge.workspace.saved'));if(!saved)throw new Error('저장한 그래프 설정이 없습니다.');await onEdit({instruction:'',document:JSON.parse(saved)});}catch(e){setError(e instanceof Error?e.message:String(e));}}}>최근 저장 설정 열기</button><button type="button" disabled={loading} onClick={()=>{if(window.confirm('처음 그래프로 되돌릴까요? 되돌리기로 취소할 수 있습니다.'))void onEdit({instruction:'',restore_initial:true});}}>처음 상태로 되돌리기</button></div></details></div></header>
    {warnings.length>0&&<details className="workspace-warnings"><summary>자료·축 범위 안내 ({warnings.length})</summary>{warnings.map((warning,i)=><p key={i}>{warning.replace(/([?&](?:apiKey|api_key|access_token)=)[^&\s)]+/gi,'$1[redacted]')}</p>)}</details>}
    <div className="workspace-panel-toggles"><button type="button" aria-expanded={dataOpen} onClick={()=>setDataOpen(!dataOpen)}>데이터 {dataOpen?'접기':'열기'}</button><button type="button" aria-expanded={propertiesOpen} onClick={()=>setPropertiesOpen(!propertiesOpen)}>속성 {propertiesOpen?'접기':'열기'}</button></div>
    <div className={`workspace-grid ${!dataOpen?'data-collapsed':''} ${!propertiesOpen?'properties-collapsed':''}`}>
    {dataOpen&&<aside className="workspace-left"><WorkspaceData series={series} hidden={state.hidden_series as string[]||[]} onEdit={editWithDraft} disabled={loading||busy} onSelect={label=>setSelection({kind:'series',label})}/></aside>}
    <section className="workspace-center" aria-label="중앙 그래프"><div className="workspace-graph-status" role="status">{loading||busy?'변경 내용 적용 중…':`현재 그래프 · 편집 ${Number((revision as {editVersion?:number}).editVersion||0)}회`}<span>선을 클릭하면 해당 데이터의 속성을 편집합니다</span></div><div className="sketch-stage" ref={stage}>
      {children}
      <svg ref={overlay} className={`sketch-overlay ${enabled?"drawing":""}`} viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="그래프 수정 표시 영역"
        onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={()=>{if(transform.current){const original=transform.current.mark;setMarks(current=>current.map(m=>m.id===original.id?original:m));transform.current=null;}active.current=null;setDraft(null);}}>
        <defs><marker id="sketch-arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#d62c43"/></marker></defs>
        {marks.map(mark=><Mark key={mark.id} mark={mark}/>)}{draft&&<Mark mark={draft}/>}
        {enabled&&selectedMark&&marks.filter(m=>m.id===selectedMark).map(mark=>{
          const b=markBounds(mark);
          return <g key={`handles-${mark.id}`} data-mark-id={mark.id} className="sketch-selection" stroke="#4568ff" fill="white" style={{pointerEvents:'auto'}}>
            <rect x={b.left*1000-4} y={b.top*1000-4} width={(b.right-b.left)*1000+8} height={(b.bottom-b.top)*1000+8} fill="none" strokeDasharray="8 5" pointerEvents="none"/>
            {(['nw','ne','sw','se'] as Corner[]).map(corner=><rect key={corner} data-corner={corner} aria-label={`크기 조절 ${corner}`} x={(corner.includes('w')?b.left:b.right)*1000-16} y={(corner.includes('n')?b.top:b.bottom)*1000-16} width="32" height="32" style={{cursor:corner==='nw'||corner==='se'?'nwse-resize':'nesw-resize'}}/>)}
          </g>;
        })}
      </svg>
    </div></section>
    {propertiesOpen&&<aside className="workspace-right"><WorkspaceProperties series={series} state={state} selection={selection} onSelect={setSelection} onEdit={editWithDraft} disabled={loading||busy}/><details><summary>고급 차트 · 인쇄 · 출처</summary><ReportPanel series={series} sessionId={sessionId} revision={revision} disabled={loading||busy} onEdit={editWithDraft}/></details><details><summary>그림판 · 보고서 주석 · 편집 도움말</summary>{controls}</details></aside>}
    </div>
    {error&&<p role="alert" className="workspace-error">{error}</p>}
    <Sujeongi inline revision={revision} sessionId={sessionId} loading={loading||busy} markCount={marks.length} model={model} onEdit={apply} canSubmitMarks={marks.some(m=>m.text.trim())||!!(model?.supportsImages&&marks.length)} markInstructions={marks.map(m=>m.text.trim()).filter(Boolean).join(" / ")}>{null}</Sujeongi>
  </div>;
}
