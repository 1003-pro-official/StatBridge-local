// Older API responses and saved workspaces may predate server-side guidance.
// Always explain acquisition without inventing a dataset or download URL.
export type InputGuidance={kind:string;title:string;description:string;searchTerms:string;verifiedAt:string;links:Array<{label:string;url:string;note:string}>;checklist:string[]};
export function resolveInputGuidance(slot:{required_data:string;reason?:string;guidance?:InputGuidance},query=''):InputGuidance{
 if(slot.guidance?.title&&slot.guidance.description)return slot.guidance;
 const name=slot.required_data,text=name+' '+(slot.reason||'');
 const base={searchTerms:name.slice(0,120),verifiedAt:'2026-10-19',links:[] as InputGuidance['links'],checklist:['필요한 지표·항목·기간·주기·단위·기준연도를 확인해 주세요.','source에는 제공기관 또는 직접 작성한 자료의 산정 기준을 적어 주세요.']};
 if(/가상|합성|시험용|검증용/.test(text)||/가상|합성/.test(query)&&/사용자|비용지수/.test(name))return {...base,kind:'self_provided',title:'직접 준비하는 시험 자료입니다',description:'이 가상·합성 지수는 공식 사이트에서 내려받는 통계가 아닙니다. 사용자가 정한 시험값과 산정 기준을 빈 양식에 입력해 주세요. 실제 통계로 분석하려면 가상지수 대신 사용할 실제 자료명을 질문에 지정해 주세요.'};
 if(/매출|사내|자사|개인|장부|사용자.*비용/.test(name))return {...base,kind:'self_provided',title:'보유한 원자료에서 준비해 주세요',description:'회사·개인의 회계 장부나 원가 관리 자료에서 해당 기간의 값을 확인해 주세요. 공개된 공식 다운로드 자료가 있다고 가정하지 않습니다.'};
 const links=[{label:'KOSIS 국가통계포털',url:'https://kosis.kr/',note:'자료명 검색 → 항목·기간·주기 확인 → 다운로드'}];
 links.push(/금리|환율|통화|국민|물가|생산|수출|수입|금융/.test(text)?{label:'한국은행 ECOS',url:'https://ecos.bok.or.kr/',note:'자료명으로 검색하고 단위·수록기간을 확인해 주세요.'}:{label:'공공데이터포털',url:'https://www.data.go.kr/',note:'파일데이터에서 자료명과 제공기관을 확인해 주세요.'});
 return {...base,links,kind:'search_candidates',title:'자료를 찾아볼 공식 사이트',description:'아래는 공식 사이트의 검색 후보입니다. 해당 지표·기간의 파일 제공 여부를 확인했다는 뜻은 아닙니다. 직접 확인한 자료를 양식에 맞춰 올려 주세요.'};
}
