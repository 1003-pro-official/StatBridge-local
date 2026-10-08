import type { SketchMark } from './api/types';

export function sketchLabel(tool:SketchMark['tool']):string {
  return {pen:'펜으로 표시한 부분 수정',arrow:'화살표 부분 수정',rectangle:'상자로 선택한 부분 수정',ellipse:'원으로 선택한 부분 수정',text:'글자로 지정한 부분 수정'}[tool];
}

export function isDrawingStroke(mark:SketchMark,width:number,height:number):boolean {
  if(mark.tool==='text')return true;
  const first=mark.points[0];
  return mark.points.some(p=>Math.hypot((p.x-first.x)*width,(p.y-first.y)*height)>=3);
}

export function periodLabel(value?:string,frequency?:string):string {
  if(!value)return '';
  if(/^\d{6}$/.test(value)&&frequency==='M')return `${value.slice(0,4)}년 ${Number(value.slice(4))}월`;
  if(/^\d{6}$/.test(value)&&frequency==='Q')return `${value.slice(0,4)}년 ${Number(value.slice(4))}분기`;
  return value;
}
