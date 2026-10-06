import test from 'node:test';
import assert from 'node:assert/strict';
import {bindMarks,changeMarkTarget} from './src/sketchRequest.ts';
const range={label:'series',scope:'segment',start:'202401',end:'202402'};
const mark={id:'m',tool:'text',target:'chart',text:'instruction',points:[{x:.4,y:.2}]};
test('axis/title/legend never borrow observation selections',()=>{
  for(const target of ['title','legend','x_axis','y_axis'])assert.equal(bindMarks([{...mark,target}],range)[0].selection,undefined);
});
test('changing target drops stale selection but preserves drawing',()=>{
  const changed=changeMarkTarget({...mark,selection:range},'title');
  assert.equal(changed.selection,undefined);assert.deepEqual(changed.points,mark.points);
});
test('unrelated series never borrows manual range',()=>assert.equal(bindMarks([{...mark,target:'other'}],range)[0].selection,undefined));
test('explicit range never overwritten by another manual interval',()=>assert.deepEqual(bindMarks([{...mark,selection:range}],{...range,end:'202405'})[0].selection,range));
test('matching series binds manual range',()=>assert.deepEqual(bindMarks([{...mark,target:'series'}],range)[0].selection,range));
test('multiple drawings require individual interval binding',()=>assert.ok(bindMarks([mark,{...mark,id:'other'}],range).every(m=>!m.selection)));
