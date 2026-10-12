/* Mechanical slicing of the six cleaned RGBA atlases. No original files changed.
 * Run with STICKER_SHARP_MODULE pointing at an installed sharp package.
 * Input is an array of six paths to the cleaned atlases, passed as JSON file.
 */
const fs=require('fs'),path=require('path');
const sharp=require(process.env.STICKER_SHARP_MODULE||'sharp');
const root=path.resolve(__dirname,'..');
const output=path.join(root,'src/agent/frontend/public/stickers');
const sheets=[
  {category:'그래프',rows:[0,290,505,745,980,1280],cols:[0,340,640,940,1280],last:[0,240,430,645,850,1015,1280],names:'세로 막대|가로 막대|누적 막대|그룹 막대|꺾은선|다중 꺾은선|영역 그래프|누적 영역|원 그래프|도넛|산점도|버블|히스토그램|상자 수염|방사형|히트맵|폭포|깔때기|트리맵|혼합 그래프|캔들|게이지'},
  {category:'편집',rows:[0,275,500,745,980,1280],cols:[0,266,514,768,1018,1280],last:[0,315,610,885,1280],names:'관측점 추가|관측점 삭제|관측점 이동|곡선 조절|곡선 부드럽게|직선 연결|연결|연결 해제|영역 선택|확대|축소|이동|커서|올가미|스포이트|붓|지우개|복사|되돌리기|다시 적용|새로고침|잠금|잠금 해제|크기 조절'},
  {category:'스타일',rows:[0,235,460,670,870,1055,1280],cols:[0,256,512,768,1024,1280],names:'팔레트|색 채우기|색 펜|선 두께|선 모양|마커 모양|마커 크기|투명도|그라데이션|사선 무늬|글꼴|굵게|기울임|숫자 형식|백분율|통화|격자|격자 제거|범례|범례 제거|값 표시|값 표시 제거|여러 패널|둥근 모서리|그림자|테두리|점선 테두리|굵은 테두리|막대 미리보기|상자 강조'},
  {category:'축·배치',rows:[0,290,530,770,1000,1280],cols:[0,270,525,770,1020,1280],last:[0,270,525],names:'가로축|세로축|보조축|축 제목|눈금|최솟값 최댓값|자동 범위|일반 축|로그 축|눈금 각도|오름차순|내림차순|축 방향|왼쪽 정렬|가운데 정렬|오른쪽 정렬|막대 간격|그래프 확대|전체 맞춤|여백|격자 배치|비율 잠금'},
  {category:'강조·주석',rows:[0,300,540,750,995,1280],cols:[0,270,520,748,1000,1280],names:'텍스트|말풍선|빨간 화살표|강조 상자|타원|선택 상자|추세선|수평 강조|빨간 십자|곡선 신뢰 구간|예측|오차 막대|신뢰 구간|경고 기준선|별|위치 핀|메모|돋보기|자|과녁|추세 영역|스포트라이트|세로 기준선|보라 수평선|자르기'},
  {category:'데이터·저장',rows:[0,275,535,765,990,1280],cols:[0,270,525,775,1025,1280],names:'데이터 불러오기|그래프 내보내기|저장|동기화 저장|폴더|엑셀 연결|엑셀 연결 해제|필터|합계|그룹|그룹 해제|피벗|병합|분리|데이터 편집|숨김|표시|정렬|주의|검증|공유|PNG 저장|SVG PDF 저장|인쇄|보고서 공유'},
];

function isolate(data,width,height) {
  // Keep separate substantial pieces in a composite icon. Discard disconnected
  // tiny atlas debris, never fill holes or replace intentional colors.
  const seen=new Uint8Array(width*height);
  for(let i=0;i<seen.length;i++) {
    if(seen[i]||data[i*4+3]<16)continue;
    const queue=[i];seen[i]=1;
    for(let q=0;q<queue.length;q++) {
      const n=queue[q],x=n%width,y=Math.floor(n/width);
      for(const v of [x? n-1:-1,x+1<width?n+1:-1,y?n-width:-1,y+1<height?n+width:-1])
        if(v>=0&&!seen[v]&&data[v*4+3]>=16){seen[v]=1;queue.push(v);}
    }
    const xs=queue.map(n=>n%width),ys=queue.map(n=>Math.floor(n/width));
    const l=Math.min(...xs),r=Math.max(...xs),t=Math.min(...ys),b=Math.max(...ys);
    const borderFragment=((r-l<width*.18)&&(l<3||r>width-4))||((b-t<height*.18)&&(t<3||b>height-4));
    if(queue.length<100||borderFragment)for(const n of queue)data[n*4+3]=0;
  }
  for(let i=0;i<seen.length;i++)if(data[i*4+3]<16)data[i*4+3]=0;
  let left=width,right=-1,top=height,bottom=-1;
  for(let y=0;y<height;y++)for(let x=0;x<width;x++)if(data[(y*width+x)*4+3]){left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);}
  if(right<left)throw Error('Empty icon cell');
  return {left,top,width:right-left+1,height:bottom-top+1};
}
(async()=>{
  const inputs=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));if(inputs.length!==6)throw Error('Six RGBA atlases required');
  fs.mkdirSync(output,{recursive:true});const catalog=[];
  for(let s=0;s<sheets.length;s++) {
    const sheet=sheets[s],names=sheet.names.split('|');let index=0;
    const image=await sharp(inputs[s]).resize(1280,1280).ensureAlpha().raw().toBuffer();
    for(let row=0;row<sheet.rows.length-1;row++) {
      const cols=row===sheet.rows.length-2&&sheet.last?sheet.last:sheet.cols;
      for(let col=0;col<cols.length-1;col++) {
        const rect={left:cols[col],top:sheet.rows[row],width:cols[col+1]-cols[col],height:sheet.rows[row+1]-sheet.rows[row]};
        // The funnel intentionally extends a few pixels into the previous gutter.
        if(s===0&&row===4&&col===1){rect.left=222;rect.width=430-222;}
        const {data,info}=await sharp(image,{raw:{width:1280,height:1280,channels:4}}).extract(rect).raw().toBuffer({resolveWithObject:true});
        const bounds=isolate(data,info.width,info.height);
        const id=`sticker-${s+1}-${String(++index).padStart(2,'0')}`,file=`${id}.png`;
        const png=await sharp(data,{raw:info}).extract(bounds).extend({top:8,bottom:8,left:8,right:8,background:{r:0,g:0,b:0,alpha:0}}).png().toBuffer();
        const meta=await sharp(png).metadata();fs.writeFileSync(path.join(output,file),png);
        catalog.push({id,name:names[index-1],category:sheet.category,file,width:meta.width,height:meta.height});
      }
    }
    if(index!==names.length)throw Error(`Sheet ${s+1}: ${index} vs ${names.length}`);
  }
  fs.writeFileSync(path.join(output,'catalog.json'),JSON.stringify(catalog,null,2)+'\n');
  console.log(JSON.stringify({icons:catalog.length,categories:sheets.map(s=>s.category),output}));
})().catch(e=>{console.error(e);process.exitCode=1;});
