import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {initialQueryRequest} from './src/querySubmission.ts';

for(const query of [
  '예금은행 고정 및 변동금리대출 비중과 신용카드 지급 내역을 2020년부터 2025년까지 그래프 그려줘',
  '예금은행 대출금리와 수신금리를 2020~2025 비교해줘',
  '지역별 결제통화(수출)와 신용카드를 2020년부터 2025년까지 보여줘',
  '잔액표, 거래표 그리고 신용카드를 비교해줘',
  '경제활동별 GDP 및 GNI(원계열 명목 분기 및 연간) 그래프',
])test(query,()=>assert.deepEqual(initialQueryRequest('  '+query+'  '),{query,execute:true}));

test('UI submits original request once, without hard-coded loan/rate questions',()=>{
  const app=readFileSync(new URL('./src/App.tsx',import.meta.url),'utf8');
  const submit=app.slice(app.indexOf('const onSubmit ='),app.indexOf('const executeMultiIntents='));
  assert.match(submit,/submitQuery\(initialQueryRequest\(query\)\)/);
  assert.equal((submit.match(/submitQuery\(/g)||[]).length,1);
  assert.doesNotMatch(submit,/isLoanRateComparison|대출 얼마나 늘었어|금리 추이를 보여줘/);
});
