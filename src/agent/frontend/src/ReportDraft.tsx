import {useEffect,useRef,useState} from 'react';
import {apiFetch} from './accountApi';
import {EDIT_TIMEOUT_MS,withRequestDeadline} from './requestDeadline';
import {workspacePng,startFileDownload} from './workspaceDownload';
import {printReportDraft,reportDraftHtml} from './reportDraftDocument';
import type {DraftDocument} from './reportDraftDocument';
import {CHART_SIZE_LIMITS,reportChartSize,resizeReportChart,validateChartSize,type ChartImageSize} from './reportChartSize';

type Draft={title:string;draftId:string;revision:number;paragraphs:string[];method:string;limitations:string[];
 plotlyFigure:{data:Record<string,unknown>[];layout:Record<string,unknown>};
 scope:{transform:string;series:Array<{label:string;unit:string;start:string;end:string}>};
 sources:Array<{tableId?:string;tableName?:string;source?:string;organizationId?:string}>;
 claims:Array<{text:string;fact_ids:string[]}>};
type Preview={draft:Draft;document:DraftDocument;originalSize:ChartImageSize};
const imageData=(blob:Blob)=>new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(new Error('보고서 이미지를 준비하지 못했습니다.'));reader.readAsDataURL(blob);});

export default function ReportDraft({sessionId,revision,getChartSize}:{sessionId:string;revision:number;getChartSize?:()=>ChartImageSize|undefined}){
 const [preview,setPreview]=useState<Preview|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[stage,setStage]=useState('');
 const generation=useRef(0),request=useRef<AbortController|null>(null);
 const [sizeForm,setSizeForm]=useState({width:'',height:''}),[ratioLocked,setRatioLocked]=useState(true);
 useEffect(()=>{generation.current++;request.current?.abort();setPreview(null);setBusy(false);setError('');return()=>{generation.current++;request.current?.abort();};},[sessionId,revision]);
 const run=async()=>{
  const displayedSize=getChartSize?.();
  const token=++generation.current;request.current?.abort();const controller=new AbortController();request.current=controller;
  setBusy(true);setError('');setStage('표시된 자료로 설명을 작성하고 있습니다…');
  try{
   const next=await withRequestDeadline(async signal=>{
    const response=await apiFetch(`${import.meta.env.VITE_API_BASE_URL??'http://127.0.0.1:8000/api'}/report/interpret`,{method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({edit_session_id:sessionId,revision,mode:'chart_brief'})},EDIT_TIMEOUT_MS);
    const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'보고서 초안을 작성하지 못했습니다.');
    const draft=data as Draft;
    if(draft.revision!==revision||!draft.plotlyFigure||!Array.isArray(draft.paragraphs))throw new Error('최신 그래프에서 보고서 초안을 다시 작성해 주세요.');
    if(token!==generation.current)throw new Error('분석이 변경되었습니다.');
    setStage('그래프 이미지를 준비하고 있습니다…');
    const originalSize=displayedSize?validateChartSize({width:Math.round(displayedSize.width),height:Math.round(displayedSize.height)}):reportChartSize(draft.plotlyFigure.layout);
    const image=await imageData(await workspacePng(draft.plotlyFigure,signal,originalSize));signal.throwIfAborted();
    const source=[...new Set((draft.sources||[]).map(s=>[s.organizationId==='301'?'한국은행':'',s.source,s.tableId].filter(Boolean).join(' · ')).filter(Boolean))].join(', ');
    const scope=draft.scope.series.map(s=>`${s.label}: ${s.start}~${s.end} (${s.unit||'단위 없음'})`).join(' / ');
    return {draft,originalSize,document:{title:draft.title||'통계 분석 보고서',image,imageWidth:originalSize.width,imageHeight:originalSize.height,paragraphs:draft.paragraphs,source:source?'자료: '+source:'자료: 현재 조회 자료',scope}};
   },'보고서 초안 작성 요청',controller.signal,EDIT_TIMEOUT_MS);
   if(token===generation.current){setPreview(next);setSizeForm({width:String(next.originalSize.width),height:String(next.originalSize.height)});setRatioLocked(true);}
  }catch(e){if(token===generation.current&&!controller.signal.aborted)setError(e instanceof Error?e.message:String(e));}
  finally{if(token===generation.current){setBusy(false);setStage('');}}
 };
 const changeSize=(axis:'width'|'height',value:string)=>{
  if(!preview)return;
  setSizeForm(current=>{
   if(value===''||!Number.isFinite(Number(value))||Number(value)<=0)return {...current,[axis]:value};
   const next=resizeReportChart({width:Number(current.width),height:Number(current.height)},axis,Number(value),preview.originalSize.width/preview.originalSize.height,ratioLocked);
   return {width:String(next.width),height:String(next.height)};
  });
 };
 const applySize=async(reset=false)=>{
  if(!preview||busy)return;
  let size:ChartImageSize;
  try{size=reset?preview.originalSize:validateChartSize({width:Number(sizeForm.width),height:Number(sizeForm.height)});}catch(e){setError(e instanceof Error?e.message:String(e));return;}
  const token=++generation.current,controller=new AbortController();request.current=controller;
  setBusy(true);setError('');setStage('설정한 크기로 그래프 이미지를 준비하고 있습니다…');
  try{
   const image=await imageData(await workspacePng(preview.draft.plotlyFigure,controller.signal,size));controller.signal.throwIfAborted();
   if(token===generation.current){setPreview({...preview,document:{...preview.document,image,imageWidth:size.width,imageHeight:size.height}});setSizeForm({width:String(size.width),height:String(size.height)});if(reset)setRatioLocked(true);}
  }catch(e){if(token===generation.current&&!controller.signal.aborted)setError(e instanceof Error?e.message:String(e));}
  finally{if(token===generation.current){setBusy(false);setStage('');}}
 };
 const save=()=>{if(!preview)return;const url=URL.createObjectURL(new Blob([reportDraftHtml(preview.document)],{type:'text/html;charset=utf-8'}));startFileDownload(url,'statbridge-report-draft.html');setTimeout(()=>URL.revokeObjectURL(url),60_000);};
 const savePdf=async()=>{
  if(!preview||busy)return;const token=generation.current;setBusy(true);setError('');setStage('PDF 파일을 준비하고 있습니다…');
  const controller=new AbortController();request.current=controller;
  try{
   const blob=await withRequestDeadline(async signal=>{
    const response=await apiFetch(`${import.meta.env.VITE_API_BASE_URL??'http://127.0.0.1:8000/api'}/report/draft/export`,{method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({edit_session_id:sessionId,revision,draft_id:preview.draft.draftId,image_data_url:preview.document.image,image_width:preview.document.imageWidth,image_height:preview.document.imageHeight})},EDIT_TIMEOUT_MS);
    if(!response.ok){const data=await response.json();throw new Error(typeof data.detail==='string'?data.detail:'보고서 PDF를 만들지 못했습니다.');}
    if(!response.headers.get('content-type')?.startsWith('application/pdf'))throw new Error('PDF 파일 응답을 확인하지 못했습니다.');
    return response.blob();
   },'보고서 PDF 저장 요청',controller.signal,EDIT_TIMEOUT_MS);
   if(token!==generation.current)return;
   const url=URL.createObjectURL(blob);startFileDownload(url,'statbridge-report-draft.pdf');setTimeout(()=>URL.revokeObjectURL(url),60_000);
  }catch(e){if(token===generation.current&&!controller.signal.aborted)setError(e instanceof Error?e.message:String(e));}
  finally{if(token===generation.current){setBusy(false);setStage('');}}
 };
 return <details className="report-draft"><summary>보고서 초안</summary>
  <p>현재 그래프와 핵심 수치를 짧은 설명으로 정리합니다.</p>
  <button type="button" disabled={busy} onClick={()=>void run()}>{preview?'보고서 초안 다시 작성':'보고서 초안 작성'}</button>
  {busy&&<p role="status">{stage}</p>}{error&&<p role="alert">{error}</p>}
  {preview&&<><fieldset className="report-chart-size" disabled={busy}><legend>보고서 그래프 크기</legend>
   <label>너비 (px)<input type="number" min={CHART_SIZE_LIMITS.minWidth} max={CHART_SIZE_LIMITS.maxWidth} step="1" value={sizeForm.width} onChange={e=>changeSize('width',e.target.value)}/></label>
   <label>높이 (px)<input type="number" min={CHART_SIZE_LIMITS.minHeight} max={CHART_SIZE_LIMITS.maxHeight} step="1" value={sizeForm.height} onChange={e=>changeSize('height',e.target.value)}/></label>
   <label className="report-ratio-lock"><input type="checkbox" checked={ratioLocked} onChange={e=>{setRatioLocked(e.target.checked);if(e.target.checked&&preview){const width=Number(sizeForm.width);if(Number.isFinite(width)&&width>0)setSizeForm({width:String(width),height:String(Math.round(width*preview.originalSize.height/preview.originalSize.width))});}}}/> 비율 유지</label>
   <button type="button" onClick={()=>void applySize()}>크기 적용</button><button type="button" onClick={()=>void applySize(true)}>원래 크기</button>
   <small>적용된 이미지: {preview.document.imageWidth} × {preview.document.imageHeight}px · 화면과 인쇄 용지에 맞춰 비율을 유지하며 축소합니다.</small>
  </fieldset><div className="report-draft-actions"><button type="button" disabled={busy} onClick={save}>HTML 저장</button><button type="button" disabled={busy} onClick={()=>void savePdf()}>PDF 저장</button><button type="button" disabled={busy} onClick={()=>void printReportDraft(preview.document).catch(e=>setError(e.message))}>인쇄</button></div>
   <section className="report-draft-page" aria-label="보고서 초안 미리보기"><h3>{preview.document.title}</h3><small>{preview.document.scope}</small>
    <figure><img src={preview.document.image} width={preview.document.imageWidth} height={preview.document.imageHeight} alt={preview.document.title}/><figcaption>{preview.document.source}</figcaption></figure>
    <div className="report-draft-caption">{preview.draft.paragraphs.map((text,i)=><p key={i}>{text}</p>)}</div>
    <small>관측 자료로 작성한 초안 · 검토 후 사용해 주세요.</small>
   </section>
   <details><summary>설명 근거 · 작성 기준</summary><p>한국은행 2026년 8월 경제전망보고서의 서술 구성을 참고했습니다. 수치는 현재 그래프의 표시 자료를 사용합니다.</p>{preview.draft.claims.map((c,i)=><p key={i}>{c.text}<small>근거: {c.fact_ids.join(', ')}</small></p>)}{preview.draft.limitations.map((s,i)=><p key={i}>{s}</p>)}</details>
  </>}
 </details>;
}
