"""Verify collected official bodies against frozen gold offline. Fail on mismatches."""
import argparse
import hashlib
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ARCHIVE = Path(__file__).resolve().parents[1]


def no_network(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        raise PermissionError('Offline verification: network disabled')


def lines(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    sys.addaudithook(no_network)
    gold_bytes = (ARCHIVE/'answer_key.jsonl').read_bytes()
    gold = lines(ARCHIVE/'answer_key.jsonl')
    records = lines(args.evidence/'requests.jsonl')
    meta = json.loads((args.evidence/'collection.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(gold_bytes).hexdigest() == meta['gold_sha256']
    assert len(records) == len(gold) == 20
    assert [r['case_id'] for r in records] == [r['id'] for r in gold]
    freq = lambda f: {'A':'Y', 'H':'S'}.get(f, f)
    results = []
    for g, request in zip(gold, records):
        e = g['expected']; p = e['params']
        rows = []; provider_error = None
        if request.get('response_file'):
            file = (args.evidence/request['response_file']).resolve()
            assert file.is_relative_to(args.evidence.resolve())
            body = file.read_bytes()
            assert hashlib.sha256(body).hexdigest() == request['body_sha256']
            try:
                data = json.loads(body)
                if isinstance(data, list): rows = data
                else: provider_error = {k:data.get(k) for k in ('err', 'errMsg')}
            except (ValueError, AttributeError):
                provider_error = {'parse_error':True}
        classes = {k:v for k,v in p.items() if k.startswith('objL')}
        points = {pt['period']:pt for pt in e['points']}
        checks = {
            'API 응답':request.get('http_status') == 200 and bool(rows) and not provider_error,
            '요청 인자':all(request['params'].get(k) == v for k,v in p.items()),
            '기관·표':bool(rows) and all(str(r.get('ORG_ID')) == p['orgId'] and r.get('TBL_ID') == p['tblId'] for r in rows),
            '항목':bool(rows) and all(r.get('ITM_ID') == p['itmId'] for r in rows),
            '분류':bool(rows) and all({f'objL{i}':r[f'C{i}'] for i in range(1,9) if r.get(f'C{i}')} == classes for r in rows),
            '주기·기간':len(rows) == len(points) and {r.get('PRD_DE') for r in rows} == set(points) and all(freq(r.get('PRD_SE')) == freq(p['prdSe']) for r in rows),
            '단위':bool(rows) and all(r.get('UNIT_NM') == e['points'][0]['unit'] for r in rows)}
        diffs = []; matched = 0
        for period, pt in points.items():
            found = [r for r in rows if r.get('PRD_DE') == period]
            try: equal = len(found) == 1 and Decimal(str(found[0]['DT']).replace(',', '')) == Decimal(pt['value'])
            except (InvalidOperation, KeyError): equal = False
            if equal: matched += 1
            else: diffs.append({'period':period,'expected':pt['value'],'official':[r.get('DT') for r in found]})
        checks['수치'] = not diffs
        results.append({'id':g['id'],'passed':all(checks.values()),'checks':checks,
                        'matched_points':matched,'expected_points':len(points),
                        'numeric_differences':diffs,'provider_error':provider_error,
                        'official_table_names':sorted({r.get('TBL_NM','') for r in rows}),
                        'official_item_names':sorted({r.get('ITM_NM','') for r in rows}),
                        'response_file':request.get('response_file')})
    summary = {'phase':'posthoc_gold_verification', 'not_original_model_run':True,
               'cases':len(results),'passed':sum(r['passed'] for r in results),
               'expected_points':sum(r['expected_points'] for r in results),
               'matched_points':sum(r['matched_points'] for r in results),
               'gold_sha256':hashlib.sha256(gold_bytes).hexdigest(),'network_disabled':True,
               'evaluation_scores_changed':False}
    for filename, obj in [('verification.json',{'summary':summary,'results':results})]:
        (args.evidence/filename).write_bytes((json.dumps(obj, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    print(json.dumps(summary, ensure_ascii=False))
    if summary['passed'] != 20:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
