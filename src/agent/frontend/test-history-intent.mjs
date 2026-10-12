import test from 'node:test';
import assert from 'node:assert/strict';
import {historyIntent} from './src/historyIntent.ts';
test('standalone natural undo and redo go through shared history',()=>{
 for(const text of ['방금 수정한 것만 취소해줘','마지막 작업을 취소해줘','이전 수정 취소','undo'])assert.equal(historyIntent(text),'undo',text);
 assert.equal(historyIntent('다시 실행해줘'),'redo');assert.equal(historyIntent('redo'),'redo');
});
test('combined edits are not swallowed by history routing',()=>{
 assert.equal(historyIntent('방금 수정 취소하고 제목을 바꿔줘'),null);
 assert.equal(historyIntent('취소라는 제목으로 바꿔줘'),null);
});
