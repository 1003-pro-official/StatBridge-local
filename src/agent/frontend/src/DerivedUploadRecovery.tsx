import {useEffect,useState} from 'react';
import {accountBase,apiFetch} from './accountApi';
import type {QueryResponse} from './api/types';
export default function DerivedUploadRecovery({open}:{open:(r:QueryResponse)=>void}){
 const [items,setItems]=useState<Array<{workspaceId:string;query:string;uploaded:number;missing:number}>>([]);
 const [error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{let active=true;apiFetch(accountBase+'/derived/supplement').then(r=>r.ok?r.json():{items:[]}).then(data=>{if(active)setItems(data.items||[]);}).catch(()=>{});return()=>{active=false;};},[]);
 if(!items.length)return null;
 const resume=async(id:string)=>{setBusy(true);setError('');try{const r=await apiFetch(accountBase+'/derived/supplement/'+id);const data=await r.json();if(!r.ok)throw new Error(data.detail||'작업을 열지 못했습니다.');open(data);}catch(e){setError((e as Error).message);}finally{setBusy(false);}};
 return <section className="availability-panel" aria-label="진행 중인 파일 연결"><h3>연결하던 자료가 있습니다</h3>{items.slice(0,3).map(w=><div key={w.workspaceId}><p>{w.query.slice(0,160)} · 파일 {w.uploaded}개 연결 / {w.missing}개 필요</p><button disabled={busy} onClick={()=>void resume(w.workspaceId)}>자료 연결 이어가기</button></div>)}{error&&<p role="alert">{error}</p>}</section>;
}
