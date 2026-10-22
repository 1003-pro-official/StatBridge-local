import {withRequestDeadline,EDIT_TIMEOUT_MS} from '../requestDeadline';
import {apiFetch} from '../accountApi';
import {queryFailure,analysisTimedOut} from "./queryFailure";
import {withAnalysisDeadline,AnalysisTimeoutError} from '../analysisDeadline';
import {derivedBudget,DERIVED_TIMEOUT_MS} from '../derivedDeadline';
import { mockResponse } from "./mock";
import type { CatalogResponse, OutputEditRequest, OutputRenderRequest, QueryRequest, QueryResponse } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api";
export class EditConflictError extends Error { constructor(){super('다른 편집이 먼저 반영됐습니다. 최신 상태를 확인한 뒤 수정 내용을 다시 보내 주세요.');this.name='EditConflictError';} }

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

export async function fetchWorkspace(id:string) {
 return withRequestDeadline(async signal=>{
 const response=await apiFetch(`${API_BASE_URL}/workspace/${encodeURIComponent(id)}`,{signal});
 const data=await response.json();if(!response.ok)throw new Error(data.detail||'편집 세션을 불러오지 못했습니다.');
 return data as QueryResponse;
 },'저장 분석 불러오기 요청');
}

export async function getReportTemplates():Promise<{templates:Array<{id:string;name:string;kind:string;sample:string}>;unsupported:string[]}> {
 return withRequestDeadline(async signal=>{
  const response=await apiFetch(`${API_BASE_URL}/report/templates`,{signal});
  if(!response.ok)throw new Error('보고서 템플릿 목록을 불러오지 못했습니다.');
  return response.json();
 },'보고서 양식 조회 요청');
}

export async function exportReportFile(edit_session_id:string,revision:number|undefined,format:string):Promise<Blob> {
 return withRequestDeadline(async signal=>{
  const response=await apiFetch(`${API_BASE_URL}/report/export`,{signal,method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({edit_session_id,revision,format})});
  if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(typeof body.detail==='string'?body.detail:'보고서 출력에 실패했습니다.');}
  return response.blob();
 },'보고서 다운로드 요청');
}

export async function exportTableFile(edit_session_id:string,revision:number,format:string):Promise<{blob:Blob;filename:string}> {
 return withRequestDeadline(async signal=>{
 const response=await apiFetch(`${API_BASE_URL}/table/export`,{signal,method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({edit_session_id,revision,format})});
 if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(typeof body.detail==='string'?body.detail:'표 출력에 실패했습니다.');}
 const filename=response.headers.get('Content-Type')?.includes('zip')?'statbridge-table.zip':`statbridge-table.${format}`;
 return {blob:await response.blob(),filename};
 },'표 다운로드 요청');
}

export async function recommendReport(edit_session_id:string,revision:number|undefined):Promise<{options:Record<string,unknown>;reasons:string[]}> {
 return withRequestDeadline(async signal=>{
  const response=await apiFetch(`${API_BASE_URL}/report/recommend`,{signal,method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({edit_session_id,revision,format:'json'})});
  if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(typeof data.detail==='string'?data.detail:'차트 추천에 실패했습니다.');}
  return response.json();
 },'차트 추천 요청');
}

export async function fetchCatalog(): Promise<CatalogResponse> {
 return withRequestDeadline(async signal=>{
  const response = await apiFetch(`${API_BASE_URL}/catalog`,{signal});
  if (!response.ok) throw new Error(`카탈로그 API 오류: HTTP ${response.status}`);
  return (await response.json()) as CatalogResponse;
 },'통계표 목록 조회 요청');
}

export async function submitQuery(payload: QueryRequest,signal?:AbortSignal): Promise<QueryResponse> {
  const budget=derivedBudget(payload.query,payload.state);
  if (USE_MOCK) {
    await new Promise((resolve) => window.setTimeout(resolve, 300));
    return { ...mockResponse, query: payload.query };
  }

  try {
    return await withAnalysisDeadline(async activeSignal=>{
    const response = await apiFetch(`${API_BASE_URL}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: activeSignal,
    },budget);

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      return queryFailure(payload.query, response.status, data.detail);
    }

    return (await response.json()) as QueryResponse;
    },signal,budget);
  } catch (error) {
    if(error instanceof AnalysisTimeoutError)return analysisTimedOut(payload.query,budget);
    const message = error instanceof Error ? error.message : "network error";
    return queryFailure(payload.query, undefined, message);
  }
}

export async function submitOutput(payload: OutputRenderRequest,signal?:AbortSignal): Promise<QueryResponse> {
 return withAnalysisDeadline(async activeSignal=>{
  const response = await apiFetch(`${API_BASE_URL}/output`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: activeSignal,
  },signal?DERIVED_TIMEOUT_MS:20_000);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === "string" ? data.detail : `출력 Agent API 오류: HTTP ${response.status}`);
  }
  return (await response.json()) as QueryResponse;
 },signal);
}

export async function inspectOutputOptions(session_ids:string[]):Promise<NonNullable<QueryResponse['outputOptions']>> {
 return withRequestDeadline(async signal=>{
  const response=await apiFetch(`${API_BASE_URL}/output/options`,{signal,method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_ids})});
  if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(typeof data.detail==='string'?data.detail:'그릴 수 있는 그래프를 확인하지 못했습니다. 다시 조회해 주세요.');}
  return response.json();
 },'그래프 선택지 조회 요청');
}

export async function submitOutputEdit(payload: OutputEditRequest,derived=false): Promise<QueryResponse> {
 const budget=Math.max(EDIT_TIMEOUT_MS,derived?DERIVED_TIMEOUT_MS:derivedBudget(payload.instruction));
 return withRequestDeadline(async signal=>{
  const response = await apiFetch(`${API_BASE_URL}/output/edit`,{signal,
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  },budget);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    if(response.status===409)throw new EditConflictError();
    if(response.status===404)throw new Error("편집 시간이 만료되었거나 서버가 재시작되었습니다. 질문을 다시 실행해 새 그래프에서 수정해 주세요.");
    const fields = Array.isArray(error.detail) ? error.detail.map((item:{loc?:string[];msg?:string})=>`${item.loc?.includes('reference_files')?'참고 그래프':'수정 요청'}: ${(item.msg||'입력값을 확인해 주세요').replace(/^Value error, /,'')}`).join(' / ') : "";
    throw new Error(typeof error.detail === "string" ? error.detail : fields || `그래프 수정 오류: HTTP ${response.status}`);
  }
  return (await response.json()) as QueryResponse;
 },'편집 요청',undefined,budget);
}
