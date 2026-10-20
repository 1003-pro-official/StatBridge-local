import {test} from 'node:test';
import assert from 'node:assert/strict';
import {periodTickUpdate} from './src/periodTicks.ts';

test('publication month labels survive responsive resizing',()=>{
 for(const meta of [{publicationYoy:true},{publicationAxes:true}]){
 const figure={layout:{meta,xaxis:{type:'category',categoryarray:['202401','202402','202403','202404','202405','202406','202407'],tickvals:[0,6],ticktext:['24.1','7']}}};
 const before=JSON.stringify(figure);
 for(const width of [400,650,1200])assert.deepEqual(periodTickUpdate(figure,width),{});
 assert.equal(JSON.stringify(figure),before);
 }
});
test('narrow date axes avoid a crowded last tick and keep original observations',()=>{
 const periods=Array.from({length:24},(_,i)=>`${2024+Math.floor(i/12)}${String(i%12+1).padStart(2,'0')}`);
 const figure={layout:{margin:{l:65,r:95},font:{size:13},xaxis:{type:'category',categoryarray:periods,ticktext:['2024-01','2025-12']}}};
 const before=JSON.stringify(figure),result=periodTickUpdate(figure,520);
 const ticks=result['xaxis.tickvals'];assert.equal(ticks[0],0);assert.equal(ticks.at(-1),23);
 assert.ok(ticks.length<=6);assert.ok(ticks.every((n,i)=>i===0||n-ticks[i-1]>=5));
 assert.equal(result['xaxis.ticktext'].at(-1),'2025-12');assert.equal(JSON.stringify(figure),before);
 figure.layout.xaxis.dtick=1;assert.deepEqual(periodTickUpdate(figure,520),{});
});

test('a mixed monthly category array cannot generate Q7 or Q12 ticks',()=>{
 const periods=Array.from({length:12},(_,i)=>`2024${String(i+1).padStart(2,'0')}`);
 const update=periodTickUpdate({layout:{xaxis:{type:'category',categoryarray:periods,ticktext:['2024 Q1','2024 Q4']}}},500);
 assert.ok(update['xaxis.ticktext'].every(t=>! /Q(?:[5-9]|1[0-2])/.test(t)));
});
