import type {QueryResponse} from './types';

export function analysisTimedOut(query:string,timeoutMs=20_000):QueryResponse {
 const result=queryFailure(query,undefined,'');
 return {...result,...(timeoutMs>20_000?{analysisKind:'derived' as const}:{}),summary:`${timeoutMs/1000}초 안에 분석 결과나 조회 조건 안내가 도착하지 않아 대기를 중단했습니다. 질문과 기존 그래프·표는 유지됩니다.`,recovery:{issue:'timeout',question:'지원 통계표를 직접 선택하거나 질문을 구체화해 주세요. 같은 요청을 다시 시도하실 수도 있습니다.',choices:[{id:'table',label:'통계표 직접 선택'},{id:'revise',label:'질문 수정'},{id:'retry',label:'같은 요청 다시 시도'}],preserveState:true}};
}

export function queryFailure(query:string,status:number|undefined,detail:unknown):QueryResponse {
 const issue=status==null?'network':status===401||status===403?'auth':status===429?'rate_limit':status>=500?'server':'input';
 const messages={network:'서버에 연결하지 못했습니다. 연결 상태를 확인한 뒤 다시 시도해 주세요.',auth:'로그인 상태 또는 접근 권한을 확인해 주세요.',rate_limit:'요청이 많아 잠시 처리할 수 없습니다. 잠시 후 다시 시도해 주세요.',server:'서버가 요청을 처리하지 못했습니다. 현재 작업을 유지하고 다시 시도해 주세요.',input:'입력한 조회 조건을 확인해 주세요.'};
 const validation=Array.isArray(detail)?detail.map((item:{loc?:unknown[];msg?:string})=>`${item.loc?.slice(1).join(' · ')||'입력값'}: ${item.msg||'조건을 확인해 주세요'}`).join(' / '):'';
 const summary=status==null?messages.network:(typeof detail==='string'?detail:validation)||messages[issue];
 const retry=['network','rate_limit','server'].includes(issue);
 const period=issue==='input'&&/기간|날짜|시작일|종료일|period_(?:start|end)/.test(summary);
 return {status:'request_failed',query,interpretedQuery:query,summary,period:{start:'',end:''},frequency:'',chart:[],tables:[],insights:[],lineage:[],warnings:[],recovery:{issue,question:messages[issue],choices:retry?[{id:'retry',label:'같은 요청 다시 시도'},{id:'revise',label:'질문 수정'}]:period?[{id:'period',label:'기간 수정'},{id:'revise',label:'질문 수정'}]:[{id:'revise',label:issue==='auth'?'로그인 후 질문 확인':'질문 수정'}],preserveState:true}};
}
