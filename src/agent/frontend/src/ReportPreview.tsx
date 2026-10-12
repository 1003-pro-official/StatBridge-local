import {useEffect,useRef} from 'react';
import * as echarts from 'echarts/core';
import type {EChartsOption} from 'echarts';
import {LineChart,BarChart,ScatterChart,CustomChart,HeatmapChart} from 'echarts/charts';
import {GridComponent,TitleComponent,LegendComponent,TooltipComponent,MarkLineComponent,MarkAreaComponent,VisualMapComponent} from 'echarts/components';
import {SVGRenderer} from 'echarts/renderers';
echarts.use([LineChart,BarChart,ScatterChart,CustomChart,HeatmapChart,GridComponent,TitleComponent,LegendComponent,TooltipComponent,MarkLineComponent,MarkAreaComponent,VisualMapComponent,SVGRenderer]);

export default function ReportPreview({option}:{option:Record<string,unknown>}) {
  const host=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    if(!host.current)return;
    const chart=echarts.init(host.current,undefined,{renderer:'svg'});
    const prepared=structuredClone(option);
    for(const axis of (prepared.xAxis as Array<Record<string,unknown>>||[])){
      const labels=axis.reportPeriodLabels as Record<string,string>|undefined;
      if(labels){const style=axis.axisLabel as Record<string,unknown>;style.formatter=(value:string)=>labels[value]||value;delete axis.reportPeriodLabels;}
    }
    const series=prepared.series as Array<Record<string,unknown>>;
    for(const trace of series){
      // Fixed application functions only. Never compile model-generated JS.
      if(trace.reportCustom==='bubble')trace.symbolSize=(value:number[])=>Math.sqrt(Math.max(0,value[2]))*6;
      if(trace.reportCustom==='waterfall')trace.renderItem=(_params:unknown,api:{value:(i:number)=>number;coord:(v:number[])=>number[];size:(v:number[])=>number[]})=>{
        const low=api.coord([api.value(0),api.value(1)]),high=api.coord([api.value(0),api.value(2)]),width=Math.abs(api.size([1,0])[0])*.65;
        return {type:'rect',shape:{x:low[0]-width/2,y:Math.min(low[1],high[1]),width,height:Math.max(1,Math.abs(low[1]-high[1]))},style:{fill:api.value(3)>=0?'#2255a4':'#c64949'}};
      };
      if(trace.reportCustom==='band')trace.renderItem=(_params:unknown,api:{value:(i:number)=>number;coord:(v:number[])=>number[]})=>({type:'polygon',shape:{points:[api.coord([api.value(0),api.value(1)]),api.coord([api.value(0),api.value(2)]),api.coord([api.value(3),api.value(5)]),api.coord([api.value(3),api.value(4)])]},style:{fill:'rgba(34,85,164,.15)'}});
      delete trace.reportCustom;
    }
    chart.setOption(prepared as EChartsOption);
    const observer=new ResizeObserver(()=>chart.resize());observer.observe(host.current);
    return()=>{observer.disconnect();chart.dispose();};
  },[option]);
  return <div ref={host} role="img" aria-label="ECharts 보고서 미리보기" style={{width:'100%',height:540}}/>;
}
