import test from 'node:test';import assert from 'node:assert/strict';import {resizeVisiblePlot} from './src/plotPanelLayout.ts';
const host=(shown=true)=>({isConnected:shown,getClientRects:()=>shown?[{}]:[],getBoundingClientRect:()=>({width:shown?100:0,height:shown?100:0})});
test('hidden plot is skipped',async()=>{let calls=0;assert.equal(await resizeVisiblePlot(host(false),async()=>{calls++}),false);assert.equal(calls,0)});
test('plot hidden during pending resize is not an unhandled failure',async()=>{const e=host();assert.equal(await resizeVisiblePlot(e,async()=>{e.isConnected=false;throw Error('hidden')}),false)});
test('visible resize errors remain visible to the caller',async()=>{await assert.rejects(resizeVisiblePlot(host(),async()=>{throw Error('actual error')}),/actual error/)});
