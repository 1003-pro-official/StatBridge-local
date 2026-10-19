import {useState} from 'react';
import type {QueryResponse} from './api/types';
import {availabilityAnswer,apiSupportScope,canConnectMissingFiles} from './derivedAvailability';
import './DerivedAvailabilityPanel.css';
import {accountBase,apiFetch} from './accountApi';

export default function DerivedAvailabilityPanel({result,busy,retry,confirm,onResult}:{result:QueryResponse;busy:boolean;retry:()=>void;confirm:(answer:string)=>void;onResult:(r:QueryResponse)=>Promise<void>}){
 const data=result.availability!;
 const scope=apiSupportScope(data),canConnect=canConnectMissingFiles(data);
 const [answers,setAnswers]=useState<Record<number,string>>({});
 const [connecting,setConnecting]=useState(false),[connectError,setConnectError]=useState('');
 const connect=async()=>{setConnecting(true);setConnectError('');try{
  const r=await apiFetch(accountBase+'/derived/supplement/from-check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({check_id:data.checkId})});
  const next=await r.json();if(!r.ok)throw new Error(typeof next.detail==='string'?next.detail:'파일 연결을 준비하지 못했습니다.');await onResult(next);
 }catch(e){setConnectError((e as Error).message);}finally{setConnecting(false);}};
 return <section className="availability-panel" aria-label="원자료 확보 확인 결과">
  <header><small>DATA AVAILABILITY · 계산 전 확인</small><h2>{scope==='unsupported'?'지원하지 않는 범위입니다':data.status==='checked'?'원자료 확인 결과를 안내합니다':'실제 API 자료를 확인하고 있습니다'}</h2><p>확인 질문은 오류가 아닙니다. 조건이 확정되기 전에는 계산하지 않습니다.</p></header>
  {data.status!=='checked'?<div role="status"><p>{result.summary}</p><p>API 확인에 실패하거나 확인이 진행 중이면 자료 부재로 판정하지 않습니다.</p><button disabled={busy} onClick={retry}>자료 확인 다시 시도</button></div>:<>
   <div className="availability-proof"><strong>실제 KOSIS 메타데이터 API 확인</strong><span>승인 표 {data.checkedTables}/{data.requiredTables}개 · TBL / ITM / PRD</span><span>확인 시각 {data.checkedAt?new Date(data.checkedAt).toLocaleString('ko-KR'):''}</span></div>
   <p>아래 결과는 승인된 349개 표에 대한 확인입니다. KOSIS 전체 또는 ECOS 전체의 자료 부재를 뜻하지 않습니다.</p>
   <p><strong>관측값 확보 {data.sources.filter(s=>s.status==='available').length}개 · 승인 범위에서 미확보 {data.sources.filter(s=>s.status==='not_found').length}개 · 추가 확인 {data.sources.filter(s=>!['available','not_found'].includes(s.status)).length}개</strong></p>
   {scope==='unsupported'&&<div className="availability-questions"><strong>필요한 한국은행 KOSIS API 입력이 없습니다</strong><p>파일만 사용하는 계산은 지원하지 않습니다. 승인 한국은행 KOSIS 원자료가 실제 계산에 하나 이상 포함되는 질문으로 다시 작성해 주세요. 자료를 단순히 언급하거나 관련 없는 자료를 추가하는 것으로 지원 조건을 충족할 수 없습니다.</p></div>}
   {scope==='verification_pending'&&<p role="status">KOSIS API 입력의 확보 여부가 아직 미확정입니다. API 장애·항목 선택 미확정을 자료 부재로 단정하지 않으며, 확인될 때까지 파일 연결을 열지 않습니다.</p>}
   {data.calculationGuide&&<section className="availability-questions" aria-label="계산 방법과 필요한 자료"><h3>이 지표는 이렇게 계산합니다</h3><p style={{whiteSpace:'pre-wrap'}}>{data.calculationGuide}</p><p>예정 산식 안내입니다. 실제 적용한 산식·사용 관측값·단위·출처는 계산 후 근거에 저장합니다.</p></section>}
   {canConnect&&<div className="availability-questions"><strong>부족 자료를 준비하셨나요?</strong><p>입수처는 아래 자료별 카드에서 확인하고, 구한 파일은 이 버튼으로 연결해 주세요. 업로드 후 계산 기준을 저장하면 그래프와 표를 생성할 수 있습니다.</p><button disabled={busy||connecting||!data.checkId} onClick={()=>void connect()}>파일 업로드 공간 열기</button></div>}
   {scope!=='unsupported'&&!!data.questions.length&&<form className="availability-questions" onSubmit={e=>{e.preventDefault();confirm(availabilityAnswer(data.questions,answers));}}><h3>계산 전에 확인해 주세요</h3><p>해당하는 조건에 답해 주세요. 선택하지 않은 기준의 조건부 질문은 비워두셔도 됩니다.</p>{data.questions.map((q,i)=><label key={i}>{i+1}. {q}<input aria-label={`계산 조건 답변 ${i+1}`} value={answers[i]||''} onChange={e=>setAnswers({...answers,[i]:e.target.value})} placeholder="원하시는 기준을 입력해 주세요"/></label>)}<button disabled={busy||!availabilityAnswer(data.questions,answers)}>조건 반영해 다시 확인</button></form>}
   <div className="availability-sources">{data.sources.map((source,i)=><article key={i}>
    <div className="availability-source-title"><h3>{source.name}</h3><span>{source.status==='available'?'관측값 확보':source.status==='not_found'?'승인 범위에서 미확보':source.status==='api_error'?'API 확인 실패':'추가 확인 필요'}</span></div>
    <dl><dt>필요 기간·주기</dt><dd>{source.periods.map((p,j)=><div key={j}>{p.label}: {p.start} ~ {p.end} · {p.frequency==='pending'?'월평균/특정일 기준 확인 필요':p.frequency==='D'?'일별':p.frequency==='M'?'월별':p.frequency}</div>)}</dd><dt>필요 단위</dt><dd>{source.unit}</dd></dl>
    {source.quotation&&<p>{source.quotation}</p>}<p>{source.reason}</p>
    {source.observationChecks?.map((check,j)=><p key={j}>{check.status==='available'?`실제 API 관측값 ${check.observations}개 · 확인 단위 ${check.unit}`:check.reason}</p>)}
    {!!source.candidateTables.length&&<details><summary>{source.status==='not_found'?'관련 단어가 있는 표 · 원자료 확보 아님':'실제 API에서 확인한 후보'} {source.candidateTables.length}개</summary>{source.candidateTables.map(t=><p key={t.tableId}>{t.name} · {t.tableId} · {t.frequencies.join(', ')}</p>)}</details>}
    {source.guidance&&<details className="availability-guidance" open={i===0}><summary>어디서 구할 수 있나요? · {source.guidance.title}</summary><p>{source.guidance.description}</p><div>{source.guidance.links.map(link=><a href={link.url} key={link.url} target="_blank" rel="noopener noreferrer">{link.label} ↗<small>{link.note}</small></a>)}</div><p>검색할 자료명: {source.name}</p></details>}
   </article>)}</div>

   {canConnect&&<footer><strong>구한 자료는 여기에 연결하세요</strong><p>아래 버튼을 누르면 부족한 자료별 파일 업로드 공간이 열립니다. 파일 연결 후 계산 기준·원자료 방향·평균 대상을 확인하고 그래프와 표를 생성합니다.</p><p>지원 형식: CSV · JSON · TSV · XLSX. 사용자 자료는 KOSIS 원자료와 구분합니다. 빈 값이나 휴일 값을 만들지 마세요.</p><button disabled={busy||connecting||!data.checkId} onClick={()=>void connect()}>{connecting?'업로드 공간 준비 중…':'부족 자료 파일 연결하기 →'}</button>{connectError&&<p role="alert">{connectError}</p>}</footer>}
  </>}
 </section>;
}
