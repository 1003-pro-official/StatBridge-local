import type {ChartEditInput,ChartSeries} from './api/types';

export function publicationCommands(series:ChartSeries[]):NonNullable<ChartEditInput['commands']>{
 if(series.length!==1)throw new Error('간행물형 그래프는 지표 한 개를 선택해 주세요.');
 return [
  {operation:'set_transform',kind:'DATA_EDIT',value:'year_over_year'},
  {operation:'set_chart_type',kind:'STYLE_EDIT',value:'bar'},
  {operation:'set_layout',kind:'STYLE_EDIT',value:'combined'},
  {operation:'set_legend',kind:'STYLE_EDIT',value:false},
  {operation:'set_presentation',kind:'STYLE_EDIT',params:{design_template:'snapshot',publication_yoy:true,latest_values:false,bar_orientation:'vertical',bar_mode:'group',bar_gap:.36,font_size:15,title_size:24,font_color:'#111111',height:520,width:650}},
  {operation:'set_series_color',kind:'STYLE_EDIT',label:series[0].label,value:'#8eace1'},
 ];
}
