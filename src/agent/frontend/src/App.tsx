import { useState, type FormEvent } from "react";
import { analyze } from "./api/client";
import type { AnalysisResponse, SeriesChoice } from "./api/types";

function Graph({ seriesList }: { seriesList: NonNullable<AnalysisResponse["chart"]> }) {
  const dates = [...new Set(seriesList.flatMap(series => series.points.map(point => point.period)))].sort();
  const values = seriesList.flatMap(series => series.points.map(point => point.value));
  const min = Math.min(...values), span = Math.max(...values) - min || 1;
  const colors = ["#4568ff", "#d65b7a", "#249b8a", "#9561d8", "#d58b2e"];
  const x = (date: string) => 40 + dates.indexOf(date) * 700 / Math.max(1, dates.length - 1);
  const y = (value: number) => 240 - (value - min) * 200 / span;
  return <figure><figcaption>{seriesList.length > 1 ? "계열 비교" : seriesList[0].label} ({seriesList[0].unit || "단위 없음"}) · {seriesList[0].frequency}</figcaption>
    <svg viewBox="0 0 780 270" role="img" aria-label={`${seriesList.map(series => series.label).join(", ")} 추이 그래프`}>
      <path d="M 40 40 L 40 240 L 740 240" fill="none" stroke="#a9b3c6" />
      {seriesList.map((series, colorIndex) => {
        const points = series.points.map(point => ({ point, index: dates.indexOf(point.period) }));
        const path = points.map(({ point, index }, i) => `${i && index === points[i - 1].index + 1 ? "L" : "M"} ${x(point.period)} ${y(point.value)}`).join(" ");
        return <g key={`${series.table_id}:${series.label}`}><path d={path} fill="none" stroke={colors[colorIndex % colors.length]} strokeWidth="3" />
          {points.map(({ point }) => <circle key={point.period} cx={x(point.period)} cy={y(point.value)} r="4" fill={colors[colorIndex % colors.length]}><title>{series.label} · {point.period}: {point.value} {series.unit}</title></circle>)}</g>;
      })}
      <text x="40" y="260">{dates[0]}</text><text x="690" y="260">{dates.at(-1)}</text>
    </svg>{seriesList.length > 1 && <div className="chart-legend">{seriesList.map((series, index) => <span key={`${series.table_id}:${series.label}`} style={{ color: colors[index % colors.length] }}>● {series.label}</span>)}</div>}</figure>;
}

export default function App() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [choices, setChoices] = useState<SeriesChoice[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [draft, setDraft] = useState<SeriesChoice | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function run(text: string, series: SeriesChoice[] = [], source: "kosis" | "local" = "kosis") {
    if (!text.trim()) return;
    setLoading(true); setError("");
    try {
      const next = await analyze(text.trim(), series, source);
      setResult(next); setChoices(series);
      if (next.reason === "series" && next.options) {
        const option = next.options;
        const old = series.find(choice => choice.table_id === option.table_id);
        setDraft({ table_id: option.table_id, item_id: old?.item_id || option.items[0]?.id,
          frequency: old?.frequency || Object.keys(option.periods)[0],
          classifications: old?.classifications || Object.fromEntries(option.axes.map(axis => [axis.key, axis.values[0]?.id])),
          start_period: old?.start_period || Object.values(option.periods)[0]?.recent_start || Object.values(option.periods)[0]?.start,
          end_period: old?.end_period || Object.values(option.periods)[0]?.end });
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "요청에 실패했습니다."); }
    finally { setLoading(false); }
  }

  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setChoices([]); setSelectedIds([]); setDraft(null); void run(query); }
  function execute(source: "kosis" | "local" = "kosis") {
    if (draft) void run(query, [...choices.filter(choice => choice.table_id !== draft.table_id), draft], source);
  }
  const options = result?.options;
  return <div className="app-shell"><header className="topbar"><div className="brand-mark" aria-hidden="true">S</div><div className="brand"><strong>StatBridge</strong><span>한국은행 통계 분석</span></div></header>
    <main><section className="hero"><span className="eyebrow">KOSIS · 한국은행</span><h1>질문으로 통계를 찾아 그래프로 확인하세요.</h1><p>표와 계열을 선택하면 KOSIS 최신 수치를 조회합니다.</p>
      <form className="search-box" onSubmit={submit}><label htmlFor="query">통계 질문</label><div className="search-input"><input id="query" value={query} onChange={event => setQuery(event.target.value)} placeholder="예: 경제심리지수 추이를 보여줘" /><button type="submit" disabled={loading || !query.trim()}>{loading ? "처리 중…" : "분석 시작"}</button></div></form>
      <div className="examples"><span>예시 질문</span>{["경제심리지수 추이", "기업경기실사지수", "가계신용 통계표"].map(text => <button key={text} type="button" onClick={() => { setQuery(text); setChoices([]); void run(text); }}>{text}</button>)}</div></section>
      <section className="results" aria-live="polite">{error && <div className="message error" role="alert">{error}</div>}{!result && !error && <div className="empty-state">질문을 입력해 시작하세요.</div>}
        {result?.status === "no_match" && <div className="empty-state">일치하는 통계표가 없습니다. 지표명을 바꿔 보세요.</div>}
        {result?.reason === "table" && <><h2>사용할 통계표를 선택하세요</h2><p>후보가 정답으로 확정된 것은 아닙니다. 비교할 표는 최대 5개까지 선택할 수 있습니다.</p><div className="candidate-list">{result.candidates?.map(candidate => <label className="candidate" key={candidate.table_id}><input type="checkbox" checked={selectedIds.includes(candidate.table_id)} onChange={event => setSelectedIds(event.target.checked ? [...selectedIds, candidate.table_id].slice(0, 5) : selectedIds.filter(id => id !== candidate.table_id))} /><code>{candidate.table_id}</code><h3>{candidate.table_name}</h3><p>{candidate.path}</p></label>)}</div><button type="button" disabled={!selectedIds.length} onClick={() => void run(query, selectedIds.map(table_id => ({ table_id })))}>계열 선택 계속</button></>}
        {result?.reason === "series" && options && draft && <><h2>{options.table_name}</h2><p>항목과 분류를 확인한 뒤 조회하세요.</p><div className="series-form">
          <label>통계 항목<select value={draft.item_id || ""} onChange={event => setDraft({ ...draft, item_id: event.target.value })}>{options.items.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
          {options.axes.map(axis => <label key={axis.key}>{axis.label}<select value={draft.classifications?.[axis.key] || ""} onChange={event => setDraft({ ...draft, classifications: { ...draft.classifications, [axis.key]: event.target.value } })}>{axis.values.map(value => <option key={value.id} value={value.id}>{value.label}</option>)}</select></label>)}
          <label>주기<select value={draft.frequency || ""} onChange={event => { const range = options.periods[event.target.value]; setDraft({ ...draft, frequency: event.target.value, start_period: range.recent_start || range.start, end_period: range.end }); }}>{Object.keys(options.periods).map(frequency => <option key={frequency}>{frequency}</option>)}</select></label>
          <label>시작 기간<input value={draft.start_period || ""} onChange={event => setDraft({ ...draft, start_period: event.target.value })} /></label><label>종료 기간<input value={draft.end_period || ""} onChange={event => setDraft({ ...draft, end_period: event.target.value })} /></label>
          <button type="button" disabled={loading} onClick={() => execute()}>다음 계열 또는 KOSIS 조회</button>{options.local_csv_available && <button type="button" disabled={loading} onClick={() => execute("local")}>다음 계열 또는 로컬 조회</button>}</div></>}
        {result?.status === "data_unavailable" && <div className="message error" role="alert"><p>{result.message}</p>{result.local_csv_available && <button type="button" onClick={() => execute("local")}>로컬 저장본으로 다시 조회</button>}</div>}
        {result?.status === "resolved" && result.chart && <><h2>그래프 결과</h2><p>{result.layout === "separate" ? "단위 또는 주기가 달라 계열별로 표시합니다." : "선택한 계열의 관측값입니다."}</p>{result.layout === "combined" && <article><Graph seriesList={result.chart} /></article>}{result.chart.map(series => <article key={`${series.table_id}:${series.label}`}>{result.layout === "separate" && <Graph seriesList={[series]} />}<p>{series.label} · 출처: {series.source === "kosis_api" ? "KOSIS 실시간 조회" : "로컬 저장본"} · {series.table_id}</p><details><summary>관측값 표</summary><table><thead><tr><th>시점</th><th>값</th></tr></thead><tbody>{series.points.map(point => <tr key={point.period}><td>{point.period}</td><td>{point.value}</td></tr>)}</tbody></table></details></article>)}</>}
      </section></main><footer>StatBridge · 선택한 계열의 실제 관측값만 표시합니다.</footer></div>;
}
