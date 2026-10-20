// Display fewer date labels in a narrow panel; observation coordinates stay intact.
export function periodTickUpdate(figure:{layout:Record<string,unknown>},width:number){
 const meta=figure.layout.meta as {publicationYoy?:boolean;publicationAxes?:boolean}|undefined;
 if(meta?.publicationYoy||meta?.publicationAxes)return {};
 const layout=figure.layout,margin=(layout.margin||{}) as {l?:number;r?:number};
 const inner=Math.max(80,width-Number(margin.l||0)-Number(margin.r||0));
 const update:Record<string,unknown>={};
 for(const [name,value] of Object.entries(layout)){
  if(!/^xaxis\d*$/.test(name))continue;
  const axis=value as {type?:string;categoryarray?:string[];ticktext?:string[];dtick?:number;domain?:number[];tickangle?:number;tickfont?:{size?:number};visible?:boolean};
  const periods=axis.categoryarray;
  if(axis.visible===false||axis.type!=='category'||axis.dtick||!periods?.length||!axis.ticktext?.length||!periods.every(p=>/^\d{4}(?:\d{2})?(?:\d{2})?$/.test(p)))continue;
  const font=axis.tickfont?.size||Number((layout.font as {size?:number}|undefined)?.size)||12;
  const span=(axis.domain?.[1]??1)-(axis.domain?.[0]??0);
  const needed=Math.max(...axis.ticktext.map(t=>String(t).length))*font*.65+14;
  const maximum=Math.max(2,Math.floor(inner*span/needed)+1);
  const minimumStep=Math.max(1,(periods.length-1)/(maximum-1));
  const minimumGap=needed/Math.max(1,inner*span)*(periods.length-1);
  const step=[1,2,3,4,6,12,24,36,48,60,120].find(s=>s>=minimumStep)??Math.ceil(minimumStep);
  const indices=Array.from({length:Math.ceil(periods.length/step)},(_,i)=>i*step);
  const last=periods.length-1;
  if(indices[indices.length-1]!==last){if(last-indices[indices.length-1]<minimumGap&&indices.length>1)indices.pop();indices.push(last);}
  const quarterly=axis.ticktext.some(t=>/ Q[1-4]$/.test(String(t)))&&periods.every(p=>p.length===6&&Number(p.slice(4))>=1&&Number(p.slice(4))<=4);
  const yearOnly=axis.ticktext.every(t=>/^\d{4}$/.test(String(t)));
  const label=(p:string)=>yearOnly?p.slice(0,4):quarterly?`${p.slice(0,4)} Q${Number(p.slice(4))}`:p.length===6?`${p.slice(0,4)}-${p.slice(4)}`:p.length===8?`${p.slice(0,4)}-${p.slice(4,6)}-${p.slice(6)}`:p;
  update[name+'.tickvals']=indices;update[name+'.ticktext']=indices.map(i=>label(periods[i]));
 }
 return update;
}
