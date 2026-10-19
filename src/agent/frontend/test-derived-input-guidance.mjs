import test from 'node:test';
import assert from 'node:assert/strict';
import {resolveInputGuidance} from './src/derivedInputGuidance.ts';

test('old response with no guidance explains synthetic data instead of generic provider text',()=>{
 const g=resolveInputGuidance({required_data:'사용자 제공 CSV의 가상비용지수',reason:'월별 시험용 합성 자료가 필요합니다.'});
 assert.equal(g.kind,'self_provided');assert.equal(g.links.length,0);assert.match(g.description,/공식 사이트에서 내려받는 통계가 아닙니다/);assert.match(g.description,/실제 자료명/);
});
test('old official-data response has safe portal candidates and a search term',()=>{
 const g=resolveInputGuidance({required_data:'소비자물가지수 총지수'});
 assert.equal(g.kind,'search_candidates');assert.equal(g.searchTerms,'소비자물가지수 총지수');assert.ok(g.links.some(l=>l.url==='https://kosis.kr/'));assert.match(g.description,/확인했다는 뜻은 아닙니다/);
});
test('own company data does not invent a public download',()=>{
 const g=resolveInputGuidance({required_data:'자사 월별 매출'});assert.equal(g.links.length,0);assert.match(g.description,/회계 장부/);
});
test('current server guidance is preserved, incomplete guidance gets a fallback',()=>{
 const g=resolveInputGuidance({required_data:'자료'});assert.equal(resolveInputGuidance({required_data:'자료',guidance:g}),g);
 assert.ok(resolveInputGuidance({required_data:'자료',guidance:{...g,title:''}}).title);
});
