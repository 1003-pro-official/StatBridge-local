import test from 'node:test';
import assert from 'node:assert/strict';
import {workspaceHistoryAction} from './src/workspaceHistory.ts';

class ElementStub {
  constructor(editable=false){this.editable=editable;}
  closest(){return this.editable ? this : null;}
}
globalThis.Element=ElementStub;
const body=new ElementStub(), inside=new ElementStub(), outside=new ElementStub();
let modal=false;
const root={contains:node=>node===inside,ownerDocument:{body,querySelector:()=>modal?{}:null}};
const event=(overrides={})=>({target:inside,key:'z',ctrlKey:true,...overrides});

test('workspace undo and redo recognize Ctrl+Z and Ctrl+Y',()=>{
  assert.equal(workspaceHistoryAction(event(),root),'undo');
  assert.equal(workspaceHistoryAction(event({key:'Y'}),root),'redo');
  assert.equal(workspaceHistoryAction(event({target:body}),root),'undo');
});
test('native text editing, unrelated controls and dialogs retain their shortcuts',()=>{
  assert.equal(workspaceHistoryAction(event({target:new ElementStub(true)}),root),null);
  assert.equal(workspaceHistoryAction(event({target:outside}),root),null);
  modal=true;
  try{assert.equal(workspaceHistoryAction(event(),root),null);}finally{modal=false;}
});
test('repeat, composition, consumed events and other combinations are ignored',()=>{
  for(const change of [{repeat:true},{isComposing:true},{defaultPrevented:true},{ctrlKey:false},{altKey:true},{metaKey:true},{shiftKey:true},{key:'x'},{target:null}])
    assert.equal(workspaceHistoryAction(event(change),root),null,JSON.stringify(change));
});
