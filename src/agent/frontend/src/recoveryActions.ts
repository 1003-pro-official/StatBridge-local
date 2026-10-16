import type {QueryResponse} from './api/types';
export function recoveryFor(result:QueryResponse|null,message:string){
 if(result?.status==='no_match')return {question:result.recovery?.question||'확인되지 않은 지표를 수정해 주세요. 입력하신 조회 기간은 유지됩니다.',choices:[{id:'revise',label:'질문 수정'},{id:'table',label:'지원 통계표 찾아보기'}]};
 if(/호출\s*제한|HTTP 429/i.test(message))return {question:'안내된 대기 시간이 지난 뒤 같은 요청을 다시 시도해 주세요. 현재 작업은 유지됩니다.',choices:[{id:'retry',label:'대기 후 같은 요청 다시 시도'},{id:'revise',label:'질문 수정'}]};
 if(result?.recovery)return result.recovery;
 if(/(기간|날짜|시작일|종료일).{0,30}(선택해|잘못|형식|범위|없습니다|이후|이전)/.test(message))return {question:'안내된 조회 기간 오류를 수정해 주세요.',choices:[{id:'period',label:'기간 수정'},{id:'revise',label:'질문 수정'}]};
 if(result?.status==='request_failed'||/HTTP (429|5\d\d)|timeout|서버 응답을 읽지 못|다른 편집이 먼저|대기를 중단|호출\s*제한|연결.*실패|호출.*실패|network/i.test(message))return {question:'연결 상태를 확인한 뒤 다시 시도해 주세요.',choices:[{id:'retry',label:'같은 요청 다시 시도'},{id:'revise',label:'질문 수정'}]};
 return {question:'안내된 오류에 해당하는 입력을 수정해 주세요.',choices:[{id:'revise',label:'질문 수정'}]};
}
