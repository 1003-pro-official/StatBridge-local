import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import { fetchCatalog, submitQuery } from "./api/client";
import type { CatalogResponse, CatalogTable, ChartSeries, QueryResponse } from "./api/types";

type IconName =
  | "logo" | "home" | "chat" | "chart" | "compare" | "lineage" | "search"
  | "send" | "menu" | "close" | "sparkle" | "database" | "download"
  | "share" | "check" | "chevron" | "bell" | "history" | "arrow";

const paths: Record<IconName, ReactNode> = {
  logo: <><path d="M4 18V11M10 18V6M16 18V9M22 18V3"/><path d="m3 13 6-4 6 2 7-7"/></>,
  home: <><path d="m3 11 9-8 9 8"/><path d="M5 10v11h14V10M9 21v-7h6v7"/></>,
  chat: <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z"/>,
  chart: <><path d="M4 19V9M10 19V5M16 19v-7M22 19V2"/><path d="M2 19h21"/></>,
  compare: <><path d="M4 7h13M14 4l3 3-3 3M20 17H7M10 14l-3 3 3 3"/></>,
  lineage: <><circle cx="5" cy="5" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="12" cy="19" r="2"/><path d="M7 5h10M6 7l5 10M18 7l-5 10"/></>,
  search: <><circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/></>,
  send: <><path d="m3 3 19 9-19 9 4-9Z"/><path d="M7 12h15"/></>,
  menu: <><path d="M4 7h16M4 12h16M4 17h16"/></>,
  close: <><path d="m6 6 12 12M18 6 6 18"/></>,
  sparkle: <><path d="m12 2 1.5 5.5L19 9l-5.5 1.5L12 16l-1.5-5.5L5 9l5.5-1.5Z"/><path d="m19 16 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7Z"/></>,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7"/></>,
  download: <><path d="M12 3v12M7 10l5 5 5-5"/><path d="M4 20h16"/></>,
  share: <><circle cx="18" cy="5" r="2"/><circle cx="6" cy="12" r="2"/><circle cx="18" cy="19" r="2"/><path d="m8 11 8-5M8 13l8 5"/></>,
  check: <path d="m5 12 4 4L19 6"/>,
  chevron: <path d="m9 6 6 6-6 6"/>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></>,
  history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></>,
  arrow: <><path d="M5 12h14M14 7l5 5-5 5"/></>,
};

function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function DateSelector({ value, min, max, onChange, label }: { value:string; min?:string; max?:string; onChange:(value:string)=>void; label:string }) {
  const today=new Date().toISOString().slice(0,10);
  const fallback=[max,today,min].find((item)=>item&&(!min||item>=min)&&(!max||item<=max))||min||max||today;
  const [open,setOpen]=useState(false);
  const [draft,setDraft]=useState(value||fallback);
  useEffect(()=>{if(value)setDraft(value)},[value]);
  const [year,month,day]=draft.split("-").map(Number);
  const minYear=Number((min||`${new Date().getFullYear()-30}-01-01`).slice(0,4));
  const maxYear=Number((max||`${new Date().getFullYear()+5}-12-31`).slice(0,4));
  const years=Array.from({length:Math.max(1,maxYear-minYear+1)},(_,index)=>minYear+index);
  const days=Array.from({length:new Date(year,month,0).getDate()},(_,index)=>index+1);
  const updateDraft=(nextYear:number,nextMonth:number,nextDay:number)=>{
    const safeDay=Math.min(nextDay,new Date(nextYear,nextMonth,0).getDate());
    setDraft(`${nextYear}-${String(nextMonth).padStart(2,"0")}-${String(safeDay).padStart(2,"0")}`);
  };
  const valid=(!min||draft>=min)&&(!max||draft<=max);
  return <div className="date-picker">
    <button type="button" className={`date-trigger ${value?"has-value":""}`} aria-expanded={open} aria-label={`${label} 선택`} onClick={()=>{setDraft(value||fallback);setOpen((current)=>!current)}}><Icon name="history" size={16}/><span>{value||"날짜 선택"}</span><Icon name="chevron" size={14}/></button>
    {open&&<div className="date-popover"><div className="date-popover-head"><div><small>{label}</small><strong>{draft.replaceAll("-",".")}</strong></div><button type="button" aria-label="날짜 선택 닫기" onClick={()=>setOpen(false)}><Icon name="close" size={15}/></button></div><div className="date-select-grid"><label>년<select value={year} onChange={(event)=>updateDraft(Number(event.target.value),month,day)}>{years.map((item)=><option key={item} value={item}>{item}년</option>)}</select></label><label>월<select value={month} onChange={(event)=>updateDraft(year,Number(event.target.value),day)}>{Array.from({length:12},(_,index)=>index+1).map((item)=><option key={item} value={item}>{item}월</option>)}</select></label><label>일<select value={day} onChange={(event)=>updateDraft(year,month,Number(event.target.value))}>{days.map((item)=><option key={item} value={item}>{item}일</option>)}</select></label></div>{min&&max&&<p>{min}부터 {max}까지 선택할 수 있습니다.</p>}<button type="button" className="date-confirm" disabled={!valid} onClick={()=>{onChange(draft);setOpen(false)}}>이 날짜로 선택</button></div>}
  </div>;
}

const navItems: { label: string; icon: IconName }[] = [
  { label: "홈", icon: "home" },
  { label: "대화하기", icon: "chat" },
  { label: "통계 탐색", icon: "chart" },
  { label: "비교 분석", icon: "compare" },
  { label: "데이터 계보", icon: "lineage" },
];

function Sidebar({ open, close, view, selectView, goHome }: { open: boolean; close: () => void; view: string; selectView: (view: "home" | "lineage") => void; goHome:()=>void }) {
  return <>
    {open && <button className="backdrop" aria-label="메뉴 닫기" onClick={close} />}
    <aside className={`sidebar ${open ? "is-open" : ""}`}>
      <div className="brand-row">
        <button type="button" className="brand-home" aria-label="StatBridge 홈으로 이동" onClick={()=>{goHome();close()}}><span className="brand-mark"><Icon name="logo" size={23}/></span><span><strong>StatBridge</strong><small>통계를 잇는 가장 투명한 방법</small></span></button>
        <button className="mobile-close" onClick={close} aria-label="메뉴 닫기"><Icon name="close"/></button>
      </div>
      <nav className="main-nav" aria-label="주 메뉴">
        {navItems.map((item) => { const target = item.label === "데이터 계보" ? "lineage" : "home"; const active = view === target && (target === "lineage" || item.label === "홈"); return <button key={item.label} className={active ? "active" : ""} onClick={() => { selectView(target); close(); }}><Icon name={item.icon}/><span>{item.label}</span>{active && <span className="active-dot"/>}</button>; })}
      </nav>
      <div className="side-divider" />
      <div className="source-group">
        <p>연결된 데이터</p>
        <div><span className="source-icon">K</span><span>한국은행 · KOSIS</span><span className="live-dot"/></div>
        <div><span className="source-icon muted">+</span><span className="muted-text">데이터 소스 추가</span></div>
      </div>
      <div className="trust-card">
        <span className="eyebrow">WHY STATBRIDGE</span>
        <strong>숫자의 출처까지<br/>확인하세요.</strong>
        <p>모든 분석 결과에 통계표와 가공 과정을 남깁니다.</p>
        <div className="mini-chart"><i/><i/><i/><i/><i/></div>
      </div>
      <div className="side-profile">
        <div className="avatar">SB</div><div><strong>StatBridge 팀</strong><span>PoC Workspace</span></div><button aria-label="알림"><Icon name="bell" size={18}/></button>
      </div>
    </aside>
  </>;
}

function ExpandableValues({ values, previewCount = 3 }: { values: string[]; previewCount?: number }) {
  const [expanded, setExpanded] = useState(false);
  const visibleValues = expanded ? values : values.slice(0, previewCount);
  if (!values.length) return <>-</>;
  return <div className="expandable-values">
    <span>{visibleValues.join(", ")}</span>
    {values.length > previewCount && <button type="button" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>
      {expanded ? "접기" : `더 보기 (${values.length - previewCount}개)`}
    </button>}
  </div>;
}

function CatalogCard({ table }: { table: CatalogTable }) {
  return <article className="catalog-card">
    <div><span>{table.organization}</span><span className="source-check"><Icon name="check" size={12}/></span></div>
    <h3>{table.name}</h3>
    <p className="catalog-table-id">통계표 ID {table.tableId}</p>
    <dl>
      <div><dt>수록 주기</dt><dd><strong>{table.frequencyLabel}</strong> <small>({table.frequency})</small></dd></div>
      <div><dt>제공 기간</dt><dd>{table.periodStart} – {table.periodEnd}</dd></div>
      <div><dt>대표 단위</dt><dd>{table.unitScale || "-"}</dd></div>
      <div><dt>수치 단위</dt><dd><ExpandableValues values={table.units}/></dd></div>
      <div><dt>통계 항목</dt><dd><ExpandableValues values={table.items}/></dd></div>
      <div><dt>분류 정보</dt><dd>{table.dimensions.length ? table.dimensions.map((dimension, index) =>
        <section className="dimension-detail" key={`${dimension.name}-${index}`}>
          <b>{dimension.name}</b><span> · {dimension.count}개</span>
          <ExpandableValues values={dimension.values}/>
        </section>) : "-"}</dd></div>
    </dl>
  </article>;
}

function DataCatalog() {
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [error, setError] = useState("");
  const [major, setMajor] = useState(""); const [middle, setMiddle] = useState("");
  const [selected, setSelected] = useState<CatalogTable | null>(null);
  useEffect(() => { fetchCatalog().then((data) => { setCatalog(data); setMajor(data.categories[0]?.name || ""); }).catch((e) => setError(e instanceof Error ? e.message : "카탈로그를 불러오지 못했습니다.")); }, []);
  const majors = catalog?.categories || [];
  const majorNode = majors.find((x) => x.name === major) || majors[0];
  const middles = majorNode?.children || [];
  const middleNode = middles.find((x) => x.name === middle) || middles[0];
  useEffect(() => { setMiddle(""); setSelected(null); }, [major]);
  useEffect(() => { setSelected(null); }, [middle]);
  return <main className="catalog-page" id="data-catalog">
    <section className="catalog-hero"><span className="eyebrow">DATA LINEAGE CATALOG</span><h1>조회 가능한 데이터 계보</h1><p>StatBridge에서 조회할 수 있는 통계표를 대분류·중분류·소분류 순서로 탐색합니다.</p><div><strong>{catalog?.total ?? "-"}</strong><span>조회 가능 통계표</span><small>{catalog?.source || "불러오는 중"}</small></div></section>
    {error && <div className="error-banner">{error}</div>}
    {catalog && <section className="catalog-browser panel">
      <div className="catalog-column"><h2><span>1</span> 대분류</h2>{majors.map((x) => <button className={x.name === major ? "selected" : ""} key={x.name} onClick={() => setMajor(x.name)}><strong>{x.name}</strong><small>{x.count}개</small><Icon name="chevron" size={15}/></button>)}</div>
      <div className="catalog-column"><h2><span>2</span> 중분류</h2>{middles.map((x) => <button className={x.name === (middleNode?.name || "") ? "selected" : ""} key={x.name} onClick={() => setMiddle(x.name)}><strong>{x.name}</strong><small>{x.count}개</small><Icon name="chevron" size={15}/></button>)}</div>
      <div className="catalog-column catalog-small"><h2><span>3</span> 소분류</h2>{middleNode?.children.map((x) => <button className={x.tableId === selected?.tableId ? "selected" : ""} key={x.tableId} onClick={() => setSelected(x)}><strong>{x.name}</strong><Icon name="chevron" size={15}/></button>)}</div>
      <div className="catalog-detail"><h2>통계표 정보 카드</h2>{selected ? <CatalogCard key={selected.tableId} table={selected}/> : <div className="catalog-empty"><Icon name="database" size={35}/><strong>소분류 통계표를 선택하세요.</strong><p>주기·기간·수치 단위·통계 항목과 분류 내용을 카드로 보여드립니다.</p></div>}</div>
    </section>}
  </main>;
}

function Header({ openMenu }: { openMenu: () => void }) {
  return <header className="topbar">
    <button className="menu-button" onClick={openMenu} aria-label="메뉴 열기"><Icon name="menu"/></button>
    <div className="mobile-brand"><span className="brand-mark"><Icon name="logo" size={19}/></span><strong>StatBridge</strong></div>
    <div className="top-search"><Icon name="search" size={19}/><span>통계나 주제를 검색하세요</span><kbd>Ctrl K</kbd></div>
    <div className="top-actions"><button aria-label="알림"><Icon name="bell" size={19}/><span className="notification-dot"/></button><span className="api-status"><i/> MCP BRIDGE</span></div>
  </header>;
}

function Hero({ query, setQuery, submit, loading }: { query: string; setQuery: (v: string) => void; submit: (e: FormEvent) => void; loading: boolean }) {
  const suggestions = ["최근 대출금리 추이", "대출금리와 생산자물가 비교", "월별 생산자물가지수"];
  return <section className="hero">
    <div className="hero-glow one"/><div className="hero-glow two"/>
    <div className="hero-content">
      <span className="hero-label"><Icon name="sparkle" size={15}/> STATBRIDGE INTELLIGENCE</span>
      <h1>통계를 찾는 것을 넘어,<br/><em>연결하고 검증합니다.</em></h1>
      <p>자연어 질문을 한국은행의 실제 통계 구조로 변환하고,<br className="desktop-break"/> 선택 근거까지 추적 가능한 분석 결과를 제공합니다.</p>
      <form className="ask-box" onSubmit={submit}>
        <Icon name="search" size={21}/>
        <input aria-label="통계 질문" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="예: 대출금리와 생산자물가를 비교해줘" />
        <button type="submit" disabled={loading || !query.trim()}>{loading ? <span className="spinner"/> : <Icon name="send" size={18}/>}<span>분석하기</span></button>
      </form>
      <div className="suggestions"><span>추천 질문</span>{suggestions.map((s) => <button key={s} onClick={() => setQuery(s)}>{s}</button>)}</div>
    </div>
    <div className="hero-visual" aria-hidden="true">
      <div className="orbit orbit-one"/><div className="orbit orbit-two"/>
      <div className="data-card card-a"><span>대출금리</span><strong>실데이터</strong><small>한국은행</small></div>
      <div className="bridge-line"><i/><i/><i/><i/><i/></div>
      <div className="data-card card-b"><span>생산자물가</span><strong>실데이터</strong><small>KOSIS</small></div>
      <div className="verified"><Icon name="check" size={15}/> SOURCE VERIFIED</div>
    </div>
  </section>;
}

function FeatureStrip() {
  const items: { icon: IconName; title: string; text: string }[] = [
    { icon: "chat", title: "자연어 분석", text: "질문을 통계 구조로 변환" },
    { icon: "compare", title: "다중 지표 비교", text: "주기·단위·시점을 자동 정합" },
    { icon: "lineage", title: "Query Planner", text: "표·항목 선택 근거를 확인" },
    { icon: "database", title: "Data Lineage", text: "수치 출처와 변환을 추적" },
  ];
  return <section className="feature-strip">{items.map((x) => <article key={x.title}><span className="feature-icon"><Icon name={x.icon}/></span><div><strong>{x.title}</strong><p>{x.text}</p></div></article>)}</section>;
}

function LineChart({ series }: { series: ChartSeries[] }) {
  if (!series.length) return <div className="empty-chart">선택한 기간에 표시할 수치가 없습니다.</div>;
  const w = 700, h = 250, px = 58, py = 26;
  const dates = [...new Set(series.flatMap((s) => s.points.map((p) => p.date)))].sort();
  const values = series.flatMap((s) => s.points.map((p) => p.value));
  const minValue = Math.min(...values), maxValue = Math.max(...values);
  const padding = Math.max((maxValue - minValue) * .12, Math.abs(maxValue) * .03, 1);
  const yMin = minValue - padding, yMax = maxValue + padding;
  const x = (date: string) => px + (Math.max(0, dates.indexOf(date)) * (w - px * 2)) / Math.max(1, dates.length - 1);
  const y = (v: number) => h - py - ((v - yMin) / Math.max(1e-9, yMax - yMin)) * (h - py * 2);
  const path = (item: ChartSeries) => item.points.map((d, i) => `${i ? "L" : "M"}${x(d.date)},${y(d.value)}`).join(" ");
  const ticks = [0, .25, .5, .75, 1].map((ratio) => yMin + (yMax - yMin) * ratio);
  return <div className="chart-wrap">
    <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label={`${series.map((s) => s.label).join(", ")} 시계열 그래프`}>
      {ticks.map((v) => <g key={v}><line className="grid" x1={px} y1={y(v)} x2={w-px} y2={y(v)}/><text className="axis-label" x={px-8} y={y(v)+4}>{v.toLocaleString(undefined,{maximumFractionDigits:1})}</text></g>)}
      {series.map((item) => <g key={item.id}><path className="line" style={{stroke:item.color}} d={path(item)}/>{item.points.map((p) => <circle key={p.date} className="dot" style={{fill:item.color}} cx={x(p.date)} cy={y(p.value)} r="3.5"><title>{item.label}: {p.value.toLocaleString()} {item.unit}</title></circle>)}</g>)}
      {dates.map((date, i) => (i % Math.max(1, Math.ceil(dates.length / 7)) === 0 || i === dates.length - 1) && <text key={date} className="x-label" x={x(date)} y={h-5}>{date}</text>)}
    </svg>
  </div>;
}

function LayoutChoice({ mode, setMode }: { mode: "combined"|"separate"; setMode: (v:"combined"|"separate")=>void }) {
  return <div className="setup-block"><strong>그래프 표시 방식</strong><div className="clarification-options"><button type="button" className={mode==="combined"?"selected":""} onClick={()=>setMode("combined")}><span className="multi-check">{mode==="combined"&&<Icon name="check" size={13}/>}</span>여러 계열을 한 그래프에</button><button type="button" className={mode==="separate"?"selected":""} onClick={()=>setMode("separate")}><span className="multi-check">{mode==="separate"&&<Icon name="check" size={13}/>}</span>계열별 그래프 여러 개</button></div></div>;
}

function PeriodPanel({ result, loading, submit }: { result: QueryResponse; loading: boolean; submit: (start: string, end: string, mode:"combined"|"separate") => void }) {
  const [start, setStart] = useState(""); const [end, setEnd] = useState("");
  const [mode,setMode]=useState<"combined"|"separate">("combined");
  const minDate=result.availablePeriod?.min||undefined, maxDate=result.availablePeriod?.max||undefined;
  const invalid=Boolean(start&&end&&(start>end||(minDate&&start<minDate)||(maxDate&&end>maxDate)));
  return <section className="clarification-section" id="analysis-result"><div className="clarification-card">
    <span className="eyebrow">CHART PERIOD</span><div className="clarification-title"><span><Icon name="chart" size={19}/></span><div><h2>그래프로 볼 정확한 기간을 입력해 주세요.</h2><p>{result.interpretedQuery} · 원자료 주기 {result.frequency}</p></div></div>
    <div className="period-form"><label>시작일<DateSelector label="시작일" value={start} min={minDate} max={end&&(!maxDate||end<maxDate)?end:maxDate} onChange={setStart}/></label><span>→</span><label>종료일<DateSelector label="종료일" value={end} min={start&&(!minDate||start>minDate)?start:minDate} max={maxDate} onChange={setEnd}/></label></div>{minDate&&maxDate&&<p className="period-availability">선택 가능 기간: {minDate} ~ {maxDate}</p>}{(result.tables.length>1||(result.seriesCount||0)>1)&&<LayoutChoice mode={mode} setMode={setMode}/>}<div className="clarification-submit"><span>{invalid?"원자료 제공 기간 안에서 선택해 주세요.":"조회 기간을 적용합니다."}</span><button disabled={loading || !start || !end || invalid} onClick={() => submit(start,end,mode)}>그래프 만들기 <Icon name="arrow" size={15}/></button></div>
  </div></section>;
}

function ChartModePanel({ result, loading, choose }: { result: QueryResponse; loading: boolean; choose: (mode: "combined" | "separate") => void }) {
  return <section className="clarification-section" id="analysis-result"><div className="clarification-card">
    <span className="eyebrow">CHART LAYOUT</span><div className="clarification-title"><span><Icon name="compare" size={19}/></span><div><h2>{result.seriesCount}개 계열을 어떻게 표시할까요?</h2><p>한 화면에서 비교하거나, 계열별 눈금을 유지하도록 각각 나눠 볼 수 있습니다.</p></div></div>
    <div className="clarification-options"><button disabled={loading} onClick={() => choose("combined")}>여러 계열을 한 그래프에 <Icon name="arrow" size={15}/></button><button disabled={loading} onClick={() => choose("separate")}>계열별 그래프 여러 개 <Icon name="arrow" size={15}/></button></div>
  </div></section>;
}


function ClarificationPanel({ result, loading, choose }: { result: QueryResponse; loading: boolean; choose: (values: Array<{ clarification_id: string; values: string[] }>,start:string,end:string,mode:"combined"|"separate") => void }) {
  const groups=result.clarifications?.length?result.clarifications:result.clarification?[result.clarification]:[];
  const [selected,setSelected]=useState<Record<string,string[]>>({});
  const [start,setStart]=useState(""); const [end,setEnd]=useState(""); const [mode,setMode]=useState<"combined"|"separate">("combined");
  const [availablePeriod,setAvailablePeriod]=useState(result.availablePeriod);
  const selectedKey=JSON.stringify(selected);
  useEffect(()=>{
    const selections=Object.entries(selected).filter(([,values])=>values.length).map(([clarification_id,values])=>({clarification_id,values}));
    if(!selections.length){setAvailablePeriod(result.availablePeriod);return;}
    const timer=window.setTimeout(()=>{submitQuery({query:result.query,state:result.state,selections,execute:false}).then((preview)=>{if(preview.availablePeriod)setAvailablePeriod(preview.availablePeriod)}).catch(()=>undefined)},120);
    return()=>window.clearTimeout(timer);
  },[selectedKey,result.query,result.state,result.availablePeriod]);
  if(result.status!=="need_clarification"||!groups.length)return null;
  const toggle=(groupId:string,value:string)=>setSelected((current)=>{const values=current[groupId]||[];return{...current,[groupId]:values.includes(value)?values.filter((item)=>item!==value):[...values,value]}});
  const selectionCount=Object.values(selected).reduce((count,values)=>count+values.length,0);
  const minDate=availablePeriod?.min||undefined, maxDate=availablePeriod?.max||undefined;
  const invalid=Boolean(start&&end&&(start>end||(minDate&&start<minDate)||(maxDate&&end>maxDate)));
  return <section className="clarification-section" id="analysis-result">
    <div className="clarification-card">
      <span className="eyebrow">AGENT CLARIFICATION</span>
      <div className="clarification-title"><span><Icon name="chat" size={19}/></span><div><h2>필요한 조건을 한 화면에서 선택해 주세요.</h2><p>각 항목은 복수 선택할 수 있습니다. 여러 지표를 선택하면 비교 데이터로 함께 조회합니다.</p></div></div>
      <div className="clarification-groups">{groups.map((group)=><fieldset key={group.id}><legend>{group.question}</legend><div className="clarification-options">{group.options.map((option)=>{const active=(selected[group.id]||[]).includes(option.value);return <button type="button" aria-pressed={active} className={active?"selected":""} key={option.value} disabled={loading} onClick={()=>toggle(group.id,option.value)}><span className="multi-check">{active&&<Icon name="check" size={13}/>}</span>{option.label}</button>})}</div></fieldset>)}</div>
      <div className="setup-block date-step"><strong>조회 날짜</strong><p>선택한 통계표가 실제 제공하는 기간 안에서 조회합니다.</p><div className="period-form"><label>시작일<DateSelector label="시작일" value={start} min={minDate} max={end&&(!maxDate||end<maxDate)?end:maxDate} onChange={setStart}/></label><span>→</span><label>종료일<DateSelector label="종료일" value={end} min={start&&(!minDate||start>minDate)?start:minDate} max={maxDate} onChange={setEnd}/></label></div>{minDate&&maxDate&&<p className="period-availability"><Icon name="check" size={14}/> 선택 가능 기간: {minDate} ~ {maxDate}</p>}</div>
      {selectionCount>1&&start&&end&&!invalid&&<div className="layout-step"><LayoutChoice mode={mode} setMode={setMode}/></div>}
      <div className="clarification-submit"><span>{invalid?"선택한 통계표의 제공 기간 안에서 날짜를 선택해 주세요.":selectionCount?`${selectionCount}개 항목 선택됨`:"항목과 조회 날짜를 선택해 주세요."}</span><button disabled={loading||!selectionCount||!start||!end||invalid} onClick={()=>choose(Object.entries(selected).filter(([,values])=>values.length).map(([clarification_id,values])=>({clarification_id,values})),start,end,mode)}>선택 완료 후 그래프 만들기 <Icon name="arrow" size={15}/></button></div>
      <div className="clarification-trace"><Icon name="lineage" size={15}/><span>UI → Agent → 통계언어 사전 → 역질문 → 선택값 확정 → 사전 재검색</span></div>
    </div>
  </section>;
}

function Results({ result }: { result: QueryResponse }) {
  const [lineageOpen, setLineageOpen] = useState(true);
  const [allDataOpen,setAllDataOpen]=useState(false);
  const allRows=result.chart.flatMap((series)=>series.points.map((point)=>({series,point})));
  const previewRows=result.chart.flatMap((series)=>{
    if(series.points.length<=6)return series.points.map((point)=>({series,point}));
    return [...series.points.slice(0,3),...series.points.slice(-3)].map((point)=>({series,point}));
  });
  const visibleRows=allDataOpen?allRows:previewRows;
  const exportCsv = () => {
    const rows = ["계열,단위,시점,값", ...result.chart.flatMap((s) => s.points.map((p) => `"${s.label}","${s.unit}",${p.date},${p.value}`))];
    const blob = new Blob(["\ufeff" + rows.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = "statbridge-analysis.csv"; a.click(); URL.revokeObjectURL(url);
  };
  const exportPng=async()=>{
    const svgs=Array.from(document.querySelectorAll<SVGSVGElement>(".chart-panel .chart-wrap svg"));
    if(!svgs.length)return;
    const width=1400,chartHeight=500,gap=28;
    const canvas=document.createElement("canvas");canvas.width=width;canvas.height=svgs.length*chartHeight+(svgs.length-1)*gap;
    const context=canvas.getContext("2d");if(!context)return;
    context.fillStyle="#ffffff";context.fillRect(0,0,canvas.width,canvas.height);
    for(let index=0;index<svgs.length;index+=1){
      const clone=svgs[index].cloneNode(true) as SVGSVGElement;
      clone.setAttribute("xmlns","http://www.w3.org/2000/svg");clone.setAttribute("width","700");clone.setAttribute("height","250");
      const style=document.createElementNS("http://www.w3.org/2000/svg","style");
      style.textContent=".grid{stroke:#e8ebf3;stroke-width:1}.axis-label,.x-label{fill:#65718d;font:10px Arial,sans-serif}.axis-label{text-anchor:end}.x-label{text-anchor:middle}.line{fill:none;stroke-width:3;stroke-linecap:round;stroke-linejoin:round}.dot{stroke:white;stroke-width:2}";
      clone.insertBefore(style,clone.firstChild);
      const blob=new Blob([new XMLSerializer().serializeToString(clone)],{type:"image/svg+xml;charset=utf-8"});
      const url=URL.createObjectURL(blob);const image=new Image();
      await new Promise<void>((resolve,reject)=>{image.onload=()=>resolve();image.onerror=()=>reject(new Error("그래프 이미지를 만들지 못했습니다."));image.src=url});
      context.drawImage(image,0,index*(chartHeight+gap),width,chartHeight);URL.revokeObjectURL(url);
    }
    const png=await new Promise<Blob|null>((resolve)=>canvas.toBlob(resolve,"image/png"));if(!png)return;
    const pngUrl=URL.createObjectURL(png);const link=document.createElement("a");link.download="statbridge-chart.png";link.href=pngUrl;link.click();
    window.setTimeout(()=>URL.revokeObjectURL(pngUrl),1000);
  };
  const noMatch=result.status==="no_match";
  return <section className="results" id="analysis-result">
    <div className="section-heading"><div><span className="eyebrow">ANALYSIS RESULT</span><h2>질문에서 근거까지, 한눈에</h2></div>{noMatch?<span className="unavailable-badge">지원 데이터 없음</span>:<span className="verified-badge"><Icon name="check" size={15}/> 검증된 데이터</span>}</div>
    <div className="result-grid">
      <article className="panel chart-panel">
        <div className="panel-top"><div><span className="question-label">분석한 질문</span><h3>“{result.query}”</h3></div><div className="panel-actions">{result.chart.length>0&&<button onClick={exportPng}><Icon name="chart" size={17}/> PNG</button>}<button onClick={exportCsv}><Icon name="download" size={17}/> CSV</button><button onClick={() => navigator.clipboard?.writeText(location.href)}><Icon name="share" size={17}/> 공유</button></div></div>
        <div className="answer-summary"><span><Icon name="sparkle" size={16}/></span><p>{result.summary}</p></div>
        {result.warnings?.map((warning,index)=><div className="error-banner" key={`${index}-${warning}`}>{warning}</div>)}
        <div className="chart-header"><div><h3>{result.chart.length ? "시계열 분석 결과" : "MCP 통계표 탐색 결과"}</h3>{result.chart.length > 0 && <div className="legend">{result.chart.map((s) => <span key={s.id}><i style={{background:s.color}}/> {s.label}{s.unit ? ` (${s.unit})` : ""}</span>)}</div>}</div>{result.chart.length>0&&<div className="filter-pills"><span>{result.period.start}–{result.period.end}</span><span>{result.frequency} <Icon name="chevron" size={13}/></span></div>}</div>
        {result.chartMode === "separate" ? <div className="separate-charts">{result.chart.map((s) => <div className="single-chart" key={s.id}><h4>{s.label} <small>{s.unit}</small></h4><LineChart series={[s]}/></div>)}</div> : <LineChart series={result.chart}/>}
        {result.insights.length>0&&<div className="insight-box"><div className="insight-title"><span><Icon name="sparkle" size={17}/></span><strong>핵심 인사이트</strong></div><ul>{result.insights.map((x,index) => <li key={`${index}-${x}`}>{x}</li>)}</ul></div>}
        {result.chart.length > 0 && <div className="data-table-wrap"><div className="subsection-title"><div><h3>{allDataOpen?"전체 데이터":"주요 데이터 예시"}</h3><p>{allDataOpen?"조회된 모든 관측치를 표시합니다.":"각 계열의 시작과 최근 값을 간략히 보여줍니다."}</p></div><span>전체 {allRows.length}개 관측치</span></div><table><thead><tr><th>계열</th><th>시점</th><th>값</th></tr></thead><tbody>{visibleRows.map(({series,point}) => <tr key={`${series.id}-${point.date}`}><td>{series.label}</td><td>{point.date}</td><td>{point.value.toLocaleString()} {series.unit}</td></tr>)}</tbody></table>{allRows.length>previewRows.length&&<div className="data-more"><span>{allDataOpen?`전체 ${allRows.length}개를 표시 중입니다.`:`${previewRows.length}개 예시만 표시 중입니다.`}</span><button type="button" aria-expanded={allDataOpen} onClick={()=>setAllDataOpen((current)=>!current)}>{allDataOpen?"간략히 보기":`전체 데이터 더 보기 (${allRows.length}개)`}<Icon name="chevron" size={14}/></button></div>}</div>}
      </article>
      <aside className="evidence-column">
        <article className="panel evidence-panel"><div className="aside-title"><span><Icon name="database" size={18}/></span><div><span className="eyebrow">DATA SOURCES</span><h3>사용한 통계</h3></div></div>{result.tables.map((t) => <div className="source-card" key={t.tableId}><div><span className="table-id">{t.tableId}</span><span className="source-check"><Icon name="check" size={12}/></span></div><strong>{t.name}</strong><p>{t.item} · {t.unit}</p><small>{t.source}</small></div>)}</article>
        <article className="panel lineage-panel"><button className="lineage-toggle" onClick={() => setLineageOpen(!lineageOpen)} aria-expanded={lineageOpen}><div className="aside-title"><span><Icon name="lineage" size={18}/></span><div><span className="eyebrow">DATA LINEAGE</span><h3>데이터 선택 과정</h3></div></div><Icon name="chevron" size={17}/></button>{lineageOpen && <div className="timeline">{result.lineage.map((step, i) => <div className="timeline-row" key={step.id}><div className="timeline-marker"><span><Icon name="check" size={12}/></span>{i < result.lineage.length - 1 && <i/>}</div><div><strong>{step.title}</strong><p>{step.description}</p></div></div>)}</div>}<button className="detail-link">전체 실행 근거 보기 <Icon name="arrow" size={16}/></button></article>
      </aside>
    </div>
  </section>;
}

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [view, setView] = useState<"home" | "lineage">("home");
  const [query, setQuery] = useState("대출 얼마나 늘었어?");
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [periodSelection, setPeriodSelection] = useState<{start:string;end:string} | null>(null);
  const examples = useMemo(() => ["대출 얼마나 늘었어?", "요즘 물가 어때?", "경기 분위기 어때?", "최근 5년 경제심리지수 추이"], []);

  useEffect(()=>{
    const restore=(state:Record<string,unknown>|null)=>{
      if(!state?.statbridge)return;
      setView(state.view==="lineage"?"lineage":"home");
      setQuery(typeof state.query==="string"?state.query:"대출 얼마나 늘었어?");
      setResult((state.result as QueryResponse|null)||null);setPeriodSelection(null);setError("");
      window.setTimeout(()=>window.scrollTo({top:state.result?document.body.scrollHeight:0,behavior:"smooth"}),20);
    };
    if(history.state?.statbridge)restore(history.state);
    else history.replaceState({statbridge:true,view:"home",query,result:null},"",location.pathname);
    const onPopState=(event:PopStateEvent)=>restore(event.state);
    window.addEventListener("popstate",onPopState);return()=>window.removeEventListener("popstate",onPopState);
  },[]);

  const historyUrl=(nextView:"home"|"lineage",nextQuery=query)=>nextView==="lineage"?`${location.pathname}?view=lineage`:`${location.pathname}${nextQuery?`?q=${encodeURIComponent(nextQuery)}`:""}`;
  const pushUiState=(nextView:"home"|"lineage",nextResult:QueryResponse|null,nextQuery=query)=>history.pushState({statbridge:true,view:nextView,query:nextQuery,result:nextResult},"",historyUrl(nextView,nextQuery));

  const showResult = (data: QueryResponse) => {
    setResult(data);
    pushUiState("home",data,data.query||query);
    window.setTimeout(() => document.getElementById("analysis-result")?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
  };

  const goHome=()=>{
    setView("home");setResult(null);setPeriodSelection(null);setError("");
    pushUiState("home",null,query);window.scrollTo({top:0,behavior:"smooth"});
  };

  const navigateView=(nextView:"home"|"lineage")=>{
    setView(nextView);pushUiState(nextView,nextView==="home"?result:null,query);window.scrollTo({top:0,behavior:"smooth"});
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true); setError(""); setResult(null); setPeriodSelection(null);
    try {
      // Preserve the user's original request. HCX classification.series and the
      // resolver's deterministic fallback own comparison decomposition.
      const data=await submitQuery({query:query.trim(),execute:true});
      showResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "알 수 없는 오류가 발생했습니다.");
    } finally { setLoading(false); }
  };

  const chooseClarification = async (selections: Array<{ clarification_id: string; values: string[] }>, start:string, end:string, mode:"combined"|"separate") => {
    if (!result || !selections.length) return;
    setLoading(true); setError("");
    try {
      const data = await submitQuery({
        query: result.query,
        state: result.state,
        selections,
        execute: true,
        period_start:start, period_end:end, chart_mode:mode,
      });
      showResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "역질문 처리 중 오류가 발생했습니다.");
    } finally { setLoading(false); }
  };

  const submitPeriod = async (start: string, end: string, mode:"combined"|"separate") => {
    if (!result) return;
    setLoading(true); setError(""); setPeriodSelection({start,end});
    try {
      const data = await submitQuery({ query: result.query, state: result.state, execute: true, period_start: start, period_end: end, chart_mode:mode });
      showResult(data);
    } catch (err) { setError(err instanceof Error ? err.message : "기간 처리 중 오류가 발생했습니다."); }
    finally { setLoading(false); }
  };

  const chooseChartMode = async (mode: "combined" | "separate") => {
    if (!result || !periodSelection) return;
    setLoading(true); setError("");
    try {
      const data = await submitQuery({ query: result.query, state: result.state, execute: true, period_start: periodSelection.start, period_end: periodSelection.end, chart_mode: mode });
      showResult(data);
    } catch (err) { setError(err instanceof Error ? err.message : "그래프 구성 중 오류가 발생했습니다."); }
    finally { setLoading(false); }
  };

  return <div className="app-shell">
    <Sidebar open={menuOpen} close={() => setMenuOpen(false)} view={view} selectView={navigateView} goHome={goHome}/>
    <div className="main-shell"><Header openMenu={() => setMenuOpen(true)}/>{view === "lineage" ? <DataCatalog/> : <main><Hero query={query} setQuery={setQuery} submit={onSubmit} loading={loading}/><FeatureStrip/>{error && <div className="error-banner">{error}</div>}{result?.status === "need_clarification" && <ClarificationPanel result={result} loading={loading} choose={chooseClarification}/>} {result?.status === "need_period" && <PeriodPanel result={result} loading={loading} submit={submitPeriod}/>} {result?.status === "need_chart_mode" && <ChartModePanel result={result} loading={loading} choose={chooseChartMode}/>} {result && !["need_clarification","need_period","need_chart_mode"].includes(result.status || "") && <Results result={result}/>}<section className="example-footer"><div><Icon name="history"/><span>다른 질문도 탐색해보세요</span></div>{examples.map((x) => <button key={x} onClick={() => { setQuery(x); setResult(null); setPeriodSelection(null); window.scrollTo({ top: 0, behavior: "smooth" }); }}>{x}</button>)}</section></main>}<footer><span>© 2026 StatBridge</span><span>UI → Agent → 통계언어 사전 → MCP → KOSIS</span></footer></div>
  </div>;
}
