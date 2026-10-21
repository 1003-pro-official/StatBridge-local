import test from 'node:test';
import assert from 'node:assert/strict';
import {setObservationAccount,observationRecords,recordObservation,subscribeObservations,captureObservation,recordClientFailure} from './src/executionObservations.ts';
const trace=i=>({traceId:i.toString(16).padStart(32,'0'),name:'request.edit',time:new Date().toISOString(),durationMs:2,status:'completed',langfuse:'not_configured',droppedSteps:0,steps:[]});
test('account changes clear in-memory records and stale replies cannot cross accounts',()=>{
 setObservationAccount(1);recordObservation(trace(1),1);assert.equal(observationRecords().length,1);
 setObservationAccount(2);assert.equal(observationRecords().length,0);recordObservation(trace(2),1);assert.equal(observationRecords().length,0);
 setObservationAccount(null);recordObservation(trace(3),null);assert.equal(observationRecords().length,0);
});
test('records are deduplicated and bounded without browser persistence',()=>{
 setObservationAccount(1);for(let i=1;i<=40;i++)recordObservation(trace(i),1);
 assert.equal(observationRecords().length,30);recordObservation(trace(40),1);assert.equal(observationRecords().length,30);
 recordObservation({...trace(50),steps:Array(129).fill({})},1);assert.equal(observationRecords().length,30);
});
test('subscriptions stop cleanly',()=>{
 let calls=0;const stop=subscribeObservations(()=>calls++);recordObservation(trace(55),1);assert.equal(calls,1);stop();recordObservation(trace(56),1);assert.equal(calls,1);
});
test('metadata is retrieved only with a valid trace header and correct account',async()=>{
 setObservationAccount(1);let calls=0;globalThis.fetch=async url=>{calls++;assert.match(url,/observability/);return new Response(JSON.stringify(trace(60)),{status:200});};
 await captureObservation(new Response('{}',{headers:{'X-StatBridge-Trace-Id':trace(60).traceId}}),'http://localhost/api',1);
 assert.equal(calls,1);assert.equal(observationRecords().at(-1).traceId,trace(60).traceId);
 await captureObservation(new Response('{}'),'http://localhost/api',1);assert.equal(calls,1);
 await captureObservation(new Response('{}',{headers:{'X-StatBridge-Trace-Id':trace(60).traceId}}),'http://localhost/api',2);assert.equal(calls,1);
});
test('observability failure never throws into the original request',async()=>{
 globalThis.fetch=async()=>{throw new Error('offline');};
 await captureObservation(new Response('{}',{headers:{'X-StatBridge-Trace-Id':trace(60).traceId}}),'http://localhost/api',1);
});

test('missing server response is labelled as browser-only, with no invented model count',()=>{
 setObservationAccount(9);recordClientFailure(9,new Date().toISOString(),42,new TypeError('secret-cannot-leak'));
 const row=observationRecords().at(-1);assert.equal(row.langfuse,'client_only');assert.equal(row.modelCalls,undefined);assert.equal(row.durationMs,42);assert(!JSON.stringify(row).includes('secret-cannot-leak'));
});
