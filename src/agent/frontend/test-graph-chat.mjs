import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
let account='one';
globalThis.__chatTestAccountKey=key=>`${key}.account.${account}`;
registerHooks({resolve(specifier,context,next){if(specifier==='./accountApi'&&context.parentURL?.endsWith('/graphChat.ts'))return {url:'data:text/javascript,export const accountKey=globalThis.__chatTestAccountKey;',shortCircuit:true};return next(specifier,context);}});
const values=new Map();let full=false;
globalThis.localStorage={getItem:k=>values.get(k)??null,setItem(k,v){if(full)throw new Error('quota');values.set(k,v);},removeItem:k=>values.delete(k)};
globalThis.sessionStorage={getItem:()=>null,removeItem:()=>{}};
globalThis.window=new EventTarget();
const chat=await import('./src/graphChat.ts');
const result={editSessionId:'graph-1',query:'은행 통계',period:{start:'2021',end:'2025'},outputSpec:{chartState:{title:'제목'}}};
test('chat and edit audit survive reopen and stay isolated by account',()=>{
 chat.appendChat('graph-1',{role:'user',text:'제목을 바꿔 주세요'});
 chat.appendChat('graph-1',{role:'assistant',kind:'edit',text:'제목을 변경했습니다.'});
 assert.equal(chat.readChat('graph-1').length,2);
 chat.saveChat(result);
 account='two';assert.deepEqual(chat.readChat('graph-1'),[]);assert.deepEqual(chat.savedChats(),[]);
 account='one';const saved=chat.savedChats()[0];assert.equal(saved.messages.length,2);assert.equal(saved.result.query,result.query);
 chat.deleteChat('graph-1');assert.deepEqual(chat.readChat('graph-1'),[]);
 chat.writeChat(saved.id,saved.messages);assert.equal(chat.readChat('graph-1').length,2);
 chat.removeSavedChat(saved.id);assert.deepEqual(chat.savedChats(),[]);assert.deepEqual(chat.readChat(saved.id),[]);
});
test('quota errors retain live chat and report failed persistent writes',()=>{
 let notified=false;window.addEventListener('statbridge:chat-storage-error',()=>{notified=true;},{once:true});
 full=true;chat.appendChat('quota',{role:'user',text:'유지할 요청'});assert.equal(chat.readChat('quota')[0].text,'유지할 요청');assert.equal(notified,true);assert.throws(()=>chat.saveChat({...result,editSessionId:'quota'}));full=false;
});
test('audit uses verified changes and distinct undo/redo descriptions',()=>{
 assert.equal(chat.editDescription(result,{...result,outputSpec:{editChanges:['제목을 변경했습니다.']}}),'제목을 변경했습니다.');
 assert.match(chat.editDescription(result,result,'undo'),/되돌렸/);assert.match(chat.editDescription(result,result,'redo'),/다시 적용/);
});
