import {useState} from 'react';
import {accountBase,apiFetch} from './accountApi';
import type {QueryResponse} from './api/types';
import './DerivedSupplementPanel.css';
import {resolveInputGuidance} from './derivedInputGuidance';
import DerivedComparisonForm from './DerivedComparisonForm';

type Format='csv'|'json'|'tsv';
const ACCEPT='.csv,.json,.tsv,.xlsx';
const frequencyName:Record<string,string>={D:'일별',M:'월별',Q:'분기별',S:'반기별',Y:'연간'};
const dateLabel=(v:string)=>/^\d{8}$/.test(v)?`${v.slice(0,4)}.${v.slice(4,6)}.${v.slice(6)}`:/^\d{6}$/.test(v)?`${v.slice(0,4)}.${v.slice(4)}`:v;
function UploadIcon(){return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M12 16V4m-4 4 4-4 4 4M5 15v5h14v-5"/></svg>;}

export default function DerivedSupplementPanel({result,onResult}:{result:QueryResponse;onResult:(r:QueryResponse)=>Promise<void>}){
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 const [paste,setPaste]=useState<Record<string,string>>({});
 const [formats,setFormats]=useState<Record<string,Format>>({});
 const [dragging,setDragging]=useState('');
 const [comparisonDirty,setComparisonDirty]=useState(false);
 const w=result.supplement;
 const missing=w?.missing.map(slot=>({...slot,guidance:resolveInputGuidance(slot,result.query)}))||[];
 const request=async(path:string,body:unknown)=>{
  const response=await apiFetch(accountBase+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)},180000);
  const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'파일 형식과 필수 항목을 확인해 주세요.');return data as QueryResponse;
 };
 const run=async(action:()=>Promise<QueryResponse>)=>{setBusy(true);setError('');try{await onResult(await action());}catch(e){setError(e instanceof Error?e.message:'자료 처리를 완료하지 못했습니다.');}finally{setBusy(false);}};
 const upload=(alias:string,filename:string,content:string,encoding='utf8')=>request(`/derived/supplement/${w!.workspaceId}/upload`,{alias,filename,content,encoding});
 const uploadFile=(alias:string,file?:File)=>{if(!file||busy)return;void run(async()=>{
  if(file.size>2000000)throw new Error('파일은 2MB 이하여야 합니다.');
  if(!/\.(csv|json|tsv|xlsx)$/i.test(file.name))throw new Error('CSV, JSON, TSV 또는 XLSX 파일을 선택해 주세요.');
  const bytes=new Uint8Array(await file.arrayBuffer());let binary='';
  for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
  return upload(alias,file.name,btoa(binary),'base64');
 });};
 const template=async(alias:string)=>{setError('');try{
  const format=formats[alias]||'csv';const r=await apiFetch(accountBase+`/derived/supplement/${w!.workspaceId}/template/${alias}?format=${format}`);
  if(!r.ok)throw new Error('파일 양식을 가져오지 못했습니다.');const url=URL.createObjectURL(await r.blob());
  const a=document.createElement('a');a.href=url;a.download=alias+'.'+format;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }catch(e){setError((e as Error).message);}};
 const fileInput=(alias:string,label:string)=><label className="ds-file-button"><UploadIcon/>{label}<input type="file" accept={ACCEPT} disabled={busy} aria-label={`자료 파일 ${alias}`} onChange={e=>{uploadFile(alias,e.target.files?.[0]);e.target.value='';}}/></label>;
 return <section className="ds-panel" aria-label="부족 자료 파일 보완" aria-busy={busy}>
  <header className="ds-heading"><div><span className="ds-eyebrow">CONTINUE YOUR ANALYSIS</span><h3>자료를 연결하고, 분석을 이어가세요</h3><p>확보한 API 자료는 유지하고, 부족한 자료만 파일로 연결합니다.</p></div><span className="ds-status">{w?.question?'조건 확인 필요':w?.missing.length?`${w.missing.length}개 자료 필요`:w?'계산 준비 완료':'자료 확인'}</span></header>
  <ol className="ds-steps" aria-label="자료 보완 진행 단계"><li className="is-done"><span>01</span>API 자료 확인</li><li className={w?.missing.length?'is-current':'is-done'}><span>02</span>부족한 자료 연결</li><li><span>03</span>그래프·표 생성</li></ol>
  {w?.calculationGuide&&<section className="ds-available"><h4>계산법과 필요한 입력</h4><p style={{whiteSpace:'pre-wrap'}}>{w.calculationGuide}</p><p>부족한 입력 {w.missing.length}개 · 연결한 파일 {w.uploaded.length}개 · API 확보 {w.available.length}개</p></section>}
  {!w?<button className="ds-primary" disabled={busy} onClick={()=>void run(()=>request('/derived/supplement',{query:result.query}))}>API 조회 및 부족 자료 확인</button>:<>
   <div className="ds-available"><div className="ds-section-label"><span className="ds-dot"/>확보한 API 자료 <b>{w.available.length}</b></div>{w.available.length?<ul>{w.available.map(a=><li key={a.tableId+a.required_data}><div><strong>{a.required_data}</strong><small>{a.tableId}</small></div><span>{a.observations}개 관측값 <i>준비됨</i></span></li>)}</ul>:<p>현재 확보된 API 자료가 없습니다. 필요한 원자료를 아래에서 확인해 주세요.</p>}</div>
   {missing.map((slot,index)=><article className="ds-input-card" key={slot.alias}>
    <div className="ds-card-heading"><div><span className="ds-kicker">추가할 자료 {String(index+1).padStart(2,'0')}</span><h4>{slot.required_data.replace(/\s*CSV\s*$/i,'')}</h4></div><span className="ds-required">파일 필요</span></div>
    <div className="ds-requirements"><span>{frequencyName[slot.frequency]||slot.frequency}</span><span>{slot.periods?slot.periods.map(p=>`${p.label}: ${dateLabel(p.start)}~${dateLabel(p.end)}`).join(' / '):`${dateLabel(result.period?.start||'')} — ${dateLabel(result.period?.end||'')}`}</span><span>{slot.unit||'파일에 실제 단위 입력'}</span>{slot.lookback>0&&<span>과거 {slot.lookback}시점 추가</span>}</div>
    <div className="ds-guidance"><span className="ds-guide-mark" aria-hidden="true">↗</span><div><h5>{slot.guidance?.title||'자료를 준비해 주세요'}</h5><p>{slot.guidance?.description||'제공기관에서 지표와 기간을 확인한 원자료를 준비해 주세요.'}</p>
     {!!slot.guidance?.links.length&&<><div className="ds-source-links">{slot.guidance.links.map(link=><a href={link.url} target="_blank" rel="noopener noreferrer" key={link.url}>{link.label} ↗<small>{link.note}</small></a>)}</div><p className="ds-search-term">검색할 자료명 <code>{slot.guidance.searchTerms}</code></p></>}
    </div></div>
    <div className="ds-upload-layout"><div className="ds-template"><h5>1. 양식 준비</h5><p>원자료를 양식에 맞춰 정리해 주세요. CSV는 엑셀에서 열어 .xlsx로 저장해도 됩니다.</p><div className="ds-template-actions"><select aria-label={`양식 형식 ${slot.alias}`} value={formats[slot.alias]||'csv'} onChange={e=>setFormats({...formats,[slot.alias]:e.target.value as Format})}><option value="csv">CSV</option><option value="json">JSON</option><option value="tsv">TSV</option></select><button disabled={busy} onClick={()=>void template(slot.alias)}>빈 양식 다운로드 ↓</button></div></div>
     <div className={`ds-dropzone ${dragging===slot.alias?'is-dragging':''}`} onDragOver={e=>{e.preventDefault();if(!busy)setDragging(slot.alias);}} onDragLeave={()=>setDragging('')} onDrop={e=>{e.preventDefault();setDragging('');if(e.dataTransfer.files.length!==1){setError('한 번에 파일 하나를 선택해 주세요.');return;}uploadFile(slot.alias,e.dataTransfer.files[0]);}}><UploadIcon/><h5>2. 파일 연결</h5><p>파일을 여기에 끌어놓거나 선택하세요</p>{fileInput(slot.alias,'파일 선택')}<small>CSV · JSON · TSV · XLSX / 최대 2MB</small></div>
    </div>
    <details className="ds-detail"><summary>입력 형식과 자료 조건 확인</summary><p>{slot.reason}</p><p>필수 필드: <code>period, value, unit, frequency, source</code>. 시점은 {slot.frequency==='D'?'20230102 (일별: YYYYMMDD)':slot.frequency==='M'?'202301':slot.frequency==='Y'?'2023':'202301'} 형태로 입력해 주세요. JSON은 이 필드를 가진 객체의 배열, 엑셀은 첫 행이 필드명인 시트 하나를 사용합니다.</p><ul>{slot.guidance?.checklist.map(check=><li key={check}>{check}</li>)}</ul><p>PDF·이미지·HWP·DOCX·구형 XLS는 지원하지 않습니다. 여러 행의 제목이나 병합 셀이 있는 원본은 양식에 맞춰 정리해 주세요.</p></details>
    <details className="ds-detail"><summary>파일 대신 텍스트로 붙여넣기</summary><label>CSV·JSON·TSV 내용<textarea aria-label={`자료 내용 ${slot.alias}`} placeholder="양식의 필드명과 관측값을 붙여넣어 주세요." value={paste[slot.alias]||''} onChange={e=>setPaste({...paste,[slot.alias]:e.target.value})}/></label><button disabled={busy||!paste[slot.alias]} onClick={()=>void run(()=>upload(slot.alias,slot.alias+'.'+(formats[slot.alias]||'csv'),paste[slot.alias]))}>내용으로 등록 · {(formats[slot.alias]||'csv').toUpperCase()}</button></details>
   </article>)}
   {!!w.uploaded.length&&<div className="ds-uploaded"><h4>연결한 사용자 자료</h4>{w.uploaded.map(f=><div key={f.alias} className="ds-file-record"><div><span className="ds-file-check">✓</span><strong>{f.filename}</strong><span>연결 완료</span></div><details className="ds-detail"><summary>출처 해시 확인 · 파일 교체</summary><p>사용자 제공 자료 · SHA-256 <code>{f.sha256}</code></p>{fileInput(f.alias,'다른 파일로 교체')}</details></div>)}</div>}
   {w.comparison&&<DerivedComparisonForm data={w.comparison} busy={busy} ready={!w.missing.length} onDirty={()=>setComparisonDirty(true)} save={settings=>void run(async()=>{const next=await request(`/derived/supplement/${w.workspaceId}/comparison`,settings);setComparisonDirty(false);return next;})}/>}
   <footer className="ds-footer"><div><strong>{comparisonDirty?'수정한 계산 기준을 먼저 저장해 주세요.':w.question?'계산 조건을 확인해 주세요.':w.missing.length?'자료를 연결하면 계산을 이어갈 수 있습니다.':'필요한 자료가 모두 연결되었습니다.'}</strong><p>최대 12개 시계열 · 파일당 6,000행 · 일별 자료는 달력일 기준이며 휴일·결측일을 채우지 않습니다.</p></div><button className="ds-primary" disabled={busy||comparisonDirty||w.missing.length>0||!w.uploaded.length||!!(w.comparison&&!w.comparison.configured)} onClick={()=>void run(()=>request(`/derived/supplement/${w.workspaceId}/resume`,{}))}>{busy?'자료 확인 중…':'파생지표 계산하기 →'}</button></footer>
   <p className="ds-footnote">사용자 파일은 KOSIS 자료와 구분해 표시합니다. 빈 값은 0으로 채우지 않으며, 엑셀 수식·매크로·외부 링크는 실행하지 않습니다.</p>
   {w.question&&<p className="ds-feedback" role="status">{w.question}</p>}
  </>}
  {busy&&<p className="ds-feedback" role="status">자료를 검증하고 있습니다. 확보한 API 자료와 기존 그래프는 유지됩니다.</p>}{error&&<p className="ds-error" role="alert">{error}</p>}
 </section>;
}
