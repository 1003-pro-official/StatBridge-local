import {useEffect,useRef,useState,lazy,Suspense} from 'react';
import type {ChartEditInput,ChartSeries} from './api/types';
import {getReportTemplates,exportReportFile,recommendReport} from './api/client';
import './ReportPanel.css';

const Preview=lazy(()=>import('./ReportPreview'));
const names:Record<string,string>={forecast:'실적·전망 시계열',dual_axis:'명시적 이중 축',contribution:'누적 기여도',panels:'다중 패널',events:'이벤트·기준선',fan:'신뢰구간 팬 차트',waterfall:'워터폴',regression:'산점도·OLS 회귀',heatmap:'히트맵',violin:'바이올린 분포',stacked_area:'누적 영역',scenario:'시나리오 비교',bubble:'버블'};
type Revision={chartState?:Record<string,unknown>;editVersion?:number;echartsOption?:Record<string,unknown>;echartsUnavailable?:string};

export default function ReportPanel({series,sessionId,revision,onEdit,disabled}:{series:ChartSeries[];sessionId:string;revision:object;onEdit:(input:ChartEditInput)=>Promise<boolean>;disabled:boolean}){
  const output=revision as Revision,state=output.chartState||{};
  const saved=state.report as Record<string,unknown>|null|undefined;
  const [options,setOptions]=useState<Record<string,unknown>>(saved||{template:'economic_outlook',kind:'forecast',right_axis:[],intervals:[],events:[],footnotes:[],width:1200,height:720,dpi:200,columns:2});
  const [templates,setTemplates]=useState<Array<{id:string;name:string;kind:string;sample:string}>>([]);
  const [error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [previewOpen,setPreviewOpen]=useState(false);
  const [reasons,setReasons]=useState<string[]>([]);
  const [intervals,setIntervals]=useState(JSON.stringify(saved?.intervals||[])),[events,setEvents]=useState(JSON.stringify(saved?.events||[]));
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{let alive=true;getReportTemplates().then(r=>{if(alive)setTemplates(r.templates);}).catch(e=>{if(alive)setError(String(e.message));});return()=>{alive=false;};},[]);
  useEffect(()=>{if(saved){setOptions(saved);setIntervals(JSON.stringify(saved.intervals||[]));setEvents(JSON.stringify(saved.events||[]));}},[revision]);
  const locked=disabled||busy;
  const commit=async(input:ChartEditInput)=>{if(locked)return;setBusy(true);setError('');try{await onEdit(input);}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}};
  const change=(key:string,value:unknown)=>setOptions(current=>({...current,[key]:value}));
  const command=(operation:string,value?:unknown,params?:Record<string,unknown>,label?:string)=>void commit({instruction:'',commands:[{operation,kind:operation==='hide_series'?'DATA_EDIT':'STYLE_EDIT',value,params,label}]});
  const apply=()=>{try{void commit({instruction:'',report:{...options,intervals:JSON.parse(intervals),events:JSON.parse(events)}});}catch{setError('신뢰구간·이벤트를 올바른 JSON으로 입력해 주세요.');}};
  const exportFile=async(format:string)=>{if(locked)return;setBusy(true);setError('');try{const blob=await exportReportFile(sessionId,output.editVersion,format),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=`statbridge-report.${format}`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}};
  const importFile=async(file?:File)=>{if(!file)return;try{if(file.size>8_000_000)throw new Error('JSON은 최대 8MB입니다.');const data=JSON.parse(await file.text());await commit({instruction:'',document:data});}catch(e){setError(e instanceof Error?e.message:String(e));}};
  const chosen=templates.find(t=>t.id===options.template);
  const recommend=async()=>{setBusy(true);setError('');try{const suggestion=await recommendReport(sessionId,output.editVersion);setOptions(suggestion.options);setReasons(suggestion.reasons);setIntervals('[]');setEvents('[]');}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}};
  const right=(options.right_axis||[]) as string[];
  const axes=(state.axes||{}) as Record<string,Record<string,unknown>>;
  const [minimum,setMinimum]=useState(''),[maximum,setMaximum]=useState('');
  return <details className="report-panel"><summary>보고서 차트 · 인쇄 설정</summary>
    <p>기존 관측값을 유지합니다. 전망·신뢰구간·이벤트 정보는 직접 제공해야 합니다.</p>
    <fieldset disabled={locked}><legend>전문 그래프</legend>
      <button type="button" onClick={()=>void recommend()}>자료 구조로 템플릿 추천</button>{reasons.map(reason=><small key={reason}>{reason}</small>)}
      <label>템플릿<select aria-label="보고서 템플릿" value={String(options.template)} onChange={e=>{const t=templates.find(t=>t.id===e.target.value);setOptions(current=>({...current,template:e.target.value,kind:t?.kind||'forecast'}));}}>{templates.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
      {chosen&&<small>{chosen.sample} · StatBridge 사용자 제작 그래프</small>}
      <label>종류<select aria-label="고급 그래프 종류" value={String(options.kind)} onChange={e=>change('kind',e.target.value)}>{Object.entries(names).map(([key,name])=><option key={key} value={key}>{name}</option>)}<option disabled>점도표 · 수익률 곡선 · 금융 네트워크: 전용 데이터 어댑터 준비 중</option></select></label>
      {options.kind==='dual_axis'&&<div>오른쪽 축 (사용자 지정){series.map(s=><label key={s.label}><input type="checkbox" checked={right.includes(s.label)} onChange={e=>change('right_axis',e.target.checked?[...right,s.label]:right.filter(label=>label!==s.label))}/>{s.label} ({s.unit})</label>)}</div>}
      {options.kind==='contribution'&&<label><input type="checkbox" checked={!!options.contribution_confirmed} onChange={e=>change('contribution_confirmed',e.target.checked)}/>조회된 값이 이미 기여도 자료임을 확인했습니다</label>}
      <label>전망 표시 시작<select value={String(options.forecast_start||'')} onChange={e=>change('forecast_start',e.target.value||null)}><option value="">없음</option>{[...new Set(series.flatMap(s=>s.points.map(p=>p.date)))].sort().map(d=><option key={d}>{d}</option>)}</select></label>
      <small>전망 표시만 지정합니다. 미래 수치와 신뢰구간을 추정하지 않습니다.</small>
      <label>패널 열 수<input type="number" min="1" max="4" value={Number(options.columns||2)} onChange={e=>change('columns',Number(e.target.value))}/></label>
      <label>날짜 표시<select value={String(options.date_format||'period')} onChange={e=>change('date_format',e.target.value)}><option value="period">원자료 주기 (분기·월)</option><option value="year">연도</option></select></label>
      <label>추가 출처 표기<input value={String(options.source_note||'')} onChange={e=>change('source_note',e.target.value)} placeholder="조회 출처는 보존되고 사용자 표기로 추가됩니다"/></label>
      <label>각주 (줄마다 하나)<textarea rows={2} value={((options.footnotes||[]) as string[]).join('\n')} onChange={e=>change('footnotes',e.target.value.split('\n').filter(Boolean))}/></label>
      <details><summary>신뢰구간 · 이벤트 데이터</summary><label>신뢰구간 JSON<textarea aria-label="신뢰구간 JSON" rows={3} value={intervals} onChange={e=>setIntervals(e.target.value)}/></label><small>배열: label, level(0~1), periods, lower, upper, method, source. 실제 계열·시점과 맞아야 합니다.</small><label>이벤트 JSON<textarea aria-label="이벤트 JSON" rows={3} value={events} onChange={e=>setEvents(e.target.value)}/></label><small>배열: period, text, source. 확인된 날짜와 출처만 입력하세요.</small></details>
      <div className="report-actions"><button type="button" onClick={apply}>보고서 설정 적용</button><button type="button" disabled={!saved} onClick={()=>void commit({instruction:'',clear_report:true})}>일반 그래프 복원</button></div>
    </fieldset>
    <fieldset disabled={locked}><legend>직접 편집 · 변경 후 입력란 밖을 누르면 적용</legend>
      <label>제목<input defaultValue={String(state.title||'')} key={`title-${output.editVersion}`} onBlur={e=>{if(e.target.value!==state.title)command('set_title',e.target.value);}}/></label>
      <label>부제<input defaultValue={String(state.subtitle||'')} key={`subtitle-${output.editVersion}`} onBlur={e=>{if(e.target.value!==state.subtitle)command('set_subtitle',e.target.value);}}/></label>
      <label>범례<select value={String(state.legend_position||'top')} onChange={e=>command('set_legend',e.target.value)}>{['top','bottom','left','right','top-left','top-right'].map(v=><option key={v}>{v}</option>)}</select></label>
      <label>글자 크기<input type="number" min="8" max="32" defaultValue={Number((state.presentation as Record<string,unknown>)?.font_size||13)} key={`font-${output.editVersion}`} onBlur={e=>command('set_presentation',undefined,{font_size:Number(e.target.value)})}/></label>
      <label>글꼴<select defaultValue={String((state.presentation as Record<string,unknown>)?.font_family||'Malgun Gothic, Noto Sans CJK KR, sans-serif')} onChange={e=>command('set_presentation',undefined,{font_family:e.target.value})}><option value="Malgun Gothic, Noto Sans CJK KR, sans-serif">맑은 고딕 · 한글 대체 글꼴</option><option value="Noto Sans CJK KR, Malgun Gothic, sans-serif">Noto Sans · 한글 대체 글꼴</option></select></label>
      <label>Y축 최솟값<input type="number" value={minimum} onChange={e=>setMinimum(e.target.value)}/></label><label>Y축 최댓값<input type="number" value={maximum} onChange={e=>setMaximum(e.target.value)}/></label>
      <button type="button" disabled={!minimum||!maximum} onClick={()=>command('set_axis_style',undefined,{minimum:Number(minimum),maximum:Number(maximum)},'y')}>축 범위 적용</button>
      <label><input type="checkbox" checked={axes.y?.show_grid!==false} onChange={e=>command('set_axis_style',undefined,{show_grid:e.target.checked},'y')}/>가로 격자</label>
      <label><input type="checkbox" checked={axes.x?.show_grid!==false} onChange={e=>command('set_axis_style',undefined,{show_grid:e.target.checked},'x')}/>세로 격자</label>
      <label><input type="checkbox" checked={axes.y?.scale==='log'} onChange={e=>command('set_axis_style',undefined,{scale:e.target.checked?'log':'linear'},'y')}/>Y축 로그 척도 (양수만)</label>
      <label>소수점 자리<input type="number" min="0" max="6" defaultValue={Number(axes.y?.decimals||1)} key={`decimals-${output.editVersion}`} onBlur={e=>command('set_axis_style',undefined,{decimals:Number(e.target.value)},'y')}/></label>
      {series.map((s,index)=><div className="report-series" key={s.label}><strong>{s.label} ({s.unit})</strong><label>색<input type="color" defaultValue={s.color} onBlur={e=>{if(e.target.value!==s.color)command('set_series_color',e.target.value,undefined,s.label);}}/></label><label>선<select defaultValue="solid" onChange={e=>command('set_series_dash',e.target.value,undefined,s.label)}>{['solid','dash','dot'].map(v=><option key={v}>{v}</option>)}</select></label><label>두께<input type="number" min="1" max="12" defaultValue={Number(state.line_width||3)} onBlur={e=>command('set_series_style',undefined,{width:Number(e.target.value)},s.label)}/></label><button type="button" onClick={()=>command('hide_series',s.label)}>표시 제외</button><button type="button" disabled={index===0||!!state.top_n} onClick={()=>{const order=series.map(s=>s.label);[order[index-1],order[index]]=[order[index],order[index-1]];command('reorder_series',[...order,...(state.hidden_series||[]) as string[]]);}}>앞으로 이동</button></div>)}
      {((state.hidden_series||[]) as string[]).map(label=><button type="button" key={label} onClick={()=>command('show_series',label)}>{label} 다시 표시</button>)}
    </fieldset>
    <fieldset disabled={locked}><legend>파일 · 저장 복원</legend>
      <label>SVG 글자<select value={String(options.svg_text_mode||'path')} onChange={e=>change('svg_text_mode',e.target.value)}><option value="path">윤곽선 · 다른 컴퓨터에서도 동일하게 표시</option><option value="text">편집용 텍스트 · 같은 한글 폰트 필요</option></select></label>
      <div className="report-size">{[['width','너비',600,2400],['height','높이',400,2000],['dpi','DPI',96,400]].map(([key,label,min,max])=><label key={key}>{label}<input type="number" min={min} max={max} value={Number(options[key]||0)} onChange={e=>change(String(key),Number(e.target.value))}/></label>)}</div><small>논리 크기 기준 100DPI. 200DPI는 가로·세로 두 배 픽셀로 출력합니다. 설정 적용 후 다운로드하세요.</small>
      <div className="report-actions">{['png','svg','pdf','json'].map(format=><button key={format} type="button" disabled={!saved&&format!=='json'} onClick={()=>void exportFile(format)}>{format.toUpperCase()} 저장</button>)}</div>
      <label>JSON 복원<input type="file" accept="application/json,.json" aria-label="보고서 JSON 복원" onChange={e=>void importFile(e.target.files?.[0])}/></label>
      <button type="button" disabled={!output.echartsOption} onClick={()=>{setPreviewOpen(true);dialog.current?.showModal();}}>ECharts SVG 미리보기</button>{output.echartsUnavailable&&<small>{output.echartsUnavailable}</small>}
    </fieldset>
    {error&&<p role="alert">{error}</p>}{busy&&<p role="status">설정 적용 중…</p>}
    <dialog ref={dialog} className="report-dialog" onClose={()=>setPreviewOpen(false)}><button type="button" onClick={()=>dialog.current?.close()}>미리보기 닫기</button><h3>ECharts 보고서 미리보기</h3>{previewOpen&&output.echartsOption&&<Suspense fallback={<p>미리보기 로드 중…</p>}><Preview option={output.echartsOption}/></Suspense>}</dialog>
  </details>;
}
