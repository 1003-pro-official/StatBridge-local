export type ChartPoint = {
  date: string;
  value: number;
};

export type ChartSeries = {
  id: string;
  label: string;
  unit: string;
  color: string;
  points: ChartPoint[];
};

export type ChartType = "line" | "bar" | "stacked_bar" | "area" | "scatter" | "bubble" | "pie" | "donut" | "histogram" | "box" | "heatmap" | "treemap" | "waterfall";

export type SelectedTable = {
  tableId: string;
  name: string;
  source: string;
  item: string;
  unit: string;
};

export type LineageStep = {
  id: string;
  title: string;
  description: string;
  status: "complete" | "active";
};

export type ClarificationOption = {
  label: string;
  value: string;
};

export type Clarification = {
  id: string;
  question: string;
  ui: string;
  options: ClarificationOption[];
};

export type QueryState = {
  original_query?: string;
  confirmed?: Record<string, string>;
  confirmed_terms?: string[];
  asked_clarifications?: string[];
  candidate_tables?: Array<{ table_id: string; table_name: string; score: number }>;
  status?: string;
  [key: string]: unknown;
};

export type QueryResponse = {
  status?: "need_clarification" | "need_period" | "need_output_config" | "resolved" | "no_match" | "data_unavailable" | "catalog_only";
  query: string;
  interpretedQuery: string;
  summary: string;
  period: { start: string; end: string };
  availablePeriod?: { min: string; max: string };
  frequency: string;
  chart: ChartSeries[];
  chartMode?: "combined" | "separate" | null;
  chartType?: ChartType;
  outputSpec?: {
    status: "ready" | "empty";
    agent: string;
    summary: string;
    table: {
      columns: string[];
      rows: Array<{ series: string; period: string; value: number; unit: string }>;
    };
    explanation: { text: string; method: string; source: string };
    evidence: Array<{
      tableId: string;
      tableName: string;
      organizationId: string;
      itemId: string;
      frequency: string;
      requestedPeriod: { start: string; end: string };
      rowCount: number | null;
      source: string;
    }>;
    plotlyFigure?: { data: Array<Record<string, unknown>>; layout: Record<string, unknown> };
    chartState?: Record<string, unknown>;
    visualization: {
      chartType: ChartType;
      layout: "combined" | "separate";
      editable: boolean;
      editOptions: {
        title?: string | null;
        showLegend?: boolean;
        xAxisLabel?: string | null;
        yAxisLabel?: string | null;
        supportedChartTypes?: ChartType[];
        supportedLayouts?: Array<"combined" | "separate">;
      };
    };
  };
  seriesCount?: number;
  outputSessionId?: string;
  outputSessionIds?: string[];
  editSessionId?: string;
  outputOptions?: {
    seriesCount: number;
    pointCount: number;
    recommendedChartType: ChartType;
    supportedChartTypes: ChartType[];
    supportedLayouts: Array<"combined" | "separate">;
    editableFields: string[];
  };
  tables: SelectedTable[];
  insights: string[];
  lineage: LineageStep[];
  warnings: string[];
  clarification?: Clarification;
  clarifications?: Clarification[];
  state?: QueryState;
  debug?: {
    selectedTable?: unknown;
    apiPlan?: Record<string, unknown>;
    executionStatus?: string;
    rowsPreview?: Array<Record<string, unknown>>;
    timingMs?: { resolve?: number; execute?: number; total?: number };
  };
};

export type OutputRenderRequest = {
  session_ids: string[];
  chart_type: "auto" | ChartType;
  chart_mode: "combined" | "separate";
  title?: string;
  show_legend: boolean;
  x_axis_label?: string;
  y_axis_label?: string;
  natural_language?: string;
};

export type OutputEditRequest = { edit_session_id: string; instruction: string };

export type QueryRequest = {
  query: string;
  state?: QueryState;
  clarification?: {
    clarification_id: string;
    value: string;
  };
  selections?: Array<{ clarification_id: string; values: string[] }>;
  dimension_values?: Record<string, string>;
  execute?: boolean;
  period_start?: string;
  period_end?: string;
  chart_mode?: "combined" | "separate";
  chart_type?: "auto" | ChartType;
  chart_options?: {
    title?: string;
    show_legend?: boolean;
    x_axis_label?: string;
    y_axis_label?: string;
  };
};

export type CatalogTable = {
  tableId: string; name: string; organization: string; frequency: string; frequencyLabel: string; unitScale: string;
  periodStart: string; periodEnd: string; items: string[]; units: string[];
  dimensions: Array<{ name: string; count: number; values: string[]; apiParam: string; valueOptions: Array<{id: string; name: string}>; defaultValueId: string }>;
};
export type CatalogMiddle = { name: string; count: number; children: CatalogTable[] };
export type CatalogMajor = { name: string; count: number; children: CatalogMiddle[] };
export type CatalogResponse = { source: string; total: number; categories: CatalogMajor[] };
