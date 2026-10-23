"""Run query_output cases through the v1 offline path and edit/follow-up through the same app.

derived/report need a model planner and stay not_executed here; run_model.py owns
the approved paid path. No expected or oracle value reaches the runner.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json

from e2e_common import BASE, CACHE, ROOT, rows, write, write_rows
from offline_app import offline_app

V1_SCRIPTS = ROOT / 'eval' / 'bok-reproduction' / 'v1' / 'scripts'


def v1_evaluate():
    spec = importlib.util.spec_from_file_location('v1_evaluate', V1_SCRIPTS / 'evaluate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_provider():
    path = CACHE / 'provider.json'
    if not path.is_file():
        raise SystemExit('run build_cases.py first: provider.json is missing')
    return path.read_text(encoding='utf-8')


def unique_calls(calls):
    seen, result = set(), []
    for call in calls:
        key = (call['table_id'], call['item_id'], json.dumps(call['classifications'], sort_keys=True), call['frequency'])
        if key not in seen:
            seen.add(key)
            result.append({'table_id': call['table_id'], 'item_id': call['item_id'],
                           'classifications': call['classifications'], 'frequency': call['frequency']})
    return result


def run_query_output(cases):
    import json as _json
    provider_file = CACHE / 'provider.json'
    standalone = [{'id': c['id'], 'input': copy.deepcopy(c['input'])} for c in cases]
    predictions = v1_evaluate().offline(standalone, provider_file)
    meta = {c['id']: c for c in cases}
    for prediction in predictions:
        prediction['mode'] = 'query_output'
        prediction['tier'] = meta[prediction['id']]['tier']
    return predictions


def post(client, trace, path, body):
    response = client.post(path, json=body)
    value = response.json()
    trace.append({'stage': path, 'http_status': response.status_code, 'response': value})
    response.raise_for_status()
    return value


def drive(client, query, actions, trace):
    """Run one query and return the output session response."""
    response = post(client, trace, '/api/query', {'query': query, 'execute': True})
    for action in actions:
        if action['kind'] == 'confirm_period' and response.get('status') in ('need_period',):
            response = post(client, trace, '/api/query', {
                'query': query, 'state': response.get('state'), 'execute': True,
                'period_start': action['start'], 'period_end': action['end']})
    session = response.get('outputSessionId')
    if not session:
        return None, response
    output = post(client, trace, '/api/output', {'session_ids': [session], 'chart_type': 'line', 'chart_mode': 'combined'})
    return output, response


def run_edit(cases, base_cases):
    predictions = []
    with offline_app(json.loads(load_provider())['series']) as (client, provider, api):
        for case in cases:
            base = base_cases[case['input']['base_case_id']]
            api.OUTPUT_SESSIONS.clear()
            api.EDIT_SESSIONS.clear()
            provider.calls.clear()
            trace = []
            prediction = {'id': case['id'], 'mode': 'edit', 'tier': case['tier']}
            try:
                output, query_response = drive(client, base['input']['query'], base['input'].get('actions', []), trace)
                if output is None:
                    raise ValueError('base query issued no output session: ' + str(query_response.get('status')))
                session = output['editSessionId']
                state = output['outputSpec']['chartState']
                operation = case['expected']['operation']
                command = command_for(operation, case, state, base['expected']['series'][0]['frequency'])
                edited = post(client, trace, '/api/output/edit', {
                    'edit_session_id': session, 'revision': output['outputSpec'].get('editVersion', 0),
                    'commands': [command]})
                spec = edited['outputSpec']
                prediction.update(execution_status='observed', decision='resolved',
                                  chart_state=spec['chartState'],
                                  point_counts=[len(item['points']) for item in spec['visualization']['series']],
                                  statistics_requests=unique_calls(provider.calls))
            except Exception as exc:  # per-case error isolation
                prediction.update(execution_status='error', error=str(exc), error_type=type(exc).__name__,
                                  statistics_requests=unique_calls(provider.calls))
            prediction['trace'] = trace
            predictions.append(prediction)
    return predictions


def api_period(value, frequency):
    if frequency == 'Q':
        return value[:4] + '0' + value[-1]
    return value


def command_for(operation, case, state, frequency):
    if operation == 'set_title':
        return {'operation': 'set_title', 'kind': 'STYLE_EDIT', 'value': case['expected']['expected_state']['title']}
    if operation == 'set_legend':
        return {'operation': 'set_legend', 'kind': 'STYLE_EDIT', 'value': case['expected']['expected_state']['legend']}
    if operation == 'set_transform':
        return {'operation': 'set_transform', 'kind': 'DATA_EDIT', 'value': case['expected']['expected_state']['transform']}
    if operation == 'filter_period':
        periods = case['expected']['periods'][-case['expected']['expected_state']['recent']:]
        return {'operation': 'filter_period', 'kind': 'DATA_EDIT',
                'start': api_period(periods[0], frequency), 'end': api_period(periods[-1], frequency)}
    raise ValueError('unknown edit operation')


def run_follow_up(cases, base_cases):
    predictions = []
    with offline_app(json.loads(load_provider())['series']) as (client, provider, api):
        for case in cases:
            base = base_cases[case['input']['base_case_id']]
            api.OUTPUT_SESSIONS.clear()
            api.EDIT_SESSIONS.clear()
            provider.calls.clear()
            trace = []
            prediction = {'id': case['id'], 'mode': 'follow_up', 'tier': case['tier']}
            try:
                first = post(client, trace, '/api/query', {'query': base['input']['query'], 'execute': True})
                for action in base['input'].get('actions', []):
                    if action['kind'] == 'confirm_period' and first.get('status') == 'need_period':
                        first = post(client, trace, '/api/query', {
                            'query': base['input']['query'], 'state': first.get('state'), 'execute': True,
                            'period_start': action['start'], 'period_end': action['end']})
                second = post(client, trace, '/api/query', {
                    'query': case['input']['query'], 'state': first.get('state'), 'execute': True})
                for action in case['input'].get('actions', []):
                    if action['kind'] == 'confirm_period' and second.get('status') == 'need_period':
                        second = post(client, trace, '/api/query', {
                            'query': case['input']['query'], 'state': second.get('state'), 'execute': True,
                            'period_start': action['start'], 'period_end': action['end']})
                session = second.get('outputSessionId')
                if not session:
                    raise ValueError('follow-up issued no output session: ' + str(second.get('status')))
                output = post(client, trace, '/api/output', {'session_ids': [session], 'chart_type': 'line', 'chart_mode': 'combined'})
                prediction.update(execution_status='observed', decision='resolved',
                                  period=output.get('period'), frequency=output.get('frequency'),
                                  point_counts=[len(item['points']) for item in output['outputSpec']['visualization']['series']],
                                  statistics_requests=unique_calls(provider.calls))
            except Exception as exc:
                prediction.update(execution_status='error', error=str(exc), error_type=type(exc).__name__,
                                  statistics_requests=unique_calls(provider.calls))
            prediction['trace'] = trace
            predictions.append(prediction)
    return predictions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--mode', default='all', choices=['all', 'query_output', 'edit', 'follow_up'])
    args = parser.parse_args()
    cases = rows(BASE / 'cases' / 'dev.jsonl') + rows(BASE / 'cases' / 'test.jsonl')
    base_cases = {c['id']: c for c in cases}
    selected = [c for c in cases if c['mode'] in ('query_output', 'edit', 'follow_up') and c['eligible_for_scoring']]
    if args.mode != 'all':
        selected = [c for c in selected if c['mode'] == args.mode]
    predictions = []
    for mode in ('query_output', 'edit', 'follow_up'):
        group = [c for c in selected if c['mode'] == mode]
        if not group:
            continue
        if mode == 'query_output':
            predictions.extend(run_query_output(group))
        elif mode == 'edit':
            predictions.extend(run_edit(group, base_cases))
        else:
            predictions.extend(run_follow_up(group, base_cases))
    write_rows(args.output, predictions)
    print(json.dumps({'executed': len(predictions), 'output': str(args.output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
