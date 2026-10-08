import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import {clampPosition, initialPosition, isDrag} from "./sujeongiPosition.mjs";
import "./Sujeongi.css";
import {colorRequests, selectedColorInstruction,colorPreview} from "./colorRequests";
import type {ColorRequest} from "./colorRequests";

function SujeongiAvatar({busy=false, floating=false}: {busy?:boolean;floating?:boolean}) {
  return <span className={`sujeongi-avatar ${floating?"floating":""}`} aria-hidden="true"><img className="sujeongi-animation" src={`/sujeongi/sujeongi-${busy?"working":"all-actions"}.gif`} alt="" draggable={false}/><img className="sujeongi-still" src="/sujeongi/guide.png" alt="" draggable={false}/></span>;
}

type Props = {
  sessionId: string;
  revision: object;
  loading: boolean;
  markCount: number;
  model?: {model:string;supportsImages:boolean};
  children: ReactNode;
  onEdit: (instruction: string, conversation: Array<{role:"user"|"assistant";text:string}>) => Promise<boolean>;
  canSubmitMarks: boolean;
  markInstructions: string;
};

type Message = {role:"user"|"assistant";text:string};
function savedConversation(sessionId:string): Message[] {
  try {
    const value=JSON.parse(sessionStorage.getItem(`statbridge.sujeongi.chat.${sessionId}`)||"[]");
    return Array.isArray(value)?value.filter((m)=>m&&(m.role==="user"||m.role==="assistant")&&typeof m.text==="string"):[];
  } catch { return []; }
}

export function Sujeongi({sessionId,revision,loading,markCount,model,onEdit,canSubmitMarks,markInstructions,children}: Props) {
  const [open,setOpen]=useState(false);
  useEffect(()=>{setOpen(false);},[revision]);
  const [draft,setDraft]=useState("");
  const [toolsOpen,setToolsOpen]=useState(true);
  const [pendingColors,setPendingColors]=useState<{instruction:string;requests:ColorRequest[]}|null>(null);
  const [conversation,setConversation]=useState(()=>({sessionId,messages:savedConversation(sessionId)}));
  const messages=conversation.sessionId===sessionId?conversation.messages:[];
  useEffect(()=>{
    if(conversation.sessionId!==sessionId)return;
    try {sessionStorage.setItem(`statbridge.sujeongi.chat.${sessionId}`,JSON.stringify(conversation.messages));} catch {/* Reopening still retains in-memory history. */}
  },[conversation,sessionId]);
  const [sending,setSending]=useState(false);
  const inFlight=useRef(false);
  const currentSession=useRef(sessionId);
  const log=useRef<HTMLDivElement>(null);
  const previousMarkCount=useRef(markCount);
  const viewport=()=>({width:window.innerWidth,height:window.innerHeight});
  const [position,setPosition]=useState(()=>{
    let stored;
    try{stored=JSON.parse(localStorage.getItem("statbridge.sujeongi.position")||"null");}catch{/* Storage may be disabled. */}
    return initialPosition(viewport(),stored);
  });

  const drag=useRef<{id:number;startX:number;startY:number;origin:{x:number;y:number};moved:boolean}|null>(null);
  const skipClick=useRef(false);
  const [dragging,setDragging]=useState(false);
  useEffect(()=>{
    const resize=()=>{const next=viewport();setPosition(value=>clampPosition(value,next));};
    window.addEventListener("resize",resize);
    return ()=>window.removeEventListener("resize",resize);
  },[]);
  useEffect(()=>{try{localStorage.setItem("statbridge.sujeongi.position",JSON.stringify(position));}catch{/* Optional preference only. */}},[position]);
  useEffect(()=>{
    currentSession.current=sessionId;
    setDraft("");setPendingColors(null);setConversation({sessionId,messages:savedConversation(sessionId)});setOpen(false);
  },[sessionId]);
  useEffect(()=>{if(log.current)log.current.scrollTop=log.current.scrollHeight;},[messages,open]);
  useEffect(()=>{
    if(markCount>previousMarkCount.current)setOpen(true);
    previousMarkCount.current=markCount;
  },[markCount]);
  const append=(role:"user"|"assistant",text:string)=>setConversation(current=>({sessionId,messages:[...(current.sessionId===sessionId?current.messages:savedConversation(sessionId)),{role,text}]}));
  const execute=async(instruction:string, recorded=false)=>{
    if((!instruction&&!canSubmitMarks)||loading||inFlight.current)return;
    inFlight.current=true;setSending(true);
    const startedSession=sessionId;
    if(!recorded)append("user",instruction||markInstructions||"그래프에 표시한 부분을 수정해줘");
    try{
      const success=await onEdit(instruction,messages);
      if(currentSession.current!==startedSession)return;
      if(success){setDraft("");setPendingColors(null);append("assistant","요청한 그래프 수정을 적용했어요. 이어서 수정할 수 있습니다.");setOpen(false);}
      else append("assistant","수정을 적용하지 못했어요. 사이드바의 오류 안내를 확인해 주세요. 입력한 요청과 기존 그래프는 유지했어요.");
    }catch(error){
      if(currentSession.current===startedSession)append("assistant",error instanceof Error?error.message:"수정에 실패했어요. 기존 그래프는 유지됩니다.");
    }finally{inFlight.current=false;setSending(false);}
  };
  const submit=async(event:FormEvent)=>{
    event.preventDefault();
    if(loading||inFlight.current||pendingColors)return;
    const instruction=draft.trim();
    if(!instruction&&!canSubmitMarks)return;
    const requests=colorRequests([instruction,markInstructions].filter(Boolean).join('\n'));
    if(requests.length){
      append('user',instruction||markInstructions);
      append('assistant','어떤 색으로 수정할까요? 대상별 RGB 색상을 골라 주세요. 다른 변경 내용도 함께 적용합니다.');
      setToolsOpen(false);setPendingColors({instruction,requests});return;
    }
    await execute(instruction);
  };
  const busy=loading||sending;
  return <>
    {open&&<section className="sujeongi-panel"  aria-label="수정이 그래프 수정 채팅">
      <header><SujeongiAvatar busy={busy}/><div><strong>그래프를 어떻게 수정할까요?</strong><small>원하는 변경을 편하게 말해 주세요</small></div><button type="button" aria-label="수정이 닫기" onClick={()=>setOpen(false)}>×</button></header>
      <div className="sujeongi-editor"><button className="sujeongi-editor-toggle" type="button" aria-expanded={toolsOpen} aria-controls="sujeongi-edit-controls" onClick={()=>setToolsOpen(value=>!value)}>그림판 편집 <span>{toolsOpen?"접기 ▴":"펼치기 ▾"}</span></button><div id="sujeongi-edit-controls" className="sujeongi-edit-controls" hidden={!toolsOpen}>{children}</div></div>
      <div className="sujeongi-body">
      <div ref={log} className="sujeongi-messages" role="log" aria-live="polite">
        <p className="assistant">원하는 변경을 한 번에 적어 주세요. 부분 수정은 날짜나 분기를 적거나 그래프에 표시해 주세요.</p>
        {messages.map((message,index)=><p key={index} className={message.role}>{message.text}</p>)}
      </div>
      </div>
      {pendingColors&&<section className="sujeongi-color-picker" aria-label="수정 색상 선택"><strong>어떤 색으로 수정할까요?</strong><p>색상표에서 선택하거나 RGB HEX 값을 입력하세요.</p><div className="sujeongi-color-options">{pendingColors.requests.map((request,index)=><div className="sujeongi-color-row" key={request.target}><label>{request.target}<input type="color" aria-label={`${request.target} RGB 색상`} value={request.color} onChange={e=>setPendingColors(current=>current?{...current,requests:current.requests.map((r,i)=>i===index?{...r,color:e.target.value}:r)}:null)}/></label><input aria-label={`${request.target} HEX 값`} value={request.color} maxLength={7} onChange={e=>setPendingColors(current=>current?{...current,requests:current.requests.map((r,i)=>i===index?{...r,color:e.target.value}:r)}:null)}/><label className="sujeongi-opacity">투명도 {Math.round((1-request.opacity)*100)}%<input type="range" min={0} max={100} step={1} aria-label={`${request.target} 투명도`} value={Math.round((1-request.opacity)*100)} onChange={e=>setPendingColors(current=>current?{...current,requests:current.requests.map((r,i)=>i===index?{...r,opacity:1-Number(e.target.value)/100}:r)}:null)}/></label><div className="sujeongi-color-preview" aria-label={`${request.target} 색과 투명도 미리보기`}><span style={{background:colorPreview(request.color,request.opacity)}}/></div><div className="sujeongi-swatches">{['#ef4444','#f97316','#eab308','#22c55e','#3b82f6','#8b5cf6','#111827'].map(color=><button type="button" key={color} aria-label={`${request.target} ${color}`} style={{background:color}} aria-pressed={request.color===color} onClick={()=>setPendingColors(current=>current?{...current,requests:current.requests.map((r,i)=>i===index?{...r,color}:r)}:null)}/>)}</div></div>)}</div><div className="sujeongi-color-actions"><button type="button" disabled={busy} onClick={()=>setPendingColors(null)}>요청 다시 작성</button><button type="button" disabled={busy||pendingColors.requests.some(r=>!/^#[\da-f]{6}$/i.test(r.color))} onClick={()=>{const instruction=selectedColorInstruction(pendingColors.instruction,pendingColors.requests);append('user',pendingColors.requests.map(r=>`${r.target}: ${r.color}, 투명도 ${Math.round((1-r.opacity)*100)}%`).join(', '));void execute(instruction,true);}}>선택한 색으로 적용</button></div></section>}
      <details className="sujeongi-symbols" hidden={!!pendingColors}><summary>그래프에 넣을 수 있는 기호</summary><p>기호를 선택하면 요청 예시가 입력됩니다. 위치와 색을 함께 적어 주세요.</p><div className="sujeongi-symbol-grid">{[['→','오른쪽 화살표'],['↗','상승 화살표'],['↘','하락 화살표'],['↔','양쪽 화살표'],['★','별'],['●','원'],['■','사각형'],['▲','삼각형'],['✓','체크'],['!','느낌표'],['♥','하트'],['◆','다이아몬드']].map(([symbol,name])=><button key={symbol} type="button" disabled={busy||!!pendingColors} aria-label={`${name} 기호 요청 예시`} onClick={event=>{setDraft(`그래프 가운데에 ${symbol} ${name} 기호를 크게 넣어줘`);event.currentTarget.closest("details")?.removeAttribute("open");}}><b aria-hidden="true">{symbol}</b>{name}</button>)}</div></details>
      <form className="sujeongi-composer" onSubmit={submit}><textarea rows={2} aria-label="수정이에게 수정 요청" value={draft} maxLength={1000} onChange={event=>setDraft(event.target.value)} disabled={busy||!!pendingColors} placeholder="예: 막대 그래프로 변경해줘"/><button type="submit" disabled={busy||!!pendingColors||(!draft.trim()&&!canSubmitMarks)}>{busy?"수정 중…":"전송"}</button></form>
    </section>}
    <button type="button" className={`sujeongi-fab ${dragging?"dragging":""}`} style={{left:position.x,top:position.y}}
      aria-label="그래프 수정 채팅 열기. 캐릭터를 끌어서 이동할 수 있습니다" aria-expanded={open} title="클릭하면 수정 채팅 · 끌어서 위치 이동"
      onPointerDown={event=>{
        if(event.button!==0||drag.current)return;
        skipClick.current=false;
        drag.current={id:event.pointerId,startX:event.clientX,startY:event.clientY,origin:position,moved:false};
        event.currentTarget.setPointerCapture(event.pointerId);
      }}
      onPointerMove={event=>{
        const current=drag.current;if(!current||current.id!==event.pointerId)return;
        const dx=event.clientX-current.startX,dy=event.clientY-current.startY;
        if(!current.moved&&!isDrag(dx,dy))return;
        current.moved=true;skipClick.current=true;setDragging(true);
        setPosition(clampPosition({x:current.origin.x+dx,y:current.origin.y+dy},viewport()));
      }}
      onPointerUp={event=>{
        if(drag.current?.id!==event.pointerId)return;
        skipClick.current=drag.current.moved;drag.current=null;setDragging(false);
        if(event.currentTarget.hasPointerCapture(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);
      }}
      onPointerCancel={()=>{drag.current=null;skipClick.current=true;setDragging(false);}}
      onLostPointerCapture={()=>{drag.current=null;setDragging(false);}}
      onKeyDown={event=>{
        const offsets:Record<string,{x:number;y:number}>={ArrowLeft:{x:-20,y:0},ArrowRight:{x:20,y:0},ArrowUp:{x:0,y:-20},ArrowDown:{x:0,y:20}};
        const offset=offsets[event.key];if(!offset)return;
        event.preventDefault();setPosition(value=>clampPosition({x:value.x+offset.x,y:value.y+offset.y},viewport()));
      }}
      onClick={event=>{if(skipClick.current&&event.detail!==0){skipClick.current=false;return;}skipClick.current=false;setOpen(value=>!value);}}>
      <SujeongiAvatar busy={busy} floating/>
    </button>
  </>;
}
