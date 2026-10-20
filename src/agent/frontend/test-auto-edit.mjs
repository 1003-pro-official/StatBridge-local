import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
let values=[];
globalThis.__autoEditState=v=>{let current=v;return [v,next=>{current=typeof next==='function'?next(current):next;values.push(current);}];};
registerHooks({resolve(s,c,next){if(s==='react'&&c.parentURL?.endsWith('/useAutoEdit.ts'))return {url:'data:text/javascript,export const useRef=v=>({current:v});export const useEffect=()=>{};export const useState=globalThis.__autoEditState;',shortCircuit:true};return next(s,c);}});
const {useAutoEdit}=await import('./src/useAutoEdit.ts');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
test('latest debounced setting is the only dispatched edit',async()=>{
 const calls=[];const auto=useAutoEdit(async x=>{calls.push(x);return true;});
 auto.schedule({instruction:'old'});auto.schedule({instruction:'latest'});auto.flush();await tick();
 assert.deepEqual(calls,[{instruction:'latest'}]);assert.equal(auto.pending('settings'),false);
});
test('false result is an error and settles pending state',async()=>{
 values=[];const auto=useAutoEdit(async()=>false);auto.schedule({instruction:''});auto.flush();await tick();
 assert(values.some(v=>typeof v==='string'&&v.includes('적용하지 못했습니다')));assert.equal(auto.pending('settings'),false);
});
test('exception is surfaced without leaving pending state',async()=>{
 values=[];const auto=useAutoEdit(async()=>{throw new Error('rejected');});auto.schedule({instruction:''});auto.flush();await tick();
 assert(values.includes('rejected'));assert.equal(auto.pending('settings'),false);
});
test('cancel prevents invalid draft from being submitted',async()=>{
 let calls=0;const auto=useAutoEdit(async()=>{calls++;return true;});auto.schedule({instruction:''});auto.cancel('settings');auto.flush();await tick();assert.equal(calls,0);
});
