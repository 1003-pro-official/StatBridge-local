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
test('unsaved chats stay memory-only and explicit saves report quota errors',()=>{
 let notified=false;window.addEventListener('statbridge:chat-storage-error',()=>{notified=true;},{once:true});
 full=true;chat.appendChat('quota',{role:'user',text:'유지할 요청'});assert.equal(chat.readChat('quota')[0].text,'유지할 요청');assert.equal(notified,false);assert.equal(values.has(globalThis.__chatTestAccountKey('statbridge.graph-chat.quota')),false);assert.throws(()=>chat.saveChat({...result,editSessionId:'quota'}));full=false;
});
test('audit uses verified changes and distinct undo/redo descriptions',()=>{
 assert.equal(chat.editDescription(result,{...result,outputSpec:{editChanges:['제목을 변경했습니다.']}}),'제목을 변경했습니다.');
 assert.match(chat.editDescription(result,result,'undo'),/되돌렸/);assert.match(chat.editDescription(result,result,'redo'),/다시 적용/);
});
test('saved chat writes cap records at five without an overflow cache',()=>{
 account='overflow';
 for(let i=0;i<8;i++)chat.saveChat({...result,editSessionId:'overflow-'+i});
 assert.equal(chat.savedChats().length,5);assert.equal(chat.allSavedChats().length,5);
 const active=JSON.parse(values.get(globalThis.__chatTestAccountKey('statbridge.saved-chats')));assert.equal(active.length,5);
 chat.saveChat({...result,editSessionId:'overflow-7'});assert.equal(chat.allSavedChats().length,5);
 account='isolated';assert.deepEqual(chat.allSavedChats(),[]);account='overflow';
 chat.removeSavedChat('overflow-7');assert.equal(chat.allSavedChats().length,4);assert.equal(chat.savedChats().length,4);
});
test('legacy overflow is pruned and archive removed',()=>{
 account='legacy';const key=globalThis.__chatTestAccountKey('statbridge.saved-chats');
 const legacy=Array.from({length:7},(_,i)=>({id:'old-'+i,title:'old',savedAt:i,result,messages:[]}));values.set(key,JSON.stringify(legacy));
 values.set(globalThis.__chatTestAccountKey('statbridge.saved-chats.archive'),JSON.stringify(legacy));
 assert.equal(chat.allSavedChats().length,5);assert.equal(JSON.parse(values.get(key)).length,5);
 assert.equal(values.has(globalThis.__chatTestAccountKey('statbridge.saved-chats.archive')),false);
});
