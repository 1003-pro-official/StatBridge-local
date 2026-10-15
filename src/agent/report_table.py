"""Observation-bound report tables. No model, interpolation or implicit aggregation."""
from __future__ import annotations

import csv
import io
import math
import re
import textwrap
import zipfile
from decimal import Decimal, ROUND_HALF_UP, localcontext
from xml.sax.saxutils import escape

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class TableOptions(BaseModel):
    model_config = ConfigDict(extra='forbid')
    orientation: Literal['indicators', 'periods'] = 'indicators'
    decimals: int = Field(default=1, ge=0, le=6)
    recent_periods: int | None = Field(default=None, ge=1, le=600)
    labels: list[str] = Field(default_factory=list, max_length=100)
    highlight_latest: bool = True
    title: str = Field(default='', max_length=150)
    note: str = Field(default='', max_length=500)
    template: Literal['default', 'BOK-T01', 'BOK-T02', 'BOK-T03', 'BOK-T04', 'BOK-T05', 'BOK-T06'] = 'default'
    emphasized_labels: list[str] = Field(default_factory=list, max_length=100)


def header_groups(headers, options):
    """Consecutive year groups; only existing period columns, never invented forecasts."""
    if options.get('template') not in {'BOK-T02', 'BOK-T03'} or options['orientation'] != 'indicators':
        return []
    groups = []
    for index, label in enumerate(headers[1:], 1):
        match = re.match(r'^(\d{4})(?:-|년|$)', label)
        year = match[1] + '년' if match else label
        if groups and groups[-1]['label'] == year:
            groups[-1]['span'] += 1
        else:
            groups.append({'label': year, 'start': index, 'span': 1})
    return groups


def period_label(value, frequency=''):
    s = str(value)
    if re.fullmatch(r'\d{6}', s):
        if frequency == 'Q' and s[-2:] in {'01', '02', '03', '04'}:
            return f'{s[:4]}년 {int(s[-2:])}분기'
        return f'{s[:4]}-{s[4:]}'
    if re.fullmatch(r'\d{4}Q[1-4]', s):
        return f'{s[:4]}년 {s[-1]}분기'
    return s


def build_table(series, options=None, *, title='', sources=None):
    options = options or TableOptions()
    known = {s['label']: s for s in series}
    if options.labels and len(set(options.labels)) != len(options.labels):
        raise ValueError('표 항목은 현재 표시된 데이터에서 중복 없이 선택해 주세요.')
    retained = [label for label in options.labels if label in known]
    # Hiding/replacing graph series must not block unrelated graph edits.
    removed = bool(set(options.labels) - set(known))
    if removed: options = options.model_copy(update={'labels': retained})
    selected = [known[label] for label in retained] if retained else series
    # Different frequencies remain separate; no fictitious shared axis or annual totals.
    groups = {}
    for item in selected:
        groups.setdefault(item.get('frequency') or '원자료 주기', []).append(item)
    sections = []
    for frequency, items in groups.items():
        periods = sorted({str(p['date']) for s in items for p in s['points']})
        if options.recent_periods:
            periods = periods[-options.recent_periods:]
        values = []
        for item in items:
            indexed = {}
            for point in item['points']:
                date, value = str(point['date']), point['value']
                if date in indexed:
                    raise ValueError('같은 항목·시점에 값이 두 개 있습니다. 분류를 구분해 다시 조회해 주세요.')
                indexed[date] = value if isinstance(value, (int, float)) and math.isfinite(value) else None
            values.append([indexed.get(p) for p in periods])
        names = [f"{s['label']} ({s['unit']})" for s in items]
        if options.orientation == 'indicators':
            headers = ['지표 · 단위', *[period_label(p, frequency) for p in periods]]
            rows = [[name, *v] for name, v in zip(names, values)]
        else:
            headers = ['시점', *names]
            rows = [[period_label(p, frequency), *[v[i] for v in values]] for i, p in enumerate(periods)]
        emphasized = [i for i, item in enumerate(items) if item['label'] in options.emphasized_labels] if options.orientation == 'indicators' else []
        sections.append({'frequency': frequency, 'periods': periods, 'periodCaption': f'{period_label(periods[0], frequency)} ~ {period_label(periods[-1], frequency)}' if periods else '관측값 없음', 'headers': headers, 'rows': rows, 'headerGroups': header_groups(headers, options.model_dump()), 'emphasizedRows': emphasized})
    return {'title': options.title or title or '통계 비교표', 'options': options.model_dump(),
            'sections': sections, 'sources': sources or [],
            'notes': ['—: 해당 시점의 관측값이 없습니다. 원자료 주기를 유지하며 합산·평균·보간하지 않았습니다.',
                      *(['그래프에서 제외되거나 변경된 항목은 표 선택에서도 제외했습니다.'] if removed else []),
                      *([options.note] if options.note else [])]}


def text_value(value, decimals):
    if value is None: return '—'
    if isinstance(value, (int, float)):
        # Match the browser Intl display at exact half-way values (1.25→1.3),
        # including negatives, without changing the stored observation.
        number = Decimal(str(value))
        with localcontext() as context:
            context.prec = max(28, number.adjusted() + decimals + 4)
            rounded = number.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
        return f'{rounded:,.{decimals}f}'
    return str(value)


def _source_lines(doc):
    return [f"자료: {s.get('tableName', '')} · {s.get('tableId', '')} · {s.get('source', '')}" for s in doc['sources']]


def render_csv(doc):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    # Match displayed cells, including rounding and thousands separators.
    # CSV cannot store fonts, cell colors or spreadsheet number formats.
    def safe(v):
        if v is None: return '—'
        if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')): return "'" + v
        return text_value(v, doc['options']['decimals'])
    writer.writerow([safe('표 1. ' + doc['title'])])
    for section in doc['sections']:
        frequency = {'M': '월별', 'Q': '분기별', 'Y': '연별', 'A': '연별', 'D': '일별'}.get(section['frequency'], section['frequency'])
        writer.writerow([f"{frequency} · {section['periodCaption']}"])
        if section.get('headerGroups'):
            grouped = [''] * len(section['headers'])
            for group in section['headerGroups']: grouped[group['start']] = group['label']
            writer.writerow(grouped)
        writer.writerow([safe(x) for x in section['headers']])
        writer.writerows([[safe(x) for x in row] for row in section['rows']])
        writer.writerow([])
    for note in [*[f'주: {n}' for n in doc['notes']], *_source_lines(doc)]: writer.writerow([safe(note)])
    return ('\ufeff' + stream.getvalue()).encode('utf-8')


def render_xlsx(doc):
    """Small dependency-free OOXML writer; numbers stay numbers, text stays text."""
    def col(n):
        out = ''
        while n:
            n, r = divmod(n - 1, 26); out = chr(65 + r) + out
        return out
    highlights = set()
    merges = []
    records = [([doc['title']], 1)]
    for section in doc['sections']:
        records += [([section['frequency'] + ' · ' + section['periodCaption']], 1)]
        if section.get('headerGroups'):
            grouped = [''] * len(section['headers'])
            for group in section['headerGroups']:
                grouped[group['start']] = group['label']
                if group['span'] > 1:
                    merges.append(f'{col(group["start"]+1)}{len(records)+1}:{col(group["start"]+group["span"])}{len(records)+1}')
            records.append((grouped, 1))
        records.append((section['headers'], 1))
        for index, row in enumerate(section['rows']):
            ri = len(records) + 1
            if doc['options']['highlight_latest']:
                if doc['options']['orientation'] == 'indicators': highlights.add(f'{col(len(row))}{ri}')
                elif index == len(section['rows']) - 1: highlights.update(f'{col(j)}{ri}' for j in range(2, len(row) + 1))
            records.append((row, 1 if doc['options'].get('template') == 'BOK-T05' and index in section.get('emphasizedRows', []) else 0))
        records += [([], 0)]
    records += [([x], 0) for x in [*doc['notes'], *_source_lines(doc)]]
    if len(records) > 1048576 or max((len(r) for r, _ in records), default=0) > 16384:
        raise ValueError('Excel의 행·열 제한을 초과했습니다. 표시 기간·항목을 줄여 주세요.')
    rows = []
    def xml_text(value):
        return escape(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(value) if value is not None else '—'))
    for i, (values, style) in enumerate(records, 1):
        cells = []
        for j, value in enumerate(values, 1):
            address = f'{col(j)}{i}'
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{address}" s="{4 if address in highlights or style else 2}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{address}" s="{style or 3}" t="inlineStr"><is><t xml:space="preserve">{xml_text(value)}</t></is></c>')
        height = max([20, *[18 * max(1, math.ceil(len(str(v)) / (24 if j == 0 else 12))) for j, v in enumerate(values) if isinstance(v, str)]])
        rows.append(f'<row r="{i}" ht="{height}" customHeight="1">{"".join(cells)}</row>')
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    decimals = doc['options']['decimals']
    number_format = '#,##0' + ('.' + '0' * decimals if decimals else '')
    sheet = f'<worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="3" topLeftCell="B4" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="1" width="48" customWidth="1"/><col min="2" max="16384" width="24" customWidth="1"/></cols><sheetData>{"".join(rows)}</sheetData></worksheet>'
    if merges:
        sheet = sheet.replace('</worksheet>', f'<mergeCells count="{len(merges)}">' + ''.join(f'<mergeCell ref="{ref}"/>' for ref in merges) + '</mergeCells></worksheet>')
    if doc['sections'] and doc['sections'][0].get('headerGroups'):
        sheet = sheet.replace('ySplit="3" topLeftCell="B4"', 'xSplit="1" ySplit="4" topLeftCell="B5"')
    files = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        '_rels/.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="보고서 표" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        'xl/styles.xml': f'<styleSheet xmlns="{ns}"><numFmts count="1"><numFmt numFmtId="164" formatCode="{number_format}"/></numFmts><fonts count="2"><font><sz val="11"/><name val="맑은 고딕"/></font><font><b/><sz val="11"/><name val="맑은 고딕"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFEDF7F3"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf><xf numFmtId="164" fontId="1" fillId="2" borderId="0" xfId="0" applyNumberFormat="1" applyFill="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
        'xl/worksheets/sheet1.xml': sheet,
    }
    out = io.BytesIO()
    if doc['options'].get('template', 'default') != 'default':
        styles = files['xl/styles.xml'].replace('val="11"', 'val="9"').replace('FFEDF7F3', 'FFF4F6F7')
        styles = styles.replace('<borders count="1"><border/></borders>', '<borders count="2"><border/><border><top style="thin"><color rgb="FF595959"/></top><bottom style="thin"><color rgb="FF595959"/></bottom></border></borders>')
        styles = styles.replace('fontId="1" fillId="0" borderId="0" xfId="0" applyAlignment', 'fontId="1" fillId="0" borderId="1" xfId="0" applyAlignment')
        if doc['options']['template'] in {'BOK-T04', 'BOK-T05'}:
            styles = styles.replace('fontId="1" fillId="0" borderId="1"', 'fontId="1" fillId="2" borderId="1"')
        files['xl/styles.xml'] = styles
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path, value in files.items(): archive.writestr(path, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + value)
    return out.getvalue()


def render_table_file(doc, format):
    if format == 'csv': return render_csv(doc)
    if format == 'xlsx': return render_xlsx(doc)
    from report_export import EXPORT_LOCK, _font
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    pages = []
    def wrap_cell(value, first=False):
        return '\n'.join(textwrap.wrap(str(value), 28 if first else 12))
    def line_count(value):
        return max(1, value.count('\n') + 1)
    footer = '\n'.join('\n'.join(textwrap.wrap(x, 80)) for x in [*doc['notes'], *_source_lines(doc)])
    appendix = footer.splitlines() if len(footer.splitlines()) > 10 else []
    # Repeat headers and split both axes instead of shrinking or clipping long tables.
    for section in doc['sections']:
        for c in range(1, len(section['headers']), 5):
            headers = [section['headers'][0], *section['headers'][c:c+5]]
            header_height = max(line_count(wrap_cell(x, j == 0)) for j, x in enumerate(headers)) + 1
            chunk, heights = [], [header_height]
            for row in section['rows']:
                subset = [row[0], *row[c:c+5]]
                height = max(line_count(wrap_cell(text_value(x, doc['options']['decimals']), j == 0)) for j, x in enumerate(subset)) + 1
                if height + header_height > 34:
                    raise ValueError('표 항목 이름이 인쇄 영역을 초과합니다. 표시 이름을 짧게 변경하거나 Excel로 출력해 주세요.')
                if chunk and (sum(heights) + height > 34 or len(chunk) >= 12):
                    pages.append((section['frequency'], headers, chunk, heights))
                    chunk, heights = [], [header_height]
                chunk.append(subset); heights.append(height)
            if chunk: pages.append((section['frequency'], headers, chunk, heights))
    if not pages: raise ValueError('출력할 표 관측값이 없습니다.')
    if len(pages) > 120: raise ValueError('인쇄 페이지가 120장을 초과합니다. 표시 기간·항목을 줄여 주세요.')
    latest = {section['frequency']: (section['headers'][-1] if doc['options']['orientation'] == 'indicators' else section['rows'][-1][0]) for section in doc['sections'] if section['rows']}
    out = io.BytesIO()
    with EXPORT_LOCK:
        font = _font()
        pdf = PdfPages(out) if format == 'pdf' else None
        images = []
        try:
            for i, (frequency, headers, rows, heights) in enumerate(pages):
                fig = plt.figure(figsize=(14, 9))
                try:
                    fig.text(.04, .95, '\n'.join(textwrap.wrap(doc['title'], 55)), fontproperties=font, fontsize=15, va='top')
                    frequency_name = {'M': '월별', 'Q': '분기별', 'Y': '연별', 'A': '연별', 'D': '일별'}.get(frequency, frequency)
                    fig.text(.04, .86, f'{frequency_name} · {i+1}/{len(pages)}', fontproperties=font, fontsize=10)
                    table_height = min(.59, max(.14, sum(heights) * .021))
                    table_bottom = .82 - table_height
                    ax = fig.add_axes([.04, table_bottom, .92, table_height]); ax.axis('off')
                    cells = [[wrap_cell(text_value(x, doc['options']['decimals']), j == 0) for j, x in enumerate(row)] for row in rows]
                    grouped = header_groups(headers, doc['options'])
                    if grouped:
                        groups = [''] * len(headers)
                        for group in grouped: groups[group['start']] = group['label']
                        cells.insert(0, [wrap_cell(x, j == 0) for j, x in enumerate(headers)])
                        heights = [1.5, *heights]
                    table = ax.table(cellText=cells, colLabels=groups if grouped else [wrap_cell(x, j == 0) for j, x in enumerate(headers)], colWidths=[.3]+[.7/(len(headers)-1)]*(len(headers)-1), cellLoc='right', bbox=[0, 0, 1, 1])
                    table.auto_set_font_size(False)
                    for (ri, ci), cell in table.get_celld().items():
                        cell.get_text().set_fontproperties(font); cell.get_text().set_fontsize(8)
                        cell.set_height(heights[ri] / sum(heights))
                        cell.set_edgecolor('#cbd8e4')
                        if ri == 0: cell.set_facecolor('#eaf2f8')
                        if doc['options'].get('template', 'default') != 'default':
                            cell.visible_edges = 'T' if ri == 0 else ('B' if ri == len(cells) else '')
                            cell.set_edgecolor('#595959'); cell.set_linewidth(1)
                            cell.set_facecolor('#f4f6f7' if ri == 0 and doc['options']['template'] in {'BOK-T04','BOK-T05'} else 'white')
                            if ri == (1 if grouped else 0): cell.visible_edges += 'B'; cell.get_text().set_weight('bold')
                            if doc['options']['template'] == 'BOK-T04': cell.PAD = .03
                        if ci == 0: cell.get_text().set_ha('left')
                        elif ri <= (1 if grouped else 0): cell.get_text().set_ha('center')
                        data_index = ri - (2 if grouped else 1)
                        if data_index >= 0 and doc['options']['template'] == 'BOK-T05' and any(rows[data_index][0] == section['rows'][r][0] for section in doc['sections'] for r in section.get('emphasizedRows', [])):
                            cell.get_text().set_weight('bold'); cell.visible_edges += 'T'
                        if data_index >= 0 and ci > 0 and doc['options']['highlight_latest'] and (headers[ci] == latest.get(frequency) if doc['options']['orientation'] == 'indicators' else rows[data_index][0] == latest.get(frequency)):
                            cell.set_facecolor('#edf7f3'); cell.get_text().set_weight('bold')
                    if grouped:
                        from matplotlib.patches import Rectangle
                        fig.canvas.draw()
                        for group in grouped:
                            first = table[0, group['start']]
                            x, y = first.get_xy()
                            width = sum(table[0, j].get_width() for j in range(group['start'], group['start'] + group['span']))
                            ax.add_patch(Rectangle((x, y), width, first.get_height(), facecolor='white', edgecolor='none', transform=ax.transAxes, zorder=3))
                            ax.plot([x, x + width], [y + first.get_height(), y + first.get_height()], color='#595959', linewidth=1, transform=ax.transAxes, zorder=4)
                            ax.text(x + width/2, y + first.get_height()/2, group['label'], ha='center', va='center', fontproperties=font, fontsize=8, fontweight='bold', transform=ax.transAxes, zorder=5)
                    fig.text(.04, table_bottom - .035, '출처·주석은 이어지는 별도 페이지에 표시합니다.' if appendix else footer, fontproperties=font, fontsize=8, va='top')
                    if pdf: pdf.savefig(fig)
                    else:
                        image = io.BytesIO(); fig.savefig(image, format='png', dpi=150); images.append(image.getvalue())
                finally: plt.close(fig)
            for start in range(0, len(appendix), 35):
                fig = plt.figure(figsize=(14, 9))
                try:
                    fig.text(.04, .94, '표의 출처 · 주석', fontproperties=font, fontsize=15, va='top')
                    fig.text(.04, .85, '\n'.join(appendix[start:start+35]), fontproperties=font, fontsize=10, va='top', linespacing=1.5)
                    if pdf: pdf.savefig(fig)
                    else:
                        image = io.BytesIO(); fig.savefig(image, format='png', dpi=150); images.append(image.getvalue())
                finally: plt.close(fig)
        finally:
            if pdf: pdf.close()
    if pdf: return out.getvalue()
    if len(images) == 1: return images[0]
    zipped = io.BytesIO()
    with zipfile.ZipFile(zipped, 'w', zipfile.ZIP_DEFLATED) as archive:
        for i, content in enumerate(images, 1): archive.writestr(f'statbridge-table-{i:03}.png', content)
    return zipped.getvalue()
