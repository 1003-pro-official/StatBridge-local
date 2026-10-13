import Plotly from 'plotly.js-dist-min';

// Render the complete observation-owned figure, including title, legend and captions.
export async function workspacePng(figure:{data:Record<string,unknown>[];layout:Record<string,unknown>}):Promise<Blob>{
 const copy=JSON.parse(JSON.stringify(figure));
 const width=Math.max(1000,Math.min(2400,Number(copy.layout.width)||1400));
 const height=Math.max(600,Math.min(10000,Number(copy.layout.height)||800));
 const node=document.createElement('div');node.style.cssText=`position:fixed;left:-20000px;top:0;width:${width}px;height:${height}px;`;document.body.appendChild(node);
 try{
  await Plotly.react(node,copy.data,{...copy.layout,width,height,autosize:false},{staticPlot:true});
  const image=await Plotly.toImage(node,{format:'png',width,height});
  const response=await fetch(image);const blob=await response.blob();
  if(!blob.size||blob.type!=='image/png')throw new Error('PNG 이미지를 생성하지 못했습니다.');
  return blob;
 }finally{Plotly.purge(node);node.remove();}
}
export function startFileDownload(url:string,filename:string){
 const link=document.createElement('a');link.href=url;link.download=filename;document.body.appendChild(link);link.click();link.remove();
}
