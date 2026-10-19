import test from 'node:test';import assert from 'node:assert/strict';
import {shouldShowDerivedSupplement,availabilityAnswer} from './src/derivedAvailability.ts';
import {recoveryFor} from './src/recoveryActions.ts';
test('clarifications and API verification failures never display an empty upload panel',()=>{
 for(const result of [{analysisKind:'derived',status:'need_details'},{analysisKind:'derived',status:'request_failed'},{analysisKind:'derived',status:'need_details',availability:{status:'checked',sources:[{status:'not_found'}]}}])assert.equal(shouldShowDerivedSupplement(result),false);
});
test('only an actual missing-input or connected-file workspace opens the file UI',()=>{
 assert.equal(shouldShowDerivedSupplement({analysisKind:'derived',status:'data_unavailable',missingData:[{required_data:'file'}]}),true);
 assert.equal(shouldShowDerivedSupplement({analysisKind:'derived',status:'need_details',missingData:[{required_data:'실제 부족 원자료'}]}),true);
 assert.equal(shouldShowDerivedSupplement({analysisKind:'derived',status:'need_details',supplement:{missing:[{}],uploaded:[]}}),true);
 assert.equal(shouldShowDerivedSupplement({analysisKind:'derived',status:'need_details',supplement:{missing:[],uploaded:[],question:'조건 확인'}}),false);
});
test('normal condition confirmation never falls back to an input error message',()=>{
 const response=recoveryFor({status:'need_details'},'평균 범위를 확인해 주세요.');assert.doesNotMatch(response.question,/오류/);assert.equal(response.choices[0].label,'계산 조건 입력');
});
test('conditional date questions may be left blank when a monthly basis is chosen',()=>{
 assert.equal(availabilityAnswer(['기간 기준','특정일인 경우 날짜','평균 대상'],{0:'월평균',2:'DXY와 중국 제외'}),'기간 기준\n답변: 월평균\n평균 대상\n답변: DXY와 중국 제외');
 assert.equal(availabilityAnswer(['기간 기준'],{}),'');
});
