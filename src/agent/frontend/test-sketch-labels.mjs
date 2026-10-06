import test from 'node:test';
import assert from 'node:assert/strict';
import {sketchLabel,isDrawingStroke,periodLabel} from './src/sketchLabels.ts';

const mark={tool:'pen',points:[{x:.3,y:.4}]};
test('click and tiny jitter are not new drawings',()=>{
  assert.equal(isDrawingStroke(mark,900,500),false);
  assert.equal(isDrawingStroke({...mark,points:[...mark.points,{x:.301,y:.401}]},900,500),false);
});
test('real drag is a drawing',()=>assert.equal(isDrawingStroke({...mark,points:[...mark.points,{x:.35,y:.4}]},900,500),true));
test('tools have user facing Korean descriptions',()=>{
  assert.equal(sketchLabel('arrow'),'화살표 부분 수정');
  for(const tool of ['pen','arrow','rectangle','text'])assert.match(sketchLabel(tool),/부분 수정/);
});
test('text remains a deliberate placement',()=>assert.equal(isDrawingStroke({...mark,tool:'text'},900,500),true));
test('period labels respect the source frequency',()=>{
  assert.equal(periodLabel('202407','M'),'2024년 7월');
  assert.equal(periodLabel('202404','Q'),'2024년 4분기');
  assert.equal(periodLabel('202404'),'202404');
});
