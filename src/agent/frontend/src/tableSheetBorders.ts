import type {CellFormat,TableLayout} from './tableLayout';
export type BorderTarget='top'|'bottom'|'left'|'right'|'outside'|'inside'|'all'|'none';
export type RangePatch={rows:string[];columns:string[];format:Partial<CellFormat>};
export function borderPatches(rows:string[],columns:string[],target:BorderTarget,style:string,color:string):RangePatch[]{
 if(!rows.length||!columns.length)return [];
 const edge=(name:string,rr=rows,cc=columns):RangePatch=>({rows:rr,columns:cc,format:{[name]:style,[name+'_color']:color}});
 if(target==='none')return [{rows,columns,format:{top:'none',bottom:'none',left:'none',right:'none'}}];
 if(target==='all')return [{rows,columns,format:{top:style,bottom:style,left:style,right:style,top_color:color,bottom_color:color,left_color:color,right_color:color}}];
 if(target==='inside')return [...(rows.length>1?[edge('bottom',rows.slice(0,-1))]:[]),...(columns.length>1?[edge('right',rows,columns.slice(0,-1))]:[])];
 const sides={top:edge('top',rows.slice(0,1)),bottom:edge('bottom',rows.slice(-1)),left:edge('left',rows,columns.slice(0,1)),right:edge('right',rows,columns.slice(-1))};
 return target==='outside'?Object.values(sides):[sides[target]];
}
export function appendRangeFormats(rules:NonNullable<TableLayout['range_formats']>,patches:RangePatch[],id:string){
 const result=[...rules];for(const [i,p] of patches.entries()){const at=result.findIndex(r=>JSON.stringify(r.rows)===JSON.stringify(p.rows)&&JSON.stringify(r.columns)===JSON.stringify(p.columns));const old=at<0?undefined:result.splice(at,1)[0];result.push({id:old?.id||id+'_'+i,...p,format:{...old?.format,...p.format}});}return result;
}
export function tableHistoryAction(event:{key:string;ctrlKey:boolean;metaKey:boolean;shiftKey:boolean;altKey:boolean},editingText:boolean):'undo'|'redo'|null{
 if(editingText||event.altKey||!(event.ctrlKey||event.metaKey))return null;const key=event.key.toLowerCase();return key==='z'?(event.shiftKey?'redo':'undo'):key==='y'?'redo':null;
}
