import test from 'node:test';
import assert from 'node:assert/strict';
import {markBounds,moveMark,resizeMark} from './src/sketchTransform.ts';

const base={id:'m',tool:'rectangle',text:'수정',target:'chart',points:[{x:.2,y:.2},{x:.4,y:.4}],selection:{label:'A',scope:'segment',start:'202401',end:'202402'}};
for(const tool of ['pen','arrow','rectangle','text']) {
  test(`${tool}: move clears stale date selection and preserves content`,()=>{
    const mark={...base,tool,points:tool==='text'?[base.points[0]]:base.points};
    const copy=structuredClone(mark),next=moveMark(mark,.1,.1);
    assert.ok(Math.abs(next.points[0].x-.3)<1e-9);
    assert.equal(next.selection,undefined);assert.equal(next.id,'m');assert.equal(next.text,'수정');assert.deepEqual(mark,copy);
  });
  test(`${tool}: resize stays finite and within viewport`,()=>{
    const next=resizeMark({...base,tool,points:tool==='text'?[base.points[0]]:base.points},'se',.7,.7);
    assert.equal(next.selection,undefined);
    assert.ok(next.points.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)&&p.x>=0&&p.x<=1&&p.y>=0&&p.y<=1));
    if(tool==='text')assert.ok(next.textSize>22);
    else assert.ok(Math.abs(next.points[1].x-.7)<1e-9);
  });
}
test('move clamps the whole object without distorting it',()=>{
  const next=moveMark(base,2,-2),b=markBounds(next);
  assert.ok(Math.abs(b.right-1)<1e-9);assert.equal(b.top,0);
  assert.ok(Math.abs(next.points[1].x-next.points[0].x-.2)<1e-9);
});
test('horizontal arrows and zero-size strokes resize without NaN',()=>{
  for(const points of [[{x:.2,y:.2},{x:.4,y:.2}],[{x:.2,y:.2},{x:.2,y:.2}]]){
    const next=resizeMark({...base,tool:'arrow',points},'se',.5,.5);
    assert.ok(next.points.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)));
  }
});
