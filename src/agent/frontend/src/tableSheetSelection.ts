import type {SheetCell,SheetRow} from './tableLayout';
export type Point={row:number;col:number};
export type Rect={top:number;bottom:number;left:number;right:number};
export function selectionRect(rows:SheetRow[],start:Point,end:Point):Rect{
 const rect={top:Math.min(start.row,end.row),bottom:Math.max(start.row,end.row),left:Math.min(start.col,end.col),right:Math.max(start.col,end.col)};
 let changed=true;
 while(changed){changed=false;for(const row of rows)for(const c of row.cells){if(c.row>rect.bottom||c.row+c.rowSpan-1<rect.top||c.column>rect.right||c.column+c.colSpan-1<rect.left)continue;
 const next={top:Math.min(rect.top,c.row),bottom:Math.max(rect.bottom,c.row+c.rowSpan-1),left:Math.min(rect.left,c.column),right:Math.max(rect.right,c.column+c.colSpan-1)};
 if(JSON.stringify(next)!==JSON.stringify(rect)){Object.assign(rect,next);changed=true;}}}return rect;
}
export function intersects(r:Rect,c:SheetCell){return c.row<=r.bottom&&c.row+c.rowSpan-1>=r.top&&c.column<=r.right&&c.column+c.colSpan-1>=r.left;}
export function columnName(index:number){let text='';for(let i=index+1;i>0;i=Math.floor((i-1)/26))text=String.fromCharCode(65+(i-1)%26)+text;return text;}
export function cellAt(rows:SheetRow[],p:Point){return rows.flatMap(r=>r.cells).find(c=>p.row>=c.row&&p.row<c.row+c.rowSpan&&p.col>=c.column&&p.col<c.column+c.colSpan);}
