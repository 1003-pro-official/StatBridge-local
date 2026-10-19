import {useEffect,useState} from 'react';
import {fetchCatalog} from './api/client';
import type {CatalogTable,QueryResponse} from './api/types';
import {recoveryFor} from './recoveryActions';

export default function RecoveryPanel({message,result,busy,retry,selectTable,selectPeriod,onRevise}:{message:string;result:QueryResponse|null;busy:boolean;retry:()=>void;selectTable:(table:CatalogTable)=>void;selectPeriod:(start:string,end:string)=>void;onRevise:()=>void}){
 const [tables,setTables]=useState<CatalogTable[]>([]),[filter,setFilter]=useState(''),[table,setTable]=useState(''),[catalogError,setCatalogError]=useState('');
 const [mode,setMode]=useState<'none'|'table'|'period'>('none');
 const [start,setStart]=useState(/^\d{4}-\d{2}-\d{2}$/.test(result?.period?.start||'')?result!.period!.start:''),[end,setEnd]=useState(/^\d{4}-\d{2}-\d{2}$/.test(result?.period?.end||'')?result!.period!.end:'');
 const [catalogBusy,setCatalogBusy]=useState(false);
 const load=()=>{setCatalogBusy(true);setCatalogError('');fetchCatalog().then(c=>setTables(c.categories.flatMap(a=>a.children.flatMap(b=>b.children)))).catch(e=>setCatalogError(e.message)).finally(()=>setCatalogBusy(false));};
 useEffect(()=>{setMode('none');setTable('');},[message,result?.query]);
 useEffect(()=>{if(mode==='table'&&!tables.length)load();},[mode]);
 const terms=filter.trim().toLowerCase().split(/\s+/);
 const found=tables.filter(t=>(result?.status!=='need_details'||result.tables.some(x=>x.tableId===t.tableId))&&terms.every(term=>`${t.name} ${t.tableId} ${t.items.join(' ')}`.toLowerCase().includes(term)));
 const noTable=result?.status==='no_match';
 const detailsOnly=result?.status==='need_details';
 const issue=result?.recovery?.issue;
 const failureTitle=issue==='model'?'분석 모델의 응답을 확인하지 못했습니다':issue==='calculation'?'증가율 계산 기준을 확인해 주세요':issue==='timeout'?(result?.analysisKind==='derived'?'파생지표 분석 대기 한도에 도달했습니다':'20초 응답 제한에 도달했습니다'):issue==='input'?'입력한 조회 조건을 확인해 주세요':issue==='auth'?'로그인 상태를 확인해 주세요':issue==='server'?'서버 처리 중 문제가 발생했습니다':issue==='rate_limit'?'잠시 후 다시 시도해 주세요':issue==='network'?'서버 연결을 확인해 주세요':'현재 작업을 유지하고 이어서 진행할 수 있습니다';
 const selectedTable=tables.find(t=>t.tableId===table);
 const recovery=recoveryFor(result,message);
 const act=(id:string)=>{if(id==='retry')retry();else if(id==='revise')onRevise();else if(id==='table')setMode('table');else if(id==='period')setMode('period');};
 return <section className="agent-recovery" role="region" aria-label="이어서 진행하기">
 <div className="recovery-heading"><span className="recovery-mark" aria-hidden="true">!</span><div><small>요청 확인</small><h3>{issue==='unsupported'?'지원하지 않는 자료입니다 · 질문을 다시 작성해 주세요':noTable?'지원되지 않는 지표를 확인해 주세요':result?.status==='need_details'?(result.analysisKind==='derived'?'파생지표에 필요한 자료와 조건을 확인해 주세요':'통계표를 찾았습니다. 조회할 분류를 지정해 주세요'):failureTitle}</h3></div></div>
 <p role="status">{message}</p>{result?.status==='need_details'&&<div className="recovery-matched-tables">{result.tables.map(t=><span key={t.tableId}>{t.name}<small>{t.tableId}</small></span>)}</div>}{recovery.question!==message&&<p className="recovery-guidance">{recovery.question}</p>}{!!result?.recovery?.requirements?.length&&<details className="recovery-requirements"><summary>{result.analysisKind==='derived'?'필요한 자료·조건':'입력해야 할 분류'} {result.recovery.requirements.length}개 확인</summary><ul>{result.recovery.requirements.map((requirement,i)=><li key={i}>{requirement}</li>)}</ul></details>}
 <div className="recovery-actions">{recovery.choices.map((c,i)=><button className={i===0?'control-primary':''} key={c.id} disabled={busy} onClick={()=>act(c.id)}>{c.label}</button>)}</div>
 {mode==='period'&&<div className="recovery-period"><label>시작일<input type="date" aria-label="재질문 시작일" value={start} onChange={e=>setStart(e.target.value)}/></label><label>종료일<input type="date" aria-label="재질문 종료일" value={end} onChange={e=>setEnd(e.target.value)}/></label><button disabled={busy||!start||!end||start>end} onClick={()=>selectPeriod(start,end)}>이 기간으로 계속</button></div>}
 {mode==='table'&&<div className="recovery-table">
 <div className="recovery-table-heading"><div><h4>{detailsOnly?'찾은 통계표의 분류 확인':'지원 통계표 탐색'}</h4><p>{detailsOnly?'통계표를 눌러 조회 가능한 분류 이름을 확인해 주세요.':'표를 직접 선택하면 해당 표를 조회하는 새 요청으로 변경됩니다. 항목과 단위를 확인해 주세요.'}</p></div><button onClick={()=>setMode('none')}>닫기</button></div>
 <label className="recovery-search">통계표 검색<input aria-label="대체 통계표 검색" placeholder="표 이름, 항목 또는 표 ID를 입력하세요" value={filter} onChange={e=>{setFilter(e.target.value);setTable('');}}/></label>
 <p className="recovery-count" role="status">{catalogBusy?'목록을 불러오고 있습니다':`${found.length}개 통계표`}</p>
 <div className="recovery-table-list" role="group" aria-label="대체 통계표 선택">{found.map(t=><button className={`recovery-table-option ${table===t.tableId?'selected':''}`} key={t.tableId} aria-pressed={table===t.tableId} disabled={busy} onClick={()=>setTable(t.tableId)}><span><strong>{t.name}</strong><small>{t.tableId} · {t.frequencyLabel} · {t.units.join(' / ')||'단위 확인 필요'}</small><small>{t.periodStart} ~ {t.periodEnd}</small></span><span className="recovery-choice-indicator" aria-hidden="true">{table===t.tableId?'✓':'+'}</span></button>)}</div>
 {!catalogBusy&&!catalogError&&!found.length&&<p>검색어에 맞는 표가 없습니다. 지표명이나 표 ID를 확인해 주세요.</p>}
 {selectedTable&&<div className="recovery-table-preview"><strong>{selectedTable.name} · 분류</strong>{selectedTable.dimensions.map((d,i)=><details key={d.apiParam}><summary>{d.name||`${i+1}번째 분류`} · {d.count}개 항목</summary><div>{d.valueOptions.map(v=><span key={v.id}>{v.name}</span>)}</div></details>)}</div>}
 <div className="recovery-table-footer"><span>{tables.find(t=>t.tableId===table)?.name||'조회할 통계표를 선택해 주세요'}</span><button className="control-primary" disabled={busy||!table} onClick={()=>{const selected=tables.find(t=>t.tableId===table);if(detailsOnly)onRevise();else if(selected)selectTable(selected);}}>{detailsOnly?'분류 확인 후 질문 수정':'선택한 표 조회'}</button></div>
 {catalogError&&<p role="alert">{catalogError}<button onClick={load} disabled={catalogBusy}>목록 다시 불러오기</button></p>}</div>}
 </section>;
}
