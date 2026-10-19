import type {QueryResponse} from './api/types';
export function availabilityAnswer(questions:string[],answers:Record<number,string>){
 return questions.flatMap((q,i)=>answers[i]?.trim()?[`${q}\n답변: ${answers[i].trim()}`]:[]).join('\n');
}
export function shouldShowDerivedSupplement(result:QueryResponse|null){
 return !!result&&result.analysisKind==='derived'&&result.status!=='request_failed'&&!result.availability&&
  (!!result.supplement?.missing.length||!!result.supplement?.uploaded.length||
   (['need_details','data_unavailable'].includes(result.status||'')&&!!result.missingData?.length));
}

export function apiSupportScope(data:NonNullable<QueryResponse['availability']>){
 if(data.status!=='checked'||!data.sources.length)return 'verification_pending';
 if(data.sources.some(s=>s.status==='available'))return data.sources.every(s=>s.status==='available')?'api_only':'mixed';
 return data.sources.every(s=>s.status==='not_found')?'unsupported':'verification_pending';
}
export function canConnectMissingFiles(data:NonNullable<QueryResponse['availability']>){
 return apiSupportScope(data)==='mixed'&&data.sources.some(s=>s.status==='not_found')&&data.sources.every(s=>['available','not_found'].includes(s.status));
}
