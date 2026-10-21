import {EDIT_TIMEOUT_MS,withRequestDeadline} from './requestDeadline';
import Plotly from 'plotly.js-dist-min';
import {reportChartSize,validateChartSize,type ChartImageSize} from './reportChartSize';

// Render the complete observation-owned figure, including title, legend and captions.
export async function workspacePng(figure:{data:Record<string,unknown>[];layout:Record<string,unknown>},parentSignal?:AbortSignal,size?:ChartImageSize):Promise<Blob>{
 const copy=JSON.parse(JSON.stringify(figure));
 const {width,height}=size?validateChartSize(size):reportChartSize(copy.layout);
 const node=document.createElement('div');node.style.cssText=`position:fixed;left:-20000px;top:0;width:${width}px;height:${height}px;`;document.body.appendChild(node);
 try{return await withRequestDeadline(async signal=>{
  await Plotly.react(node,copy.data,{...copy.layout,width,height,autosize:false},{staticPlot:true});
  signal.throwIfAborted();
  const image=await Plotly.toImage(node,{format:'png',width,height});
  signal.throwIfAborted();
  const response=await fetch(image,{signal});const blob=await response.blob();
  if(!blob.size||blob.type!=='image/png')throw new Error('PNG 이미지를 생성하지 못했습니다.');
  return blob;
 },'그래프 PNG 생성 요청',parentSignal,parentSignal?EDIT_TIMEOUT_MS:undefined);}finally{Plotly.purge(node);node.remove();}
}
export function startFileDownload(url:string,filename:string){
 const link=document.createElement('a');link.href=url;link.download=filename;document.body.appendChild(link);link.click();link.remove();
}
