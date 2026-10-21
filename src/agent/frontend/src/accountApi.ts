import {setObservationAccount,captureObservation,recordClientFailure} from './executionObservations';
import {withRequestDeadline} from './requestDeadline';
export const accountBase=import.meta.env.VITE_API_BASE_URL??'http://127.0.0.1:8000/api';
let accountId:number|null=null;
export function setAccountId(id:number|null){accountId=id;setObservationAccount(id);}
export function accountKey(key:string){return `${key}.account.${accountId??'signed-out'}`;}
export async function apiFetch(input:RequestInfo|URL,init:RequestInit={},timeoutMs=20_000){
 setObservationAccount(accountId);
 const observationOwner=accountId,observationStart=performance.now(),observationTime=new Date().toISOString();
 let response:Response;
 try{response=await withRequestDeadline(signal=>fetch(input,{...init,credentials:'include',signal}),'서버 요청',init.signal??undefined,timeoutMs);}
 catch(error){recordClientFailure(observationOwner,observationTime,performance.now()-observationStart,error);if(error instanceof TypeError)throw new Error('서버 연결에 실패했습니다. 입력과 현재 작업은 유지됩니다. 연결을 확인한 뒤 다시 시도해 주세요.');throw error;}
 if(response.status===401&&!String(input).includes('/auth/'))window.dispatchEvent(new Event('statbridge:auth-expired'));
 void captureObservation(response,accountBase,observationOwner);
 return response;
}
export async function accountRequest(path:string,body?:unknown,method?:string){
 return withRequestDeadline(async signal=>{
 const response=await apiFetch(accountBase+path,{signal,method:method??(body?'POST':'GET'),headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});
 const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'입력 내용을 확인해 주세요.');return data;
 },'계정 저장·불러오기 요청');
}
