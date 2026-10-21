/** Selection-only edge scrolling. Never edits data or creates server requests. */
export function edgeSpeed(position:number,start:number,end:number){
 const zone=Math.min(40,(end-start)/3);
 if(zone<=0)return 0;
 if(position<start+zone)return -Math.ceil(22*Math.min(1,(start+zone-position)/zone));
 if(position>end-zone)return Math.ceil(22*Math.min(1,(position-end+zone)/zone));
 return 0;
}

export function installSheetAutoScroll(grid:HTMLElement,onCell:(row:number,column:number)=>void){
 let active=false,frame=0,x=0,y=0,last=0;
 const stop=()=>{active=false;cancelAnimationFrame(frame);frame=0;last=0;};
 const hit=()=>{
  const box=grid.getBoundingClientRect();
  const right=box.left+grid.clientWidth,bottom=box.top+grid.clientHeight;
  const gutter=grid.querySelector('.sheet-row-number')?.getBoundingClientRect().width||42;
  const header=grid.querySelector('thead')?.getBoundingClientRect().height||28;
  const node=document.elementFromPoint(Math.max(Math.min(right-2,box.left+gutter+2),Math.min(right-2,x)),Math.max(Math.min(bottom-2,box.top+header+2),Math.min(bottom-2,y)));
  const cell=node?.closest<HTMLElement>('[data-sheet-row][data-sheet-column]');
  if(cell&&grid.contains(cell))onCell(Number(cell.dataset.sheetRow),Number(cell.dataset.sheetColumn));
 };
 const tick=(time:number)=>{
  if(!active)return;
  const box=grid.getBoundingClientRect(),scale=last?Math.min(2,(time-last)/16.67):1;last=time;
  grid.scrollLeft+=edgeSpeed(x,box.left,box.left+grid.clientWidth)*scale;
  grid.scrollTop+=edgeSpeed(y,box.top,box.top+grid.clientHeight)*scale;
  hit();frame=requestAnimationFrame(tick);
 };
 const move=(e:PointerEvent)=>{if(!active)return;if(!(e.buttons&1)){stop();return;}x=e.clientX;y=e.clientY;hit();};
 const start=(e:{clientX:number;clientY:number})=>{stop();active=true;x=e.clientX;y=e.clientY;frame=requestAnimationFrame(tick);};
 window.addEventListener('pointermove',move);window.addEventListener('pointerup',stop);window.addEventListener('pointercancel',stop);window.addEventListener('blur',stop);
 return {start,stop,dispose(){stop();window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',stop);window.removeEventListener('pointercancel',stop);window.removeEventListener('blur',stop);}};
}
