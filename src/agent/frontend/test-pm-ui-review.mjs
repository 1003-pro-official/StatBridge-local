import test from 'node:test';
import assert from 'node:assert/strict';
import {displayedPeriod,observationDate,emptyAvailablePeriod,groupSources,resultInsights,savedTime,titlePeriodMismatch} from './src/resultPresentation.ts';
import {queryFailure} from './src/api/queryFailure.ts';
import {colorRequests} from './src/colorRequests.ts';
import {recoveryFor} from './src/recoveryActions.ts';

test('restored dates follow monthly observations, including leap years',()=>{
 assert.deepEqual(displayedPeriod([{frequency:'M',points:[{date:'202412',value:1},{date:'202402',value:2}]}]),{start:'2024-02-01',end:'2024-12-31'});
 assert.equal(observationDate('202402','M',true),'2024-02-29');
});
test('quarter codes use quarters, not months, and restored dates update after edits',()=>{
 assert.deepEqual(displayedPeriod([{frequency:'Q',points:[{date:'202401',value:1},{date:'202404',value:2}]}]),{start:'2024-01-01',end:'2024-12-31'});
 assert.equal(observationDate('2025Q2','Q',true),'2025-06-30');
 assert.equal(observationDate('2024','A',true),'2024-12-31');
 assert.deepEqual(displayedPeriod([]),{start:'',end:''});
});
test('invalid observation dates are never fabricated',()=>{
 for(const code of ['202413','20240230','n/a'])assert.equal(observationDate(code,'M'),'');
 assert.equal(observationDate('202405','Q'),'');
});
test('inverted common availability stops date selection',()=>{
 assert.equal(emptyAvailablePeriod({min:'1996-01-01',max:'1964-12-31'}),true);
 assert.equal(emptyAvailablePeriod({min:'2024-01-01',max:'2024-01-01'}),false);
});
test('period text in a title is compared with the actual observations',()=>{
 const actual={start:'2024-01-01',end:'2025-12-31'};
 assert.equal(titlePeriodMismatch('2016~2025년 GDP 성장기여도',actual),true);
 assert.equal(titlePeriodMismatch('2024~2025년 GDP 성장기여도',actual),false);
 assert.equal(titlePeriodMismatch('생산자물가지수(2020=100)',actual),false);
});
test('compound title and line color request asks only for the line color',()=>{
 const request=colorRequests('제목을 검토용 생산자물가지수로 바꾸고 선 색상을 빨간색으로 변경해줘.');
 assert.deepEqual(request,[{target:'차트',color:'#ef4444',opacity:1}]);
 assert.deepEqual(colorRequests('제목 색상은 파란색으로 변경하고 선 색상은 빨간색으로 변경해줘').map(r=>r.target),['제목','차트']);
});
test('source cards deduplicate tables while preserving different items and units',()=>{
 const table={tableId:'DT_1',name:'표',source:'한국은행 · KOSIS',item:'가계',unit:'%'};
 const grouped=groupSources([table,{...table,item:'기업'},table]);
 assert.equal(grouped.length,1);assert.equal(grouped[0].item,'가계 / 기업');
});
test('processing logs are shown as evidence, separate from observation descriptions',()=>{
 const insight='대출금리는 5.04%에서 4.64%로 하락했습니다.';
 assert.deepEqual(resultInsights(['출력 Agent가 MCP 24개 행을 2개 계열로 변환','대출금리: DT_121Y006',insight]),{logs:['출력 Agent가 MCP 24개 행을 2개 계열로 변환','대출금리: DT_121Y006'],observations:[insight]});
});
test('input validation errors preserve field messages and offer period correction',()=>{
 const result=queryFailure('질문',422,[{loc:['body','period_start'],msg:'시작일이 종료일 이후입니다'}]);
 assert.match(result.summary,/period_start/);assert.equal(result.recovery.issue,'input');
 assert.deepEqual(recoveryFor(result,result.summary).choices.map(c=>c.id),['period','revise']);
 assert.deepEqual(result.insights,[]);assert.deepEqual(result.warnings,[]);
});
for(const [status,issue] of [[500,'server'],[503,'server'],[429,'rate_limit'],[undefined,'network']])test(`${issue} offers retry without claiming missing data or launcher instructions`,()=>{
 const result=queryFailure('질문',status,undefined);
 assert.equal(result.status,'request_failed');assert.equal(result.recovery.issue,issue);
 assert.equal(result.recovery.choices[0].id,'retry');assert.doesNotMatch(JSON.stringify(result),/START_STATBRIDGE|지원 데이터 없음/);
});
test('auth and non-period input errors do not offer retries or date selection',()=>{
 for(const [status,issue] of [[401,'auth'],[403,'auth'],[400,'input']]){
  const result=queryFailure('질문',status,'입력 조건을 확인해 주세요');assert.equal(result.recovery.issue,issue);assert.deepEqual(result.recovery.choices.map(c=>c.id),['revise']);
 }
});
test('saved times display only recorded timestamps',()=>{
 assert.notEqual(savedTime(1720000000),'저장 시점 정보 없음');assert.equal(savedTime(0),'저장 시점 정보 없음');
});
