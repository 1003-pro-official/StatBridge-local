"""Build a source-grounded research catalog, or verify its queries locally.

Only collect.py accesses the web. --verify uses the real local API and CSVs,
with models/vector retrieval disabled, and stores observations only in cache.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = ROOT / '.venv/cache/kosis-bok-reproduction'
sys.path.insert(0, str(HERE))
from cases import CASES


def norm(value):
    return re.sub(r'\d+\)|[^0-9a-zA-Z가-힣]', '', str(value)).casefold()


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(name, rows, fields=None):
    with (HERE / name).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]), extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                             for k, v in row.items()})


def check_plans(plans, expected, labels):
    """Match every requested series once; duplicates/omissions/wrong tables fail."""
    if len(plans) != len(expected):
        return False
    remaining = list(plans)
    for target in expected:
        for index, plan in enumerate(remaining):
            table = plan['table_id']
            values = {norm(labels.get((table, code), code)) for code in plan.get('classifications', {}).values()}
            required_codes = set(target.get('codes', {}).values())
            if (table == target['table_id'] and {norm(x) for x in target['values']} <= values
                    and required_codes <= set(plan.get('classifications', {}).values())):
                remaining.pop(index)
                break
        else:
            return False
    fingerprints = [(p['table_id'], tuple(sorted(p.get('classifications', {}).items()))) for p in plans]
    return len(set(fingerprints)) == len(plans)


def numeric_rows(rows):
    try:
        return bool(rows) and all(math.isfinite(float(str(r.get('DT', '')).replace(',', ''))) for r in rows)
    except (ValueError, TypeError):
        return False


def pdf_pages(file):
    import pypdfium2 as pdfium
    path = ROOT / file['path']
    dest = path.with_suffix('.pages.json')
    if not dest.exists():
        document = pdfium.PdfDocument(path)
        pages = []
        try:
            for page in document:
                text = page.get_textpage()
                pages.append(text.get_text_range())
                text.close()
                page.close()
        finally:
            document.close()
        dest.write_text(json.dumps(pages, ensure_ascii=False))
    return json.loads(dest.read_text())


def source_for(case, releases):
    release = releases[case['source_id']]
    candidates = []
    for file in release.get('files', []):
        if not file['name'].lower().endswith('.pdf'):
            continue
        pages = pdf_pages(file)
        page = case.get('source_page')
        if page and page <= len(pages) and norm(case['source_caption']) in norm(pages[page - 1]):
            candidates.append((file, page))
        elif not page:
            # Prefer a matching title line over running prose/TOC matches.
            for index, text in enumerate(pages):
                if index == 0 or '차 례' in text or '차례' in text:
                    continue
                if any(norm(case['source_caption']) in norm(line) and len(norm(line)) < 50
                       for line in text.splitlines()):
                    candidates.append((file, index + 1))
                    break
    if not candidates:
        return {'publication': release['title'], 'publication_date': release['date'], 'url': release['url'],
                'page': case.get('source_page'), 'review': '원본 위치 확인 대기', 'human_reviewed': False}
    file, page = candidates[0]
    return {'publication': release['title'], 'publication_date': release['date'], 'url': release['url'],
            'filename': file['name'], 'attachment_url': file['url'], 'sha256': file['sha256'], 'page': page,
            'caption': case['source_caption'], 'review': '에이전트 PDF 텍스트 대조; 시각·사람 검수 미완료',
            'human_reviewed': False}


def expected_parameters(case, classifications, items):
    result = []
    for target in case['expected']:
        table = target['table_id']
        selected = {}
        for value in target['values']:
            hits = [r for r in classifications if r['TBL_ID'] == table and norm(r['ITM_NM']) == norm(value)]
            if value in target.get('codes', {}):
                hits = [r for r in hits if r['ITM_ID'] == target['codes'][value]]
            if len(hits) != 1:
                raise ValueError(f"{case['id']}: ambiguous/missing metadata {table} {value}: {len(hits)}")
            row = hits[0]
            selected['objL' + row['OBJ_ID_SN']] = row['ITM_ID']
        item = next(r['ITM_ID'] for r in items if r['TBL_ID'] == table)
        result.append({'table_id': table, 'org_id': '301', 'item_id': item,
                       'frequency': case['frequency'], 'classifications': selected})
    return result


def screen_legacy(tables):
    """Lexical triage only. Never elevate the old extraction into verified gold."""
    old = read_csv(ROOT / 'research/그림표-분석/그림표_마스터.csv')
    result = []
    for row in old:
        title = norm(row['제목'])
        ranked = []
        for table in tables:
            base = re.split(r'[（(]', table['TBL_NM'])[0]
            tokens = [norm(x) for x in re.split(r'\s+|및|별', base) if len(norm(x)) >= 3]
            hits = [x for x in tokens if x in title]
            if hits:
                ranked.append((sum(len(x) for x in hits), table['TBL_ID']))
        ids = [t for _, t in sorted(ranked, reverse=True)[:5]]
        source = row['사용 데이터·출처']
        result.append({'결과물ID': row['결과물ID'], '보고서': row['보고서'], '발간일': row['발간일'],
                       '구분': row['구분'], '번호': row['번호'], '제목': row['제목'], '출처표기': source,
                       '후보통계표': ids, '판정': '확인 대기',
                       '선별상태': '제목 일치 후보' if ids else '제목만으로 매핑 불가',
                       '비고': '어휘 기반 선별; 계열·기간·단위·수치 미검증; 재현 가능 건수에 포함하지 않음; 근거는 기존 결과물ID로 원본 마스터 참조'})
    write_csv('기존추출물_선별.csv', result)
    return Counter(r['선별상태'] for r in result)


def inventory(collection):
    listings = []
    selected = {r['id']: r for r in collection['releases']}
    for r in collection['listings']:
        chosen = selected.get(r['id'])
        listings.append({'게시물ID': r['id'], '발간일': r['date'], '제목': r['title'], '자료군': r['family'],
                         '공식URL': r['url'], '선정': bool(chosen),
                         '선정제외사유': chosen['selection'] if chosen else
                         '동일 자료군·연도 대표판 우선; 본문 미조사' if r['family'] != '범위외' else '우선 통계자료군 밖; 본문 미조사'})
    write_csv('조사목록.csv', listings)
    attachments = []
    for release in collection['releases']:
        for file in release.get('files', []):
            attachments.append({'게시물ID': release['id'], '제목': release['title'], '발간일': release['date'],
                                '자료군': release['family'], '공식URL': release['url'], '파일명': file['name'],
                                '첨부URL': file['url'], 'SHA256': file['sha256'],
                                '로컬상태': release['status'], '검수': '원본 수집; 전체 그림표 판정 아님'})
    write_csv('원본목록.csv', attachments)
    return len(attachments)


def caption_candidates(text):
    """Unnumbered statistical releases need triage, not invented figure numbers."""
    found = []
    lines = [re.sub(r'\s+', ' ', s).strip() for s in text.splitlines()]
    for index, line in enumerate(lines):
        if not 5 <= len(line) <= 80 or any(x in line for x in ['문의', 'http', '@', '공보', '기자', '목차', '차 례']):
            continue
        if re.search(r'[。.]$|(?:합니다|하였다|하였음|하였으며|참조|의미|주십시오)$', line):
            continue
        if not re.search(r'추이|현황|증감액|증감률|등락률|가중평균금리|지출항목별|지수 및|성장성|수익성|안정성', line):
            continue
        if len(re.findall(r'\d', line)) > len(line) / 4 or re.match(r'^(?:□|―|ㅇ|주\s*:|자료\s*:)', line):
            continue
        # Caption candidates have short labels or a nearby printed unit.
        nearby = ' '.join(lines[max(0, index-1):index+4])
        if len(line) < 35 or re.search(r'\(%|\(.*원\)|\(.*달러\)|단위', nearby):
            if line not in found:
                found.append(line)
    return found


def extract_inventory(collection):
    candidates, pages_count = [], 0
    for release in collection['releases']:
        for file in release.get('files', []):
            if not file['name'].endswith('.pdf'):
                continue
            pages = pdf_pages(file)
            pages_count += len(pages)
            for page, text in enumerate(pages, 1):
                for caption in caption_candidates(text):
                    stable = f"{release['id']}|{file['sha256']}|{page}|{caption}"
                    candidates.append({'후보ID': 'CAP-' + hashlib.sha256(stable.encode()).hexdigest()[:16],
                                       '게시물ID': release['id'], '자료군': release['family'], '발간물': release['title'],
                                       '공식URL': release['url'], '파일명': file['name'], 'SHA256': file['sha256'],
                                       'PDF물리페이지': page, '캡션후보': caption,
                                       '판정': '확인 대기', '비고': '텍스트 규칙 후보; 본문·목차 오탐 및 무번호 그림 누락 가능; 검증된 재현 건수 아님'})
    write_csv('확장그림표_후보.csv', candidates)
    print('PDF pages', pages_count, 'caption candidates', len(candidates))
    return pages_count, len(candidates)


def verify(queries, labels):
    # Do not read .env or use credentialed model/vector calls in this offline check.
    os.environ.update(PYTHON_DOTENV_DISABLED='1', STATBRIDGE_HYBRID_RETRIEVAL='0', STATBRIDGE_JEV_ENABLED='0',
                      MPLCONFIGDIR='/tmp/statbridge-research-mpl',
                      STATBRIDGE_AUTH_DB=str(CACHE / 'verify-accounts.sqlite3'))
    for key in ['KOSIS_API_KEY', 'OPENAI_API_KEY', 'NCP_CLOVA_API_KEY', 'NCP_API_KEY', 'CLOVA_STUDIO_API_KEY']:
        os.environ[key] = ''
    sys.path[:0] = [str(ROOT / 'src/backend'), str(ROOT / 'src/agent'), str(ROOT / 'tests')]
    import bridge_api as api
    from authenticated_client import TestClient

    records = []
    with TestClient(api.app) as client:
        for case in queries:
            for variant in ['업무형', '정확형']:
                for display in ['그래프', '표']:
                    q = case['queries'][variant][display]
                    record = {'id': case['id'], 'variant': variant, 'display': display, 'query': q,
                              'source': 'local_csv', 'kosis_live_verified': False}
                    try:
                        response = client.post('/api/query', json={'query': q, 'execute': True})
                        data = response.json()
                        record.update(query_http=response.status_code, query_status=data.get('status'))
                        session_id = data.get('outputSessionId')
                        session = api.OUTPUT_SESSIONS.get(session_id, {})
                        result = session.get('result') or {}
                        plans = result.get('api_plans') or ([result['api_plan']] if result.get('api_plan') else [])
                        record['actual_plans'] = plans
                        record['series_match'] = check_plans(plans, case['expected'], labels)
                        rows = (result.get('execution') or {}).get('rows') or []
                        record['row_count'] = len(rows)
                        starts, ends = ('2022', '2024') if case['frequency'] == 'A' else ('202301', '202504' if case['frequency'] == 'Q' else '202512')
                        record['frequency_match'] = bool(plans) and all(p.get('frequency') in ({'A', 'Y'} if case['frequency'] == 'A' else {case['frequency']}) for p in plans)
                        record['period_match'] = bool(plans) and all(p.get('start_period') == starts and p.get('end_period') == ends for p in plans)
                        record['period'] = data.get('period')
                        record['rows_present'] = bool(rows)
                        record['numeric_observations'] = numeric_rows(rows)
                        record['observations_complete'] = len(rows) == len(case['expected']) * {'A': 3, 'Q': 12, 'M': 36}[case['frequency']]
                        if session_id and record['series_match']:
                            rendered = client.post('/api/output', json={'session_ids': [session_id], 'quick_output': True,
                                                                       'chart_type': 'line'})
                            output = rendered.json()
                            spec = output.get('outputSpec') or {}
                            record.update(output_http=rendered.status_code, output_status=output.get('status'),
                                          plotly_present=bool(spec.get('plotlyFigure')),
                                          table_present=bool(spec.get('table')), insights_present=bool(spec.get('summary')))
                            plotted = output.get('chart') or []
                            count = {'A': 3, 'Q': 12, 'M': 36}[case['frequency']]
                            record['point_counts'] = [len(s.get('points') or s.get('data') or []) for s in plotted]
                            record['plotted_complete'] = record['point_counts'] == [count] * len(case['expected'])
                            if case['id'] in {'ESI-01', 'RATE-03', 'PRICE-02', 'CREDIT-02', 'PAY-03'} and variant == '업무형' and display == '그래프' and spec.get('plotlyFigure'):
                                import plotly.io as pio
                                previews = CACHE / 'previews'
                                previews.mkdir(exist_ok=True)
                                pio.write_html(spec['plotlyFigure'], previews / (case['id'] + '.html'), include_plotlyjs=True, auto_open=False)
                            edit = output.get('editSessionId')
                            if edit:
                                exported = client.post('/api/table/export', json={'edit_session_id': edit,
                                                                                'revision': 0, 'format': 'xlsx'})
                                record['xlsx_export_ok'] = exported.status_code == 200 and exported.content.startswith(b'PK')
                        record['passed'] = all([record.get('series_match'), record.get('rows_present'),
                                                record.get('frequency_match'), record.get('period_match'),
                                                record.get('observations_complete'),
                                                record.get('numeric_observations'),
                                                record.get('plotted_complete'),
                                                record.get('plotly_present'), record.get('table_present'),
                                                record.get('insights_present'), record.get('xlsx_export_ok')])
                        # Diagnostics stay free of raw observations and arbitrary exception payloads.
                        if data.get('clarification'):
                            record['followup'] = data['clarification']
                    except Exception as exc:
                        record.update(passed=False, error=type(exc).__name__)
                    records.append(record)
                    (CACHE / 'workflow.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
                    print(case['id'], variant, display, record.get('query_status'), record.get('series_match'),
                          record['passed'], flush=True)
    (CACHE / 'workflow.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--extract-inventory', action='store_true')
    args = parser.parse_args()
    collection = json.loads((CACHE / 'collection.json').read_text())
    releases = {r['id']: r for r in collection['releases']}
    tables = read_csv(ROOT / 'data/processed/bok_table_master.csv')
    classifications = read_csv(ROOT / 'data/processed/bok_classifications.csv')
    items = read_csv(ROOT / 'data/processed/bok_items.csv')
    labels = {(r['TBL_ID'], r['ITM_ID']): r['ITM_NM'] for r in classifications}
    queries = []
    for target in CASES:
        case = dict(target)
        case['source'] = source_for(case, releases)
        case['expected_parameters'] = expected_parameters(case, classifications, items)
        ids = ', '.join(dict.fromkeys(x['table_id'] for x in case['expected']))
        cadence = {'M': '월별로', 'Q': '분기별로', 'A': '연도별로'}[case['frequency']]
        stem = f"{case['period_text']} {case['topic']} 자료를 {cadence}"
        exact = f"{case['period_text']} {case['topic']} [{ids}] 자료를 {cadence}"
        case['queries'] = {kind: {'그래프': text + ' 선그래프로 보여줘', '표': text + ' 표로 보여줘'}
                           for kind, text in [('업무형', stem), ('정확형', exact)]}
        case['interpretation'] = '빠른 출력의 관측 요약 확인; 원인·전망·보고서 원문 해석 재현 검증 아님'
        queries.append(case)
    records = verify(queries, labels) if args.verify else (
        json.loads((CACHE / 'workflow.json').read_text()) if (CACHE / 'workflow.json').exists() else [])
    # Invalidate stale results if the authored query changed.
    records = [r for r in records if any(r['id'] == c['id'] and r['query'] == c['queries'][r['variant']][r['display']] for c in queries)]
    for case in queries:
        case['verification'] = [r for r in records if r['id'] == case['id']]
    attachments = inventory(collection)
    if args.extract_inventory:
        extract_inventory(collection)
    legacy_counts = screen_legacy(tables)
    # Detailed execution results/predicted plans belong only in the ignored cache.
    (HERE / '질의집.jsonl').write_text(''.join(json.dumps({k: v for k, v in c.items() if k != 'verification'}, ensure_ascii=False) + '\n' for c in queries))
    matrix = []
    for case in queries:
        passed = [r for r in case['verification'] if r.get('passed')]
        matrix.append({'유형ID': case['id'], '원본': case['source']['publication'], '원본URL': case['source']['url'],
                       'PDF물리페이지': case['source'].get('page'), '원본캡션': case['source_caption'],
                       '원본검수': case['source']['review'], '재현범위': case['coverage'],
                       '실행판정': '출력 확인' if passed else '기능·질의 보완 필요' if case['verification'] else '실행 미확인',
                       '기대조회조건': case['expected_parameters'], '제약': case['note'], '사람검수': False})
    write_csv('재현매핑.csv', matrix)
    lines = ['# 자연어 질의집', '', '> 모든 사례는 보고서에서 계열·기간을 선별한 응용형입니다. 원본 전체·동일 수치·동일 디자인 재현을 뜻하지 않습니다.',
             '> 원본 페이지는 PDF 물리 페이지입니다. 에이전트 텍스트 대조와 사람 검수를 구분합니다.', '',
             '로그인 → 질의 입력 → 필요한 통계표·분류·기간 확인 → 빠른 출력 → 그래프/표 선택 → 관측 요약 확인 → 필요 시 XLSX 내보내기 순서로 사용합니다.',
             '아래 실행 확인 질의를 우선 사용하세요. 정확형은 표 ID를 추가한 진단 변형이며, 일부는 업무형보다 잘못 해석됩니다. 실패 변형을 성공 대안으로 사용하지 마세요.', '',
             '## 실행 확인 질의 바로 사용하기', '',
             '| 유형 | 그래프 입력 | 표 입력 |', '|---|---|---|']
    for case in queries:
        pairs = [v for v in ['업무형', '정확형'] if all(any(r['variant'] == v and r['display'] == display and r.get('passed') for r in case['verification']) for display in ['그래프', '표'])]
        if pairs:
            pair = case['queries'][pairs[0]]
            lines.append(f"| {case['id']} | {pair['그래프']} | {pair['표']} |")
    lines += ['', '## 후보·실패 변형을 포함한 상세 기록', '']
    for case in queries:
        lines += [f"## {case['id']} · {case['topic']}", '',
                  f"원본: [{case['source']['publication']}]({case['source']['url']}), PDF p.{case['source'].get('page') or '확인 대기'}, {case['source_caption']}.", '',
                  f"범위: {case['coverage']}. {case['note']}", '']
        for variant, pair in case['queries'].items():
            for display, q in pair.items():
                record = next((r for r in case['verification'] if r['variant'] == variant and r['display'] == display), {})
                status = '로컬 API·출력·XLSX 확인' if record.get('passed') else record.get('query_status', '미실행')
                if record and not record.get('series_match'):
                    status += ' / 기대 계열 불일치 또는 미도달'
                lines += [f"- **{variant} {display}** [{status}]: {q}"]
        lines += ['', '해석 범위: ' + case['interpretation'], '']
    (HERE / '질의집.md').write_text('\n'.join(lines) + '\n')
    summary = {'listings': len(collection['listings']), 'releases': len(releases), 'attachments': attachments,
               'legacy': dict(legacy_counts), 'types': len(queries), 'queries': len(queries)*4,
               'verified_queries': len(records), 'passed_queries': sum(bool(r.get('passed')) for r in records),
               'types_with_output': sum(any(r.get('passed') for r in c['verification']) for c in queries),
               'full_original_verified': 0}
    (CACHE / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
