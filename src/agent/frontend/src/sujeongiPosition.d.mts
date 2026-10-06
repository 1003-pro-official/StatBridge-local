type Position={x:number;y:number};
type Viewport={width:number;height:number};
export const CHARACTER_SIZE: Viewport;
export function clampPosition(position:Position,viewport:Viewport,size?:Viewport):Position;
export function initialPosition(viewport:Viewport,stored?:Position|null):Position;
export function panelPosition(position:Position,viewport:Viewport):{left:number;top:number;width:number;maxHeight:number};
export function isDrag(dx:number,dy:number):boolean;
