import {useEffect,useState} from 'react';
import {fetchCatalog,submitQuery} from './api/client';
import type {CatalogTable,ChartSeries,ChartEditInput} from './api/types';

export default function WorkspaceData({series,hidden,onEdit,disabled,onSelect}:{series:ChartSeries[];hidden:string[];onEdit:(v:ChartEditInput)=>Promise<boolean>;disabled:boolean;onSelect:(label:string)=>void}){
 const [tables,setTables]=useState<CatalogTable[]>([]),[search,setSearch]=useState(''),[tableId,setTableId]=useState(''),[dimensions,setDimensions]=useState<Record<string,string>>({});
 const [start,setStart]=useState('2020-01-01'),[end,setEnd]=useState('2025-12-31'),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const table=tables.find(t=>t.tableId===tableId);
 useEffect(()=>{fetchCatalog().then(r=>setTables(r.categories.flatMap(c=>c.children.flatMap(m=>m.children)))).catch(e=>setError(e.message));},[]);
 const load=async(replace:boolean,chosen=table,chosenDimensions=dimensions)=>{
  if(!chosen||disabled||busy)return;setBusy(true);setError('');
  try{
   const query=`${chosen.name} (${chosen.tableId})`;
   const response=await submitQuery({query,dimension_values:chosenDimensions,execute:true,period_start:start,period_end:end});
   if(!response.outputSessionId)throw new Error(response.summary||'조회 조건을 더 명확히 선택해 주세요.');
   await onEdit({instruction:'',...(replace?{replace_session_ids:[response.outputSessionId]}:{append_session_ids:[response.outputSessionId]})});
  }catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}
 };
 const edit=async(input:ChartEditInput)=>{setError('');try{await onEdit(input);}catch(e){setError(e instanceof Error?e.message:String(e));}};
 return <div className="workspace-data"><h3>데이터</h3><p className="workspace-hint">현재 그래프의 항목을 선택하거나 통계표를 조회해 추가하세요.</p>
  <label>통계 항목 변경<select aria-label="현재 통계 항목 변경" value="" disabled={disabled||busy} onChange={e=>{const selected=tables.find(t=>t.tableId===e.target.value);if(selected)void load(true,selected,Object.fromEntries(selected.dimensions.map(d=>[d.apiParam,d.defaultValueId])));}}><option value="">다른 통계로 변경 · 자동 조회</option>{tables.map(t=><option key={t.tableId} value={t.tableId}>{t.name} ({t.tableId})</option>)}</select></label>
  <ul className="workspace-series-list">{series.map(s=><li key={s.id}><button type="button" title="이 데이터의 선·색상 편집" onClick={()=>onSelect(s.label)}><i style={{background:s.color}}/><strong>{s.label}</strong><small>{s.unit} · {s.frequency} · {s.points.length}개</small><small>{s.points[0]?.date}~{s.points.at(-1)?.date}</small></button><button type="button" title="원자료를 보존하고 그래프에서 제외" aria-label={`${s.label} 데이터 제외`} disabled={disabled||series.length<=1} onClick={()=>void edit({instruction:'',commands:[{operation:'hide_series',kind:'DATA_EDIT',value:s.label}]})}>×</button></li>)}</ul>
  {hidden.map(label=><button type="button" key={label} disabled={disabled} onClick={()=>void edit({instruction:'',commands:[{operation:'show_series',kind:'STYLE_EDIT',value:label}]})}>{label} 다시 표시</button>)}
  <details><summary>통계 항목 추가 · 변경</summary><fieldset disabled={disabled||busy}><label>통계표 검색<input aria-label="워크스페이스 통계표 검색" value={search} onChange={e=>setSearch(e.target.value)}/></label><label>통계 항목<select aria-label="워크스페이스 통계 항목" value={tableId} onChange={e=>{setTableId(e.target.value);const chosen=tables.find(t=>t.tableId===e.target.value);setDimensions(Object.fromEntries((chosen?.dimensions||[]).map(d=>[d.apiParam,d.defaultValueId])));}}><option value="">통계표 선택</option>{tables.filter(t=>!search||`${t.name} ${t.tableId}`.includes(search)).map(t=><option key={t.tableId} value={t.tableId}>{t.name} ({t.tableId})</option>)}</select></label>
   {table&&<><small>{table.unitScale} · {table.frequencyLabel} · {table.periodStart}~{table.periodEnd}</small>{table.dimensions.map(d=><label key={d.apiParam}>{d.name}<select aria-label={`데이터 ${d.name}`} value={dimensions[d.apiParam]||d.defaultValueId} onChange={e=>setDimensions(v=>({...v,[d.apiParam]:e.target.value}))}>{d.valueOptions.map(v=><option key={v.id} value={v.id}>{v.name}</option>)}</select></label>)}</>}
   <label>조회 시작일<input aria-label="조회 시작일" type="date" value={start} onChange={e=>setStart(e.target.value)}/></label><label>조회 종료일<input aria-label="조회 종료일" type="date" value={end} onChange={e=>setEnd(e.target.value)}/></label><div className="workspace-data-actions"><button type="button" disabled={!table||start>end} onClick={()=>void load(false)}>데이터 추가</button><button type="button" disabled={!table||start>end} onClick={()=>void load(true)}>선택 데이터로 변경</button></div></fieldset></details>
  <details><summary>현재 데이터 기간 변경</summary><fieldset disabled={disabled||busy}><label>시작일<input aria-label="현재 시작일" type="date" value={start} onChange={e=>setStart(e.target.value)}/></label><label>종료일<input aria-label="현재 종료일" type="date" value={end} onChange={e=>setEnd(e.target.value)}/></label><button type="button" disabled={!start||!end||start>end} onClick={()=>void edit({instruction:`기간을 ${start}부터 ${end}까지로 변경해줘`})}>기간 적용 · 재조회</button></fieldset></details>
  {busy&&<p role="status">실제 통계 자료 조회 중…</p>}{error&&<p role="alert">{error}</p>}
 </div>;
}
