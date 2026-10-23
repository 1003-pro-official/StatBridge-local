"""Quantitative scoring plus the qualitative gate. Never sums the two axes."""
from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation

from e2e_common import BASE, CACHE, RUBRIC, read, review_packet, review_valid, write, rows

TOLERANCE = Decimal('0.000001')


def norm(value, frequency):
    text = str(value).strip().upper().replace('-', '').replace('.', '').replace(' ', '')
    if frequency == 'A':
        return text[:4]
    if frequency == 'Q':
        return text[:4] + 'Q' + text[-1] if text[-1] in '1234' else text
    return text[:6]


def identity(series):
    return (series.get('table_id'), series.get('item_id'),
            json.dumps(series.get('classifications') or {}, sort_keys=True))


def index_series(series, frequency):
    result = {}
    for item in series or []:
        key = identity(item)
        if key in result:
            raise ValueError('duplicate observed series')
        points = {}
        for point in item.get('points', []):
            period = norm(point['period'], frequency)
            if period in points:
                raise ValueError('duplicate observed period')
            points[period] = None if point.get('value') is None else Decimal(str(point['value']))
        result[key] = points
    return result


def compare(case, prediction, oracle):
    reasons = []
    frequency = (case['expected'].get('series') or [{}])[0].get('frequency') or next(
        (t for t in read(BASE / 'inventory.json')['types'] if t['type_id'] == case['group_id']), {}).get('frequency')
    expected_periods = {norm(p, frequency) for p in case['expected']['periods']}
    observed = index_series(prediction.get('series'), frequency)
    if not observed:
        raise ValueError('no observed series')
    wanted = {identity(s) for s in case['expected']['series']}
    if set(observed) != wanted:
        reasons.append('series set mismatch')
    for key, points in observed.items():
        if set(points) != expected_periods:
            reasons.append('period set mismatch')
            break
    numeric = bool(case['expected'].get('oracle_sha256'))
    if numeric:
        if not oracle:
            reasons.append('oracle missing')
        else:
            gold = index_series(oracle['series'], frequency)
            if set(gold) != set(observed):
                reasons.append('oracle series mismatch')
            for key, points in gold.items():
                if key not in observed:
                    continue
                for period, value in points.items():
                    got = observed[key].get(period)
                    if (value is None) != (got is None):
                        reasons.append('null mismatch')
                        break
                    if value is not None and abs(value - got) > TOLERANCE:
                        reasons.append('numeric mismatch')
                        break
    return reasons


def compare_edit(case, prediction):
    reasons = []
    wanted = case['expected']['expected_state']
    state = prediction.get('chart_state') or {}
    if 'title' in wanted and state.get('title') != wanted['title']:
        reasons.append('title mismatch')
    if 'legend' in wanted and state.get('show_legend') != wanted['legend']:
        reasons.append('legend mismatch')
    if 'transform' in wanted and state.get('transform') != wanted['transform']:
        reasons.append('transform mismatch')
    if 'recent' in wanted:
        counts = prediction.get('point_counts') or []
        available = len(case['expected'].get('periods') or [])
        if not counts or max(counts) != min(wanted['recent'], available):
            reasons.append('period window mismatch')
    return reasons


def compare_follow_up(case, prediction):
    reasons = []
    wanted = {identity(series) for series in case['expected']['series']}
    got = {identity(call) for call in prediction.get('statistics_requests', [])}
    if got != wanted:
        reasons.append('series set mismatch')
    periods = case['expected']['periods']
    window = prediction.get('period') or {}
    frequency = case['expected']['series'][0]['frequency']
    start, end = norm(window.get('start'), frequency), norm(window.get('end'), frequency)
    if start != norm(periods[0], frequency) or end != norm(periods[-1], frequency):
        reasons.append('period range mismatch')
    return reasons


def score_case(case, prediction, oracle, review):
    if not case['eligible_for_scoring']:
        return {'id': case['id'], 'mode': case['mode'], 'tier': case['tier'], 'status': 'excluded',
                'reasons': ['tier C probe is not a gold answer']}
    if prediction is None:
        return {'id': case['id'], 'mode': case['mode'], 'tier': case['tier'], 'status': 'not_executed',
                'reasons': ['mode requires a runtime adapter that is not part of this package']}
    if prediction.get('execution_status') != 'observed':
        return {'id': case['id'], 'mode': case['mode'], 'tier': case['tier'], 'status': 'unobserved',
                'reasons': [prediction.get('error') or prediction.get('execution_status') or 'unobserved']}
    reasons = []
    decision = prediction.get('decision')
    if decision != case['expected']['decision']:
        reasons.append(f'decision {decision}')
    try:
        if case['mode'] == 'edit':
            reasons.extend(compare_edit(case, prediction))
        elif case['mode'] == 'follow_up':
            reasons.extend(compare_follow_up(case, prediction))
        else:
            reasons.extend(compare(case, prediction, oracle))
    except (ValueError, KeyError, TypeError, InvalidOperation) as exc:
        reasons.append(str(exc))
    quantitative = not reasons
    reviewed = review_valid(case, prediction, review) if review else False
    if not quantitative:
        status = 'failed'
    elif reviewed:
        status = 'passed'
    else:
        status = 'pending_review'
    return {'id': case['id'], 'mode': case['mode'], 'tier': case['tier'], 'status': status,
            'reasons': reasons,
            'qualitative_scores': review.get('scores') if reviewed else None,
            'input_sha256': review_packet(case, prediction)['input_sha256'],
            'expected_sha256': review_packet(case, prediction)['expected_sha256']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('predictions')
    parser.add_argument('--output', required=True)
    parser.add_argument('--reviews')
    args = parser.parse_args()
    cases = rows(BASE / 'cases' / 'dev.jsonl') + rows(BASE / 'cases' / 'test.jsonl')
    predictions = {p['id']: p for p in rows(args.predictions)}
    oracles = read(CACHE / 'oracles.json')['cases'] if (CACHE / 'oracles.json').is_file() else {}
    reviews = {r['id']: r for r in rows(args.reviews)} if args.reviews else {}
    scores = [score_case(c, predictions.get(c['id']), oracles.get(c['id']), reviews.get(c['id'])) for c in cases]
    summary = {'total_cases': len(scores), 'scored': sum(s['status'] not in ('excluded', 'not_executed') for s in scores),
               'by_status': {}, 'by_mode': {}, 'quantitative': sum(s['status'] in ('passed', 'pending_review') for s in scores),
               'qualitative_reviewed': sum(s.get('qualitative_scores') is not None for s in scores)}
    for score in scores:
        summary['by_status'][score['status']] = summary['by_status'].get(score['status'], 0) + 1
        summary['by_mode'].setdefault(score['mode'], {}).setdefault(score['status'], 0)
        summary['by_mode'][score['mode']][score['status']] += 1
    qualitative = {name: {'n': len(values), 'mean': round(sum(values) / len(values), 3)}
                   for name in RUBRIC
                   if (values := [s['qualitative_scores'][name] for s in scores
                                  if s.get('qualitative_scores') and s['qualitative_scores'].get(name) is not None])}
    report = {'summary': summary, 'qualitative': qualitative, 'cases': scores,
              'note': 'quantitative and qualitative axes are reported separately; no combined score exists'}
    write(args.output, report)
    print(json.dumps({'summary': summary, 'qualitative': qualitative}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
