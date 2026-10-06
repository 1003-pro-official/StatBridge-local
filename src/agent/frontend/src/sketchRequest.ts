import type { SketchMark, EditSelection } from "./api/types.ts";

export const elementTargets = new Set(["title", "legend", "x_axis", "y_axis"]);

export function inferMarkTarget<T extends SketchMark>(mark:T, legend?:{left:number;right:number;top:number;bottom:number}):T {
  if(mark.target&&mark.target!=='chart')return mark;
  if(mark.text.includes('제목'))return {...mark,target:'title',selection:undefined};
  if(mark.text.includes('범례'))return {...mark,target:'legend',selection:undefined};
  if(mark.tool==='rectangle'&&legend){
    const a=mark.points[0],b=mark.points.at(-1)!;
    const x=(a.x+b.x)/2,y=(a.y+b.y)/2;
    if(x>=legend.left&&x<=legend.right&&y>=legend.top&&y<=legend.bottom)return {...mark,target:'legend',selection:undefined};
  }
  return mark;
}

export function bindMarks<T extends SketchMark>(marks:T[], manual?:EditSelection):T[] {
  return marks.map(mark=> marks.length===1 && !mark.selection && manual && !elementTargets.has(mark.target) &&
    (mark.target==="chart"||mark.target===manual.label) ? {...mark,selection:manual} : mark);
}

export function changeMarkTarget<T extends SketchMark>(mark:T, target:string):T {
  const {selection:oldSelection,...rest}=mark;
  const selection=oldSelection&&target===oldSelection.label ? oldSelection : undefined;
  return {...rest,target,selection} as T;
}
