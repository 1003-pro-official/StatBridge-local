import {groupSources,resultInsights} from './resultPresentation';
import {useEffect,useRef,useState} from 'react';
import type {QueryResponse,ExecutionRun} from './api/types';
import './ExecutionEvidence.css';
const names:Record<string,string>={resolve_request:'질문·통계표 확인',await_clarification:'선택 조건 확인 대기',finish_unresolved:'조회 조건 보완',execute_statistics:'통계 원자료 조회',await_output_selection:'그래프 선택 대기',prepare_output:'출력 명세 생성',interpret_edit:'편집 요청 해석·검증',render_output:'그래프 렌더링',validate_revision:'최신 그래프 확인',apply_validated_settings:'선택한 설정 적용',undo:'이전 편집 되돌리기',redo:'편집 다시 적용',restore_initial:'처음 설정 복원',restore_document:'저장 설정 복원',restore_property:'선택 속성 복원'};
export default function ExecutionEvidence({result,open,onClose}:{result:QueryResponse;open:boolean;onClose:()=>void}){
 const sources=groupSources(result.tables);
 const logs=resultInsights(result.insights,result.outputSpec?.editChanges).logs;
 const dialog=useRef<HTMLDialogElement>(null);
 const detail=useRef<HTMLElement>(null),navigation=useRef<HTMLElement>(null);
 const fallback=result.debug?.orchestration;
 const runs:ExecutionRun[]=result.executionRuns?.length?result.executionRuns:fallback?.path?.length?[{id:'current-query',kind:'query',engine:fallback.engine||'unknown',path:fallback.path,stage:fallback.stage||'complete',changes:[]}]:[];
 const [selected,setSelected]=useState(runs.at(-1)?.id||'');
 const last=runs.at(-1)?.id;
 useEffect(()=>{if(open){setSelected(last||'');if(!dialog.current?.open)dialog.current?.showModal();}else dialog.current?.close();},[open,last]);
 useEffect(()=>{
  if(!open)return;
  const frame=requestAnimationFrame(()=>{
   detail.current?.scrollTo({top:0});
   const nav=navigation.current,button=nav?.querySelector<HTMLElement>('[aria-pressed="true"]');
   if(nav&&button){const a=nav.getBoundingClientRect(),b=button.getBoundingClientRect();nav.scrollTo({top:nav.scrollTop+b.top-a.top,left:nav.scrollLeft+b.left-a.left});}
  });
  return()=>cancelAnimationFrame(frame);
 },[open,selected]);
 const run=runs.find(r=>r.id===selected)||runs.at(-1);
 return <dialog ref={dialog} className="execution-modal" aria-label="전체 실행 근거" onCancel={event=>{event.preventDefault();onClose();}}><header><div><small>EXECUTION EVIDENCE</small><h2>분석·편집 실행 흐름</h2></div><button type="button" onClick={onClose} aria-label="실행 근거 닫기">닫기 ×</button></header><p className="execution-intro">실제 실행에서 기록된 단계와 사용한 통계를 확인합니다. 모델의 내부 추론 대신 검증 가능한 실행 경로를 표시합니다.</p><div className="execution-layout"><nav ref={navigation} aria-label="실행 기록">{runs.map((entry,index)=><button key={entry.id} type="button" aria-pressed={run?.id===entry.id} onClick={()=>setSelected(entry.id)}><strong>{index+1}. {entry.kind==='edit'?`그래프 편집 ${entry.revision??''}`:entry.kind==='output'?'그래프 생성':'통계 분석'}</strong><small>{entry.engine==='langgraph'?'LangGraph 실행':entry.engine==='direct'?'직접 설정 처리':'실행 엔진 정보 없음'}{entry.time?` · 기록 ${new Date(entry.time).toLocaleTimeString('ko-KR')}`:''}</small></button>)}</nav><section ref={detail} className="execution-detail" tabIndex={0} aria-label="선택한 실행의 상세 근거">{run?<><div className="execution-meta"><span>{run.engine==='langgraph'?'LangGraph':run.engine==='direct'?'직접 설정 처리':run.engine}</span><span>상태: {({complete:'완료',output_ready:'출력 완료',awaiting_output_selection:'그래프 선택 대기',executed:'조회 완료',resolved_request:'질문 확인 완료'} as Record<string,string>)[run.stage]||run.stage}</span>{run.revision!=null&&<span>편집 버전 {run.revision}</span>}</div>{run.engine==='direct'&&<p>이 작업은 검증된 설정을 직접 적용한 처리이며 LangGraph 노드를 실행하지 않았습니다.</p>}<ol className="execution-flow" aria-label="실행 단계 순서">{run.path.map((node,index)=><li key={index}><span>{index+1}</span><div><strong>{names[node]||node}</strong><code>{node}</code></div>{index<run.path.length-1&&<b aria-hidden="true">↓</b>}</li>)}</ol>{!run.path.length&&<p>이 실행의 노드 경로는 기록되지 않았습니다.</p>}{run.changes?.length>0&&<section><h3>적용 결과</h3><ul>{run.changes.map((change,index)=><li key={index}>{change}</li>)}</ul></section>}</>:<p>이 저장 그래프에는 이전 버전의 실행 기록이 없습니다. 새 분석 또는 편집을 실행하면 실제 경로를 확인할 수 있습니다.</p>}{logs.length>0&&<details className="execution-logs"><summary>데이터 처리 기록</summary><ul>{logs.map((text,index)=><li key={index}>{text}</li>)}</ul></details>}<section className="execution-sources"><h3>현재 그래프의 데이터 근거</h3><p>{result.period.start} ~ {result.period.end} · {result.chart.length}개 계열 · {result.chart.reduce((n,s)=>n+s.points.length,0)}개 관측치</p>{sources.map(table=><article key={table.tableId}><code>{table.tableId}</code><strong>{table.name}</strong></article>)}<p>출처: 한국은행 · KOSIS</p></section></section></div></dialog>;
}
