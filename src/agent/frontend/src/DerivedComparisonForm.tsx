import {useState} from 'react';
import type {QueryResponse} from './api/types';

type Comparison=NonNullable<NonNullable<QueryResponse['supplement']>['comparison']>;
const compact=(s:string)=>s.replaceAll('-','');
const date=(s:string)=>`${s.slice(0,4)}-${s.slice(4,6)}-${s.slice(6,8)}`;
const boundary=(s:string,end=false)=>s.length===8?s:s+(end?String(new Date(Number(s.slice(0,4)),Number(s.slice(4,6)),0).getDate()):'01');
export default function DerivedComparisonForm({data,busy,ready,save,onDirty}:{data:Comparison;busy:boolean;ready:boolean;save:(settings:unknown)=>void;onDirty:()=>void}){
 const [periods,setPeriods]=useState(data.settings?.periods||data.periods.map(p=>({label:p.label,start:boundary(p.start),end:boundary(p.end,true),basis:p.start.length===8?'exact':''})));
 const [series,setSeries]=useState(data.settings?.series||data.series.map(s=>({alias:s.alias,label:s.label,direction:''})));
 const [average,setAverage]=useState<string[]>(data.settings?.average_aliases||[]);
 const [complete,setComplete]=useState(data.settings?.complete_observations_confirmed||false);
 return <form className="ds-input-card ds-comparison" aria-label="기간 비교 계산 설정" onChange={onDirty} onSubmit={e=>{e.preventDefault();save({periods,series,average_aliases:average,complete_observations_confirmed:complete});}}>
  <h4>계산 방법과 평균 대상을 확정해 주세요</h4>
  <p>특정일 비교는 해당 날짜의 관측값을 사용합니다. 월평균 비교는 시작 월과 종료 월의 실제 일별 환율을 각각 평균한 뒤 변화율을 계산합니다. 일별 자료 한 파일에 두 비교기간의 필요한 관측값을 넣어 주세요.</p>
  {periods.map((p,i)=><fieldset key={i}><legend>{p.label}</legend>
   <label>계산 기준 <select aria-label={`기간 ${i+1} 계산 기준`} value={p.basis} onChange={e=>setPeriods(periods.map((v,j)=>i===j?{...v,basis:e.target.value}:v))} required><option value="">선택해 주세요</option><option value="exact">특정 시작일·종료일</option>{data.periods[i].start.length===6&&<option value="monthly_mean">시작 월·종료 월의 관측값 평균</option>}</select></label>
   <label>시작일 <input type="date" aria-label={`기간 ${i+1} 시작일`} value={date(p.start)} onChange={e=>setPeriods(periods.map((v,j)=>i===j?{...v,start:compact(e.target.value)}:v))} required/></label>
   <label>종료일 <input type="date" aria-label={`기간 ${i+1} 종료일`} value={date(p.end)} onChange={e=>setPeriods(periods.map((v,j)=>i===j?{...v,end:compact(e.target.value)}:v))} required/></label>
  </fieldset>)}
  <p><strong>변화율 산식</strong> · 직접 변화율: (종료값 ÷ 시작값 − 1) × 100 · 역방향: (시작값 ÷ 종료값 − 1) × 100. DXY는 지수의 직접 변화율입니다. 평균선은 체크한 대상의 변화율 산술평균입니다.</p>
  <p>파일의 단위는 거래 티커가 아닌 실제 관측 단위입니다. 예: JPY/USD는 1달러당 엔화, USD/EUR는 1유로당 달러입니다. 제공기관의 단위 설명과 대조해 주세요.</p>
  {series.map((s,i)=><fieldset key={s.alias}><legend>{data.series[i].label}</legend>
   <label>가로축 이름 <input aria-label={`가로축 이름 ${s.alias}`} value={s.label} maxLength={100} onChange={e=>setSeries(series.map((v,j)=>i===j?{...v,label:e.target.value}:v))} required/></label>
   <p>업로드 단위: <strong>{data.series[i].unit||'파일을 연결해 주세요'}</strong></p>
   <label>원자료의 표시 방향 <select aria-label={`계산 방향 ${s.alias}`} value={s.direction} onChange={e=>setSeries(series.map((v,j)=>i===j?{...v,direction:e.target.value}:v))} required><option value="">파일의 단위를 확인하고 선택하세요</option><option value="direct">지수 또는 USD/자국통화 → 직접 변화율</option><option value="inverse">자국통화/USD (1달러당 자국통화) → 역방향 변화율</option></select></label>
   <label><input type="checkbox" aria-label={`평균 포함 ${s.alias}`} checked={average.includes(s.alias)} onChange={e=>setAverage(e.target.checked?[...average,s.alias]:average.filter(a=>a!==s.alias))}/>평균선에 포함</label>
  </fieldset>)}
  <label><input type="checkbox" checked={complete} onChange={e=>setComplete(e.target.checked)}/>필요한 날짜와 월평균 대상 월의 모든 원자료 관측값을 넣었습니다. 휴일·결측값은 만들지 않았습니다.</label>
  <p>월평균의 관측값 완전성은 제공기관 자료와 직접 대조해 주세요. 서버는 휴일 달력을 추측하거나 부분 파일을 전체 월 자료로 보증하지 않습니다.</p>
  <button disabled={busy||!ready||!complete||!average.length||periods.some(p=>!p.basis)||series.some(s=>!s.direction)}>계산 기준 저장</button>
  {data.configured&&<p role="status">계산 기준이 저장되었습니다. 아래 ‘파생지표 계산하기’를 누르면 그래프와 표를 생성합니다. 설정을 수정했다면 먼저 다시 저장해 주세요.</p>}
 </form>;
}
