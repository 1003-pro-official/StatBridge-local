import test from 'node:test';
import assert from 'node:assert/strict';
import {edgeSpeed,installSheetAutoScroll} from './src/tableSheetAutoScroll.ts';
test('edge speed is bounded, symmetric and idle in the centre',()=>{
 assert.equal(edgeSpeed(150,0,300),0);assert.equal(edgeSpeed(-100,0,300),-22);assert.equal(edgeSpeed(400,0,300),22);
 assert.equal(edgeSpeed(10,0,300),-edgeSpeed(290,0,300));assert.equal(edgeSpeed(0,0,0),0);
});
function fixture(){
 const listeners=new Map(),frames=new Map();let seq=0;const selected=[];
 globalThis.window={addEventListener:(k,f)=>listeners.set(k,f),removeEventListener:(k,f)=>{if(listeners.get(k)===f)listeners.delete(k);}};
 globalThis.requestAnimationFrame=f=>{frames.set(++seq,f);return seq;};globalThis.cancelAnimationFrame=id=>frames.delete(id);
 const grid={scrollLeft:0,scrollTop:0,clientWidth:300,clientHeight:200,getBoundingClientRect:()=>({left:0,top:0}),contains:()=>true,querySelector:()=>null};
 globalThis.document={elementFromPoint:(x,y)=>({closest:()=>({dataset:{sheetRow:String(Math.floor((grid.scrollTop+y)/30)),sheetColumn:String(Math.floor((grid.scrollLeft+x)/50))}})})};
 const controller=installSheetAutoScroll(grid,(r,c)=>selected.push([r,c]));
 const tick=t=>{const pending=[...frames.values()];frames.clear();pending.forEach(f=>f(t));};
 return {grid,controller,listeners,frames,selected,tick};
}
test('stationary pointer at right edge keeps scrolling and extends selection',()=>{
 const f=fixture();f.controller.start({clientX:299,clientY:80});f.tick(1);const initial=f.grid.scrollLeft;
 for(let t=17;t<180;t+=17)f.tick(t);
 assert(f.grid.scrollLeft>initial+100);assert(f.selected.at(-1)[1]>f.selected[0][1]);f.controller.dispose();assert.equal(f.frames.size,0);assert.equal(f.listeners.size,0);
});
test('left and top edges scroll back and skip sticky row/column gutters',()=>{
 const f=fixture();f.grid.scrollLeft=300;f.grid.scrollTop=300;f.controller.start({clientX:-30,clientY:-40});f.tick(1);
 assert(f.grid.scrollLeft<300&&f.grid.scrollTop<300);assert(f.selected.length);f.controller.dispose();
});
for(const reason of ['pointerup','pointercancel','blur'])test(reason+' stops scrolling immediately',()=>{
 const f=fixture();f.controller.start({clientX:299,clientY:199});f.tick(1);f.listeners.get(reason)({});const old=f.grid.scrollLeft;f.tick(100);assert.equal(f.grid.scrollLeft,old);assert.equal(f.frames.size,0);f.controller.dispose();
});
test('losing the primary button stops the drag',()=>{
 const f=fixture();f.controller.start({clientX:299,clientY:199});f.listeners.get('pointermove')({buttons:0});assert.equal(f.frames.size,0);f.controller.dispose();
});
