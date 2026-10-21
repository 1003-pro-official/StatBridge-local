import {validateChartSize} from './reportChartSize.ts';
export type DraftDocument={title:string;image:string;imageWidth?:number;imageHeight?:number;paragraphs:string[];source:string;scope:string};
const escape=(value:string)=>value.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));

export function reportDraftHtml(doc:DraftDocument){
 if(!/^data:image\/png;base64,[A-Za-z0-9+/=\r\n]+$/.test(doc.image))throw new Error('보고서 그래프 이미지를 확인해 주세요.');
 const size=doc.imageWidth!==undefined||doc.imageHeight!==undefined?validateChartSize({width:doc.imageWidth!,height:doc.imageHeight!}):undefined;
 const dimensions=size?` width="${size.width}" height="${size.height}"`:'';
 return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>${escape(doc.title)}</title><style>
@page{size:A4;margin:20mm}*{box-sizing:border-box}body{max-width:820px;margin:32px auto;padding:0 20px;color:#172f43;font-family:"Malgun Gothic",sans-serif;line-height:1.8}h1{font-size:22px;line-height:1.5}figure{margin:24px 0 16px}img{display:block;width:auto;height:auto;max-width:100%;max-height:220mm;object-fit:contain;margin:auto}figcaption,small{color:#536b7e;font-size:12px;overflow-wrap:anywhere}p{font-size:15px;overflow-wrap:anywhere}footer{margin-top:24px;border-top:1px solid #dce5ec;padding-top:12px}@media print{body{max-width:none;margin:0;padding:0}figure{break-inside:avoid}p{orphans:3;widows:3}}
</style></head><body><main><h1>${escape(doc.title)}</h1><small>${escape(doc.scope)}</small><figure><img src="${doc.image}"${dimensions} alt="${escape(doc.title)}"><figcaption>${escape(doc.source)}</figcaption></figure>${doc.paragraphs.map(p=>`<p>${escape(p)}</p>`).join('')}<footer><small>관측 자료로 작성한 보고서 초안 · 검토 후 사용해 주세요.</small></footer></main></body></html>`;
}

export async function printReportDraft(doc:DraftDocument){
 const frame=document.createElement('iframe');frame.title='보고서 초안 인쇄';
 frame.style.cssText='position:fixed;left:-20000px;top:0;width:900px;height:1100px;border:0;';
 const ready=new Promise<void>((resolve,reject)=>{frame.onload=()=>{const image=frame.contentDocument?.querySelector('img');if(!image){reject(new Error('인쇄용 그래프를 준비하지 못했습니다.'));return;}image.decode().then(()=>resolve(),()=>reject(new Error('인쇄용 그래프를 읽지 못했습니다.')));};});
 frame.srcdoc=reportDraftHtml(doc);document.body.appendChild(frame);
 try{await ready;frame.contentWindow?.focus();frame.contentWindow?.print();}
 finally{setTimeout(()=>frame.remove(),60_000);}
}
