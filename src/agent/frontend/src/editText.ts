/** Display-only migration for audit text saved by earlier versions. */
export function readableEditText(text:string):string {
 const kinds:Record<string,string>={line:'선 그래프',bar:'막대 그래프',stacked_bar:'누적 막대 그래프',area:'영역 그래프',scatter:'산점도',bubble:'버블 그래프',pie:'원 그래프',donut:'도넛 그래프',histogram:'히스토그램',box:'상자 그림',heatmap:'히트맵',treemap:'트리맵',waterfall:'폭포 그래프'};
 const fields:Record<string,string>={axis_styles:'축 표시',series_styles:'데이터 표시',series_colors:'데이터 색상',series_dashes:'선 모양',range_styles:'부분 표시',presentation:'글꼴·배치',hidden_series:'숨긴 데이터',series_chart_types:'데이터별 그래프 종류',secondary_axis_series:'보조축',display_names:'데이터 표시 이름',stickers:'이모티콘',notes:'설명 메모',guides:'기준선',highlights:'강조 구간',paper_shapes:'강조 도형',report:'보고서',report_table:'표',title:'제목',subtitle:'부제',legend_position:'범례 위치',chart_type:'그래프 종류'};
 return text.split('\n').map(line=>{
  const old=line.match(/^([^:]{1,100}):\s*(?:\{|\[)/);
  if(old)return `${fields[old[1]]||(/[가-힣]/.test(old[1])?old[1]:'그래프 표시')} 설정을 변경했습니다.`;
  return line.replace(/markers\s+(False|True|false|true)/g,(_,v)=>`관측점 표시를 ${v.toLowerCase()==='true'?'켰습니다':'껐습니다'}`)
   .replace(/show_values\s+(False|True|false|true)/g,(_,v)=>`수치 표시를 ${v.toLowerCase()==='true'?'켰습니다':'껐습니다'}`)
   .replace(/(?:그래프 종류|chart_type):\s*([a-z_]+)/g,(_,v)=>`${kinds[v]||'그래프 표시 방식'} 형식으로 변경했습니다.`)
   .replace(/\b(solid|dashdot|longdash|dash|dot)\b/g,v=>({solid:'실선',dashdot:'파선과 점선',longdash:'긴 파선',dash:'파선',dot:'점선'}[v]!));
 }).join('\n');
}
