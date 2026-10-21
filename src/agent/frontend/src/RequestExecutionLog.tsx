import {useState} from 'react';
import ExecutionEvidence from './ExecutionEvidence';
import type {QueryResponse} from './api/types';
export default function RequestExecutionLog({result}:{result:QueryResponse}){
 const [open,setOpen]=useState(false);
 return <div className="request-execution-log"><button type="button" onClick={()=>setOpen(true)}>실행 흐름 · 요청 기록 확인</button><ExecutionEvidence result={result} open={open} onClose={()=>setOpen(false)}/></div>;
}
