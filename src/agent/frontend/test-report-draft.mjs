import test from 'node:test';
import assert from 'node:assert/strict';
import {reportDraftHtml} from './src/reportDraftDocument.ts';
import {publicationImageSize,reportChartSize,resizeReportChart,validateChartSize} from './src/reportChartSize.ts';

const doc={title:'검증 그래프',image:'data:image/png;base64,aGVsbG8=',paragraphs:['간략한 설명입니다.'],source:'자료: 한국은행',scope:'2026년 1월~7월'};
test('standalone draft includes its own image before the explanation and preserves intrinsic ratio',()=>{
 const html=reportDraftHtml(doc);
 assert.ok(html.indexOf('<img')<html.indexOf('<p>간략한 설명'));
 assert.ok(html.includes(doc.image));assert.ok(html.includes('자료: 한국은행'));
 assert.match(html,/width:auto;height:auto;max-width:100%/);
 assert.match(html,/object-fit:contain/);assert.match(html,/@page\{size:A4/);
});
test('report text is escaped and arbitrary image URLs cannot execute or fetch resources',()=>{
 const html=reportDraftHtml({...doc,title:'<script>alert(1)</script>',paragraphs:['<img src=x onerror="alert(1)">']});
 assert.ok(!html.includes('<script>'));assert.ok(html.includes('&lt;script&gt;'));
 assert.throws(()=>reportDraftHtml({...doc,image:'https://example.com/track.png'}));
 assert.throws(()=>reportDraftHtml({...doc,image:'data:image/svg+xml,<svg onload="alert(1)"/>'}));
});

test('report captures the displayed chart ratio instead of expanding to 1400px',()=>{
 assert.deepEqual(reportChartSize({height:520},{width:650,height:520}),{width:650,height:520});
 assert.deepEqual(reportChartSize({height:520,meta:{publicationYoy:true}}),{width:715,height:662});
 assert.deepEqual(reportChartSize({width:1200,height:600}),{width:1200,height:600});
 const scaled=reportChartSize({}, {width:325,height:260});
 assert.equal(scaled.width/scaled.height,1.25);
});

test('reference publication ratio wins over viewport sizing for PNG and report exports',()=>{
 const layout={width:715,height:662,meta:{publicationYoy:true}};
 assert.deepEqual(reportChartSize(layout,{width:650,height:520}),{width:715,height:662});
 assert.deepEqual(reportChartSize(layout,{width:400,height:900}),{width:715,height:662});
 assert.deepEqual(reportChartSize({height:520,meta:{publicationYoy:true}},{width:650,height:520}),{width:715,height:662});
 assert.deepEqual(publicationImageSize({}),undefined);
 assert.deepEqual(reportChartSize({...layout,width:1000,height:700}),{width:1000,height:700});
});

test('locked pixel edits retain the original ratio and unlocked edits accept a new ratio',()=>{
 const original={width:650,height:520};
 assert.deepEqual(resizeReportChart(original,'width',1300,1.25,true),{width:1300,height:1040});
 assert.deepEqual(resizeReportChart(original,'height',800,1.25,true),{width:1000,height:800});
 assert.deepEqual(resizeReportChart(original,'width',1000,1.25,false),{width:1000,height:520});
 for(const size of [{width:0,height:520},{width:650,height:NaN},{width:32000001,height:1},{width:650.5,height:520},{width:650,height:100000}])assert.throws(()=>validateChartSize(size));
});

test('saved HTML retains applied pixel dimensions and validates them',()=>{
 const html=reportDraftHtml({...doc,imageWidth:1300,imageHeight:1040});
 assert.match(html,/width="1300" height="1040"/);
 assert.throws(()=>reportDraftHtml({...doc,imageWidth:1300}));
 assert.throws(()=>reportDraftHtml({...doc,imageWidth:Infinity,imageHeight:1040}));
});


test('custom output dimensions accept compact publication and portrait sizes without old axis caps',()=>{
 for(const size of [{width:580,height:740},{width:379,height:614},{width:496,height:419},{width:3000,height:1200}])assert.deepEqual(validateChartSize(size),size);
 assert.throws(()=>validateChartSize({width:100000,height:100000}));
});
