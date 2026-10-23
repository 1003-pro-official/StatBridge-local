import {readableEditText} from './editText';
import {appendChat,readChat} from './graphChat';
import {readReference} from './referenceFiles';
import type {ChartReference} from './api/types';
import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import {clampPosition, initialPosition, isDrag} from "./sujeongiPosition.mjs";
import "./Sujeongi.css";
import {colorRequests, requiresColorChoice, selectedColorInstruction,colorPreview} from "./colorRequests";
import type {ColorRequest} from "./colorRequests";

function SujeongiAvatar({busy=false, floating=false}: {busy?:boolean;floating?:boolean}) {
  return <span className={`sujeongi-avatar ${floating?"floating":""}`} aria-hidden="true"><img className="sujeongi-animation" src={`/sujeongi/sujeongi-${busy?"working":"all-actions"}.gif`} alt="" draggable={false}/><img className="sujeongi-still" src="/sujeongi/guide.png" alt="" draggable={false}/></span>;
}

type Props = {
  tableMode?:boolean;
  targets?:string[];
  inline?: boolean;
  sessionId: string;
  revision: object;
  loading: boolean;
  markCount: number;
  children: ReactNode;
  onEdit: (instruction: string, conversation: Array<{role:"user"|"assistant";text:string}>,references?:ChartReference[]) => Promise<boolean>;
  canSubmitMarks: boolean;
  markInstructions: string;
};

type Message = {role:"user"|"assistant";text:string};
function savedConversation(sessionId:string): Message[] {return readChat(sessionId);}

export function Sujeongi({sessionId,revision,loading,markCount,onEdit,canSubmitMarks,markInstructions,children,inline=false,targets=[],tableMode=false}: Props) {
  const [open,setOpen]=useState(false);
  useEffect(()=>{setOpen(false);},[revision]);
  const [draft,setDraft]=useState("");
  const [references,setReferences]=useState<ChartReference[]>([]),[fileError,setFileError]=useState('');
  const [recovery,setRecovery]=useState('');
  const [recoverTarget,setRecoverTarget]=useState(''),[extraInfo,setExtraInfo]=useState('');
  const attach=async(files:FileList|null)=>{if(!files)return;setFileError('');try{if(references.length+files.length>3)throw new Error('참고 파일은 최대 3개입니다.');const next=await Promise.all(Array.from(files).map(readReference));setReferences(current=>[...current,...next]);}catch(e){setFileError(e instanceof Error?e.message:String(e));}};
  const [toolsOpen,setToolsOpen]=useState(true);
  const [pendingColors,setPendingColors]=useState<{instruction:string;requests:ColorRequest[]}|null>(null);
  const colorTouched=useRef(new Set<string>()),colorAttempt=useRef('');
  const changeColors=(update:(value:typeof pendingColors)=>typeof pendingColors)=>setPendingColors(current=>{const next=update(current);if(current&&next)next.requests.forEach((r,i)=>{if(JSON.stringify(r)!==JSON.stringify(current.requests[i]))colorTouched.current.add(r.target);});return next;});
  const [conversation,setConversation]=useState(()=>({sessionId,messages:savedConversation(sessionId)}));
  const messages=conversation.sessionId===sessionId?conversation.messages:[];
  useEffect(()=>{
    const refresh=(event:Event)=>{if((event as CustomEvent<string>).detail===sessionId)setConversation({sessionId,messages:readChat(sessionId)});};
    window.addEventListener('statbridge:chat-updated',refresh);
    return()=>window.removeEventListener('statbridge:chat-updated',refresh);
  },[sessionId]);
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
    setDraft("");setReferences([]);setRecovery("");setPendingColors(null);setConversation({sessionId,messages:savedConversation(sessionId)});setOpen(false);
  },[sessionId]);
  useEffect(()=>{if(log.current)log.current.scrollTop=log.current.scrollHeight;},[messages,open]);
  useEffect(()=>{
    if(markCount>previousMarkCount.current)setOpen(true);
    previousMarkCount.current=markCount;
  },[markCount]);
  const append=(role:"user"|"assistant",text:string)=>{appendChat(sessionId,{role,text});setConversation({sessionId,messages:readChat(sessionId)});};
  const execute=async(instruction:string, recorded=false)=>{
    if((!instruction&&!canSubmitMarks&&!references.length)||loading||inFlight.current)return;
    inFlight.current=true;setSending(true);setRecovery("");
    const startedSession=sessionId;
    if(!recorded)append("user",instruction||markInstructions||"그래프에 표시한 부분을 수정해줘");
    try{
      const success=await onEdit(instruction,readChat(sessionId).slice(-40).map(({role,text})=>({role,text:text.slice(0,2000)})),references);
      if(currentSession.current!==startedSession)return;
      if(success){setDraft("");setReferences([]);setPendingColors(null);append("assistant",tableMode?"요청한 표 수정을 적용했습니다. 이어서 수정하실 수 있습니다.":"요청한 그래프 수정을 적용했어요. 이어서 수정할 수 있습니다.");setOpen(false);}
      else append("assistant","수정을 적용하지 못했어요. 화면의 오류 안내를 확인해 주세요. 입력한 요청과 기존 그래프는 유지했어요.");
    }catch(error){
      if(currentSession.current===startedSession){const message=error instanceof Error?error.message:"수정에 필요한 내용을 알려 주세요. 기존 그래프는 유지됩니다.";append("assistant",message);setRecovery(message);}
    }finally{inFlight.current=false;setSending(false);}
  };
  useEffect(()=>{
    if(!pendingColors||loading||sending||pendingColors.requests.some(r=>!/^#[\da-f]{6}$/i.test(r.color)||!colorTouched.current.has(r.target)))return;
    const token=JSON.stringify(pendingColors);if(colorAttempt.current===token)return;
    const timer=setTimeout(()=>{colorAttempt.current=token;const instruction=selectedColorInstruction(pendingColors.instruction,pendingColors.requests);void execute(instruction);},350);
    return()=>clearTimeout(timer);
  },[pendingColors,loading,sending]);
  const submit=async(event:FormEvent)=>{
    event.preventDefault();
    if(loading||inFlight.current||pendingColors)return;
    const instruction=draft.trim();
    if(!instruction&&!canSubmitMarks&&!references.length)return;
    const requests=colorRequests([instruction,markInstructions].filter(Boolean).join('\n'));
    if(!tableMode&&requests.length&&!references.length&&requiresColorChoice([instruction,markInstructions].filter(Boolean).join('\n'))){
      append('user',instruction||markInstructions);
      append('assistant','어떤 색으로 수정할까요? 대상별 RGB 색상을 골라 주세요. 다른 변경 내용도 함께 적용합니다.');
      setToolsOpen(false);colorTouched.current.clear();colorAttempt.current='';setPendingColors({instruction,requests});return;
    }
    // Explicit colors already belong to their original clauses/marks. Collapsing
    // them into a synthetic global "차트" choice overrides independent targets.
    // A selected-color override is emitted only by the actual picker above.
    await execute(instruction);
  };
  const busy=loading||sending;
  return <>
    {(open||inline)&&<section className={`sujeongi-panel ${inline?'workspace-natural':''}`} aria-label={tableMode?"자연어 표 편집":"자연어 그래프 편집"}>
      <header>{!inline&&<SujeongiAvatar busy={busy}/>}<div><strong>{tableMode?"표를 어떻게 수정할까요?":"그래프를 어떻게 수정할까요?"}</strong><small>{tableMode?"배치·서식·참고 표 파일로 수정합니다":"대화 맥락과 그래프 편집 기록을 이어갑니다"}</small></div>{!inline&&<button type="button" aria-label="수정이 닫기" onClick={()=>setOpen(false)}>×</button>}</header>

      {!inline&&<div className="sujeongi-editor"><button className="sujeongi-editor-toggle" type="button" aria-expanded={toolsOpen} aria-controls="sujeongi-edit-controls" onClick={()=>setToolsOpen(value=>!value)}>그림판 편집 <span>{toolsOpen?"접기 ▴":"펼치기 ▾"}</span></button><div id="sujeongi-edit-controls" className="sujeongi-edit-controls" hidden={!toolsOpen}>{children}</div></div>}
      <div className="sujeongi-body">
      <div ref={log} className="sujeongi-messages" role="log" aria-label={tableMode?"표 대화 및 편집 기록":"그래프 대화 및 편집 기록"} aria-live="polite">
        <p className="assistant">원하는 변경을 말씀해 주세요. 왼쪽에서 직접 바꾼 설정도 여기에 기록됩니다.</p>
        {messages.map((message,index)=><article key={index} className={`chat-message ${message.role} ${(message as {kind?:string}).kind||''}`}><small>{(message as {kind?:string}).kind==='edit'?(tableMode?'표 편집 기록':'그래프 편집 기록'):message.role==='user'?'나':'StatBridge'}</small><p>{message.role==='assistant'&&(message as {kind?:string}).kind==='edit'?readableEditText(message.text):message.text}</p></article>)}
        {busy&&<p className="assistant" role="status">변경 내용을 확인하고 있습니다…</p>}
      </div>
      </div>
      {pendingColors&&<section className="sujeongi-color-picker" aria-label="수정 색상 선택"><strong>어떤 색으로 수정할까요?</strong><p>색상표에서 선택하거나 RGB HEX 값을 입력하세요.</p><div className="sujeongi-color-options">{pendingColors.requests.map((request,index)=><div className="sujeongi-color-row" key={request.target}><label>{request.target}<input type="color" aria-label={`${request.target} RGB 색상`} value={request.color} onChange={e=>changeColors(current=>current?{...current,requests:current.requests.map((r,i)=>i===index?{...r,color:e.target.value}:r)}:null)}/></label><input aria-label={`${request.target} HEX 값`} value={request.color} maxLength={7} onChange={e=>changeColors(current=>current?{...current,requests:current.requests.map((r,i)=>i===index?{...r,color:e.target.value}:r)}:null)}/><label className="sujeongi-opacity">투명도 {Math.round((1-request.opacity)*100)}%<input type="range" min={0} max={100} step={1} aria-label={`${request.target} 투명도`} value={Math.round((1-request.opacity)*100)} onChange={e=>changeColors(current=>current?{...current,requests:current.requests.map((r,i)=>i===index?{...r,opacity:1-Number(e.target.value)/100}:r)}:null)}/></label><div className="sujeongi-color-preview" aria-label={`${request.target} 색과 투명도 미리보기`}><span style={{background:colorPreview(request.color,request.opacity)}}/></div><div className="sujeongi-swatches">{['#ef4444','#f97316','#eab308','#22c55e','#3b82f6','#8b5cf6','#111827'].map(color=><button type="button" key={color} aria-label={`${request.target} ${color}`} style={{background:color}} aria-pressed={request.color===color} onClick={()=>changeColors(current=>current?{...current,requests:current.requests.map((r,i)=>i===index?{...r,color}:r)}:null)}/>)}</div></div>)}</div><div className="sujeongi-color-actions"><button type="button" disabled={busy} onClick={()=>setPendingColors(null)}>요청 다시 작성</button><small>대상별 색상을 선택하면 자동 반영됩니다.</small></div></section>}
      {tableMode&&recovery&&<p role="alert" className="agent-recovery">{recovery}</p>}
      {recovery&&!tableMode&&<section className="agent-recovery" aria-label="수정 역질문"><strong>어떤 정보를 보완해 수정할까요?</strong><p>{recovery}</p><label>보완할 수정 요소<select aria-label="보완할 수정 요소" value={recoverTarget} onChange={e=>setRecoverTarget(e.target.value)}><option value="">요소를 선택하세요</option>{['제목','범례','가로축','세로축','기간 강조',...targets].map(target=><option key={target}>{target}</option>)}</select></label><label>추가 설명<input aria-label="수정 보완 설명" value={extraInfo} maxLength={500} onChange={e=>setExtraInfo(e.target.value)} placeholder="원하는 제목·색상·시점 등을 적어 주세요"/></label><button disabled={busy||!recoverTarget||!extraInfo.trim()} onClick={()=>{const combined=[draft,`수정 대상: ${recoverTarget}`,`추가 설명: ${extraInfo.trim()}`].join('\n');if(combined.length>1000){setRecovery('수정 요청과 추가 설명을 합쳐 1000자 이내로 줄여 주세요.');return;}setDraft(combined);void execute(combined);}}>선택과 설명으로 이어서 수정</button><button disabled={busy} onClick={()=>void execute(draft.trim(),true)}>같은 요청 다시 시도</button><button onClick={()=>document.querySelector<HTMLTextAreaElement>('.sujeongi-composer textarea')?.focus()}>변경 내용 보완</button></section>}
      <details className="reference-upload"><summary>{tableMode?'참고 표 파일 첨부':'참고 그래프 첨부'}</summary><label>{tableMode?'참고 표 업로드':'참고 그래프 업로드'}<input aria-label={tableMode?'참고 표 업로드':'참고 그래프 업로드'} type="file" accept="image/png,image/jpeg,image/webp,application/pdf" multiple disabled={busy} onChange={e=>{void attach(e.target.files);e.target.value='';}}/></label><small>PNG·JPG·WebP·PDF · 최대 3개, 각각 4MB · PDF 5쪽 이하. 전송하면 참고 파일을 OpenAI로 보내 형식을 분석합니다.</small>{references.map((file,index)=><div key={index}>{file.mime.startsWith('image/')&&<img src={file.data_url} alt={`${file.name} 참고 미리보기`}/>}<span>{file.name}</span><button type="button" disabled={busy} onClick={()=>setReferences(current=>current.filter((_,i)=>i!==index))}>첨부 제거</button></div>)}{fileError&&<p role="alert">{fileError}</p>}</details>
      <form className="sujeongi-composer" onSubmit={submit}><textarea rows={2} aria-label={tableMode?"자연어 표 수정":inline?"자연어 그래프 수정":"수정이에게 수정 요청"} value={draft} maxLength={1000} onChange={event=>setDraft(event.target.value)} disabled={busy||!!pendingColors} placeholder={tableMode?"예: 소수점 한 자리로 바꿔줘":"예: 막대 그래프로 변경해줘"}/><button type="submit" disabled={busy||!!pendingColors||(!draft.trim()&&!canSubmitMarks&&!references.length)}>{busy?"수정 중…":"전송"}</button></form>
    </section>}
    {!inline&&<button type="button" className={`sujeongi-fab ${dragging?"dragging":""}`} style={{left:position.x,top:position.y}}
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
    </button>}
  </>;
}
