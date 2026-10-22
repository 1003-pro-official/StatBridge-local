import test from 'node:test';
import assert from 'node:assert/strict';
import {publicationImageSize,reportChartSize,validateChartSize} from './src/reportChartSize.ts';

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

test('custom output dimensions accept compact publication and portrait sizes without old axis caps',()=>{
 for(const size of [{width:580,height:740},{width:379,height:614},{width:496,height:419},{width:3000,height:1200}])assert.deepEqual(validateChartSize(size),size);
 assert.throws(()=>validateChartSize({width:100000,height:100000}));
});
