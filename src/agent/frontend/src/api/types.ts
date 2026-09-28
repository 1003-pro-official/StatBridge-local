export type Candidate = {
  table_id: string;
  table_name: string;
  score: number;
  path: string;
  frequencies: string[];
  start_period: string | null;
  end_period: string | null;
  local_csv_available: boolean;
};

export type SearchResponse = {
  status: "search_results";
  query: string;
  candidates: Candidate[];
  note: string;
};

export type SeriesChoice = {
  table_id: string;
  item_id?: string;
  classifications?: Record<string, string>;
  frequency?: string;
  start_period?: string;
  end_period?: string;
};

export type SeriesOptions = {
  table_id: string;
  table_name: string;
  items: { id: string; label: string }[];
  axes: { key: string; label: string; values: { id: string; label: string }[] }[];
  periods: Record<string, { start: string; end: string; recent_start?: string }>;
  local_csv_available: boolean;
};

export type AnalysisResponse = {
  status: "need_clarification" | "resolved" | "no_match" | "data_unavailable";
  query: string;
  reason?: "table" | "series";
  candidates?: Candidate[];
  options?: SeriesOptions;
  series?: SeriesChoice[];
  table_id?: string;
  message?: string;
  local_csv_available?: boolean;
  layout?: "combined" | "separate";
  chart?: {
    table_id: string;
    table_name: string;
    label: string;
    unit: string;
    frequency: string;
    source: string;
    points: { period: string; value: number }[];
  }[];
};
