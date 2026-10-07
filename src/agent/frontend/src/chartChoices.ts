import type {ChartType} from './api/types';

export const chartLabels:Record<ChartType,string>={line:'선 그래프',bar:'막대 그래프',stacked_bar:'누적 막대 그래프',area:'영역 그래프',scatter:'산점도',bubble:'버블 그래프',pie:'원 그래프',donut:'도넛 그래프',histogram:'히스토그램',box:'상자 그림',heatmap:'히트맵',treemap:'트리맵',waterfall:'폭포 그래프'};
export const chartDescriptions:Record<ChartType,string>={line:'시간에 따른 변화',bar:'시점별 값 비교',stacked_bar:'여러 계열을 쌓아 비교',area:'변화를 면적으로 표시',scatter:'두 지표의 관계',bubble:'세 지표를 위치와 크기로 비교',pie:'같은 시점의 구성비',donut:'같은 시점의 구성비',histogram:'값이 어느 구간에 모이는지',box:'값의 분포와 퍼짐',heatmap:'계열·시점별 값을 색으로 비교',treemap:'구성비를 사각형 크기로 비교',waterfall:'시점 사이 증감 표시'};
export function allowedCharts(types?:ChartType[]):ChartType[]{
  return Array.from(new Set(types||[])).filter(type=>type in chartLabels);
}

export function blockedCharts(types?:ChartType[],reasons?:Partial<Record<ChartType,string>>):Array<{type:ChartType;reason:string}>{
  const allowed=new Set(allowedCharts(types));
  return (Object.keys(chartLabels) as ChartType[]).filter(type=>!allowed.has(type)).map(type=>({type,
    reason:reasons?.[type]||'지원 조건을 확인할 정보가 없습니다. 데이터 조회를 다시 진행해 주세요.'}));
}
