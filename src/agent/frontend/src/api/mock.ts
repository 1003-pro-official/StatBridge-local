import type { QueryResponse } from "./types";

// Mock mode must not present invented statistics as verified KOSIS results.
export const mockResponse: QueryResponse = {
  status: "no_match",
  query: "통계 질문",
  interpretedQuery: "Mock UI 확인",
  summary: "Mock 모드에서는 실제 통계 수치를 표시하지 않습니다.",
  period: { start: "-", end: "-" },
  frequency: "-",
  chart: [],
  chartMode: null,
  tables: [],
  insights: ["실제 결과를 확인하려면 Agent API와 KOSIS 연결을 사용해 주세요."],
  lineage: [
    { id: "mock", title: "Mock UI", description: "실데이터 조회를 수행하지 않음", status: "active" },
  ],
  warnings: ["예시 수치를 검증된 통계처럼 표시하지 않습니다."],
};
