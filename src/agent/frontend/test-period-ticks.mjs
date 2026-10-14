import {test} from 'node:test';
import assert from 'node:assert/strict';
import {periodTickUpdate} from './src/periodTicks.ts';
test('narrow date axes avoid a crowded last tick and keep original observations',()=>{
 const periods=Array.from({length:24},(_,i)=>`${2024+Math.floor(i/12)}${String(i%12+1).padStart(2,'0')}`);
 const figure={layout:{margin:{l:65,r:95},font:{size:13},xaxis:{type:'category',categoryarray:periods,ticktext:['2024-01','2025-12']}}};
 const before=JSON.stringify(figure),result=periodTickUpdate(figure,520);
 const ticks=result['xaxis.tickvals'];assert.equal(ticks[0],0);assert.equal(ticks.at(-1),23);
 assert.ok(ticks.length<=6);assert.ok(ticks.every((n,i)=>i===0||n-ticks[i-1]>=5));
 assert.equal(result['xaxis.ticktext'].at(-1),'2025-12');assert.equal(JSON.stringify(figure),before);
 figure.layout.xaxis.dtick=1;assert.deepEqual(periodTickUpdate(figure,520),{});
});
