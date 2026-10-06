import { PointerEvent, ReactNode, useEffect, useRef, useState } from "react";
import Plotly from "plotly.js-dist-min";
import type { ChartEditInput, ChartSeries, SketchMark, EditSelection } from "./api/types";
import { graphHitPoints, resolveMarkSelection } from "./chartSelection";
import { isDrawingStroke, periodLabel, sketchLabel } from "./sketchLabels";
import { markBounds,moveMark,resizeMark } from "./sketchTransform";
import type { EditableMark,Corner } from "./sketchTransform";
import { bindMarks, changeMarkTarget, elementTargets, inferMarkTarget } from "./sketchRequest";
import { Sujeongi } from "./Sujeongi";

type Props = {
  children: ReactNode;
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
    {mark.tool === "rectangle" && <rect x={Math.min(x,last.x*1000)} y={Math.min(y,last.y*1000)} width={Math.abs(x-last.x*1000)} height={Math.abs(y-last.y*1000)}/>}
    {mark.tool==="text" && mark.text && <text x={x} y={Math.max(20,y-8)} fill="#a81830" stroke="none" fontSize={mark.textSize||22}>{mark.text}</text>}
  </g>;
}

async function readImage(src: string): Promise<HTMLImageElement> {
  const image = new Image();
  await new Promise<void>((resolve,reject) => { image.onload=()=>resolve(); image.onerror=()=>reject(new Error("그래프 이미지 생성에 실패했습니다.")); image.src=src; });
  return image;
}

export default function ChartSketchEditor({ children, series, sessionId, revision, loading, onEdit, model, canUndo, canRedo }: Props) {
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
  const apply = async (requestedInstruction=instruction): Promise<boolean> => {
    if(applying.current||loading)return false;
    applying.current=true;
    setBusy(true);setError("");
    try {
      const boundMarks=bindMarks(marks,manual);
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
      const success=await onEdit({instruction:requestedInstruction.trim(),visual});
      if(success){setMarks([]);setInstruction("");setNote("");}
      return success;
    } catch(err){setError(err instanceof Error?err.message:"수정 요청을 준비하지 못했습니다.");return false;}
    finally{applying.current=false;setBusy(false);}
  };
  return <div className="sketch-editor">
    <div className="sujeongi-guide"><img src="/sujeongi/guide.png" alt="그래프 수정 도우미 캐릭터"/><div><strong>수정은 수정이에게 지시하세요</strong><p>화면의 캐릭터를 누르고 원하는 변경을 말해 주세요. 캐릭터는 끌어서 옮길 수 있어요.</p></div></div>
    <div className="sketch-toolbar">
      <button type="button" disabled={!canUndo||loading||busy} onClick={()=>void onEdit({instruction:"",action:"undo"})}>편집 취소</button>
      <button type="button" disabled={!canRedo||loading||busy} onClick={()=>void onEdit({instruction:"",action:"redo"})}>편집 다시 적용</button>
      <button type="button" aria-pressed={enabled} disabled={loading||busy} onClick={()=>setEnabled(!enabled)}>{enabled?"그림 편집 종료":"그림판 편집 켜기"}</button>
      {enabled && <>
        <button type="button" aria-pressed={selectMode} disabled={loading||busy} onClick={()=>{setSelectMode(true);setTextAnchor(null);}}>선택·이동</button>
        {([ ["pen","펜"],["arrow","화살표"],["rectangle","사각형"],["text","텍스트"] ] as const).map(([value,label])=><button type="button" key={value} aria-pressed={!selectMode&&tool===value} disabled={loading||busy} onClick={()=>{setTool(value);setSelectMode(false);setSelectedMark(null);setTextAnchor(null);setNote("");}}>{label}</button>)}
        <button type="button" disabled={!marks.length||loading||busy} onClick={()=>setMarks(current=>current.slice(0,-1))}>표시 되돌리기</button>
        <button type="button" disabled={!marks.length||loading||busy} onClick={()=>setMarks([])}>표시 지우기</button>
      </>}
    </div>
    <div className="sketch-fields">
      <label>수정 대상<select value={target} disabled={loading||busy} onChange={e=>{setTarget(e.target.value);setStart("");setEnd("");}}>
        <option value="chart">그래프 전체 / 확인 필요</option><option value="title">제목</option><option value="legend">범례</option><option value="x_axis">가로축</option><option value="y_axis">세로축</option>
        {Array.from(new Set(series.map(s=>s.label))).map(label=><option key={label} value={label}>{label}</option>)}
      </select></label>
      <label>적용 범위<select value={scope} disabled={loading||busy||elementTargets.has(target)} onChange={e=>setScope(e.target.value as EditSelection["scope"])}><option value="segment">선분 / 관측 구간</option><option value="point">관측점 / 막대 하나</option><option value="series">계열 전체</option></select>{elementTargets.has(target)&&<small>제목·축·범례는 시점 선택 없이 수정합니다.</small>}</label>
      {chosen&&scope!=="series"&&<><label>시작 시점<select value={start} onChange={e=>setStart(e.target.value)}><option value="">그림으로 선택</option>{periods.map(p=><option key={p}>{p}</option>)}</select></label>{scope==="segment"&&<label>종료 시점<select value={end} onChange={e=>setEnd(e.target.value)}><option value="">그림으로 선택</option>{periods.map(p=><option key={p}>{p}</option>)}</select></label>}</>}
      {manual&&<span>선택: {manual.label} · {manual.scope} · {manual.start} ~ {manual.end}</span>}
      {enabled && tool!=="text" && <label>이번 표시의 수정 요청 (선택)<input value={note} maxLength={300} disabled={loading||busy||selectMode} onChange={e=>setNote(e.target.value)} placeholder={selectMode?"선택한 표시를 끌어서 이동하거나 크기를 바꾸세요":"한 번만 적용됩니다. 예: 빨간색으로"}/></label>}
    </div>
    {enabled&&!selectMode&&tool==="text"&&<div className="setup-block sketch-text-panel" role="group" aria-label="그래프 텍스트 표시 입력">
      <label>표시할 텍스트<textarea ref={textInput} value={note} maxLength={300} disabled={loading||busy} onChange={e=>setNote(e.target.value)} placeholder="그래프 위에 배치할 수정 설명을 입력하세요"/></label>
      <p>{textAnchor?"배치 위치를 선택했습니다. 텍스트 배치를 눌러 주세요.":"텍스트를 입력한 뒤 그래프에서 배치할 위치를 클릭하세요."} 최종 그래프 주석이 아닌 수정 지시용 표시입니다.</p>
      <button type="button" disabled={!textAnchor||!note.trim()||loading||busy||marks.length>=40} onClick={()=>{if(textAnchor){saveMark({id:crypto.randomUUID(),tool:"text",points:[textAnchor],text:note.trim(),target});setTextAnchor(null);setNote("");setEnabled(false);setTool("pen");}}}>텍스트 배치</button>
    </div>}
    <div className="sketch-stage" ref={stage}>
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
    </div>
    {!!marks.length&&<p className="sketch-help">표시를 클릭해 선택한 뒤 끌어서 이동하세요. 파란 모서리 조절점을 끌면 크기를 바꿀 수 있습니다. 이동 후 수정 위치는 다시 확인합니다.</p>}
    {!!marks.length && <div className="sketch-mark-summary">
      <p>표시한 위치 {marks.length}개 · 각 표시의 대상을 확인하고 설명 수정에서 원하는 내용을 적어 주세요.</p>
      <ol className="sketch-mark-list">{marks.map((mark,index)=><li key={mark.id}>
        <strong>{sketchLabel(mark.tool)}</strong>
        <label>수정할 요소<select aria-label={`표시 ${index+1}의 수정 대상`} value={mark.target||"chart"} disabled={loading||busy}
          onChange={e=>setMarks(current=>current.map(m=>m.id===mark.id?changeMarkTarget(m,e.target.value):m))}>
          <option value="chart">자동 확인 / 그래프</option><option value="title">제목</option><option value="legend">범례</option><option value="x_axis">가로축</option><option value="y_axis">세로축</option>
          {Array.from(new Set(series.map(s=>s.label))).map(label=><option key={label} value={label}>{label}</option>)}
        </select></label>
        <span> · {elementTargets.has(mark.target)?"시점 선택 없이 편집 가능":mark.selection?`${periodLabel(mark.selection.start)}${mark.selection.end&&mark.selection.end!==mark.selection.start?` ~ ${periodLabel(mark.selection.end)}`:""}${mark.selection.scope==="series"?"선 전체":""}`:"계열·시점 확인 필요"}</span>
        {mark.text&&<p>수정 요청: {mark.text}</p>}
        {!elementTargets.has(mark.target)&&<button type="button" disabled={!manual||loading||busy||(mark.target!=="chart"&&mark.target!==manual.label)} onClick={()=>setMarks(current=>current.map(m=>m.id===mark.id?{...m,selection:manual}:m))}>위에서 선택한 범위 연결</button>}
        <button type="button" disabled={loading||busy} onClick={()=>setEditingMark(editingMark===mark.id?null:mark.id)}>{editingMark===mark.id?"설명 닫기":"설명 수정"}</button>
        <button type="button" disabled={loading||busy} onClick={()=>setMarks(current=>current.filter(m=>m.id!==mark.id))}>표시 삭제</button>
        {editingMark===mark.id&&<input aria-label={`표시 ${index+1}의 수정 설명`} value={mark.text} maxLength={300} disabled={loading||busy} placeholder="예: 제목을 수출 추이로 / 가로축을 12개월 간격으로" onChange={e=>setMarks(current=>current.map(m=>m.id===mark.id?{...m,text:e.target.value}:m))}/>}
      </li>)}</ol>
    </div>}
    <details><summary>편집 가능한 항목과 예시</summary><p>구간만 빨간 점선 · 점 하나만 다이아몬드 · 막대 하나 강조 · 값 표시 · 계열 이름/순서/숨김 · 축 범위/로그/눈금/격자 · 보조축 · 좌우/격자 배치 · 글꼴/범례/여백/배경 · 기간 음영 · 기준선 · 관측점 화살표 주석 · 메모/도형 이동·색 변경·삭제 · 스타일 초기화. 실제 데이터가 없는 전망·범위는 생성하지 않습니다.</p></details>
    <Sujeongi sessionId={sessionId} loading={loading||busy} markCount={marks.length} model={model} onEdit={apply} onDraw={value=>{
      setTool(value);setEnabled(true);setSelectMode(false);setSelectedMark(null);setTextAnchor(null);setNote("");
      stage.current?.scrollIntoView({behavior:"smooth",block:"center"});
    }}/>
    <details><summary>직접 수정 입력 (고급)</summary><form className="chart-edit-form" onSubmit={e=>{e.preventDefault();void apply();}}>
      <label htmlFor="chart-edit-input">텍스트 / 그림 표시로 수정 지시</label>
      <div><input id="chart-edit-input" value={instruction} maxLength={1000} disabled={loading||busy} onChange={e=>setInstruction(e.target.value)} placeholder="예: 표시한 계열을 빨간 점선으로, 범례는 아래로 옮겨줘"/>
        <button type="submit" disabled={loading||busy||(!instruction.trim()&&!marks.some(m=>m.text.trim())&&!(model?.supportsImages&&marks.length))}>{busy||loading?"수정 중…":"수정 적용"}</button></div>
    </form></details>
    <p className="sketch-help">{model?.supportsImages?`${model.model}에 그림 표시와 수정 지시를 전달합니다.`:`현재 ${model?.model||"HCX-007"}은 이미지·손글씨를 읽지 않습니다. 대상 선택과 표시 설명을 함께 입력해 주세요.`} 표시 좌표는 통계값을 바꾸지 않으며, 수정 지시용 표시는 최종 PNG에 포함되지 않습니다.</p>
    {error&&<p role="alert" className="error-banner">{error}</p>}
  </div>;
}
