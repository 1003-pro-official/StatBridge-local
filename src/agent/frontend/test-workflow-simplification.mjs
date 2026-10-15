import test from 'node:test';
import assert from 'node:assert/strict';
import {automaticOutput} from './src/automaticOutput.ts';
import {analysisEntries} from './src/analysisLibrary.ts';
import {requiresColorChoice} from './src/colorRequests.ts';

const prepared={status:'need_output_config',query:'원래 질문',outputSessionId:'rows-only',outputOptions:{supportedChartTypes:['line','bar'],recommendedChartType:'line'}};
test('automatic output consumes the existing data session and preserves the original query',()=>{
 assert.deepEqual(automaticOutput(prepared),{session_ids:['rows-only'],chart_type:'auto',chart_mode:'combined',show_legend:true,natural_language:'원래 질문',quick_output:true});
});
test('missing capabilities and unresolved conditions never trigger automatic output',()=>{
 for(const status of ['no_match','need_details','need_period','need_clarification','request_failed'])assert.equal(automaticOutput({...prepared,status}),null);
 assert.equal(automaticOutput({...prepared,outputOptions:undefined}),null);
 assert.equal(automaticOutput({...prepared,outputSessionId:undefined}),null);
});
test('mixed data use the server layout reason and preserve all sessions',()=>{
 const result=automaticOutput({...prepared,outputSessionIds:['first','second'],outputOptions:{...prepared.outputOptions,combinedLayoutReason:'단위가 다릅니다'}});
 assert.equal(result.chart_mode,'separate');assert.deepEqual(result.session_ids,['first','second']);
});
test('explicit colors do not ask the same color again',()=>{
 for(const text of ['선을 빨간색으로 변경해줘','제목을 검토용으로 바꾸고 선 색상은 #123abc로 변경해줘','배경색을 rgb(10, 20, 30)으로 바꿔줘'])assert.equal(requiresColorChoice(text),false,text);
 for(const text of ['선 색상을 바꿔줘','배경색을 민트색으로 변경해줘','선 색상을 rgb(300, 0, 0)으로 변경해줘','제목은 빨간색, 배경색은 민트색으로 바꿔줘'])assert.equal(requiresColorChoice(text),true,text);
});
test('one library entry joins local conversation with account graph, retaining separate persistence',()=>{
 const local={id:'same',title:'수정한 제목',savedAt:3000,messages:[{role:'user',text:'범례 변경'}]};
 const server={id:'same',title:'저장한 제목',saved_at:2};
 const entries=analysisEntries([local],[server,{id:'other',title:'다른 분석',saved_at:1}]);
 assert.equal(entries.length,2);assert.equal(entries[0].title,'수정한 제목');assert.equal(entries[0].local,local);assert.equal(entries[0].account,server);
 assert.equal(entries[1].local,undefined);assert.equal(entries[1].savedAt,1000);
});
