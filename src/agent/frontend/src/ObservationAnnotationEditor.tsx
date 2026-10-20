import {useEffect,useState,type RefObject} from 'react';
import type {ChartEditInput,ChartSeries} from './api/types';
import {graphHitPoints} from './chartSelection';
import './ObservationAnnotationEditor.css';
type Note={id:string;text:string;label?:string;period?:string;x:number;y:number;x_shift?:number;y_shift?:number;color:string;font_size:number;arrow:boolean};
type State={notes?:Note[];range_styles?:Array<{id:string;label:string;start:string;scope:string;style:{markers?:boolean}}>};
type Props={stage:RefObject<HTMLDivElement|null>;series:ChartSeries[];state:State;disabled:boolean;onEdit:(input:ChartEditInput)=>Promise<boolean>;onActivate:()=>void};
function dateLabel(date:string,frequency?:string){return frequency==='Q'?`${date.slice(0,4)}년 ${Number(date.slice(4))}/4분기`:date.length===6?`${date.slice(0,4)}년 ${Number(date.slice(4))}월`:date;}
export default function ObservationAnnotationEditor({stage,series,state,disabled,onEdit,onActivate}:Props){
 const [label,setLabel]=useState(series[0]?.label||''),[period,setPeriod]=useState(series[0]?.points.at(-1)?.date||''),[text,setText]=useState(''),[color,setColor]=useState('#246294'),[size,setSize]=useState(8),[font,setFont]=useState(12),[autoLabel,setAutoLabel]=useState(true),[x,setX]=useState(50),[y,setY]=useState(80),[selected,setSelected]=useState<string|null>(null),[mode,setMode]=useState<'point'|'text'|'move'|null>(null),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
 const chosen=series.find(s=>s.label===label),notes=state.notes||[],point=chosen?.points.find(p=>p.date===period);
 useEffect(()=>{if(!chosen&&series.length){setLabel(series[0].label);setPeriod(series[0].points.at(-1)?.date||'');}},[series]);
 const command=async(commands:NonNullable<ChartEditInput['commands']>)=>{setBusy(true);setNotice('');try{if(!await onEdit({instruction:'',commands}))setNotice('변경하지 못했습니다. 기존 그래프는 유지됩니다.');else setNotice('그래프에 적용했습니다. PNG·PDF·SVG 내보내기에도 포함됩니다.');}catch(e){setNotice(e instanceof Error?e.message:String(e));}finally{setBusy(false);}};
 useEffect(()=>{
  if(!mode||disabled||busy||!stage.current)return;
  const element=stage.current;
  const click=(event:MouseEvent)=>{
   const plot=element.querySelector('.js-plotly-plot') as (HTMLElement&{_fullLayout?:{_size?:{l:number;t:number;w:number;h:number}}})|null;
   if(!plot)return;const bounds=element.getBoundingClientRect(),px=event.clientX-bounds.left,py=event.clientY-bounds.top;
   event.preventDefault();event.stopPropagation();
   if(mode==='point'){
    const hits=graphHitPoints(plot,element).sort((a,b)=>Math.hypot(a.x-px,a.y-py)-Math.hypot(b.x-px,b.y-py));
    const hit=hits[0];if(!hit||Math.hypot(hit.x-px,hit.y-py)>24){setNotice('실제 관측점 가까이를 클릭하거나 계열과 시점을 직접 선택해 주세요.');return;}
    setLabel(hit.label);setPeriod(hit.period);setMode(null);setNotice('관측점을 선택했습니다. 관측점 표시 추가를 눌러 적용하세요.');return;
   }
   const box=plot.getBoundingClientRect(),area=plot._fullLayout?._size;if(!area)return;
   const nx=(event.clientX-box.left-area.l)/area.w,ny=1-(event.clientY-box.top-area.t)/area.h;
   if(nx<0||nx>1||ny<0||ny>1){setNotice('그래프의 실제 그리기 영역 안에서 위치를 선택해 주세요.');return;}
   setX(Math.round(nx*100));setY(Math.round(ny*100));setMode(null);
   if(mode==='move'&&selected){
    const note=notes.find(n=>n.id===selected);if(!note)return;
    let params:Record<string,unknown>={x:nx,y:ny};
    if(note.label){const anchor=graphHitPoints(plot,element).find(h=>h.label===note.label&&h.period===note.period);if(!anchor){setNotice('주석이 연결된 관측점이 현재 그래프에 없습니다.');return;}params={x_shift:Math.max(-400,Math.min(400,px-anchor.x)),y_shift:Math.max(-400,Math.min(400,anchor.y-py))};}
    void command([{operation:'update_note',kind:'STYLE_EDIT',value:selected,params}]);
   }else setNotice('텍스트 위치를 선택했습니다. 텍스트 추가를 눌러 적용하세요.');
  };
  element.addEventListener('click',click,true);return()=>element.removeEventListener('click',click,true);
 },[mode,disabled,busy,stage,selected,notes,onEdit]);
 const addPoint=async()=>{
  if(!chosen||!point)return;
  const commands:NonNullable<ChartEditInput['commands']>=[{operation:'set_point_style',kind:'STYLE_EDIT',label,start:period,end:period,params:{markers:true,marker_symbol:'circle-open',marker_size:size,color}}];
  if(autoLabel)commands.push({operation:'add_note',kind:'STYLE_EDIT',params:{label,period,text:"시점·관측값",observation_label:true,font_size:font,color,y_shift:22,arrow:false}});
  await command(commands);
 };
 const addText=()=>command([{operation:selected?'update_note':'add_note',kind:'STYLE_EDIT',...(selected?{value:selected}:{}),params:{text,color,font_size:font,observation_label:false,...(!selected||!notes.find(n=>n.id===selected)?.label?{x:x/100,y:y/100}:{})}}]);
 const activate=(next:typeof mode)=>{onActivate();setMode(next);setNotice(next==='point'?'그래프에서 실제 관측점을 클릭하세요.':'그래프에서 원하는 위치를 클릭하세요.');};
 return <details className="observation-annotation-editor" onToggle={e=>{if(!e.currentTarget.open)setMode(null);}}><summary>관측점 · 직접 텍스트</summary><div className="annotation-editor-grid">
  <fieldset disabled={disabled||busy}><legend>관측점 별도 표시</legend>
   <label>계열<select aria-label="관측점 계열" value={label} onChange={e=>{const s=series.find(s=>s.label===e.target.value);setLabel(e.target.value);setPeriod(s?.points.at(-1)?.date||'');}}>{series.map(s=><option key={s.label}>{s.label}</option>)}</select></label>
   <label>시점<select aria-label="관측점 시점" value={period} onChange={e=>setPeriod(e.target.value)}>{chosen?.points.map(p=><option key={p.date} value={p.date}>{dateLabel(p.date,chosen.frequency)} · {p.value}</option>)}</select></label>
   <label>점 크기<input aria-label="관측점 크기" type="number" min={2} max={24} value={size} onChange={e=>setSize(Number(e.target.value))}/></label>
   <label><input type="checkbox" checked={autoLabel} onChange={e=>setAutoLabel(e.target.checked)}/>시점·값 라벨 함께 추가</label>
   <button type="button" onClick={()=>activate('point')}>그래프에서 관측점 선택</button><button type="button" disabled={!point} onClick={()=>void addPoint()}>관측점 표시 추가</button>
  </fieldset>
  <fieldset disabled={disabled||busy}><legend>출력용 텍스트</legend>
   <label>직접 작성할 문구<textarea aria-label="출력용 텍스트" value={text} maxLength={300} onChange={e=>setText(e.target.value)} placeholder="예: 가계부채 비율은 점차 하락"/></label>
   <div className="annotation-position"><label>가로 위치 (%)<input aria-label="텍스트 가로 위치" type="number" min={0} max={100} value={x} onChange={e=>setX(Number(e.target.value))}/></label><label>세로 위치 (%)<input aria-label="텍스트 세로 위치" type="number" min={0} max={100} value={y} onChange={e=>setY(Number(e.target.value))}/></label></div>
   <label>글자 크기<input aria-label="주석 글자 크기" type="number" min={8} max={30} value={font} onChange={e=>setFont(Number(e.target.value))}/></label><label>색상<input aria-label="주석 색상" type="color" value={color} onChange={e=>setColor(e.target.value)}/></label>
   <button type="button" onClick={()=>activate(selected?'move':'text')}>그래프에서 위치 지정</button><button type="button" disabled={!text.trim()} onClick={()=>void addText()}>{selected?'선택 텍스트 수정':'텍스트 추가'}</button>{selected&&<button type="button" onClick={()=>{setSelected(null);setText('');}}>새 텍스트 작성</button>}
  </fieldset></div>
  <p>빈 공간에 새 통계값을 만들지 않습니다. 점은 실제 관측값에 연결되며 직접 입력한 문구는 사용자 주석입니다.</p>
  {notes.map(n=><div className="annotation-item" key={n.id}><span>{n.text}</span><button type="button" disabled={disabled||busy} onClick={()=>{setSelected(n.id);setText(n.text);setColor(n.color);setFont(n.font_size);setX(n.x*100);setY(n.y*100);}}>문구·위치 수정</button><button type="button" disabled={disabled||busy} onClick={()=>void command([{operation:'remove_note',kind:'STYLE_EDIT',value:n.id}])}>텍스트 삭제</button></div>)}
  {(state.range_styles||[]).filter(r=>r.scope==='point'&&r.style.markers).map(r=><div className="annotation-item" key={r.id}><span>{r.label} · {r.start}</span><button type="button" disabled={disabled||busy} onClick={()=>void command([{operation:'remove_range_style',kind:'STYLE_EDIT',value:r.id}])}>관측점 표시 삭제</button></div>)}
  {mode&&<button type="button" onClick={()=>setMode(null)}>위치 선택 취소</button>}{notice&&<p role="status">{notice}</p>}
 </details>;
}
