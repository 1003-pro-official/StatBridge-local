import test from 'node:test';
import assert from 'node:assert/strict';
import {tableCell,tableInstruction,wantsReportTable,tableFrequencyMatches} from './src/reportTable.ts';
test('annual A and Y codes both accept years, but months and quarters are not aggregated',()=>{
 assert.equal(tableFrequencyMatches('A','Y'),true);assert.equal(tableFrequencyMatches('Y','Y'),true);
 assert.equal(tableFrequencyMatches('M','Y'),false);assert.equal(tableFrequencyMatches('Q','M'),false);
});
test('report requests open the table while statistical catalog mentions remain graphs',()=>{
 assert.equal(wantsReportTable('2024년 지표를 표로 보여줘'),true);
 assert.equal(wantsReportTable('보고서용 표를 만들어줘'),true);
 assert.equal(wantsReportTable('통계표에서 선 그래프를 그려줘'),false);
});
test('missing and zero remain different, decimals only affect display',()=>{
 assert.equal(tableCell(null,2),'—');assert.equal(tableCell(0,2),'0.00');assert.equal(tableCell(1.234567,2),'1.23');
});
test('table instructions preserve observations and ambiguous edits need clarification',()=>{
 assert.deepEqual(tableInstruction('소수점 한 자리로 바꿔줘'),{decimals:1});
 assert.deepEqual(tableInstruction('소수점 일 자리로 바꿔줘'),{decimals:1});
 assert.deepEqual(tableInstruction('최근 12개월만 보여줘'),{recent_periods:12});
 assert.deepEqual(tableInstruction('기간을 행으로 바꿔줘'),{orientation:'periods'});
 for(const text of ['숫자를 100으로 바꿔줘','최근 12개월 합계 보여줘','소수점 7자리로 바꿔줘','국가를 행으로 바꾸고 값을 두 배로 해줘'])assert.equal(tableInstruction(text),null);
});

test('all six pack templates can be selected with deterministic table instructions',()=>{
 for(let n=1;n<=6;n++)assert.deepEqual(tableInstruction(`BOK-T0${n}로 바꿔줘`),{template:`BOK-T0${n}`});
 assert.equal(tableInstruction('BOK-T07로 바꿔줘'),null);
});
