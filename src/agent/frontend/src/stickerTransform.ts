import type { ChartSticker } from "./api/types";

export const clamp = (value:number,min:number,max:number) => Math.min(max,Math.max(min,value));
export type PlotBox = {left:number;top:number;width:number;height:number};
export function stickerCenter(sticker:ChartSticker,box:PlotBox) {
  return {x:box.left+sticker.x*box.width,y:box.top+(1-sticker.y)*box.height};
}
export function moveSticker(sticker:ChartSticker,dx:number,dy:number,box:PlotBox):ChartSticker {
  return {...sticker,x:clamp(sticker.x+dx/box.width,0,1),y:clamp(sticker.y-dy/box.height,0,1)};
}
export function rotationAt(x:number,y:number,center:{x:number;y:number}) {
  return Math.round(Math.atan2(y-center.y,x-center.x)*180/Math.PI+90);
}
