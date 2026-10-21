import {useEffect,useRef,useState} from 'react';
import type {ChartEditInput} from './api/types';
export function useAutoEdit(onEdit:(input:ChartEditInput)=>Promise<boolean>){
 const callback=useRef(onEdit);callback.current=onEdit;
 const jobs=useRef(new Map<string,{input:ChartEditInput;scope:unknown}>()),timer=useRef<ReturnType<typeof setTimeout>|null>(null),alive=useRef(true);
 const active=useRef(new Map<string,number>());
 const [error,setError]=useState(''),[settled,setSettled]=useState(0);
 const flush=()=>{if(timer.current)clearTimeout(timer.current);timer.current=null;const pending=[...jobs.current.entries()];jobs.current.clear();for(const [key,{input,scope}] of pending){if(scope!==(callback.current as typeof onEdit & {scope?:string}).scope)continue;active.current.set(key,(active.current.get(key)||0)+1);void callback.current(input).then(ok=>{if(!ok&&alive.current)setError('변경을 적용하지 못했습니다. 이전 설정을 유지합니다.');}).catch(e=>{if(alive.current)setError(e instanceof Error?e.message:'설정을 저장하지 못했습니다.');}).finally(()=>{const count=(active.current.get(key)||1)-1;if(count)active.current.set(key,count);else active.current.delete(key);if(alive.current)setSettled(n=>n+1);});}};
 const schedule=(input:ChartEditInput,key='settings')=>{setError('');jobs.current.set(key,{input,scope:(callback.current as typeof onEdit & {scope?:string}).scope});if(timer.current)clearTimeout(timer.current);timer.current=setTimeout(flush,350);};
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;flush();};},[]);
 const cancel=(key:string)=>jobs.current.delete(key);
 const pending=(key:string)=>jobs.current.has(key)||active.current.has(key);
 return {schedule,flush,cancel,pending,error,settled};
}
