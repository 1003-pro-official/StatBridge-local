import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {clampPosition,initialPosition,panelPosition,isDrag} from './src/sujeongiPosition.mjs';
const viewport={width:1280,height:720};
test('drag clamps all viewport edges, including small screens',()=>{
  assert.deepEqual(clampPosition({x:-30,y:900},viewport),{x:0,y:600});
  assert.deepEqual(clampPosition({x:900,y:-3},{width:320,height:480}),{x:160,y:0});
  assert.deepEqual(clampPosition({x:10,y:10},{width:100,height:80}),{x:0,y:0});
});
test('saved position is validated and clamped after resize',()=>{
  assert.deepEqual(initialPosition(viewport,{x:10000,y:10000}),{x:1120,y:600});
  assert.deepEqual(initialPosition(viewport,{x:'bad',y:3}),{x:1104,y:584});
  assert.deepEqual(initialPosition(viewport,42),{x:1104,y:584});
});
test('drag threshold distinguishes clicks from mouse/touch movement',()=>{
  assert.equal(isDrag(3,3),false);assert.equal(isDrag(7,0),true);
});
test('chat stays in the viewport at each corner and on mobile',()=>{
  for(const screen of [viewport,{width:320,height:480}])
    for(const point of [{x:0,y:0},{x:screen.width,y:0},{x:0,y:screen.height},{x:screen.width,y:screen.height}]){
      const panel=panelPosition(point,screen);
      assert.ok(panel.left>=12&&panel.top>=12);
      assert.ok(panel.left+panel.width<=screen.width-12);
      assert.ok(panel.top+panel.maxHeight<=screen.height-12);
    }
});
test('new character only, guide PNG, capture/cancel and click suppression are connected',()=>{
  const source=readFileSync(new URL('./src/Sujeongi.tsx',import.meta.url),'utf8');
  assert.ok(!source.includes('<span>수정이</span>')&&!source.includes('<svg'));
  for(const text of ['setPointerCapture','onPointerCancel','onLostPointerCapture','skipClick.current','ArrowLeft','localStorage.setItem'])assert.ok(source.includes(text));
  for(const name of ['sujeongi-all-actions.gif','sujeongi-working.gif','guide.png'])assert.ok(existsSync(new URL('./public/sujeongi/'+name,import.meta.url)));
  const editor=readFileSync(new URL('./src/ChartSketchEditor.tsx',import.meta.url),'utf8');
  assert.ok(editor.includes('수정은 수정이에게 지시하세요'));
});
