"""Paid model path for derived/report. Refuses to run until a human fills profiles.json.

This runner never receives expected/oracle data. Model attribution is recorded as
unverified because the API does not expose the model that answered.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

from e2e_common import BASE, CACHE, read, rows, write_rows


def require_approval(profiles, profile_name, modes, repeats):
    problems = []
    if not profile_name:
        problems.append('selected_profile is null')
    elif profile_name not in profiles['profiles']:
        problems.append(f'unknown profile: {profile_name}')
    approval = profiles.get('approval') or {}
    if not approval.get('approved_by'):
        problems.append('approval.approved_by is empty')
    if not approval.get('approved_at'):
        problems.append('approval.approved_at is empty')
    if approval.get('repeats') != repeats:
        problems.append(f'approval.repeats={approval.get("repeats")} differs from --repeats={repeats}')
    if not isinstance(approval.get('cost_cap_usd'), (int, float)) or approval['cost_cap_usd'] <= 0:
        problems.append('approval.cost_cap_usd must be a positive number')
    approved_modes = set(approval.get('modes') or [])
    if set(modes) != approved_modes:
        problems.append(f'approved modes {sorted(approved_modes)} differ from requested {sorted(modes)}')
    profile = (profiles.get('profiles') or {}).get(profile_name) or {}
    missing = [role for role, value in (profile.get('models') or {}).items() if not value]
    if missing:
        problems.append('profile models are not filled: ' + ', '.join(missing))
    missing_env = [name for name in profile.get('env', []) if not os.getenv(name)]
    if missing_env:
        problems.append('missing credentials: ' + ', '.join(missing_env))
    return problems


def post(base_url, path, body, timeout=180):
    request = urllib.request.Request(base_url.rstrip('/') + path, method='POST',
                                     data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, json.loads(response.read().decode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', required=True)
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--mode', action='append', choices=['derived', 'report'], required=True)
    parser.add_argument('--base-url')
    parser.add_argument('--allow-paid', action='store_true')
    parser.add_argument('--output')
    args = parser.parse_args()
    profiles = read(BASE / 'profiles.json')
    if not args.allow_paid:
        raise SystemExit('paid run refused: pass --allow-paid after the approval block is filled')
    problems = require_approval(profiles, args.profile, args.mode, args.repeats)
    if problems:
        raise SystemExit('paid run refused:\n - ' + '\n - '.join(problems))
    if not args.base_url:
        raise SystemExit('paid run refused: --base-url of a running product instance is required')
    cases = [c for c in rows(BASE / 'cases' / 'dev.jsonl') + rows(BASE / 'cases' / 'test.jsonl')
             if c['mode'] in args.mode and c['eligible_for_scoring']]
    output = args.output or str(CACHE / 'model-runs' / f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.jsonl")
    observations = []
    for case in cases:
        for attempt in range(1, args.repeats + 1):
            record = {'id': case['id'], 'mode': case['mode'], 'tier': case['tier'], 'attempt': attempt,
                      'profile': args.profile, 'started_at': datetime.now(timezone.utc).isoformat(),
                      'model_attribution': 'unverified', 'actual_models': None}
            try:
                body = {'query': case['input']['query'], 'execute': True}
                status, response = post(args.base_url, '/api/query', body)
                record.update(http_status=status, decision=(response.get('status') or ''), query=case['input']['query'])
                session = response.get('outputSessionId')
                if session:
                    status, output_response = post(args.base_url, '/api/output', {
                        'session_ids': [session], 'chart_type': 'line', 'chart_mode': 'combined'})
                    record.update(output_http_status=status,
                                  series=output_response.get('outputSpec', {}).get('visualization', {}).get('series', []),
                                  period=output_response.get('period'))
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
                record.update(error=type(exc).__name__, error_detail=str(exc)[:300])
            record['execution_status'] = 'observed' if record.get('series') or record.get('decision') else 'error'
            observations.append(record)
    write_rows(output, observations)
    print(json.dumps({'cases': len(cases), 'attempts': len(observations), 'output': output,
                      'notice': 'model attribution is unverified; score with score.py and review with REVIEW.md'},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
