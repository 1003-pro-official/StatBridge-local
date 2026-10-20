import test from 'node:test';
import assert from 'node:assert/strict';
import {annotationMove,bindAnnotationDrag} from './src/annotationDrag.ts';
const note={id:'text',x:.5,y:.8};
test('right/down pointer movement becomes paper right/lower coordinates',()=>{const move=annotationMove(note,100,50,500,250);assert.equal(move.params.x,.7);assert.ok(Math.abs(move.params.y-.6)<1e-12);});
test('paper text stays inside the plotting frame',()=>{assert.deepEqual(annotationMove(note,10000,-10000,500,250).params,{x:1,y:1});assert.deepEqual(annotationMove(note,-10000,10000,500,250).params,{x:0,y:0});});
test('anchored labels retain their data anchor and move only the pixel offset',()=>{const result=annotationMove({...note,label:'actual series',x_shift:20,y_shift:30},50,10,500,250);assert.deepEqual(result.params,{x_shift:70,y_shift:20});assert.ok(!('x' in result.params));});
test('anchored labels respect the validated offset limit',()=>{assert.deepEqual(annotationMove({...note,label:'actual series'},1000,-1000,500,250).params,{x_shift:400,y_shift:400});});
test('invalid or missing plot geometry fails closed',()=>{for(const [w,h] of [[0,250],[500,0],[NaN,250]])assert.throws(()=>annotationMove(note,20,30,w,h));});
test('drag projection does not mutate saved text or positions',()=>{const before=structuredClone(note);annotationMove(note,30,40,500,250);assert.deepEqual(note,before);});

function harness(t,{known=true,accepted=true}={}){
 const oldElement=globalThis.Element,oldWindow=globalThis.window,oldObserver=globalThis.MutationObserver;
 class FakeElement extends EventTarget{
  attrs=new Map();classes=new Set();classList={add:(name)=>this.classes.add(name),remove:(name)=>this.classes.delete(name)};
  closest(selector){return this.matches?.[selector]||null;}
  getAttribute(name){return this.attrs.get(name)??null;}setAttribute(name,value){this.attrs.set(name,String(value));}
 }
 globalThis.Element=FakeElement;const win=new EventTarget();globalThis.window=win;globalThis.MutationObserver=class{observe(){}disconnect(){}};
 const stage=new FakeElement(),plot=new FakeElement(),group=new FakeElement(),text=new FakeElement();
 stage.contains=()=>true;stage.querySelectorAll=()=>[text];stage.capture=null;stage.setPointerCapture=id=>stage.capture=id;stage.hasPointerCapture=id=>stage.capture===id;stage.releasePointerCapture=()=>stage.capture=null;
 plot._fullLayout={width:500,height:250,_size:{w:500,h:250},annotations:[{name:known?'text':'automatic-latest-value'}]};plot.getBoundingClientRect=()=>({width:500,height:250});
 group.setAttribute('data-index','0');group.matches={'.js-plotly-plot':plot};text.matches={'.annotation-text-g':text,'g.annotation':group};text.setAttribute('transform','rotate(0,250,50)');
 const commits=[],errors=[];const cleanup=bindAnnotationDrag(stage,[note],async(id,params)=>{commits.push({id,params});return accepted;},message=>errors.push(message));
 t.after(()=>{cleanup();globalThis.Element=oldElement;globalThis.window=oldWindow;globalThis.MutationObserver=oldObserver;});
 function fire(type,values={}){const event=new Event(type,{cancelable:true});Object.assign(event,{pointerId:1,button:0,clientX:100,clientY:100,...values});Object.defineProperty(event,'target',{value:text});(type==='pointerdown'?stage:win).dispatchEvent(event);}
 return {fire,text,stage,commits,errors,cleanup};
}
test('mouse movement previews locally and release commits exactly once',async t=>{const h=harness(t);h.fire('pointerdown');h.fire('pointermove',{clientX:200,clientY:150});assert.match(h.text.getAttribute('transform'),/^translate/);assert.equal(h.commits.length,0);h.fire('pointerup',{clientX:200,clientY:150});assert.equal(h.commits.length,1);assert.equal(h.commits[0].id,'text');assert.equal(h.commits[0].params.x,.7);});
test('a text click without dragging does not call the backend',t=>{const h=harness(t);h.fire('pointerdown');h.fire('pointerup');assert.equal(h.commits.length,0);});
test('Escape cancels the preview and preserves the original transform',t=>{const h=harness(t);h.fire('pointerdown');h.fire('pointermove',{clientX:200});h.fire('keydown',{key:'Escape'});h.fire('pointerup',{clientX:200});assert.equal(h.text.getAttribute('transform'),'rotate(0,250,50)');assert.equal(h.commits.length,0);});
for(const type of ['pointercancel','blur','cleanup'])test(`${type} does not save a partial drag`,t=>{const h=harness(t);h.fire('pointerdown');h.fire('pointermove',{clientX:200});if(type==='cleanup')h.cleanup();else h.fire(type);h.fire('pointerup',{clientX:200});assert.equal(h.commits.length,0);});
test('automatic value labels and captions cannot be moved as user text',t=>{const h=harness(t,{known:false});h.fire('pointerdown');h.fire('pointerup',{clientX:200});assert.equal(h.commits.length,0);});
test('rejected saves restore the original position and expose failure',async t=>{const h=harness(t,{accepted:false});h.fire('pointerdown');h.fire('pointerup',{clientX:200});await new Promise(resolve=>setImmediate(resolve));assert.equal(h.commits.length,1);assert.equal(h.errors.length,1);assert.equal(h.text.getAttribute('transform'),'rotate(0,250,50)');});
