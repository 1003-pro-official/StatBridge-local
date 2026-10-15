import test from 'node:test';
import assert from 'node:assert/strict';
import {readableEditText} from './src/editText.ts';
test('old audit entries become readable without changing ordinary conversation',()=>{
 assert.equal(readableEditText('계열 스타일 · 대출금리: markers False'),'계열 스타일 · 대출금리: 관측점 표시를 껐습니다');
 assert.equal(readableEditText('그래프 종류: treemap'),'트리맵 형식으로 변경했습니다.');
 assert.equal(readableEditText('axis_styles: {"y":{"minimum":0}}'),'축 표시 설정을 변경했습니다.');
 assert.equal(readableEditText('관측점 표시를 껐습니다.'),'관측점 표시를 껐습니다.');
});
