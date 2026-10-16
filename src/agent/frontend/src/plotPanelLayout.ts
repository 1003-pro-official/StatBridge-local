export function panelGeometry(figure:{data:Array<Record<string,unknown>>;layout:Record<string,unknown>}){
 const domain=(axis:string)=>{const key=axis[0]+'axis'+axis.slice(1);return (figure.layout[key] as {domain?:number[]}|undefined)?.domain||[0,1];};
 const pairs=new Set<string>(),rows=new Set<string>(),columns=new Set<string>();
 for(const trace of figure.data){if(trace.type==='pie'||trace.type==='treemap')continue;const x=domain(String(trace.xaxis||'x')),y=domain(String(trace.yaxis||'y'));pairs.add(JSON.stringify([x,y]));rows.add(JSON.stringify(y));columns.add(JSON.stringify(x));}
 const series=new Set(figure.data.filter(t=>t.visible!==false&&t.visible!=='legendonly').map((t,i)=>String((t.meta as {seriesLabel?:string}|undefined)?.seriesLabel||t.legendgroup||t.name||i))).size;
 const domainChart=figure.data.some(t=>t.type==='pie'||t.type==='treemap');
 // Even a single/dual-axis chart must grow outside the viewport-sized
 // workspace. A short flex frame can clip the entire plot below its legend
 // while layout containment prevents the scroll parent seeing that overflow.
 const expanded=series>0||domainChart;
 const seriesHeight=series>=5?760+Math.min(740,(series-5)*60):series>=3?520:420;
 const multi=pairs.size>1;
 const annotations=(figure.layout.annotations||[]) as Array<{text?:string;name?:string;font?:{size?:number};y?:number}>;
 const titleSpace=Math.max(35,...annotations.filter(a=>!a.name&&(a.y===undefined||a.y>=.9)).map(a=>(String(a.text||'').split(/<br\s*\/?\s*>/i).length)*(a.font?.size||14)*1.4+24));
 const margins=figure.layout.margin as {t?:number;b?:number}|undefined;
 const domainHeight=Math.max(500,(Number(figure.layout.height)||580)-Number(margins?.t||0)-Number(margins?.b||0)+125);
 return {multi,expanded,domainChart,series,minWidth:multi&&columns.size>1?columns.size*280+120:0,rows:Math.max(1,rows.size),minHeight:multi?Math.max(Number(figure.layout.height)||0,rows.size*420+200,seriesHeight):domainChart?domainHeight:seriesHeight,titleSpace};
}

export function splitPlotAnnotations(figure:{layout:Record<string,unknown>}){
 const annotations=(figure.layout.annotations||[]) as Array<Record<string,unknown>>;
 const isFooter=(a:Record<string,unknown>)=>String(a.name||'').startsWith('statbridge-footer:')||(a.yref==='paper'&&a.y===0&&typeof a.yshift==='number'&&a.yshift<0)||(!a.name&&a.yref==='paper'&&typeof a.y==='number'&&a.y<0);
 return {plot:annotations.filter(a=>!isFooter(a)),footer:annotations.filter(isFooter)};
}


export async function resizeVisiblePlot(element:HTMLElement,resize:(element:HTMLElement)=>Promise<unknown>){
 const visible=()=>element.isConnected&&element.getClientRects().length>0&&element.getBoundingClientRect().width>0&&element.getBoundingClientRect().height>0;
 if(!visible())return false;
 try{await resize(element);return visible();}catch(error){if(visible())throw error;return false;}
}
