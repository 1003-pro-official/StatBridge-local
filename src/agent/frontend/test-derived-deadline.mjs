import test from 'node:test';
import assert from 'node:assert/strict';
import {derivedBudget} from './src/derivedDeadline.ts';
import {analysisTimedOut} from './src/api/queryFailure.ts';

test('derived plans and followups get a bounded multi-turn budget, direct lookup keeps 20s',()=>{
 assert.equal(derivedBudget('경제심리지수 추이'),20_000);
 assert.equal(derivedBudget('수출물가와 수입물가 상승률 차이를 계산'),120_000);
 assert.equal(derivedBudget('월별로 해주세요',{_derived_query:'구매력 변화율'}),120_000);
 const failed=analysisTimedOut('파생지표',120_000);
 assert.equal(failed.analysisKind,'derived');assert.match(failed.summary,/120초/);
 assert.equal(failed.recovery.preserveState,true);
});

test('natural division and subtraction forms use the derived budget',()=>{
 for(const query of [
  '한국은행의 명목 GDP를 세계은행의 인구로 나눠 1인당 GDP를 계산해줘',
  '세계은행의 배출량을 인구로 나눠 그래프로 보여줘',
  '대출금리에서 저축성수신금리를 뺀 금리차를 계산해줘',
  '두 지수를 곱해 그래프로 보여줘',
 ])assert.equal(derivedBudget(query),120_000,query);
 assert.equal(derivedBudget('세계은행 인구 자료를 찾아줘'),20_000);
});
