import test from 'node:test';
import assert from 'node:assert/strict';
import {canMix,isMixed,mixedCommands,mixedChoices,mixedPresets,mixedSelection,seriesKind,canRegression} from './src/mixedChart.ts';
const series=[{label:'금리',unit:'%',frequency:'M',points:[{date:'202401',value:1},{date:'202402',value:2}]},{label:'금액',unit:'억원',frequency:'M',points:[{date:'202401',value:1},{date:'202402',value:2}]}];
test('mixed menu requires two series, supported line/bar and compatible frequencies/units',()=>{
 assert.equal(canMix(series,['line','bar']),true);
 assert.equal(canMix(series,[]),false);assert.equal(canMix(series.slice(0,1),['line','bar']),false);
 assert.equal(canMix([series[0],{...series[1],frequency:'Q'}],['line','bar']),false);
 assert.equal(canMix([...series,{label:'물가',unit:'지수',frequency:'M',points:[{date:'202401',value:1},{date:'202402',value:2}]}],['line','bar']),false);
});
test('two units select a deterministic right axis; same-unit series use one axis',()=>{
 const commands=mixedCommands(series);
 assert.equal(commands.length,5);assert.equal(commands[0].value,'line');
 assert.deepEqual(commands[3].params.patch,{kind:'dual_axis',right_axis:['금액']});
 const same=mixedCommands(series.map(s=>({...s,unit:'%'})));
 assert.equal(same[3].operation,'set_series_chart_types');assert.deepEqual(same[3].params.types,{금리:'line',금액:'bar'});
 const many=mixedCommands(Array.from({length:10},(_,i)=>({...series[0],label:`항목${i}`})));
 assert.equal(many.length,4);
});
test('mixed status respects both report defaults and explicit per-series choices',()=>{
 const state={chart_type:'line',report:{kind:'dual_axis',right_axis:['금액']}};
 assert.equal(isMixed(state,series),true);assert.equal(seriesKind(state,'금액'),'bar');
 assert.equal(isMixed({...state,series_chart_types:{금액:'line'}},series),false);
});

test('all seven supported compositions use bounded commands and faithful per-series shapes',()=>{
 const data=Array.from({length:10},(_,i)=>({...series[0],label:`항목${i}`,points:[{date:'202401',value:i},{date:'202402',value:i+1}]}));
 assert.equal(mixedChoices(data,['line','bar','area','stacked_bar']).length,7);
 for(const preset of mixedPresets){
  const commands=mixedCommands(data,preset.id),mapping=commands.at(-1).params.types;
  assert.equal(commands.length,4);assert.equal(Object.keys(mapping).length,10);
  assert.deepEqual(new Set(Object.values(mapping)),new Set(preset.shapes));
  assert.equal(mixedSelection({chart_type:preset.shapes[0],series_chart_types:mapping,presentation:commands[2].params},data),preset.id);
 }
 assert.equal(mixedChoices(data.slice(0,2),['line','bar','area','stacked_bar']).length,3);
 const missing=[data[0],{...data[1],points:[]},data[2]];
 assert.equal(mixedChoices(missing,['line','bar','area','stacked_bar']).some(p=>p.stack),false);
 assert.equal(mixedChoices(series,['line','bar','area','stacked_bar']).some(p=>p.stack),false);
});

test('scatter plus regression requires actual paired observations and a varying predictor',()=>{
 const data=series.map(s=>({...s,points:[{date:'202401',value:1},{date:'202402',value:2},{date:'202403',value:3}]}));
 assert.equal(canRegression(data,['scatter']),true);
 assert.equal(canRegression(data,[]),false);assert.equal(canRegression([...data,data[0]],['scatter']),false);
 assert.equal(canRegression(series,['scatter']),false);
 assert.equal(canRegression([{...data[0],points:data[0].points.map(p=>({...p,value:1}))},data[1]],['scatter']),false);
});
