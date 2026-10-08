import assert from 'node:assert/strict';
import {colorRequests,selectedColorInstruction,colorPreview} from './colorRequests.ts';
assert.deepEqual(colorRequests('화살표부터 뒤로 빨간색으로 그리고 박스는 색을 넣어 강조해줘').map(r=>r.target),['화살표 이후 차트','박스 강조']);
assert.equal(colorRequests('격자를 지워주고 제목은 가운데로').length,0);
assert.equal(colorRequests('그 색은 유지하고 제목을 바꿔줘').length,0);
assert.equal(colorRequests('선 rgb(255, 0, 0)으로 변경해줘')[0].color,'#ff0000');
assert.equal(colorRequests('선 #112233으로 변경해줘')[0].color,'#112233');
const requests=colorRequests('현재 강조되어있는 부분보다 한칸 앞까지 색을 넣어줘');
assert.equal(requests[0].target,'강조 영역');
requests[0].color='#22c55e';
assert.match(selectedColorInstruction('기존 강조를 넓혀줘',requests),/강조 영역 #22c55e/);
console.log('COLOR_QUESTIONS_AND_TARGETS_OK');

assert.equal(colorPreview("#22c55e",.4),"rgba(34,197,94,0.4)");
requests[0].opacity=0;
assert.match(selectedColorInstruction("강조 색 변경",requests),/불투명도 0/);

assert.equal(colorRequests('화살표 부분에 크게 빨간색 화살표를 그려줘')[0].target,'화살표 기호');
assert.equal(colorRequests('화살표부터 뒤로 차트 색을 빨간색으로 그려줘')[0].target,'화살표 이후 차트');
