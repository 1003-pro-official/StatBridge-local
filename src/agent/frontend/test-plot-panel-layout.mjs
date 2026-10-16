import test from 'node:test';import assert from 'node:assert/strict';import {panelGeometry,splitPlotAnnotations} from './src/plotPanelLayout.ts';
test('stacked panels retain enough height for long subplot titles',()=>{const x=panelGeometry({data:[{yaxis:'y'},{yaxis:'y2'}],layout:{height:880,yaxis:{domain:[.59,1]},yaxis2:{domain:[0,.41]},annotations:[{text:'긴 통계표 제목<br>두 번째 줄<br>세 번째 줄'}]}});assert.equal(x.multi,true);assert.equal(x.rows,2);assert.ok(x.minHeight>=880);assert.ok(x.titleSpace>=80);});
test('shared secondary axes are one panel; horizontal panels remain distinct',()=>{assert.equal(panelGeometry({data:[{yaxis:'y'},{yaxis:'y2'}],layout:{yaxis:{domain:[0,1]},yaxis2:{domain:[0,1]}}}).multi,false);const x=panelGeometry({data:[{xaxis:'x'},{xaxis:'x2'}],layout:{xaxis:{domain:[0,.4]},xaxis2:{domain:[.6,1]}}});assert.equal(x.multi,true);assert.equal(x.rows,1);});

test('all nonempty charts keep a drawable body; larger comparisons grow further',()=>{const size=n=>panelGeometry({data:Array.from({length:n},(_,i)=>({name:`series ${i}`,type:'scatter'})),layout:{}});assert.equal(size(1).minHeight,420);assert.equal(size(2).minHeight,420);assert.equal(size(1).expanded,true);assert.equal(size(2).expanded,true);assert.equal(size(3).minHeight,520);assert.equal(size(4).minHeight,520);assert.equal(size(5).minHeight,760);assert.ok(size(8).minHeight>size(5).minHeight);assert.equal(size(4).multi,false);assert.equal(size(4).expanded,true);});
test('duplicate traces and hidden series do not inflate the visible series count',()=>{const result=panelGeometry({data:[{name:'one'},{name:'one'},{name:'two'},{name:'hidden',visible:false},{name:'legend only',visible:'legendonly'}],layout:{}});assert.equal(result.series,2);assert.equal(result.minHeight,420);});
test('a shared dual axis receives real height without being mistaken for two panels',()=>{
 const geometry=panelGeometry({data:[{name:'잔액',type:'scatter',yaxis:'y'},{name:'증가율',type:'bar',yaxis:'y2'}],layout:{yaxis:{domain:[0,1]},yaxis2:{domain:[0,1]},height:580}});
 assert.equal(geometry.multi,false);assert.equal(geometry.expanded,true);assert.ok(geometry.minHeight>=420);
});

test('pie, donut and treemap retain a drawable domain above the value explanation',()=>{for(const type of ['pie','treemap']){const g=panelGeometry({data:[{type,labels:['a','b'],values:[4,6]}],layout:{height:900,margin:{t:100,b:500},annotations:[{text:'many<br>lines<br>below<br>the chart',y:-.08,font:{size:12}}]}});assert.equal(g.domainChart,true);assert.equal(g.expanded,true);assert.ok(g.minHeight>=500);assert.equal(g.titleSpace,35);}});

test('automatic captions are outside axes for 1 through 10 series; user marks remain',()=>{for(let count=1;count<=10;count++){const figure={data:Array.from({length:count},(_,i)=>({name:`s${i}`})),layout:{annotations:[{text:'자료: KOSIS',yref:'paper',y:-.2},{text:'기준 시점',yref:'paper',y:-.08},{name:'user-note',text:'사용자 표시',yref:'paper',y:-.1},{text:'패널 제목',yref:'paper',y:1}]}};const captions=splitPlotAnnotations(figure);assert.equal(captions.footer.length,2);assert.deepEqual(captions.plot.map(a=>a.text),['사용자 표시','패널 제목']);assert.ok(panelGeometry(figure).minHeight>=260);}});

// The renderer preserves a user note ID for subsequent edits. Outside notes
// must move to the HTML footer before the responsive chart shrinks its margin.
test('named below-chart notes remain visible outside the responsive plot',()=>{
 for(let count=1;count<=10;count++){
  const note={name:'saved-note-id',text:'그래프 설명 위치',xref:'paper',yref:'paper',x:0,y:0,yshift:-180,yanchor:'top'};
  const source={name:'statbridge-footer:0',text:'자료: KOSIS',yref:'paper',y:0,yshift:-140};
  const inside={name:'inside-note',text:'관측점 설명',yref:'paper',y:.8};
  const figure={data:Array.from({length:count},(_,i)=>({name:`s${i}`})),layout:{annotations:[source,note,inside]}};
  const captions=splitPlotAnnotations(figure);
  assert.deepEqual(captions.footer.map(a=>a.text),['자료: KOSIS','그래프 설명 위치']);
  assert.deepEqual(captions.plot,[inside]);
  assert.equal(captions.footer[1].name,'saved-note-id');
  assert.equal(figure.layout.annotations.length,3);
 }
});
