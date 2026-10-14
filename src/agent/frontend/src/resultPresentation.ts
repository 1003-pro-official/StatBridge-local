import type {ChartSeries, QueryResponse, SelectedTable} from './api/types';

// Observation codes are interpreted using each series' own frequency.
export function observationDate(code:string, frequency:string|undefined, end=false):string {
 const value=code.replace(/[-/]/g,'');
 const quarter=code.match(/^(\d{4})Q([1-4])$/i);
 let year=0,month=0;
 if(quarter){year=Number(quarter[1]);month=(Number(quarter[2])-1)*3+(end?3:1);}
 else if(/^\d{4}$/.test(value)){year=Number(value);month=end?12:1;}
 else if(/^\d{6}$/.test(value)){
  year=Number(value.slice(0,4));month=Number(value.slice(4));
  if(frequency==='Q'){if(month<1||month>4)return '';month=(month-1)*3+(end?3:1);}
 }else if(/^\d{8}$/.test(value)){
  const date=`${value.slice(0,4)}-${value.slice(4,6)}-${value.slice(6)}`;
  return validDate(date)?date:'';
 }else return '';
 if(!year||month<1||month>12)return '';
 const day=end?new Date(Date.UTC(year,month,0)).getUTCDate():1;
 return `${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
}
export function validDate(value:string):boolean {
 return /^\d{4}-\d{2}-\d{2}$/.test(value)&&Number.isFinite(Date.parse(value))&&new Date(value+'T00:00:00Z').toISOString().slice(0,10)===value;
}
export function displayedPeriod(series:ChartSeries[]){
 const starts=series.flatMap(s=>s.points.map(p=>observationDate(p.date,s.frequency))).filter(Boolean).sort();
 const ends=series.flatMap(s=>s.points.map(p=>observationDate(p.date,s.frequency,true))).filter(Boolean).sort();
 return {start:starts[0]||'',end:ends.at(-1)||''};
}
export function emptyAvailablePeriod(available:QueryResponse['availablePeriod']):boolean {
 return Boolean(available?.min&&available.max&&available.min>available.max);
}
export function titlePeriodMismatch(title:string,period:{start:string;end:string}):boolean {
 const range=title.match(/(\d{4})년?(?:\s*[1-4]분기)?\s*(?:~|–|부터|-)\s*(\d{4})년?/);
 return Boolean(range&&period.start&&period.end&&(range[1]!==period.start.slice(0,4)||range[2]!==period.end.slice(0,4)));
}
export function groupSources(tables:SelectedTable[]):SelectedTable[]{
 const grouped=new Map<string,{table:SelectedTable;items:Set<string>;units:Set<string>}>();
 for(const table of tables){const group=grouped.get(table.tableId)||{table,items:new Set<string>(),units:new Set<string>()};if(table.item)group.items.add(table.item);if(table.unit)group.units.add(table.unit);grouped.set(table.tableId,group);}
 return [...grouped.values()].map(group=>({...group.table,item:[...group.items].join(' / '),unit:[...group.units].join(' / ')}));
}
export function resultInsights(insights:string[],editChanges:string[]=[]){
 const logs:string[]=[],observations:string[]=[];
 for(const text of insights)(editChanges.includes(text)||/^(?:출력\s*Agent|MCP\s*\d|(?:입력|출력|조회)\s*(?:에이전트|Agent)\s*[:·]|편집 다시 적용$|편집 되돌리기$|[^:]+:\s*DT_\w+\s*$)/i.test(text)?logs:observations).push(text);
 return {logs,observations};
}
export function savedTime(seconds:number):string {
 return Number.isFinite(seconds)&&seconds>0?new Date(seconds*1000).toLocaleString('ko-KR'):'저장 시점 정보 없음';
}
