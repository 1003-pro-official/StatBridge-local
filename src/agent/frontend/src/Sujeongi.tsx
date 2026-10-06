import { FormEvent, useEffect, useRef, useState } from "react";
import type { SketchMark } from "./api/types";
import {clampPosition, initialPosition, isDrag, panelPosition} from "./sujeongiPosition.mjs";
import "./Sujeongi.css";

function SujeongiAvatar({busy=false, floating=false}: {busy?:boolean;floating?:boolean}) {
  return <span className={`sujeongi-avatar ${floating?"floating":""}`} aria-hidden="true"><img className="sujeongi-animation" src={`/sujeongi/sujeongi-${busy?"working":"all-actions"}.gif`} alt="" draggable={false}/><img className="sujeongi-still" src="/sujeongi/guide.png" alt="" draggable={false}/></span>;
}


type Props = {
  sessionId: string;
  loading: boolean;
  markCount: number;
  model?: {model:string;supportsImages:boolean};
  onEdit: (instruction: string) => Promise<boolean>;
  onDraw: (tool: SketchMark["tool"]) => void;
};

export function Sujeongi({sessionId,loading,markCount,model,onEdit,onDraw}: Props) {
  const [open,setOpen]=useState(false);
  const [draft,setDraft]=useState("");
  const [messages,setMessages]=useState<Array<{role:"user"|"assistant";text:string}>>([]);
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
  const [screen,setScreen]=useState(viewport);
  const drag=useRef<{id:number;startX:number;startY:number;origin:{x:number;y:number};moved:boolean}|null>(null);
  const skipClick=useRef(false);
  const [dragging,setDragging]=useState(false);
  useEffect(()=>{
    const resize=()=>{const next=viewport();setScreen(next);setPosition(value=>clampPosition(value,next));};
    window.addEventListener("resize",resize);
    return ()=>window.removeEventListener("resize",resize);
  },[]);
  useEffect(()=>{try{localStorage.setItem("statbridge.sujeongi.position",JSON.stringify(position));}catch{/* Optional preference only. */}},[position]);
  useEffect(()=>{
    currentSession.current=sessionId;
    setDraft("");setMessages([]);setOpen(false);
  },[sessionId]);
  useEffect(()=>{if(log.current)log.current.scrollTop=log.current.scrollHeight;},[messages,open]);
  useEffect(()=>{
    if(markCount>previousMarkCount.current)setOpen(true);
    previousMarkCount.current=markCount;
  },[markCount]);
  const append=(role:"user"|"assistant",text:string)=>setMessages(current=>[...current,{role,text}].slice(-40));
  const submit=async(event:FormEvent)=>{
    event.preventDefault();
    const instruction=draft.trim();
    if(!instruction||loading||inFlight.current)return;
    inFlight.current=true;setSending(true);
    const startedSession=sessionId;
    append("user",instruction);
    try{
      const success=await onEdit(instruction);
      if(currentSession.current!==startedSession)return;
      if(success){setDraft("");append("assistant","요청한 그래프 수정을 적용했어요.");}
      else append("assistant","수정을 적용하지 못했어요. 화면의 오류 안내를 확인해 주세요. 입력한 요청과 기존 그래프는 유지했어요.");
    }catch(error){
      if(currentSession.current===startedSession)append("assistant",error instanceof Error?error.message:"수정에 실패했어요. 기존 그래프는 유지됩니다.");
    }finally{inFlight.current=false;setSending(false);}
  };
  const busy=loading||sending;
  return <>
    {open&&<section className="sujeongi-panel" style={panelPosition(position,screen)} aria-label="수정이 그래프 수정 채팅">
      <header><SujeongiAvatar busy={busy}/><div><strong>그래프 수정 도우미</strong><small>원하는 변경을 편하게 말해 주세요</small></div><button type="button" aria-label="수정이 닫기" onClick={()=>setOpen(false)}>×</button></header>
      <div ref={log} className="sujeongi-messages" role="log" aria-live="polite">
        <p className="assistant">원하는 변경을 적어 주세요. 부분 수정은 아래 도구로 그래프를 표시하고, 수정 대상과 실제 시점을 확인해 주세요.</p>
        {messages.map((message,index)=><p key={index} className={message.role}>{message.text}</p>)}
      </div>
      {markCount>0&&<div className="sujeongi-mark-summary">그래프에 표시한 위치 {markCount}개를 함께 전달합니다.</div>}
      <div className="sujeongi-tools">{([["rectangle","▭ 사각형"],["pen","✎ 펜"],["arrow","➜ 화살표"],["text","텍스트"]] as const).map(([tool,label])=><button key={tool} type="button" disabled={busy} onClick={()=>{onDraw(tool);setOpen(false);}}>{label}</button>)}</div>
      <form onSubmit={submit}><input aria-label="수정이에게 수정 요청" value={draft} maxLength={1000} onChange={event=>setDraft(event.target.value)} disabled={busy} placeholder="예: 막대 그래프로 변경해줘"/><button type="submit" disabled={busy||!draft.trim()}>{busy?"수정 중…":"전송"}</button></form>
      <small className="sujeongi-help">수정 요청은 기존 수정 에이전트로 전달합니다. {model?.supportsImages?`${model.model}에 텍스트와 그림 표시를 전달합니다.`:`${model?.model||"HCX-007"}은 이미지·손글씨 대신 텍스트와 확인된 표시 범위를 해석합니다.`}</small>
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
