import type {ChartEditInput,ChartSeries,ChartType} from './api/types';
type Shape='line'|'bar'|'area';
export type MixedState={chart_type?:string;layout?:string;series_chart_types?:Record<string,string>;presentation?:{bar_mode?:string};report?:{kind?:string;right_axis?:string[]}};
export const mixedPresets=[
 {id:'mixed',name:'선 · 막대 혼합 차트',shapes:['line','bar'],stack:false},
 {id:'mixed_line_area',name:'선 · 영역 혼합 차트',shapes:['line','area'],stack:false},
 {id:'mixed_bar_area',name:'막대 · 영역 혼합 차트',shapes:['bar','area'],stack:false},
 {id:'mixed_all',name:'선 · 막대 · 영역 혼합 차트',shapes:['line','bar','area'],stack:false},
 {id:'mixed_line_stack',name:'선 · 누적 막대 혼합 차트',shapes:['line','bar'],stack:true},
 {id:'mixed_area_stack',name:'영역 · 누적 막대 혼합 차트',shapes:['area','bar'],stack:true},
 {id:'mixed_all_stack',name:'선 · 영역 · 누적 막대 혼합 차트',shapes:['line','area','bar'],stack:true},
] as const;
export function mixedChoices(series:ChartSeries[],types:ChartType[]){
 if(series.some(s=>(s.points?.length??0)<2)||new Set(series.map(s=>s.frequency||'')).size!==1||new Set(series.map(s=>s.unit)).size>2)return [];
 return mixedPresets.filter(p=>series.length>=p.shapes.length+(p.stack?1:0)&&p.shapes.every(t=>types.includes(t))&&(!p.stack||(types.includes('stacked_bar')&&new Set(series.map(s=>s.unit)).size===1&&series.every(s=>JSON.stringify(s.points?.map(p=>p.date))===JSON.stringify(series[0].points?.map(p=>p.date))))));
}
export function canMix(series:ChartSeries[],types:ChartType[]){return mixedChoices(series,types).some(p=>p.id==='mixed');}
export function dualAxisCommands(series:ChartSeries[],state:MixedState&{secondary_axis_series?:string[]}={}):NonNullable<ChartEditInput['commands']>{
 if(!canMix(series,['line','bar']))throw new Error('이중축은 같은 주기의 지표 두 개 이상과 최대 두 종류의 단위가 필요합니다.');
 const units=[...new Set(series.map(s=>s.unit))];
 const existing=(state.secondary_axis_series?.length?state.secondary_axis_series:state.report?.right_axis??[]).filter(label=>series.some(s=>s.label===label));
 const rightUnit=units.find(u=>/[%％]/.test(u))??units.at(-1);
 const right=existing.length&&existing.length<series.length?existing:units.length===2?series.filter(s=>s.unit===rightUnit).map(s=>s.label):[series.at(-1)!.label];
 return [{operation:'set_chart_type',kind:'STYLE_EDIT',value:'line'},{operation:'set_layout',kind:'STYLE_EDIT',value:'combined'},
  {operation:'set_presentation',kind:'STYLE_EDIT',params:{shared_y:false,sync_y_axes:false,bar_mode:'group'}},
  {operation:'set_report',kind:'STYLE_EDIT',params:{patch:{kind:'dual_axis',right_axis:right}}},
  {operation:'set_series_chart_types',kind:'STYLE_EDIT',params:{types:Object.fromEntries(series.map(s=>[s.label,right.includes(s.label)?'bar':'line']))}}];
}
export function canRegression(series:ChartSeries[],types:ChartType[]){
 if(series.length!==2||!types.includes('scatter')||new Set(series.map(s=>s.frequency||'')).size!==1)return false;
 const second=new Set(series[1].points.map(p=>p.date)),pairs=series[0].points.filter(p=>second.has(p.date));
 return pairs.length>=3&&new Set(pairs.map(p=>p.value)).size>=2;
}
export function seriesKind(state:MixedState,label:string){return state.series_chart_types?.[label]??(state.report?.kind==='dual_axis'&&state.report.right_axis?.includes(label)?'bar':state.chart_type??'line');}
export function isMixed(state:MixedState,series:ChartSeries[]){const kinds=new Set(series.map(s=>seriesKind(state,s.label)));return kinds.size>1&&[...kinds].every(k=>['line','bar','area'].includes(k));}
export function mixedSelection(state:MixedState,series:ChartSeries[]){
 const kinds=new Set(series.map(s=>seriesKind(state,s.label))),stack=['stack','relative'].includes(state.presentation?.bar_mode??'');
 return mixedPresets.find(p=>p.stack===stack&&p.shapes.length===kinds.size&&p.shapes.every(k=>kinds.has(k)))?.id;
}
export function mixedCommands(series:ChartSeries[],presetId='mixed'):NonNullable<ChartEditInput['commands']>{
 const preset=mixedPresets.find(p=>p.id===presetId);
 if(!preset||series.length<preset.shapes.length+(preset.stack?1:0))throw new Error('이 조합에 필요한 지표를 먼저 조회해 주세요.');
 const mapping:Record<string,Shape>={};
 series.forEach((s,i)=>{mapping[s.label]=preset.stack?(i<preset.shapes.length-1?preset.shapes[i]:'bar'):i>=series.length-preset.shapes.length+1?preset.shapes[i-(series.length-preset.shapes.length)]:preset.shapes[0];});
 const commands:NonNullable<ChartEditInput['commands']>=[{operation:'set_chart_type',kind:'STYLE_EDIT',value:preset.shapes[0]},{operation:'set_layout',kind:'STYLE_EDIT',value:'combined'},{operation:'set_presentation',kind:'STYLE_EDIT',params:{shared_y:false,bar_mode:preset.stack?'relative':'group'}}];
 const right=series.filter(s=>s.unit!==series[0].unit).map(s=>s.label);
 if(right.length)commands.push({operation:'set_report',kind:'STYLE_EDIT',params:{patch:{kind:'dual_axis',right_axis:right}}});
 commands.push({operation:'set_series_chart_types',kind:'STYLE_EDIT',params:{types:mapping}});
 return commands;
}
