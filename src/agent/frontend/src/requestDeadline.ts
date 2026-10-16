import {withAnalysisDeadline,AnalysisTimeoutError,ANALYSIS_TIMEOUT_MS} from './analysisDeadline.ts';
export class RequestTimeoutError extends AnalysisTimeoutError {
 constructor(label:string){super();this.name='RequestTimeoutError';this.message=`20초 안에 ${label}을 완료하지 못해 대기를 중단했습니다. 현재 작업은 유지됩니다. 다시 시도하거나 입력을 수정해 주세요.`;}
}
export async function withRequestDeadline<T>(action:(signal:AbortSignal)=>Promise<T>,label='서버 요청',parentSignal?:AbortSignal,timeoutMs=ANALYSIS_TIMEOUT_MS):Promise<T>{
 try{return await withAnalysisDeadline(signal=>action(parentSignal?AbortSignal.any([signal,parentSignal]):signal),undefined,timeoutMs);}
 catch(error){if(error instanceof AnalysisTimeoutError)throw new RequestTimeoutError(label);if(error instanceof SyntaxError)throw new Error('서버 응답을 읽지 못했습니다. 현재 작업은 유지됩니다. 같은 요청을 다시 시도해 주세요.');throw error;}
}
