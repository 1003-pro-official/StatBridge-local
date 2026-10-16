import type {ChartEditInput} from './api/types';
export default function QuickPeriodControls({state,disabled,onEdit}:{state:Record<string,unknown>;disabled:boolean;onEdit:(v:ChartEditInput)=>Promise<boolean>}){
 const active=state.period_window_years??(!state.period_start&&!state.period_end?'all':null);
 return <div className="workspace-quick-periods" role="group" aria-label="빠른 표시 기간"><strong>표시 기간</strong>{[1,5,10,'all'].map(years=><button type="button" key={years} aria-pressed={active===years} disabled={disabled||active===years} onClick={()=>void onEdit({instruction:'',commands:[{operation:'filter_period',kind:'DATA_EDIT',params:{years:years==='all'?null:years}}]})}>{years==='all'?'전체':`${years}년`}</button>)}<small>마지막 관측시점 기준 · 조회한 자료 안에서 표시</small></div>;
}
