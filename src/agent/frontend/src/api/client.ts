import type { AnalysisResponse, SearchResponse, SeriesChoice } from "./types";

export async function searchTables(query: string): Promise<SearchResponse> {
  const base = import.meta.env.VITE_API_BASE_URL ?? "/api";
  const response = await fetch(`${base}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!response.ok) {
    throw new Error(response.status === 400 ? "질문을 확인해 주세요." : `검색 서버 오류 (${response.status})`);
  }
  return response.json() as Promise<SearchResponse>;
}

export async function analyze(query: string, series: SeriesChoice[] = [], source: "kosis" | "local" = "kosis"): Promise<AnalysisResponse> {
  const base = import.meta.env.VITE_API_BASE_URL ?? "/api";
  const response = await fetch(`${base}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, series, source }),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `분석 서버 오류 (${response.status})`);
  return body as AnalysisResponse;
}
