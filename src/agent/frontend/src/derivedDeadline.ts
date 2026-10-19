// Multiple catalog/semantic model turns need a separate bounded analysis budget.
export const DERIVED_TIMEOUT_MS=120_000;
export function derivedBudget(query:string,state?:Record<string,unknown>|null):number {
 return state?._derived_query||/파생|구매력|통화\s*가치|실질\s*가치|교역조건|상승률|변화율|전년.*대비|전월.*대비|전기.*대비|차이.*계산|비율.*계산|나누|나눈|곱하|곱한|역수|로그|거듭제곱|누적합|이동\s*평균|기준.*100|기준\s*연도|100.*지수|지수화|두.*(?:차이|비율)|실질화|차이(?:를|가|는)?\s*(?:보여|구해|알려|그려)|차감|빼줘|합산.*(?:보여|계산)|대비.*몇.*배|분모|분자|평균.*(?:구해|계산|내줘)/.test(query)?DERIVED_TIMEOUT_MS:20_000;
}
