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
