export const CHARACTER_SIZE = {width:160,height:120};
export function clampPosition(position, viewport, size=CHARACTER_SIZE) {
  const width=Math.max(0,viewport.width-size.width),height=Math.max(0,viewport.height-size.height);
  return {x:Math.min(width,Math.max(0,position.x)),y:Math.min(height,Math.max(0,position.y))};
}
export function initialPosition(viewport, stored) {
  if(stored&&Number.isFinite(stored.x)&&Number.isFinite(stored.y))return clampPosition(stored,viewport);
  return clampPosition({x:viewport.width-CHARACTER_SIZE.width-16,y:viewport.height-CHARACTER_SIZE.height-16},viewport);
}
export function panelPosition(position, viewport) {
  const width=Math.min(360,Math.max(0,viewport.width-24));
  const height=Math.min(540,Math.max(0,viewport.height-24));
  const above=position.y-height-8;
  const y=above>=12?above:position.y+CHARACTER_SIZE.height+8;
  return {left:Math.max(12,Math.min(position.x,viewport.width-width-12)),
    top:Math.max(12,Math.min(y,viewport.height-height-12)),width,maxHeight:height};
}
export function isDrag(dx,dy) {return Math.hypot(dx,dy)>6;}
