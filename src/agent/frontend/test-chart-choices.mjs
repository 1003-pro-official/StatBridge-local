import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {allowedCharts,blockedCharts,chartLabels} from './src/chartChoices.ts';

test('Plotly multiline text and SVG legends are isolated from fallback chart CSS',()=>{
  const css=readFileSync(new URL('./src/styles.css',import.meta.url),'utf8');
  assert.match(css,/\.plotly-chart tspan\.line\s*\{\s*fill:\s*inherit;\s*stroke:\s*none;/);
  assert.match(css,/\.plotly-chart \.legend\s*\{\s*display:\s*inline;/);
});

test('blocked list is separate and preserves precise backend reasons',()=>{
  const blocked=blockedCharts(['line','scatter'],{bubble:'현재 2개입니다. 1개 지표를 추가 조회해 주세요.'});
  assert.equal(blocked.length,11);
  assert.ok(!blocked.some(item=>item.type==='line'||item.type==='scatter'));
  assert.equal(blocked.find(item=>item.type==='bubble').reason,'현재 2개입니다. 1개 지표를 추가 조회해 주세요.');
});
test('missing capability information never fabricates support',()=>{
  assert.equal(blockedCharts().length,13);
  assert.match(blockedCharts()[0].reason,/정보가 없습니다/);
});
import {inferMarkTarget} from './src/sketchRequest.ts';
test('selector uses backend choices, never the full catalogue',()=>assert.deepEqual(allowedCharts(['bar','line']),['bar','line']));
test('missing capability metadata fails closed',()=>assert.deepEqual(allowedCharts(),[]));
test('choices are deduplicated and unknown types dropped',()=>assert.deepEqual(allowedCharts(['bar','unknown','bar']),['bar']));
test('user facing labels are Korean',()=>assert.equal(chartLabels.bubble,'버블 그래프'));
const mark={id:'m',tool:'rectangle',target:'chart',text:'오른쪽 위로 위치 이동 시켜줘',points:[{x:.1,y:.1},{x:.3,y:.2}]};
test('rectangle on rendered legend resolves to legend',()=>assert.equal(inferMarkTarget(mark,{left:.09,right:.31,top:.09,bottom:.21}).target,'legend'));
test('unrelated rectangle is not guessed',()=>assert.equal(inferMarkTarget(mark,{left:.5,right:.8,top:.5,bottom:.8}).target,'chart'));
test('explicit title request becomes title without observations',()=>assert.equal(inferMarkTarget({...mark,tool:'text',text:'제목을 만들어서 이 위치에 넣어줘'}).target,'title'));
test('explicit series target is respected',()=>assert.equal(inferMarkTarget({...mark,target:'series'}).target,'series'));
