export const ANALYSIS_TIMEOUT_MS=20_000;
export class AnalysisTimeoutError extends Error {
 constructor(timeoutMs=ANALYSIS_TIMEOUT_MS){super(`${timeoutMs/1000}초 안에 분석 결과나 조회 조건 안내가 도착하지 않아 대기를 중단했습니다. 입력과 기존 분석은 유지됩니다.`);this.name='AnalysisTimeoutError';}
}
// One deadline covers response headers, body reading and the complete automatic
// query→output chain. A late response cannot settle the promise a second time.
export async function withAnalysisDeadline<T>(action:(signal:AbortSignal)=>Promise<T>,parentSignal?:AbortSignal,timeoutMs=ANALYSIS_TIMEOUT_MS):Promise<T>{
 if(parentSignal)return action(parentSignal);
 const controller=new AbortController();
 let timer:ReturnType<typeof setTimeout>|undefined;
 const expired=new Promise<never>((_,reject)=>{timer=setTimeout(()=>{reject(new AnalysisTimeoutError(timeoutMs));controller.abort();},timeoutMs);});
 try{return await Promise.race([Promise.resolve().then(()=>action(controller.signal)),expired]);}
 finally{if(timer!==undefined)clearTimeout(timer);}
}
