export type ColorRequest = {target:string;color:string;opacity:number};
export function colorPreview(color:string,opacity:number):string {
  const safe=/^#[\da-f]{6}$/i.test(color)?color:'#3b82f6';
  return `rgba(${parseInt(safe.slice(1,3),16)},${parseInt(safe.slice(3,5),16)},${parseInt(safe.slice(5,7),16)},${opacity})`;
}
const names:Record<string,string>={빨간:'#ef4444',빨강:'#ef4444',노란:'#eab308',노랑:'#eab308',초록:'#22c55e',녹색:'#22c55e',파란:'#3b82f6',파랑:'#3b82f6',보라:'#8b5cf6',주황:'#f97316',검정:'#111827',흰색:'#ffffff'};
export function colorRequests(text:string):ColorRequest[] {
  const pieces=text.split(/[\n;]+|(?=화살표|사각형|박스|타원|원 부분|격자|배경|제목|부제|범례|가로축|세로축|보조축|글자|텍스트|강조(?:된|되어|영역))/);
  const requests:ColorRequest[]=[];
  const arrowClause=text.match(/화살표(?:(?!박스|사각형|격자).)*/)?.[0]||'';
  const arrowGlyph=/그려|넣|추가/.test(arrowClause)&&!/차트|그래프|선 색|선의|부터|이후|뒤로/.test(arrowClause);
  for(const piece of pieces){
    if(/(?:색|빨간|노란|초록|파란|보라).*유지/.test(piece)&&!/(바꿔|변경|넣|채워|그려)/.test(piece))continue;
    if(!/색|빨간|빨강|노란|노랑|초록|파란|파랑|보라|주황|검정|채워|#[\da-f]{6}|rgb\s*\(/i.test(piece)||/색(?:상)?(?:을|은)?\s*(?:삭제|지워|제거)/.test(piece))continue;
    const target=/화살표/.test(piece)?(arrowGlyph?'화살표 기호':'화살표 이후 차트'):/사각형|박스/.test(piece)?'박스 강조':/타원|원 부분/.test(piece)?'원 강조':/격자/.test(piece)?'격자':/배경/.test(piece)?'배경':/제목/.test(piece)?'제목':/부제/.test(piece)?'부제':/범례/.test(piece)?'범례':/가로축|세로축|보조축/.test(piece)?piece.match(/가로축|세로축|보조축/)![0]:/글자|텍스트/.test(piece)?'글자':/강조/.test(piece)?'강조 영역':'차트';
    if(requests.some(r=>r.target===target))continue;
    const hex=piece.match(/#[\da-f]{6}/i)?.[0];
    const named=Object.entries(names).find(([name])=>piece.includes(name));
    const rgb=piece.match(/rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)/i);
    const rgbHex=rgb&&rgb.slice(1).every(n=>Number(n)<=255)?'#'+rgb.slice(1).map(n=>Number(n).toString(16).padStart(2,'0')).join(''):undefined;
    requests.push({target,color:hex||rgbHex||named?.[1]||'#3b82f6',opacity:/강조/.test(target)?.25:1});
  }
  return requests;
}
export function selectedColorInstruction(instruction:string,requests:ColorRequest[]):string {
  return `${instruction}\n사용자가 고른 RGB 색상(앞서 언급한 색보다 이 선택을 우선): ${requests.map(r=>`${r.target} ${r.color} 불투명도 ${r.opacity.toFixed(2)}`).join(', ')}.`;
}
