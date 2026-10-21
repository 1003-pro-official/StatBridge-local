import {useEffect,useId,useRef} from 'react';
import {createPortal} from 'react-dom';
import './ReportMarkdownPreview.css';
type Entry={id:string;revision:number;paragraphs:string[];table?:{columns:string[];rows:string[][]};sources?:string[]};
export default function ReportMarkdownPreview({entries,onClose,onDownload,busy}:{entries:Entry[];onClose:()=>void;onDownload:()=>void;busy:boolean}){
 const modal=useRef<HTMLDialogElement>(null),heading=useId();
 useEffect(()=>{const element=modal.current;if(!element)return;const overflow=document.body.style.overflow;const previous=document.activeElement as HTMLElement|null;element.showModal();document.body.style.overflow='hidden';return()=>{element.close();document.body.style.overflow=overflow;previous?.focus({preventScroll:true});};},[]);
 return createPortal(<dialog ref={modal} className="report-md-dialog" aria-labelledby={heading} onCancel={e=>{e.preventDefault();onClose();}} onClose={e=>{if(!e.currentTarget.open)onClose();}}>
  <header><div><h2 id={heading}>모은 답변 MD 미리보기</h2><p>추가한 순서 · {entries.length}개 답변 · 내려받을 문서의 내용입니다.</p></div><div className="report-md-dialog-actions"><button type="button" disabled={busy} onClick={onDownload}>MD 내려받기</button><button type="button" autoFocus onClick={onClose}>닫기 ✕</button></div></header>
  <div className="report-md-dialog-scroll"><article aria-label="누적 보고서 미리보기"><h1>통계 분석 보고서</h1>{entries.map((entry,index)=><section key={entry.id}><h2>{index+1}. 분석 결과</h2>{entry.paragraphs.map((text,i)=><p key={i}>{text}</p>)}{entry.table&&<div className="report-md-preview-table"><table><thead><tr>{entry.table.columns.map((c,i)=><th key={i}>{c}</th>)}</tr></thead><tbody>{entry.table.rows.map((row,i)=><tr key={i}>{row.map((v,j)=><td key={j}>{v}</td>)}</tr>)}</tbody></table></div>}<footer><p>자료 기준: 편집 {entry.revision}회 시점의 검산 결과.</p>{!!entry.sources?.length&&<p>자료: 한국은행 · KOSIS / {entry.sources.join(', ')}</p>}</footer></section>)}</article></div>
 </dialog>,document.body);
}
