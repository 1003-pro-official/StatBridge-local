import {useEffect,useState} from 'react';
import type {ChartEditInput,ChartSeries} from './api/types';
import type {TableDocument,TableOptions} from './reportTable';
import {tableCell,tableFrequency,tableTemplates} from './reportTable';

export function TableControls({document,series,disabled,onEdit}:{document:TableDocument;series:ChartSeries[];disabled:boolean;onEdit:(input:ChartEditInput)=>Promise<boolean>}){
 const [draft,setDraft]=useState<TableOptions>(document.options);
 useEffect(()=>setDraft(document.options),[document]);
 const update=(patch:Partial<TableOptions>)=>setDraft({...draft,...patch});
 const chosen=draft.labels.length?draft.labels:series.map(s=>s.label);
 const toggle=(label:string)=>update({labels:chosen.includes(label)?chosen.filter(x=>x!==label):[...chosen,label]});
 return <fieldset className="report-table-controls" disabled={disabled}><legend>보고서 표 편집</legend>
 <label>표 양식<select value={draft.template??'default'} onChange={e=>update({template:e.target.value as TableOptions['template']})}>{tableTemplates.map(([id,name])=><option key={id} value={id}>{id==='default'?'':id+' · '}{name}</option>)}</select></label>
 <small>첨부 표 스타일 팩의 6종 구현 양식입니다. 한국은행 공식 인증 양식은 아닙니다. 다단 머리글은 지표를 행으로 배치하면 연도별로 묶습니다.</small>
 {draft.template==='BOK-T05'&&<details open><summary>강조할 항목 · 소계</summary>{series.map(s=><label className="table-check" key={s.label}><input type="checkbox" checked={(draft.emphasized_labels??[]).includes(s.label)} onChange={()=>update({emphasized_labels:(draft.emphasized_labels??[]).includes(s.label)?draft.emphasized_labels!.filter(x=>x!==s.label):[...(draft.emphasized_labels??[]),s.label]})}/>{s.label}</label>)}<small>조회된 항목만 강조합니다. 합계나 소계를 새로 계산하지 않습니다.</small></details>}
 <label>표 제목<input maxLength={150} value={draft.title} placeholder="그래프 제목 사용" onChange={e=>update({title:e.target.value})}/></label>
 <label>행 · 열 배치<select value={draft.orientation} onChange={e=>update({orientation:e.target.value as TableOptions['orientation']})}><option value="indicators">지표를 행 · 시점을 열</option><option value="periods">시점을 행 · 지표를 열</option></select></label>
 <label>소수점 자리<select value={draft.decimals} onChange={e=>update({decimals:Number(e.target.value)})}>{[0,1,2,3,4,5,6].map(n=><option key={n} value={n}>{n}자리</option>)}</select></label>
 <label>최근 시점 수<input type="number" min={1} max={600} placeholder="전체 기간" value={draft.recent_periods??''} onChange={e=>update({recent_periods:e.target.value?Number(e.target.value):null})}/></label><small>각 자료 주기의 최근 시점을 표시합니다. 월→연 변환은 하지 않습니다.</small>
 <label className="table-check"><input type="checkbox" checked={draft.highlight_latest} onChange={e=>update({highlight_latest:e.target.checked})}/>최신 시점 강조</label>
 <details open><summary>표 항목 · 순서</summary>{series.map(s=><label className="table-check" key={s.label}><input type="checkbox" checked={chosen.includes(s.label)} disabled={chosen.length===1&&chosen.includes(s.label)} onChange={()=>toggle(s.label)}/>{s.label}</label>)}{chosen.map((label,i)=><div className="table-order" key={label}><span>{i+1}. {label}</span><button type="button" disabled={i===0} aria-label={`${label} 앞으로 이동`} onClick={()=>{const next=[...chosen];[next[i-1],next[i]]=[next[i],next[i-1]];update({labels:next});}}>↑</button></div>)}</details>
 <label>추가 주석<textarea maxLength={500} value={draft.note} onChange={e=>update({note:e.target.value})}/></label><small>출처는 조회 결과에서 자동 표시됩니다. 수치는 편집할 수 없습니다.</small>
 <button type="button" onClick={()=>void onEdit({instruction:'',commands:[{operation:'set_table',kind:'STYLE_EDIT',params:{patch:draft}}]})}>표 설정 적용</button>
 </fieldset>;
}

export default function ReportTable({document}:{document:TableDocument}){
 return <article className="report-table-document" data-template={document.options.template??'default'} aria-label="보고서 표"><h3>표 1. {document.title}</h3><p className="table-data-notice">조회 관측값 · 단위는 각 지표에 표시 · 소수점 {document.options.decimals}자리</p>
 {document.sections.map((section,index)=><section key={`${section.frequency}-${index}`}><h4>{tableFrequency(section.frequency)} · {section.periodCaption}</h4><div className="report-table-scroll" tabIndex={0} role="region" aria-label={`${tableFrequency(section.frequency)} 표 스크롤`}><table><thead>{!!section.headerGroups?.length&&<tr className="table-year-groups"><th scope="col">구분</th>{section.headerGroups.map(g=><th key={g.start} scope="colgroup" colSpan={g.span}>{g.label}</th>)}</tr>}<tr>{section.headers.map((h,i)=><th key={i} scope="col">{h}</th>)}</tr></thead><tbody>{section.rows.map((row,r)=><tr key={r} className={document.options.template==='BOK-T05'&&section.emphasizedRows?.includes(r)?'table-emphasized':''}>{row.map((cell,c)=>c===0?<th key={c} scope="row">{String(cell)}</th>:<td key={c} className={document.options.highlight_latest&&(document.options.orientation==='indicators'?c===section.headers.length-1:r===section.rows.length-1)?'table-latest':''}>{tableCell(cell,document.options.decimals)}</td>)}</tr>)}</tbody></table></div></section>)}
 <footer>{document.notes.map((note,i)=><p key={i}>주: {note}</p>)}{document.sources.map((source,i)=><p key={i}>자료: {source.tableName} · {source.tableId} · {source.source}</p>)}<p>CSV는 화면에 표시된 값으로 저장합니다. Excel은 조회 수치의 원래 정밀도를 유지합니다.</p></footer></article>;
}
