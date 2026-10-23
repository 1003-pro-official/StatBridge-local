"""Collect new KOSIS evidence for the frozen gold; never calls an evaluation model."""
import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

ARCHIVE = Path(__file__).resolve().parents[1]
ROOT = ARCHIVE.parent
ENDPOINT = 'https://kosis.kr/openapi/Param/statisticsParameterData.do'


def utc():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='New evidence directory; refuses to overwrite existing evidence.')
    args = parser.parse_args()
    import requests
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env')
    key = os.environ.get('KOSIS_API_KEY', '').strip()
    if not key:
        raise SystemExit('KOSIS_API_KEY is required; no credential will be printed.')
    args.output.mkdir(parents=True, exist_ok=False)
    raw_dir = args.output/'official_responses'
    raw_dir.mkdir()
    gold_bytes = (ARCHIVE/'answer_key.jsonl').read_bytes()
    gold = [json.loads(s) for s in gold_bytes.decode('utf-8').splitlines()]
    session = requests.Session()
    records = []
    for case in gold:
        expected = case['expected']
        assert expected['endpoint'] == ENDPOINT
        params = {'method':'getList', 'format':'json', 'jsonVD':'Y', 'smblChk':'Y',
                  **expected['params']}
        record = {'case_id':case['id'], 'phase':'posthoc_gold_verification',
                  'endpoint':ENDPOINT, 'params':params, 'started_at_utc':utc()}
        try:
            response = session.get(ENDPOINT, params={**params, 'apiKey':key}, timeout=(10, 45))
            body = response.content
            if key.encode() in body:
                raise RuntimeError('credential unexpectedly present in response; body not saved')
            relative = f'official_responses/{case["id"]}.bin'
            (args.output/relative).write_bytes(body)
            record.update(http_status=response.status_code, response_file=relative,
                          body_sha256=hashlib.sha256(body).hexdigest(), byte_count=len(body),
                          content_type=response.headers.get('Content-Type'),
                          server_date=response.headers.get('Date'))
        except Exception as exc:
            # Do not persist exception text: requests errors may include credential URLs.
            record['error_type'] = type(exc).__name__
        record['finished_at_utc'] = utc()
        records.append(record)
        with (args.output/'requests.jsonl').open('ab') as f:
            f.write((json.dumps(record, ensure_ascii=False)+'\n').encode('utf-8'))
        print(case['id'], record.get('http_status', record.get('error_type')), flush=True)
        time.sleep(0.3)
    meta = {'phase':'posthoc_gold_verification', 'not_original_model_run':True,
            'collected_at_utc':utc(), 'gold_sha256':hashlib.sha256(gold_bytes).hexdigest(),
            'cases':len(records), 'model_calls':0,
            'body_scope':'Decoded HTTP entity-body bytes from requests.Response.content; not TLS/network wire bytes.',
            'this_collection_is_model_run':False,
            'note':'Fresh official responses independently verify frozen gold; do not replace prior run evidence or scores.'}
    (args.output/'collection.json').write_bytes((json.dumps(meta, indent=2)+'\n').encode('utf-8'))


if __name__ == '__main__':
    main()
