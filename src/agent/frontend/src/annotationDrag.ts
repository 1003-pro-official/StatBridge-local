export type DragNote={id:string;x:number;y:number;label?:string;x_shift?:number;y_shift?:number;placement?:string};
type Params={x?:number;y?:number;x_shift?:number;y_shift?:number};
const clamp=(v:number,min:number,max:number)=>Math.max(min,Math.min(max,v));
export function annotationMove(note:DragNote,dx:number,dy:number,width:number,height:number){
 if(![dx,dy,width,height,note.x,note.y].every(Number.isFinite)||width<=0||height<=0)throw new Error('그래프 위치를 확인할 수 없습니다.');
 if(note.label){const x=clamp((note.x_shift||0)+dx,-400,400),y=clamp((note.y_shift||0)-dy,-400,400);return {params:{x_shift:x,y_shift:y} as Params,dx:x-(note.x_shift||0),dy:(note.y_shift||0)-y};}
 const x=clamp(note.x+dx/width,0,1),y=clamp(note.y-dy/height,0,1);return {params:{x,y} as Params,dx:(x-note.x)*width,dy:(note.y-y)*height};
}
export function bindAnnotationDrag(stage:HTMLElement,notes:DragNote[],commit:(id:string,params:Params)=>Promise<boolean>,error:(text:string)=>void,clearHover:(plot:HTMLElement)=>void=()=>{}){
 type Plot=HTMLElement&{_fullLayout?:{width:number;height:number;_size:{w:number;h:number};annotations:Array<{name?:string}>}};
 type Drag={id:number;note:DragNote;node:Element;original:string;startX:number;startY:number;sx:number;sy:number;width:number;height:number;dx:number;dy:number;moved:boolean};
 let drag:Drag|null=null,pending=false,disposed=false,suppressClick=false;
 const marked=new Set<Element>();let hovering=false;
 const find=(target:EventTarget|null)=>{
  if(!(target instanceof Element))return null;
  const text=target.closest('.annotation-text-g'),group=text?.closest('g.annotation'),plot=group?.closest('.js-plotly-plot') as Plot|null;
  if(!text||!group||!plot||!stage.contains(group))return null;
  const index=Number(group.getAttribute('data-index')),id=plot._fullLayout?.annotations?.[index]?.name;
  const note=notes.find(n=>n.id===id&&n.placement!=='below');return note?{text,plot,note}:null;
 };
 const findAt=(event:PointerEvent)=>{
  if(event.target instanceof Element&&event.target.closest('.modebar'))return null;
  for(const node of marked){
   if(!stage.contains(node)||typeof node.getBoundingClientRect!=='function')continue;
   const box=node.getBoundingClientRect();
   if(box.width&&box.height&&event.clientX>=box.left-4&&event.clientX<=box.right+4&&event.clientY>=box.top-4&&event.clientY<=box.bottom+4){const hit=find(node);if(hit)return hit;}
  }
  return null;
 };
 const hover=(hit:ReturnType<typeof find>)=>{
  if(hit){stage.classList.add('annotation-note-hover');if(!hovering){try{clearHover(hit.plot);}catch{/* CSS still prevents tooltip interception. */}}}
  else stage.classList.remove('annotation-note-hover');hovering=!!hit;
 };
 const mark=()=>{stage.querySelectorAll('g.annotation .annotation-text-g').forEach(node=>{if(find(node)){node.classList.add('statbridge-note-draggable');marked.add(node);}});};
 mark();const observer=new MutationObserver(mark);observer.observe(stage,{childList:true,subtree:true});
 const restore=()=>{if(!drag)return;const current=drag;drag=null;current.node.setAttribute('transform',current.original);current.node.classList.remove('statbridge-note-dragging');stage.classList.remove('annotation-drag-active');if(stage.hasPointerCapture(current.id))stage.releasePointerCapture(current.id);};
 const down=(event:PointerEvent)=>{
  if(event.button!==0||drag||pending)return;const hit=find(event.target)||findAt(event),layout=hit?.plot._fullLayout;if(!hit||!layout)return;
  const bounds=hit.plot.getBoundingClientRect(),sx=bounds.width/layout.width,sy=bounds.height/layout.height;
  if(![sx,sy,layout._size.w,layout._size.h].every(v=>Number.isFinite(v)&&v>0))return;
  event.preventDefault();event.stopImmediatePropagation();suppressClick=false;hover(hit);stage.classList.add('annotation-drag-active');try{clearHover(hit.plot);}catch{/* Do not block the drag on tooltip errors. */}
  drag={id:event.pointerId,note:{...hit.note},node:hit.text,original:hit.text.getAttribute('transform')||'',startX:event.clientX,startY:event.clientY,sx,sy,width:layout._size.w,height:layout._size.h,dx:0,dy:0,moved:false};
  hit.text.classList.add('statbridge-note-dragging');stage.setPointerCapture(event.pointerId);
 };
 const move=(event:PointerEvent)=>{
  if(!drag){hover(find(event.target)||findAt(event));return;}if(event.pointerId!==drag.id)return;event.preventDefault();event.stopImmediatePropagation();
  drag.dx=(event.clientX-drag.startX)/drag.sx;drag.dy=(event.clientY-drag.startY)/drag.sy;
  drag.moved=drag.moved||Math.hypot(event.clientX-drag.startX,event.clientY-drag.startY)>=3;
  if(!drag.moved)return;const next=annotationMove(drag.note,drag.dx,drag.dy,drag.width,drag.height);
  drag.node.setAttribute('transform',`translate(${next.dx},${next.dy}) ${drag.original}`);
 };
 const up=(event:PointerEvent)=>{
  if(!drag||event.pointerId!==drag.id)return;move(event);const current=drag;event.preventDefault();event.stopImmediatePropagation();
  suppressClick=true;restore();if(!current.moved)return;
  const params=annotationMove(current.note,current.dx,current.dy,current.width,current.height).params;pending=true;
  void commit(current.note.id,params).then(ok=>{if(!ok&&!disposed)error('텍스트 이동을 저장하지 못했습니다. 기존 위치를 유지합니다.');}).catch(()=>{if(!disposed)error('텍스트 이동을 저장하지 못했습니다. 기존 위치를 유지합니다.');}).finally(()=>{pending=false;});
 };
 const cancel=()=>{if(drag){suppressClick=true;restore();}};
 const key=(event:KeyboardEvent)=>{if(event.key==='Escape'&&drag){event.preventDefault();event.stopImmediatePropagation();cancel();}};
 const click=(event:MouseEvent)=>{if(suppressClick){suppressClick=false;event.preventDefault();event.stopImmediatePropagation();}};
 stage.addEventListener('lostpointercapture',cancel);stage.addEventListener('pointerdown',down,true);stage.addEventListener('click',click,true);
 window.addEventListener('pointermove',move,true);window.addEventListener('pointerup',up,true);window.addEventListener('pointercancel',cancel,true);window.addEventListener('blur',cancel);window.addEventListener('keydown',key,true);
 return()=>{disposed=true;restore();stage.classList.remove('annotation-note-hover');stage.classList.remove('annotation-drag-active');observer.disconnect();marked.forEach(n=>n.classList.remove('statbridge-note-draggable'));stage.removeEventListener('lostpointercapture',cancel);stage.removeEventListener('pointerdown',down,true);stage.removeEventListener('click',click,true);window.removeEventListener('pointermove',move,true);window.removeEventListener('pointerup',up,true);window.removeEventListener('pointercancel',cancel,true);window.removeEventListener('blur',cancel);window.removeEventListener('keydown',key,true);};
}
