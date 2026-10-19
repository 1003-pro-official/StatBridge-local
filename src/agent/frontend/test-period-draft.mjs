import test from 'node:test';
import assert from 'node:assert/strict';
import {periodDraft} from './src/periodDraft.ts';
test('submitted dates override a previously displayed period without reinterpretation',()=>{
 const stale={start:'2023-01-01',end:'2024-12-31'};
 const data=new FormData();data.set('period_start','2023-07-01');data.set('period_end','2024-06-30');
 assert.deepEqual(periodDraft(data),{start:'2023-07-01',end:'2024-06-30',instruction:'기간을 2023-07-01부터 2024-06-30까지로 변경해줘'});
 assert.equal(stale.start,'2023-01-01');
});
test('empty, reversed and impossible calendar dates never request recalculation',()=>{
 for(const [start,end] of [['','2024-01-01'],['2024-12-01','2023-01-01'],['2023-02-29','2023-03-01'],['2024-13-01','2025-01-01']]){
  const data=new Map([['period_start',start],['period_end',end]]);assert.throws(()=>periodDraft(data),/시작일/);
 }
});
test('valid leap day and equal endpoints stay exact',()=>{
 const data=new Map([['period_start','2024-02-29'],['period_end','2024-02-29']]);
 assert.equal(periodDraft(data).start,'2024-02-29');
});
