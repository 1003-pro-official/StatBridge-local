import {useEffect,useState} from 'react';
import {validateChartSize} from './reportChartSize';

// Measured from BOK Sep-2025 report p.15: Figure I-16 source raster and Table I-11 at 144 dpi.
export const publicationDefaults={graph:{width:496,height:419},table:{width:379,height:614}};
export default function OutputSizeControls({width,height,disabled,onApply,variant='graph'}:{width?:number|null;height?:number|null;disabled:boolean;onApply:(width:number|null,height:number|null)=>Promise<boolean>;variant?:'graph'|'table'}){
 const preset=publicationDefaults[variant];
 const [enabled,setEnabled]=useState(true),[w,setW]=useState(String(width||preset.width)),[h,setH]=useState(String(height||preset.height)),[lock,setLock]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState('');
 useEffect(()=>{setW(String(width||preset.width));setH(String(height||preset.height));if(width&&height)setEnabled(true);},[width,height,variant]);
 const resize=(axis:'w'|'h',value:string)=>{const ratio=Number(w)/Number(h);if(axis==='w'){setW(value);if(lock&&Number(value)>0)setH(String(Math.round(Number(value)/ratio)));}else{setH(value);if(lock&&Number(value)>0)setW(String(Math.round(Number(value)*ratio)));}};
 const apply=async(active:boolean,size={width:+w,height:+h})=>{try{if(active)validateChartSize(size);setBusy(true);setError('');if(!await onApply(active?size.width:null,active?size.height:null))throw Error('크기를 적용하지 못했습니다.');setEnabled(active);}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}};
 return <details className="workspace-property-group" onToggle={e=>{if(e.currentTarget.open&&!width&&!height&&!busy)void apply(true,preset);}}><summary>출력 크기 · 그래프 / 표</summary><fieldset disabled={disabled||busy} aria-label="출력 크기 설정">
 <p>한국은행 통화신용정책보고서(2025.9) 15쪽 {variant==='graph'?'그림 I-16 원본 이미지 비율':'표 I-11 인쇄 영역 · 144DPI 환산'} 기준: {preset.width} × {preset.height}px</p>
 <label><input type="checkbox" checked={enabled} onChange={e=>{if(e.target.checked)setEnabled(true);else void apply(false);}}/>크기 직접 지정</label>
 <label>출력 너비 (px)<input type="number" min="1" step="1" disabled={!enabled} value={w} onChange={e=>resize('w',e.target.value)}/></label>
 <label>출력 높이 (px)<input type="number" min="1" step="1" disabled={!enabled} value={h} onChange={e=>resize('h',e.target.value)}/></label>
 <label><input type="checkbox" checked={lock} onChange={e=>setLock(e.target.checked)}/>비율 유지</label>
 <button type="button" disabled={!enabled} onClick={()=>void apply(true)}>출력 크기 적용</button>
 <button type="button" onClick={()=>void apply(true,preset)}>간행물 기본 크기 적용</button>
 <button type="button" onClick={()=>void apply(true,{width:preset.width*2,height:preset.height*2})}>간행물 비율 2배</button>
 <small>너비·높이 고정 제한 없이 입력합니다. 메모리 보호를 위해 총 3,200만 픽셀 이하로 검증합니다. PNG는 지정 픽셀, PDF·SVG는 100px당 1인치입니다. 표는 쪽별 적용하며 CSV·XLSX 셀 데이터는 유지합니다.</small>
 <a href="https://www.bok.or.kr/portal/bbs/B0000156/view.do?menuNo=200067&nttId=10093507" target="_blank" rel="noreferrer">기본 크기 참고 간행물</a>{error&&<p role="alert">{error}</p>}</fieldset></details>;
}
