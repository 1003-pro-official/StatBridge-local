import test from 'node:test';
import assert from 'node:assert/strict';
import {resolveMarkSelection, graphHitPoints} from './src/chartSelection.ts';

const points=[{label:'A',period:'202401',x:10,y:50,trace:0,connected:true},
  {label:'A',period:'202402',x:40,y:20,trace:0,connected:true},
  {label:'A',period:'202403',x:80,y:60,trace:0,connected:true}];
const arrow={id:'1',tool:'arrow',target:'chart',text:'red',points:[{x:.8,y:.2},{x:.6,y:.4}]};
test('arrow tip binds nearest actual edge, not full series',()=>{
  assert.deepEqual(resolveMarkSelection(arrow,points,100,100,'segment'),{label:'A',scope:'segment',start:'202402',end:'202403'});
});
test('point binds one observation',()=>{
  assert.equal(resolveMarkSelection({...arrow,points:[{x:.4,y:.2}]},points,100,100,'point').start,'202402');
});
test('rectangle selects actual interval',()=>{
  assert.deepEqual(resolveMarkSelection({...arrow,tool:'rectangle',points:[{x:.3,y:.1},{x:.9,y:.7}]},points,100,100,'segment'),{label:'A',scope:'segment',start:'202402',end:'202403'});
});
test('crossing labels fail closed unless target chosen',()=>{
  const crossing=points.concat(points.map(p=>({...p,label:'B',trace:1})));
  assert.throws(()=>resolveMarkSelection(arrow,crossing,100,100,'segment'),/겹친/);
  assert.equal(resolveMarkSelection({...arrow,target:'A'},crossing,100,100,'segment').label,'A');
});
test('unrelated screen position is not guessed',()=>{
  assert.throws(()=>resolveMarkSelection({...arrow,points:[{x:0,y:1}]},points,100,100,'segment'));
});
test('missing Plotly projection supports manual selection only',()=>{
  const stage={getBoundingClientRect:()=>({left:0,top:0,width:100,height:100})};
  assert.deepEqual(graphHitPoints({...stage,data:[]},stage),[]);
});
test('category dates project using category indexes, not numeric date strings',()=>{
  const stage={getBoundingClientRect:()=>({left:0,top:0,width:100,height:100})};
  const axis={type:'category',_categories:['202401','202402'],_offset:0,d2p:Number,l2p:i=>10+i*30};
  const plot={...stage,_fullLayout:{xaxis:axis,yaxis:{_offset:0,d2p:Number}},data:[{x:['202401','202402'],y:[20,30],customdata:[['A','202401'],['A','202402']],mode:'lines'}]};
  assert.deepEqual(graphHitPoints(plot,stage).map(p=>p.x),[10,40]);
});
