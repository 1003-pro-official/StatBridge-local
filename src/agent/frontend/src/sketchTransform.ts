import type { SketchMark } from './api/types';

export type EditableMark=SketchMark & {textSize?:number};
export type Corner='nw'|'ne'|'sw'|'se';
export function markBounds(mark:EditableMark) {
  const xs=mark.points.map(p=>p.x),ys=mark.points.map(p=>p.y);
  if(mark.tool==='text') {
    const size=mark.textSize||22,p=mark.points[0];
    return {left:p.x,top:Math.max(0,p.y-size/1000-.008),right:Math.min(1,p.x+Math.max(.04,mark.text.length*size*.6/1000)),bottom:p.y};
  }
  return {left:Math.min(...xs),top:Math.min(...ys),right:Math.max(...xs),bottom:Math.max(...ys)};
}
export function moveMark(mark:EditableMark,dx:number,dy:number):EditableMark {
  const b=markBounds(mark);
  dx=Math.max(-b.left,Math.min(1-b.right,dx));dy=Math.max(-b.top,Math.min(1-b.bottom,dy));
  return {...mark,selection:undefined,points:mark.points.map(p=>({x:p.x+dx,y:p.y+dy}))};
}
export function resizeMark(mark:EditableMark,corner:Corner,x:number,y:number):EditableMark {
  const b=markBounds(mark),west=corner.includes('w'),north=corner.includes('n');
  const left=west?Math.max(0,Math.min(b.right-.01,x)):b.left;
  const right=west?b.right:Math.min(1,Math.max(b.left+.01,x));
  const top=north?Math.max(0,Math.min(b.bottom-.01,y)):b.top;
  const bottom=north?b.bottom:Math.min(1,Math.max(b.top+.01,y));
  const sx=(right-left)/Math.max(.001,b.right-b.left),sy=(bottom-top)/Math.max(.001,b.bottom-b.top);
  if(mark.tool==='text') {
    const size=Math.max(10,Math.min(100,(mark.textSize||22)*Math.min(sx,sy)));
    return {...mark,textSize:size,selection:undefined,points:[{x:left,y:bottom}]};
  }
  return {...mark,selection:undefined,points:mark.points.map(p=>({x:Math.max(0,Math.min(1,left+(p.x-b.left)*sx)),y:Math.max(0,Math.min(1,top+(p.y-b.top)*sy))}))};
}
