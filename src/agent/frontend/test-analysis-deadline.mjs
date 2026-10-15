import test from 'node:test';
import assert from 'node:assert/strict';
import {withAnalysisDeadline,AnalysisTimeoutError,ANALYSIS_TIMEOUT_MS} from './src/analysisDeadline.ts';
import {analysisTimedOut} from './src/api/queryFailure.ts';
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
test('the production budget is 20 seconds and a fast response stays unchanged',async()=>{
 assert.equal(ANALYSIS_TIMEOUT_MS,20_000);
 const data={status:'need_clarification'};
 assert.equal(await withAnalysisDeadline(async()=>data),data);
});
test('timeout stops waiting even if the underlying task ignores cancellation',async()=>{
 let signal;let resolveLate;
 const action=new Promise(resolve=>{resolveLate=resolve;});
 const pending=withAnalysisDeadline(s=>{signal=s;return action;},undefined,30);
 await assert.rejects(pending,AnalysisTimeoutError);
 assert.equal(signal.aborted,true);
 resolveLate({status:'resolved'});await delay(10);
 await assert.rejects(pending,AnalysisTimeoutError);
});
test('query and automatic output consume one total budget',async()=>{
 let signal;const start=performance.now();
 await assert.rejects(withAnalysisDeadline(async s=>{signal=s;await delay(120);return withAnalysisDeadline(async inherited=>{assert.equal(inherited,s);await delay(120);return 'late';},s);},undefined,180),AnalysisTimeoutError);
 assert.equal(signal.aborted,true);assert.ok(performance.now()-start<400);
});
test('timeout is a recoverable request failure, never an unsupported statistic',()=>{
 const result=analysisTimedOut('대출금리와 생산자 물가를 비교해줘');
 assert.equal(result.query,'대출금리와 생산자 물가를 비교해줘');assert.equal(result.status,'request_failed');
 assert.equal(result.recovery.issue,'timeout');assert.equal(result.recovery.preserveState,true);
 assert.deepEqual(result.recovery.choices.map(x=>x.id),['table','revise','retry']);
 assert.equal(result.recovery.choices.some(x=>x.id==='period'),false);
});
