import { mockResponse } from "./mock";
import type { CatalogResponse, OutputEditRequest, OutputRenderRequest, QueryRequest, QueryResponse } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api";
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

function localFallback(query: string, reason: string): QueryResponse {
  return {
    ...mockResponse,
    status: "no_match",
    query,
    interpretedQuery: query,
    summary: `Agent API에 연결하지 못해 UI 안전 응답으로 전환했습니다. (${reason})`,
    chart: [],
    tables: [],
    insights: [
      "UI 자체는 정상 동작하고 있습니다.",
      "START_STATBRIDGE.cmd로 Agent API와 MCP를 함께 실행해 주세요.",
    ],
    lineage: [
      { id: "ui", title: "UI 질의 수신", description: "질의 입력과 제출은 정상", status: "complete" },
      { id: "api", title: "Agent API 연결", description: reason, status: "active" },
    ],
    warnings: ["Agent API 연결 실패로 실제 통계 검색을 수행하지 못했습니다."],
  };
}

export async function fetchCatalog(): Promise<CatalogResponse> {
  const response = await fetch(`${API_BASE_URL}/catalog`);
  if (!response.ok) throw new Error(`카탈로그 API 오류: HTTP ${response.status}`);
  return (await response.json()) as CatalogResponse;
}

export async function submitQuery(payload: QueryRequest): Promise<QueryResponse> {
  if (USE_MOCK) {
    await new Promise((resolve) => window.setTimeout(resolve, 300));
    return { ...mockResponse, query: payload.query };
  }

  try {
    const response = await fetch(`${API_BASE_URL}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      const detail = typeof data.detail === "string" ? data.detail : `HTTP ${response.status}`;
      return {...localFallback(payload.query, detail), summary:detail, warnings:[detail]};
    }

    return (await response.json()) as QueryResponse;
  } catch (error) {
    const message = error instanceof Error ? error.message : "network error";
    return localFallback(payload.query, message);
  }
}

export async function submitOutput(payload: OutputRenderRequest): Promise<QueryResponse> {
  const response = await fetch(`${API_BASE_URL}/output`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === "string" ? data.detail : `출력 Agent API 오류: HTTP ${response.status}`);
  }
  return (await response.json()) as QueryResponse;
}

export async function inspectOutputOptions(session_ids:string[]):Promise<NonNullable<QueryResponse['outputOptions']>> {
  const response=await fetch(`${API_BASE_URL}/output/options`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_ids})});
  if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(typeof data.detail==='string'?data.detail:'그릴 수 있는 그래프를 확인하지 못했습니다. 다시 조회해 주세요.');}
  return response.json();
}

export async function submitOutputEdit(payload: OutputEditRequest): Promise<QueryResponse> {
  const response = await fetch(`${API_BASE_URL}/output/edit`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    if(response.status===404)throw new Error("편집 시간이 만료되었거나 서버가 재시작되었습니다. 질문을 다시 실행해 새 그래프에서 수정해 주세요.");
    const fields = Array.isArray(error.detail) ? error.detail.map((item:{loc?:string[];msg?:string})=>`${item.loc?.slice(1).join(' · ')||'수정 요청'}: ${item.msg||'입력값을 확인해 주세요'}`).join(' / ') : "";
    throw new Error(typeof error.detail === "string" ? error.detail : fields || `그래프 수정 오류: HTTP ${response.status}`);
  }
  return (await response.json()) as QueryResponse;
}
