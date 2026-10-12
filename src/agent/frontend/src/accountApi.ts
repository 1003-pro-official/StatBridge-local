export const accountBase=import.meta.env.VITE_API_BASE_URL??'http://127.0.0.1:8000/api';
let accountId:number|null=null;
export function setAccountId(id:number|null){accountId=id;}
export function accountKey(key:string){return `${key}.account.${accountId??'signed-out'}`;}
export async function apiFetch(input:RequestInfo|URL,init:RequestInit={}){
 const response=await fetch(input,{...init,credentials:'include'});
 if(response.status===401&&!String(input).includes('/auth/'))window.dispatchEvent(new Event('statbridge:auth-expired'));
 return response;
}
export async function accountRequest(path:string,body?:unknown,method?:string){
 const response=await apiFetch(accountBase+path,{method:method??(body?'POST':'GET'),headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});
 const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'입력 내용을 확인해 주세요.');return data;
}
