import type {QueryResponse} from './api/types';

export default function SummaryEvidence({result}:{result:QueryResponse}) {
 const explanation=result.outputSpec?.explanation;
 if(!explanation)return null;
 const facts=explanation.facts??[];
 const selected=new Set(explanation.factIds??[]);
 return <div className="summary-evidence">
  <p>조회 원자료의 관측 요약입니다. 변화는 표시값의 반올림 전 원자료로 계산합니다. 원인·전망을 추정하지 않습니다.</p>
  {explanation.scope?.transform&&!['none','raw'].includes(explanation.scope.transform)&&<p>그래프 변환: {({cumulative:'누적',average:'평균',growth_rate:'증가율',year_over_year:'전년동기 증가율'} as Record<string,string>)[explanation.scope.transform]??explanation.scope.transform}. 요약은 변환 전 원자료 기준입니다.</p>}
  {/원계열/.test(result.interpretedQuery)&&<p>원계열 자료입니다. 전기 대비 변화에는 계절 영향이 포함될 수 있으며 계절조정 성장률을 뜻하지 않습니다.</p>}
  <details><summary>문장별 수치·계산 근거 확인</summary>{facts.filter(f=>selected.has(f.id)).map(f=><article key={f.id}><p>{f.text}</p><small>근거 ID: {f.id}{f.unit?` · 단위: ${f.unit}`:''}{f.formula?` · 산식: ${({"latest - baseline":"최신 값 − 비교 기준 값","left - right":"앞 계열 − 뒤 계열"} as Record<string,string>)[f.formula]??f.formula}`:''}{f.result?` · 결과: ${f.result}`:''}</small><ul>{f.observations.map((p,i)=><li key={i}>{p.date}: {p.value}</li>)}</ul></article>)}</details>
 </div>;
}
