import type { EditSelection, SketchMark } from "./api/types";

export type HitPoint = {label:string; period:string; x:number; y:number; trace:number; connected:boolean};

// Plotly pixel projection is isolated here. Missing/changed internals fail closed;
// users can still explicitly choose actual observation periods in the editor.
export function graphHitPoints(plot:HTMLElement, stage:HTMLElement):HitPoint[] {
  const graph = plot as unknown as {data?:Array<Record<string, any>>; _fullLayout?:Record<string, any>};
  const layout=graph._fullLayout, box=stage.getBoundingClientRect(), graphBox=plot.getBoundingClientRect();
  if(!layout || !box.width || !box.height)return [];
  return (graph.data||[]).flatMap((trace,index)=>{
    const xa=layout[String(trace.xaxis||"x").replace("x","xaxis")];
    const ya=layout[String(trace.yaxis||"y").replace("y","yaxis")];
    if(!xa?.d2p||!ya?.d2p||!Array.isArray(trace.customdata))return [];
    return trace.customdata.flatMap((entry:any,i:number)=>{
      if(!Array.isArray(entry)||typeof entry[0]!=="string"||typeof entry[1]!=="string")return [];
      const project=(axis:any,value:any)=>axis.type==="category"&&Array.isArray(axis._categories)&&axis.l2p ? axis.l2p(axis._categories.indexOf(String(value))) : axis.d2p(value);
      const x=project(xa,trace.x?.[i])+xa._offset+graphBox.left-box.left;
      const y=project(ya,trace.y?.[i])+ya._offset+graphBox.top-box.top;
      return Number.isFinite(x)&&Number.isFinite(y)&&x>=0&&x<=box.width&&y>=0&&y<=box.height ?
        [{label:entry[0],period:entry[1],x,y,trace:index,connected:String(trace.mode||"").includes("lines")}] : [];
    });
  });
}

function distanceToEdge(x:number,y:number,a:HitPoint,b:HitPoint):number {
  const dx=b.x-a.x,dy=b.y-a.y,t=Math.max(0,Math.min(1,((x-a.x)*dx+(y-a.y)*dy)/(dx*dx+dy*dy||1)));
  return Math.hypot(x-a.x-t*dx,y-a.y-t*dy);
}

export function resolveMarkSelection(mark:SketchMark, hits:HitPoint[], width:number,height:number,scope:EditSelection["scope"]):EditSelection {
  const points=hits.filter(p=>mark.target==="chart"||p.label===mark.target);
  const first=mark.points[0],last=mark.points.at(-1)!;
  let candidates:Array<{distance:number;selection:EditSelection}> = [];
  if(mark.tool==="rectangle"){
    const inside=points.filter(p=>p.x>=Math.min(first.x,last.x)*width&&p.x<=Math.max(first.x,last.x)*width&&p.y>=Math.min(first.y,last.y)*height&&p.y<=Math.max(first.y,last.y)*height);
    const labels=[...new Set(inside.map(p=>p.label))];
    if(labels.length!==1)throw new Error("사각형 안의 계열이 없거나 여러 개입니다. 수정 대상을 선택하거나 시점을 직접 지정해 주세요.");
    const periods=[...new Set(inside.map(p=>p.period))].sort();
    if(scope==="point"&&periods.length!==1)throw new Error("점 편집은 한 관측점만 선택해 주세요.");
    return {label:labels[0],scope,start:periods[0],end:periods.at(-1)};
  }
  if(scope==="segment"){
    for(let i=0;i<points.length-1;i++){
      const a=points[i],b=points[i+1];
      if(a.trace!==b.trace||a.label!==b.label||!a.connected||a.period===b.period)continue;
      candidates.push({distance:distanceToEdge(last.x*width,last.y*height,a,b),selection:{label:a.label,scope,start:a.period,end:b.period}});
    }
  }else candidates=points.map(p=>({distance:Math.hypot(last.x*width-p.x,last.y*height-p.y),selection:{label:p.label,scope,start:p.period,end:p.period}}));
  candidates.sort((a,b)=>a.distance-b.distance);
  if(!candidates.length||candidates[0].distance>24)throw new Error("표시 끝을 실제 선분/점 가까이에 그리거나 시점을 직접 지정해 주세요.");
  if(candidates.some(c=>c.selection.label!==candidates[0].selection.label&&c.distance<candidates[0].distance+4))throw new Error("겹친 계열을 구분할 수 없습니다. 수정 대상을 선택해 주세요.");
  return candidates[0].selection;
}
