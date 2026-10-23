/** Match the rendered/exported trace instead of displaying every line as solid. */
export function WorkspaceLegendSwatch({trace}:{trace:Record<string,unknown>}) {
  const line=trace.line as {color?:string;dash?:string}|undefined;
  const marker=trace.marker as {color?:string|string[]}|undefined;
  const color=line?.color||(Array.isArray(marker?.color)?marker.color[0]:marker?.color)||'#4568ff';
  const patterns:Record<string,string>={dot:'1 3',dash:'6 4',longdash:'10 4',dashdot:'6 3 1 3',longdashdot:'10 3 1 3'};
  return <svg width="24" height="12" viewBox="0 0 24 12" aria-hidden="true" style={{verticalAlign:'middle',marginRight:6,flexShrink:0}}>
    {trace.type==='bar'?<rect x="1" y="1" width="22" height="10" fill={color}/>:<line x1="1" y1="6" x2="23" y2="6" stroke={color} strokeWidth="2" strokeDasharray={patterns[line?.dash||'solid']}/>}
  </svg>;
}
