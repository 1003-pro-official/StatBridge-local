import {accountKey} from './accountApi';
import type {QueryResponse} from './api/types';
export type ChatMessage={role:'user'|'assistant';text:string;kind?:'edit';time?:number};
export type SavedChat={id:string;title:string;savedAt:number;result:QueryResponse;messages:ChatMessage[]};
const memory=new Map<string,ChatMessage[]>();
const key=(id:string)=>accountKey(`statbridge.graph-chat.${id}`);
export function readChat(id:string):ChatMessage[]{
 const k=key(id);if(memory.has(k))return memory.get(k)!;
 let value:unknown=[];try{value=JSON.parse(localStorage.getItem(k)||sessionStorage.getItem(`statbridge.sujeongi.chat.${id}`)||'[]');}catch{}
 const messages=Array.isArray(value)?value.filter(m=>m&&(m.role==='user'||m.role==='assistant')&&typeof m.text==='string'):[];
 memory.set(k,messages);return messages;
}
function notify(id:string){window.dispatchEvent(new CustomEvent('statbridge:chat-updated',{detail:id}));}
export function writeChat(id:string,messages:ChatMessage[]){
 const k=key(id);memory.set(k,messages);
 try{localStorage.setItem(k,JSON.stringify(messages));}catch{window.dispatchEvent(new Event('statbridge:chat-storage-error'));}
 notify(id);
}
export function appendChat(id:string,message:ChatMessage){writeChat(id,[...readChat(id),{...message,time:Date.now()}]);}
export function deleteChat(id:string){localStorage.removeItem(key(id));sessionStorage.removeItem(`statbridge.sujeongi.chat.${id}`);memory.delete(key(id));notify(id);}
export function savedChats():SavedChat[]{try{const x=JSON.parse(localStorage.getItem(accountKey('statbridge.saved-chats'))||'[]');return Array.isArray(x)?x:[];}catch{return [];}}
export function saveChat(result:QueryResponse){
 const id=result.editSessionId;if(!id)return;
 const entry:SavedChat={id,title:String(result.outputSpec?.chartState?.title||result.query),savedAt:Date.now(),result,messages:readChat(id)};
 localStorage.setItem(accountKey('statbridge.saved-chats'),JSON.stringify([entry,...savedChats().filter(x=>x.id!==id)]));
}
export function removeSavedChat(id:string){localStorage.setItem(accountKey('statbridge.saved-chats'),JSON.stringify(savedChats().filter(x=>x.id!==id)));deleteChat(id);}
export function editDescription(before:QueryResponse,after:QueryResponse,action?:string):string{
 if(action==='undo')return '직전 그래프 편집을 되돌렸습니다.';
 if(action==='redo')return '취소한 그래프 편집을 다시 적용했습니다.';
 const changes=after.outputSpec?.editChanges||[];
 if(changes.length)return changes.join('\n');
 const old=before.outputSpec?.chartState||{},next=after.outputSpec?.chartState||{};
 const fields=Object.keys(next).filter(k=>JSON.stringify(old[k])!==JSON.stringify(next[k]));
 const labels:Record<string,string>={title:'제목',subtitle:'부제',chart_type:'그래프 종류',legend_position:'범례 위치',series_colors:'데이터 색상',report:'보고서 설정',stickers:'그래프 기호'};
 return fields.length?Array.from(new Set(fields.map(k=>labels[k]||'그래프 표시 설정'))).map(label=>`${label}을 변경했습니다.`).join('\n'):'그래프 데이터를 조회하거나 표시 설정을 적용했습니다.';
}
