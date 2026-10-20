import {useEffect,useId,useRef,useState,type FormEvent} from 'react';
import {accountBase,apiFetch} from './accountApi';
import {EDIT_TIMEOUT_MS,withRequestDeadline} from './requestDeadline';
import './StatisticalQuestion.css';
import {startFileDownload} from './workspaceDownload';
import ReportMarkdownPreview from './ReportMarkdownPreview';

type Answer={question:string;revision:number;status:string;paragraphs:string[];requiredData:string[];limitations:string[];
 table?:{columns:string[];rows:string[][]};plannerMethod?:string;modelCalls?:number};
type Turn={id:number;question:string;answer:Answer;askedRevision:number;verifiedRevision:number;planning?:{calls:number;method:string}};
type MarkdownEntry={id:string;turnId:number;revision:number;paragraphs:string[];table?:{columns:string[];rows:string[][]};sources?:string[]};
type Conversation={markdownEntries?:MarkdownEntry[];version:number;revision:number;displayMode?:"graph"|"table";turns:Turn[]};

export default function StatisticalQuestion({sessionId,revision,displayMode="graph",disabled=false}:{sessionId?:string;revision:number;displayMode?:"graph"|"table";summary:string;disabled?:boolean}){
 const id=useId(),[question,setQuestion]=useState(''),[conversation,setConversation]=useState<Conversation>({version:0,revision:0,turns:[]});
 const [boundSession,setBoundSession]=useState(sessionId),[busy,setBusy]=useState(false),[syncing,setSyncing]=useState(false),[error,setError]=useState(''),[reload,setReload]=useState(0);
 const [preview,setPreview]=useState(false);
 const previewOpener=useRef<HTMLButtonElement>(null);
 const [draftBusy,setDraftBusy]=useState(false),[draftNote,setDraftNote]=useState('');
 const request=useRef<AbortController|null>(null),generation=useRef(0),tail=useRef<HTMLDivElement>(null);
 useEffect(()=>{
  const token=++generation.current;request.current?.abort();const controller=new AbortController();request.current=controller;
  setBusy(false);setError('');setSyncing(!!sessionId);setDraftBusy(false);setDraftNote('');
  if(boundSession!==sessionId){setPreview(false);setConversation({version:0,revision,turns:[]});setQuestion('');setBoundSession(sessionId);}
  if(sessionId)void withRequestDeadline(async signal=>{
   const response=await apiFetch(`${accountBase}/report/conversation/${encodeURIComponent(sessionId)}?display_mode=${displayMode}`,{signal});
   const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'대화를 불러오지 못했습니다.');
   if(data.revision!==revision||!Array.isArray(data.turns))throw new Error('분석이 변경되었습니다. 대화를 다시 불러와 주세요.');
   return data as Conversation;
  },'보고서 대화 재검산',controller.signal,EDIT_TIMEOUT_MS).then(data=>{if(token===generation.current)setConversation(data);}).catch(e=>{
   if(token===generation.current&&!controller.signal.aborted)setError(e instanceof Error?e.message:String(e));
  }).finally(()=>{if(token===generation.current)setSyncing(false);});
  return()=>{generation.current++;controller.abort();};
 },[sessionId,revision,displayMode,reload]);
 const submit=async(event:FormEvent)=>{
  event.preventDefault();if(!sessionId||disabled||busy||syncing||!question.trim())return;
  const token=++generation.current,controller=new AbortController();request.current?.abort();request.current=controller;
  setBusy(true);setError('');
  try{
   const data=await withRequestDeadline(async signal=>{
    const response=await apiFetch(`${accountBase}/report/question`,{method:'POST',signal,headers:{'Content-Type':'application/json'},
     body:JSON.stringify({edit_session_id:sessionId,revision,question:question.trim(),conversational:true,display_mode:displayMode,conversation_version:conversation.version})});
    const next=await response.json();if(!response.ok)throw new Error(typeof next.detail==='string'?next.detail:'질문에 답변하지 못했습니다.');
    if(next.revision!==revision||!Array.isArray(next.conversation?.turns))throw new Error('최신 분석에서 다시 질문해 주세요.');
    return next.conversation as Conversation;
   },'보고서 대화',controller.signal,EDIT_TIMEOUT_MS);
   if(token===generation.current){setConversation(data);setQuestion('');requestAnimationFrame(()=>tail.current?.scrollIntoView({behavior:'smooth',block:'nearest'}));}
  }catch(e){if(token===generation.current&&!controller.signal.aborted)setError(e instanceof Error?e.message:String(e));}
  finally{if(token===generation.current)setBusy(false);}
 };
 const addMarkdown=async(turn:Turn)=>{
  if(!sessionId)return;const token=generation.current;setDraftBusy(true);setDraftNote('');
  try{
   const response=await apiFetch(`${accountBase}/report/markdown/append`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({edit_session_id:sessionId,revision,turn_id:turn.id})});
   const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'보고서에 추가하지 못했습니다.');
   if(token!==generation.current)return;setConversation(current=>({...current,markdownEntries:data.entries}));setDraftNote(`${data.entries.length}번째 답변을 보고서에 추가했습니다.`);
  }catch(e){if(token===generation.current)setDraftNote(e instanceof Error?e.message:String(e));}finally{if(token===generation.current)setDraftBusy(false);}
 };
 const downloadMarkdown=async()=>{
  if(!sessionId)return;const token=generation.current;setDraftBusy(true);
  try{
   const response=await apiFetch(`${accountBase}/report/markdown/export`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({edit_session_id:sessionId,revision})});
   if(!response.ok){const data=await response.json();throw new Error(typeof data.detail==='string'?data.detail:'MD 파일을 만들지 못했습니다.');}
   const blob=await response.blob();if(token!==generation.current)return;const url=URL.createObjectURL(blob);startFileDownload(url,'statbridge-report.md');setTimeout(()=>URL.revokeObjectURL(url),60000);
  }catch(e){if(token===generation.current)setDraftNote(e instanceof Error?e.message:String(e));}finally{if(token===generation.current)setDraftBusy(false);}
 };
 const turns=boundSession===sessionId?conversation.turns:[];
 return <section className="statistical-question report-conversation" aria-label="보고서 작성 대화">
  <div className="report-chat-heading"><strong>현재 자료에 질문하기</strong><span>이전 질문의 맥락을 이어가요 · 최근 20개 대화</span></div>
  <p id={`${id}-help`}>원하는 설명이나 형식을 편하게 말해 주세요. “그중 가장 많이 하락한 건?”, “표로 정리해줘”처럼 이어서 질문할 수 있어요.</p>
  {syncing&&<p role="status">대화를 유지하면서 최신 그래프·표의 자료로 다시 검산하고 있어요…</p>}
  <div className="report-chat-messages" aria-label="보고서 대화 기록" aria-live="polite">
   {turns.map(turn=><article className="report-chat-turn" key={turn.id}>
    <div className="report-chat-user"><span>나</span><p>{turn.question}</p></div>
    <div className="report-chat-assistant"><strong>StatBridge</strong>
     <small>{turn.verifiedRevision===revision&&!syncing&&conversation.displayMode===displayMode?`최신 자료 검산 완료 · 편집 ${revision}회`:'최신 자료 재검산 필요'}{turn.askedRevision!==revision?' · 그래프 변경 반영':''}{` · 질문 해석 GPT ${turn.planning?.calls??0}회`}</small>
     {turn.verifiedRevision!==revision||syncing||conversation.displayMode!==displayMode?<p>이전 답변의 수치를 최신 자료로 다시 계산하고 있어요. 완료 전에는 이전 수치를 표시하지 않습니다.</p>:<>
      {turn.answer.paragraphs.map((text,i)=><p key={i}>{text}</p>)}
      {turn.answer.table&&<div className="report-chat-table"><table><thead><tr>{turn.answer.table.columns.map((c,i)=><th key={i}>{c}</th>)}</tr></thead><tbody>{turn.answer.table.rows.map((row,i)=><tr key={i}>{row.map((v,j)=><td key={j}>{v}</td>)}</tr>)}</tbody></table></div>}
      {turn.answer.limitations.map((text,i)=><p className="report-chat-note" key={i}>{text}</p>)}
      <button className="report-md-add" type="button" disabled={draftBusy||busy||disabled||!['answered','partially_answered'].includes(turn.answer.status)||(conversation.markdownEntries||[]).some(e=>e.turnId===turn.id&&e.revision===revision)} onClick={()=>void addMarkdown(turn)}>{(conversation.markdownEntries||[]).some(e=>e.turnId===turn.id&&e.revision===revision)?'MD에 추가됨':'MD에 추가'}</button>
     </>}
    </div>
   </article>)}
   <div ref={tail}/>
  </div>
  <div className="report-md-collection"><strong>모은 답변 {(conversation.markdownEntries||[]).length}개</strong><span>추가 버튼을 누른 순서대로 저장합니다. 추가 당시 검산 결과를 보존합니다.</span><div className="report-md-actions"><button ref={previewOpener} type="button" aria-haspopup="dialog" aria-expanded={preview} disabled={draftBusy||!(conversation.markdownEntries||[]).length} onClick={()=>setPreview(true)}>답변 MD 미리보기</button><button type="button" disabled={draftBusy||!(conversation.markdownEntries||[]).length} onClick={()=>void downloadMarkdown()}>답변 MD 내려받기</button></div>{draftNote&&<p role="status">{draftNote}</p>}</div>
  {preview&&<ReportMarkdownPreview key={sessionId} entries={conversation.markdownEntries||[]} onClose={()=>{setPreview(false);previewOpener.current?.focus({preventScroll:true});}} onDownload={()=>void downloadMarkdown()} busy={draftBusy}/>}
  <form onSubmit={event=>void submit(event)} aria-busy={busy||syncing}>
   <label className="report-chat-input-label" htmlFor={id}>보고서 질문</label>
   <div className="statistical-question-input"><textarea id={id} aria-describedby={`${id}-help`} rows={2} maxLength={1000}
    placeholder={turns.length?'이어서 질문해 보세요. 예: 그중 가장 많이 하락한 것은?':'예: 해당 그래프의 변화를 보고서처럼 설명해줘'}
    value={question} onChange={event=>setQuestion(event.target.value)} disabled={busy||syncing||disabled||!sessionId}/>
    <button type="submit" disabled={busy||syncing||disabled||!sessionId||!question.trim()}>{busy?'답변 작성 중…':'질문하기'}</button></div>
   {busy&&<p role="status">이전 대화의 대상과 비교 기준을 확인하고 최신 자료로 계산하고 있어요…</p>}
   {error&&<div role="alert"><p>{error}</p><button type="button" onClick={()=>setReload(n=>n+1)}>대화 다시 불러오기</button><span>입력한 질문과 기존 대화는 유지됩니다.</span></div>}
  </form>
 </section>;
}
