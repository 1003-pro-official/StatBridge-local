import test from 'node:test';import assert from 'node:assert/strict';
import {withRequestDeadline,RequestTimeoutError} from './src/requestDeadline.ts';
import {recoveryFor} from './src/recoveryActions.ts';
test('stalled editing, saving and downloads release their queue with recovery choices',async()=>{
 for(const label of ['편집 요청','계정 저장 요청','표 다운로드 요청']){
  let signal;const started=Date.now();
  await assert.rejects(withRequestDeadline(s=>{signal=s;return new Promise(()=>{});},label,undefined,15),e=>{assert(e instanceof RequestTimeoutError);assert(e.message.includes(label));assert(recoveryFor(null,e.message).choices.some(c=>c.id==='retry'));return true;});
  assert(signal.aborted);assert(Date.now()-started<250);
  assert.equal(await withRequestDeadline(async()=>true,label,undefined,15),true);
 }
});
test('body read and a late result cannot silently finish a timed-out action',async()=>{
 let applied=false;
 await assert.rejects(withRequestDeadline(async()=>{await new Promise(r=>setTimeout(r,40));return 'late';},'편집 요청',undefined,10).then(()=>{applied=true;}),RequestTimeoutError);
 await new Promise(r=>setTimeout(r,50));assert.equal(applied,false);
});
test('provider rate limiting always offers retry',()=>{assert(recoveryFor(null,'KOSIS 호출 제한으로 대기 중입니다. 약 31초 후 다시 시도해 주세요.').choices.some(c=>c.id==='retry'));});

test('a caller signal without its own timer never disables the request deadline',async()=>{
 const parent=new AbortController();let child;
 await assert.rejects(withRequestDeadline(signal=>{child=signal;return new Promise(()=>{});},'목록 조회',parent.signal,10),RequestTimeoutError);
 assert(child.aborted);assert.equal(parent.signal.aborted,false);
});

test('an invalid server body becomes an actionable retry instead of parser code',async()=>{
 await assert.rejects(withRequestDeadline(async()=>JSON.parse('<html>broken proxy</html>'),'편집 요청'),error=>{assert(error.message.includes('서버 응답을 읽지'));assert(recoveryFor(null,error.message).choices.some(c=>c.id==='retry'));return true;});
});

test('rate-limit guidance wins over a legacy generic input recovery',()=>{
 const result={recovery:{issue:'input',question:'입력 수정',choices:[{id:'revise',label:'수정'}]}};
 assert(recoveryFor(result,'KOSIS 호출 제한으로 대기 중입니다. 31초 후 다시 시도해 주세요.').choices.some(c=>c.id==='retry'));
});
