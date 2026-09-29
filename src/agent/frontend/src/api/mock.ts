import type { QueryResponse } from "./types";

export const mockResponse: QueryResponse = {
  query: "2020년 이후 한국의 기준금리와 소비자물가상승률을 비교해줘",
  interpretedQuery: "기준금리와 소비자물가상승률의 월별 시계열 비교",
  summary:
    "두 지표는 2022년부터 함께 상승했지만, 기준금리는 물가보다 늦게 정점을 형성한 뒤 완만하게 하락했습니다.",
  period: { start: "2020.01", end: "2025.08" },
  frequency: "월",
  chart: [
    { id: "rate", label: "기준금리", unit: "%", color: "#4568ff", points: [
      { date: "2020", value: 0.75 }, { date: "2021", value: 0.5 }, { date: "2022", value: 2.5 },
      { date: "2023", value: 3.5 }, { date: "2024", value: 3.25 }, { date: "2025", value: 2.75 },
    ]},
    { id: "inflation", label: "소비자물가상승률", unit: "%", color: "#ff805e", points: [
      { date: "2020", value: 0.5 }, { date: "2021", value: 2.5 }, { date: "2022", value: 5.1 },
      { date: "2023", value: 3.6 }, { date: "2024", value: 2.3 }, { date: "2025", value: 2.1 },
    ]},
  ],
  chartMode: "combined",
  tables: [
    {
      tableId: "DT_301Y056",
      name: "한국은행 기준금리 및 여수신금리",
      source: "한국은행 · KOSIS",
      item: "한국은행 기준금리",
      unit: "연 %",
    },
    {
      tableId: "DT_301Y013",
      name: "소비자물가 등락률",
      source: "한국은행 · KOSIS",
      item: "소비자물가상승률",
      unit: "전년동월비 %",
    },
  ],
  insights: [
    "2022년 하반기 이후 기준금리 인상과 함께 소비자물가상승률이 둔화되는 경향을 보였습니다.",
    "물가 상승은 금리 변화에 약 3~6개월 앞서 움직이는 패턴이 관찰됩니다.",
    "2024년 이후 두 지표 모두 완화되는 추세입니다.",
  ],
  lineage: [
    { id: "parse", title: "자연어 분석", description: "지표 2개 · 기간 · 비교 의도 추출", status: "complete" },
    { id: "search", title: "통계표 탐색", description: "Hybrid Retrieval 후보 12건 검색", status: "complete" },
    { id: "plan", title: "Query Planner", description: "표·항목·기간·월 주기 확정", status: "complete" },
    { id: "fetch", title: "KOSIS 조회", description: "MCP fetch_data 2회 호출", status: "complete" },
    { id: "merge", title: "정합·병합", description: "월 기준 병합, 단위 유지", status: "active" },
  ],
  warnings: [],
};
