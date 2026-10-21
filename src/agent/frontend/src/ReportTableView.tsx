import ReportTablePreview from './ReportTablePreview';
import RichTableEditor from './RichTableEditor';
import {useAutoEdit} from './useAutoEdit';
import {useEffect,useId,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import type {ChartEditInput,ChartSeries} from './api/types';
import type {TableDocument,TableOptions} from './reportTable';
import {tableCell,tableFrequency,tableTemplates} from './reportTable';

export function TableControls({document,series,disabled,onEdit}:{document:TableDocument;series:ChartSeries[];disabled:boolean;onEdit:(input:ChartEditInput)=>Promise<boolean>}){
 const [draft,setDraft]=useState<TableOptions>(document.options);
 const auto=useAutoEdit(onEdit),draftRef=useRef(document.options);
 useEffect(()=>{if(auto.pending('settings'))return;draftRef.current=document.options;setDraft(document.options);},[document,auto.error,auto.settled]);
 const update=(patch:Partial<TableOptions>)=>{const next={...draftRef.current,...patch};draftRef.current=next;setDraft(next);if(next.recent_periods!=null&&(!Number.isInteger(next.recent_periods)||next.recent_periods<1||next.recent_periods>600)){auto.cancel('settings');return;}auto.schedule({instruction:'',commands:[{operation:'set_table',kind:'STYLE_EDIT',params:{patch:next}}]});};
 const chosen=draft.labels.length?draft.labels:series.map(s=>s.label);
 const toggle=(label:string)=>update({labels:chosen.includes(label)?chosen.filter(x=>x!==label):[...chosen,label]});
 return <fieldset className="report-table-controls" disabled={disabled}><legend>보고서 표 편집</legend>
 <label>표 양식<select value={draft.template??'default'} onChange={e=>update({template:e.target.value as TableOptions['template']})}>{tableTemplates.map(([id,name])=><option key={id} value={id}>{id==='default'?'':id+' · '}{name}</option>)}</select></label>
 <small>첨부 표 스타일 팩의 6종 구현 양식입니다. 한국은행 공식 인증 양식은 아닙니다. 다단 머리글은 지표를 행으로 배치하면 연도별로 묶습니다.</small>
 {draft.template==='BOK-T05'&&<details open><summary>강조할 항목 · 소계</summary>{series.map(s=><label className="table-check" key={s.label}><input type="checkbox" checked={(draft.emphasized_labels??[]).includes(s.label)} onChange={()=>update({emphasized_labels:(draft.emphasized_labels??[]).includes(s.label)?draft.emphasized_labels!.filter(x=>x!==s.label):[...(draft.emphasized_labels??[]),s.label]})}/>{s.label}</label>)}<small>조회된 항목만 강조합니다. 합계나 소계를 새로 계산하지 않습니다.</small></details>}
 <label>표 번호<input maxLength={20} value={draft.table_number??"1"} onChange={e=>update({table_number:e.target.value})}/></label><label>인쇄 배치<select value={draft.print_preset??"auto"} onChange={e=>update({print_preset:e.target.value as TableOptions["print_preset"]})}><option value="auto">본문 삽입형 · 내용에 맞춤</option><option value="a4_portrait">A4 세로</option><option value="a4_landscape">A4 가로</option></select></label><label>표 제목<input maxLength={150} value={draft.title} placeholder="그래프 제목 사용" onChange={e=>update({title:e.target.value})}/></label>
 <label>행 · 열 배치<select value={draft.orientation} onChange={e=>update({orientation:e.target.value as TableOptions['orientation'],comparison:e.target.value==='periods'?'none':draft.comparison??'none'})}><option value="indicators">지표를 행 · 시점을 열</option><option value="periods">시점을 행 · 지표를 열</option></select></label>
 {draft.orientation==='indicators'&&<label>비교 계산 열<select value={draft.comparison??"none"} onChange={e=>update({comparison:e.target.value as TableOptions["comparison"],orientation:"indicators"})}><option value="none">계산 열 없음</option><option value="previous_change">마지막 시점 전기 대비 변화</option><option value="yearly_change">마지막 시점 전년동기 대비 변화</option><option value="period_change">조회 시작 대비 변화</option><option value="period_growth">조회 시작 대비 증가율</option></select></label>}<label>소수점 자리<select value={draft.decimals} onChange={e=>update({decimals:Number(e.target.value)})}>{[0,1,2,3,4,5,6].map(n=><option key={n} value={n}>{n}자리</option>)}</select></label>
 <label>최근 시점 수<input type="number" min={1} max={600} placeholder="전체 기간" value={draft.recent_periods??''} onChange={e=>update({recent_periods:e.target.value?Number(e.target.value):null})}/></label><small>각 자료 주기의 최근 시점을 표시합니다. 월→연 변환은 하지 않습니다.</small>
 <label className="table-check"><input type="checkbox" checked={draft.highlight_latest} onChange={e=>update({highlight_latest:e.target.checked})}/>최신 시점 강조</label>
 <details open><summary>표 항목 · 순서</summary>{series.map(s=><label className="table-check" key={s.label}><input type="checkbox" checked={chosen.includes(s.label)} disabled={chosen.length===1&&chosen.includes(s.label)} onChange={()=>toggle(s.label)}/>{s.label}</label>)}{chosen.map((label,i)=><div className="table-order" key={label}><span>{i+1}. {label}</span><button type="button" disabled={i===0} aria-label={`${label} 앞으로 이동`} onClick={()=>{const next=[...chosen];[next[i-1],next[i]]=[next[i],next[i-1]];update({labels:next});}}>↑</button></div>)}</details>
 <label>추가 주석<textarea maxLength={500} value={draft.note} onChange={e=>update({note:e.target.value})}/></label><small>출처는 조회 결과에서 자동 표시됩니다. 수치는 편집할 수 없습니다. 행·열·기간·항목 변경 시 위치에 종속된 병합·셀 서식·맞춤 배치를 초기화합니다. Ctrl+Z로 이전 배치와 서식을 복원할 수 있습니다.</small>
 <small role="status">설정을 변경하면 자동 반영됩니다.</small>{auto.error&&<p role="alert">{auto.error}</p>}
 </fieldset>;
}

export default function ReportTable({document,onEdit,disabled=false}:{document:TableDocument;onEdit?:(input:ChartEditInput)=>Promise<boolean>;disabled?:boolean}){
 const [expanded,setExpanded]=useState(false);
 const dialog=useRef<HTMLDialogElement>(null),opener=useRef<HTMLButtonElement>(null),heading=useId();
 useEffect(()=>{
  if(!expanded)return;
  const modal=dialog.current;if(!modal)return;
  const previousOverflow=window.document.body.style.overflow;
  modal.showModal();window.document.body.style.overflow='hidden';
  return()=>{modal.close();window.document.body.style.overflow=previousOverflow;opener.current?.focus({preventScroll:true});};
 },[expanded]);
 const content=<><h3>{document.caption??`표 1. ${document.title}`}</h3><p className="table-data-notice">조회 관측값 · 단위는 각 지표에 표시 · 소수점 {document.options.decimals}자리</p>
 <RichTableEditor document={document} onEdit={onEdit} disabled={disabled}/>{!document.layoutSections&&document.sections.map((section,index)=><section key={`${section.frequency}-${index}`}><h4>{tableFrequency(section.frequency)} · {section.periodCaption}</h4><div className="report-table-scroll" tabIndex={0} role="region" aria-label={`${tableFrequency(section.frequency)} 표 스크롤`}><table><thead>{!!section.headerGroups?.length&&<tr className="table-year-groups"><th scope="col">구분</th>{section.headerGroups.map(g=><th key={g.start} scope="colgroup" colSpan={g.span}>{g.label}</th>)}</tr>}<tr>{section.headers.map((h,i)=><th key={i} scope="col">{h}</th>)}</tr></thead><tbody>{section.rows.map((row,r)=><tr key={r} className={document.options.template==='BOK-T05'&&section.emphasizedRows?.includes(r)?'table-emphasized':''}>{row.map((cell,c)=>c===0?<th key={c} scope="row">{String(cell)}</th>:<td key={c} className={document.options.highlight_latest&&(document.options.orientation==='indicators'?c===section.periods.length:r===section.rows.length-1)?'table-latest':''}>{tableCell(cell,document.options.decimals)}</td>)}</tr>)}</tbody></table></div>{!!section.computedCells?.length&&<details><summary>비교 셀의 산식·관측 근거</summary>{section.computedCells.map((cell,i)=><p key={i}>{cell.label}: {cell.formula} · {cell.unit} · {cell.observations.map(p=>`${p.date}: ${p.value}`).join(" / ")} {cell.reason}</p>)}</details>}</section>)}
 <footer>{document.notes.map((note,i)=><p key={i}>주: {note}</p>)}{document.sources.map((source,i)=><p key={i}>자료: {source.displaySource??"KOSIS"} · {source.tableName}</p>)}<details><summary>상세 데이터 계보</summary>{document.sources.map((source,i)=><p key={i}>{source.tableId} · {source.source}</p>)}</details><p>변화는 반올림 전 원자료로 계산합니다. CSV는 화면에 표시된 값으로 저장합니다. Excel은 조회 수치의 원래 정밀도를 유지합니다.</p></footer></>;
 return <>
  <article className="report-table-document" data-template={document.options.template??'default'} aria-label="보고서 표">
   <button ref={opener} type="button" className="table-expand-button" aria-haspopup="dialog" aria-expanded={expanded} onClick={()=>setExpanded(true)}>표 확대 보기</button>{content}
  </article>
  {expanded&&createPortal(<dialog ref={dialog} className="report-table-dialog" aria-labelledby={heading} onCancel={e=>{e.preventDefault();setExpanded(false);}} onClose={()=>setExpanded(false)}>
   <header className="report-table-dialog-header"><h2 id={heading}>표 확대 보기</h2><button type="button" autoFocus onClick={()=>setExpanded(false)}>확대 중지 ✕</button></header>
   <div className="report-table-dialog-content"><article className="report-table-document" data-template={document.options.template??'default'} aria-label="확대된 보고서 표"><ReportTablePreview document={document}/></article></div>
  </dialog>,window.document.body)}
 </>;
}
