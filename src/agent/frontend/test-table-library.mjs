import test from 'node:test';
import assert from 'node:assert/strict';
import {analysisEntries,olderAnalysisEntries} from './src/analysisLibrary.ts';
test('latest five merge local and server by ID; older records remain separately accessible',()=>{
 const local=Array.from({length:8},(_,i)=>({id:'l'+i,title:'local '+i,savedAt:10000+i,result:{},messages:[]}));
 const account=[{id:'l7',title:'server',saved_at:10},{id:'remote',title:'remote',saved_at:20}];
 const active=analysisEntries(local,account),older=olderAnalysisEntries(local,account);
 assert.equal(active.length,5);assert.equal(active[0].id,'remote');assert.equal(older.length,4);assert.equal(new Set([...active,...older].map(x=>x.id)).size,9);assert.equal(local.length,8);
});
