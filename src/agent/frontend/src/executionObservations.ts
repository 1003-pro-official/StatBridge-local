export type ObservationStep={id:string;parentId:string|null;name:string;type:string;startedAt:string;endedAt?:string;durationMs:number;status:string;metadata:Record<string,string|number|boolean>;model?:string;usage?:Record<string,number>;error?:{code:string;type:string;message:string;httpStatus?:number}};
export type ObservationTrace={traceId:string;name:string;time:string;durationMs:number;status:string;langfuse:string;droppedSteps:number;modelCalls?:number;steps:ObservationStep[];sessionId?:string};
let account:number|null=null;
let records:ObservationTrace[]=[];
const listeners=new Set<()=>void>();
export function setObservationAccount(id:number|null){if(account===id)return;account=id;records=[];listeners.forEach(f=>f());}
export function observationAccount(){return account;}
export function observationRecords(){return records;}
export function subscribeObservations(fn:()=>void){listeners.add(fn);return()=>{listeners.delete(fn);};}
export function recordObservation(value:unknown,owner:number|null){
 if(owner===null||owner!==account||!value||typeof value!=='object')return;
 const row=value as ObservationTrace;
 if(!/^[a-f0-9]{32}$/.test(row.traceId)||!Array.isArray(row.steps)||row.steps.length>128||!Number.isFinite(row.durationMs))return;
 records=[...records.filter(x=>x.traceId!==row.traceId),row].slice(-30);listeners.forEach(f=>f());
}
export async function captureObservation(response:Response,base:string,owner:number|null){
 const id=response.headers.get('X-StatBridge-Trace-Id');
 if(owner===null||owner!==account||!id||!/^[a-f0-9]{32}$/.test(id))return;
 try{
  for(let attempt=0;attempt<3;attempt++){
   const result=await fetch(base+'/observability/'+id,{credentials:'include',cache:'no-store',signal:AbortSignal.timeout(5000)});
   if(result.ok){recordObservation(await result.json(),owner);break;}
   if(result.status!==404)break;
   if(attempt<2)await new Promise(resolve=>setTimeout(resolve,200));
  }
 }catch{/* Observability never changes the original response or blocks the user. */}
}
export const observationNames:Record<string,string>={
 'client.request':'브라우저 요청','request.query':'통계 질문 전체','request.output':'출력 요청 전체','request.edit':'편집 요청 전체','request.export':'파일 내보내기 전체','request.save':'분석 저장 전체','request.restore':'저장 분석 열기','request.file':'추가 자료 처리',
 'query.handle':'질문 처리','intent.route':'요청 분류','request.resolve':'질문·조건 해석','request.clarify':'추가 조건 확인',
 'catalog.search':'승인 통계표 검색','catalog.metadata':'통계표 메타데이터','source.validate':'자료 선택 검증','planner.plan':'파생지표 계획','planner.generate':'계산 계획 설계','planner.action':'자료 선택·계획 생성','planner.semantic_review':'경제학적 의미 검토','plan.validate':'계획 검증','dag.validate':'DAG·단위 검증',
 'sources.fetch':'필요 원자료 조회','statistics.execute':'통계 조회 실행','source.fetch':'통계 서비스 조회','kosis.http':'KOSIS HTTP 호출','kosis.metadata':'KOSIS 메타데이터 호출','kosis.statistics':'KOSIS 관측값 호출',
 'model.openai':'OpenAI 모델 호출','model.ncp':'NCP 모델 호출','file.parse':'업로드 파일 읽기','file.upload':'파일 업로드','file.validate':'추가 자료 검증','file.resume':'파일 연결 후 계속','file.configure':'비교 조건 설정',
 'dag.calculate':'파생지표 계산','dag.execute':'DAG 실행','dag.node':'계산 노드','dag.revise':'변경 부분 재계산','output.prepare':'출력 명세 준비','output.build':'그래프·표 생성','chart.render':'그래프 렌더링','table.build':'표 구성',
 'edit.validate_apply':'편집 검증·적용','edit.apply':'편집 명령 적용','edit.reference':'참고 파일 편집','evidence.save':'계산 근거 저장','analysis.save':'분석 저장','analysis.restore':'분석 복원','export.table':'표 내보내기','export.report':'보고서 내보내기'
};
export const observationStatus:Record<string,string>={completed:'완료',running:'진행 중',failed:'실패',awaiting_input:'조건 확인 대기',missing_data:'자료 부족',unsupported_scope:'지원 범위 밖',cancelled:'취소',timeout:'시간 초과'};

export function recordClientFailure(owner:number|null,startedAt:string,elapsed:number,error:unknown){
 const kind=error instanceof Error?error.name:'';
 const status=/timeout/i.test(kind)?'timeout':kind==='AbortError'?'cancelled':'failed';
 const id=crypto.randomUUID().replaceAll('-','');
 recordObservation({traceId:id,name:'client.request',time:startedAt,durationMs:elapsed,status,langfuse:'client_only',droppedSteps:0,
  steps:[{id:id.slice(0,16),parentId:null,name:'client.request',type:'span',startedAt,endedAt:new Date().toISOString(),durationMs:elapsed,status,metadata:{origin:'browser'},error:{code:'client_'+status,type:'BrowserRequest',message:'브라우저에서 서버 응답을 받지 못했습니다. 서버 내부 단계의 결과는 확인되지 않았습니다.'}}]},owner);
}
