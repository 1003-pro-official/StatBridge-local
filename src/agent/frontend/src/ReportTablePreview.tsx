import type {TableDocument} from './reportTable';
import {tableCell} from './reportTable';
import {cellStyle} from './tableLayout';
export default function ReportTablePreview({document:doc}:{document:TableDocument}){
 return <div className="report-table-reading"><h3>{doc.caption??`표 1. ${doc.title}`}</h3>
 {doc.layoutSections?doc.layoutSections.map((s,si)=><section key={si}><p>{s.periodCaption}</p><div className="report-table-scroll"><table className="table-reading-grid"><colgroup>{s.columns.map(c=><col key={c.id} style={{width:c.width}}/>)}</colgroup><tbody>{s.sheetRows?.map(row=><tr key={row.id} style={{height:row.height}}>{row.cells.map(c=><td key={c.key} rowSpan={c.rowSpan} colSpan={c.colSpan} style={{...cellStyle(c.format),whiteSpace:c.format.wrap?'pre-wrap':'pre'}}>{c.text}</td>)}</tr>)}</tbody></table></div></section>):doc.sections.map((s,i)=><section key={i}><p>{s.periodCaption}</p><div className="report-table-scroll"><table><thead><tr>{s.headers.map((h,j)=><th key={j}>{h}</th>)}</tr></thead><tbody>{s.rows.map((row,r)=><tr key={r}>{row.map((c,j)=><td key={j}>{tableCell(c,doc.options.decimals)}</td>)}</tr>)}</tbody></table></div></section>)}
 <footer>{doc.annotations?.map(n=><p key={n.number}>주 {n.number}: {n.text}</p>)}{doc.notes.map((n,i)=><p key={i}>주: {n}</p>)}{doc.sources.map((s,i)=><p key={i}>자료: {s.displaySource??'KOSIS'} · {s.tableName}</p>)}</footer></div>;
}
