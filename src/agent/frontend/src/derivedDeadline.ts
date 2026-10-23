// Multiple catalog/semantic model turns need a separate bounded analysis budget.
export const DERIVED_TIMEOUT_MS=120_000;
export function derivedBudget(query:string,state?:Record<string,unknown>|null):number {
 const text=query.replace(/"[^"]*"|'[^']*'|“[^”]*”|‘[^’]*’|「[^」]*」/g,'');
 const visual=/제목|색상|색|범례|글꼴|두께|강조|음영|주석|배경|격자/.test(text);
 const symbolMath=(!visual||/계산|연산/.test(text))&&/(?:금리|환율|지수|지표|계열)\s*[−\-+×÷/]\s*.+?(?:금리|환율|지수|지표|계열)/.test(text);
 const explicitMath=/(?:계산|연산)(?:해|하|을)|산술\s*평균|평균(?:을)?\s*(?:해|내|구해)/.test(text)&&!/(?:계산|연산|평균)\s*(?:은|을|는)?\s*(?:하지|말|금지)/.test(text);
 return state?._derived_query||symbolMath||explicitMath||/파생|구매력|통화\s*가치|실질\s*가치|교역조건|상승률|변화율|전년.*대비|전월.*대비|전기.*대비|차이.*계산|비율.*계산|나누|나눈|나눠|나눗|1인당|곱하|곱한|곱해|역수|로그|거듭제곱|누적합|이동\s*평균|기준.*100|기준\s*연도|100.*지수|지수화|두.*(?:차이|비율)|실질화|차이(?:를|가|는)?\s*(?:보여|구해|알려|그려)|차감|빼줘|뺀|빼서|빼고|합산.*(?:보여|계산)|대비.*몇.*배|분모|분자|평균.*(?:구해|계산|내줘)/.test(query)?DERIVED_TIMEOUT_MS:20_000;
}
