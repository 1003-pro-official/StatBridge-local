import test from 'node:test';
import assert from 'node:assert/strict';
import {reportExportIntent} from './src/reportExportIntent.ts';
test('standalone Korean print and export instructions use fixed export routes',()=>{
  assert.equal(reportExportIntent('인쇄용 PDF로 출력해줘'),'pdf');
  assert.equal(reportExportIntent('SVG 파일로 저장해 주세요'),'svg');
  assert.equal(reportExportIntent('PNG로 다운로드해줘'),'png');
  assert.equal(reportExportIntent('JSON으로 저장해줘'),'json');
});
test('combined or unrelated edits are not silently swallowed',()=>{
  assert.equal(reportExportIntent('제목을 PDF로 바꿔줘'),null);
  assert.equal(reportExportIntent('제목을 바꾸고 PDF로 출력해줘'),null);
  assert.equal(reportExportIntent('PDF로 저장해줘; 격자는 삭제'),null);
});
