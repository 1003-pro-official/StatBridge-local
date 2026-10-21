"""Independent evaluation contracts; never imports the application's calculator."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import statistics
from decimal import Decimal, InvalidOperation
from pathlib import Path

BASE = Path(__file__).absolute().parents[1]
ROOT = BASE.parents[2]
RUBRIC = ('facts', 'completeness', 'clarity', 'source_limits', 'visual', 'conversation_recovery')


def read(path):
    def reject(value):
        raise ValueError('non-finite JSON: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8'), parse_constant=reject)


def rows(path):
    return [read_json_line(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def read_json_line(line):
    def reject(value):
        raise ValueError('non-finite JSON: '+value)
    return json.loads(line,parse_constant=reject)


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_rows(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(v, ensure_ascii=False, allow_nan=False) + '\n' for v in values), encoding='utf-8')


def digest_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest_value(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def number(value):
    if isinstance(value, bool):
        raise ValueError('boolean is not an observation')
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('invalid observation') from exc
    if not result.is_finite():
        raise ValueError('non-finite observation')
    return result


def period(value, frequency):
    value = str(value)
    if frequency in ('Y', 'A') and len(value) == 4 and value.isdigit():
        return value
    if frequency == 'Q':
        if len(value) == 6 and value.isdigit() and 1 <= int(value[4:]) <= 4:
            return value[:4] + 'Q' + str(int(value[4:]))
        if len(value) == 6 and value[4] == 'Q' and value[5] in '1234' and value[:4].isdigit():
            return value
    if frequency == 'M' and len(value) == 6 and value.isdigit() and 1 <= int(value[4:]) <= 12:
        return value
    raise ValueError('invalid or unsupported period/frequency')


def previous(value, frequency, year=False):
    value = period(value, frequency)
    if year or frequency in ('Y', 'A'):
        return str(int(value[:4]) - 1) + value[4:]
    if frequency == 'M':
        y, m = divmod(int(value[:4]) * 12 + int(value[4:]) - 2, 12)
        return f'{y:04d}{m+1:02d}'
    q = int(value[-1])
    return f'{int(value[:4]) - (q == 1):04d}Q{4 if q == 1 else q-1}'


def calculate(points, operation, frequency, factor='1'):
    if operation not in ('level', 'scale', 'difference', 'yoy', 'growth'):
        raise ValueError('unsupported operation')
    data = {period(p, frequency): None if v is None else number(v) for p, v in points.items()}
    result = {}
    for p, value in sorted(data.items()):
        base = data.get(previous(p, frequency, operation == 'yoy'))
        if value is None:
            answer = None
        elif operation == 'level':
            answer = value
        elif operation == 'scale':
            answer = value * number(factor)
        elif base is None or (operation in ('yoy', 'growth') and base == 0):
            answer = None
        elif operation == 'difference':
            answer = value - base
        else:
            answer = (value / base - 1) * 100
        result[p] = str(answer) if answer is not None else None
    return result


def identity(series):
    return (series['table_id'], series['item_id'], json.dumps(series['classifications'], sort_keys=True), series['frequency'])


class FrozenProvider:
    """Only actual requested identities select data; no case/gold argument exists."""
    def __init__(self, series):
        self.series, self.calls, self.plans = copy.deepcopy(series), [], []
        self.index = {}
        for s in self.series:
            key = identity(s)
            if key in self.index:
                raise ValueError('duplicate source identity; resolve vintage explicitly')
            mapped = {}
            for point in s['points']:
                p = period(point['period'], s['frequency'])
                if p in mapped:
                    raise ValueError('duplicate source period')
                mapped[p] = None if point['value'] is None else str(number(point['value']))
            self.index[key] = (s, mapped)

    def get_statistics(self, table_id, item_id='ALL', classifications=None, frequency=None,
                       start_period=None, end_period=None, **kwargs):
        call = dict(provider='kosis',table_id=table_id, item_id=item_id, classifications=classifications or {}, frequency=frequency,
                    start_period=start_period, end_period=end_period)
        self.calls.append(copy.deepcopy(call))
        key = identity(call)
        if key not in self.index:
            raise ValueError('unregistered request; no answer substitution')
        s, data = self.index[key]
        start = period(start_period, frequency) if start_period else min(data)
        end = period(end_period, frequency) if end_period else max(data)
        points = [(p, v) for p, v in sorted(data.items()) if start <= p <= end]
        if not points:
            raise ValueError('requested source period unavailable')
        output = []
        for p, v in points:
            row = dict(TBL_ID=table_id, ITM_ID=item_id, PRD_DE=p.replace('Q', '0'), PRD_SE=frequency,
                       DT=v, UNIT_NM=s['unit'], C1_NM=s['label'], _SERIES_LABEL=s['label'],
                       _FREQUENCY=frequency, _SOURCE_SERIES_ID=table_id)
            for axis, code in s['classifications'].items():
                row['C' + axis.removeprefix('objL')] = code
            output.append(row)
        return dict(status='success', source='offline_fixture', rows=output, row_count=len(output), used_params=call)


def compare_series(expected, observed, tolerance='0.000001'):
    report = dict(passed=False, matched_cells=0, expected_cells=sum(len(s['points']) for s in expected), reasons=[])
    try:
        def indexed(series):
            result = {}
            for s in series:
                key = identity(s)
                if key in result:
                    raise ValueError('duplicate series')
                points = {}
                for point in s['points']:
                    p = period(point['period'], s['frequency'])
                    if p in points:
                        raise ValueError('duplicate period')
                    points[p] = None if point['value'] is None else number(point['value'])
                result[key] = (s['unit'], points)
            return result
        gold, actual = indexed(expected), indexed(observed)
        if not gold or gold.keys() != actual.keys():
            raise ValueError('empty/missing/extra series')
        for key, (unit, points) in gold.items():
            actual_unit, actual_points = actual[key]
            if not unit or unit != actual_unit or not points or points.keys() != actual_points.keys():
                raise ValueError('unit or period mismatch')
            for p, value in points.items():
                got = actual_points[p]
                if (value is None and got is None) or (value is not None and got is not None and abs(value-got) <= number(tolerance)):
                    report['matched_cells'] += 1
                else:
                    report['reasons'].append('numeric_mismatch')
        report['passed'] = not report['reasons'] and report['expected_cells'] > 0
    except (ValueError, KeyError, TypeError) as exc:
        report['reasons'].append(str(exc))
    return report


def figure_consistent(prediction):
    """Compare rendered line traces to actually observed visualization data."""
    figure=prediction.get('plotly_figure') or {}
    traces=[t for t in figure.get('data',[]) if t.get('showlegend',True) and t.get('name') in {s['label'] for s in prediction.get('series',[])}]
    series=prediction.get('series',[])
    if not series or len(traces)!=len(series):
        return False
    for s in series:
        matching=[t for t in traces if t.get('name')==s['label']]
        if len(matching)!=1:
            return False
        trace=matching[0]
        if trace.get('type','scatter')!='scatter' or 'lines' not in trace.get('mode','lines'):
            return False
        def chart_period(value):
            value=str(value).replace('-','')
            if s['frequency']=='M':
                value=value[:6]
            return period(value,s['frequency'])
        try:
            xs=[chart_period(x) for x in trace.get('x',[])]
            expected_x=[period(p['period'],s['frequency']) for p in s['points']]
            ys=trace.get('y',[])
            if xs!=expected_x or len(ys)!=len(s['points']):
                return False
            for value,p in zip(ys,s['points']):
                if value is None or p['value'] is None:
                    if value is not None or p['value'] is not None:
                        return False
                elif abs(number(value)-number(p['value']))>number('0.000001'):
                    return False
        except (ValueError,TypeError):
            return False
    return True


def review_packet(case, prediction):
    return dict(id=case['id'], group_id=case['group_id'], input_sha256=digest_value(case['input']),
                expected_sha256=digest_value(case['expected']), prediction_sha256=digest_value(prediction),
                reviewer=None, human_approved=False, scores={k: None for k in RUBRIC},
                not_applicable=sorted(set(RUBRIC)-set(case.get('qualitative_applicable',RUBRIC))),
                evidence_notes={}, critical_error=None, second_review=None)


def review_valid(case, prediction, review):
    if not review or review.get('human_approved') is not True or not str(review.get('reviewer') or '').strip():
        return False
    expected = review_packet(case, prediction)
    if any(review.get(k) != expected[k] for k in ('id', 'input_sha256', 'expected_sha256', 'prediction_sha256')):
        return False
    scores = review.get('scores', {})
    na = review.get('not_applicable', [])
    allowed_na=set(RUBRIC)-set(case.get('qualitative_applicable',RUBRIC))
    if set(scores) != set(RUBRIC) or set(na)!=allowed_na or type(review.get('critical_error')) is not bool:
        return False
    notes=review.get('evidence_notes',{})
    return 'facts' not in na and all((scores[k] is None if k in na else type(scores[k]) is int and scores[k] in (0, 1, 2)
                                    and isinstance(notes.get(k),str) and bool(notes[k].strip())) for k in RUBRIC)


def gold_approved(case):
    review=case.get('review',{})
    return (review.get('human_approved') is True and bool(str(review.get('reviewer') or '').strip())
            and review.get('input_sha256')==digest_value(case['input'])
            and review.get('expected_sha256')==digest_value(case['expected']))


def score_case(case, prediction, expected_series=None, review=None):
    if prediction is None:
        return dict(id=case['id'], status='not_executed', quantitative_pass=False)
    if prediction.get('execution_status') != 'observed':
        return dict(id=case['id'], status=prediction.get('execution_status', 'unobserved'), quantitative_pass=False)
    if prediction.get('input_sha256') != digest_value(case['input']):
        return dict(id=case['id'], status='stale_input', quantitative_pass=False)
    gold = case['expected']
    if gold.get('source_snapshot_sha256') and prediction.get('provider_sha256')!=gold['source_snapshot_sha256']:
        return dict(id=case['id'],status='source_vintage_mismatch',quantitative_pass=False)
    if isinstance(expected_series,dict):
        def output_series(points, unit, frequency):
            return [dict(table_id='calculated',item_id='result',classifications={},unit=unit,frequency=frequency,points=points)]
        expected_output=output_series(expected_series['points'],expected_series['unit'],expected_series['frequency'])
        observed_output=output_series(prediction.get('calculated_points',[]),prediction.get('output_unit'),prediction.get('output_frequency'))
        numeric=compare_series(expected_output,observed_output,gold.get('tolerance','0.000001'))
        try:
            source_match={identity(s) for s in expected_series['sources']}=={identity(s) for s in prediction.get('statistics_requests',[])}
        except (KeyError,TypeError):
            source_match=False
        numeric['passed']=numeric['passed'] and source_match
        if not source_match:
            numeric['reasons'].append('calculation source identities mismatch')
    else:
        numeric = compare_series(expected_series or gold.get('series', []), prediction.get('series', []), gold.get('tolerance', '0.000001'))
    passed = prediction.get('decision') == gold.get('decision')
    if gold.get('requires_numeric', True):
        passed = passed and numeric['passed']
    if gold.get('chart_kind')=='line':
        passed = passed and figure_consistent(prediction)
    observed_contract=prediction.get('observed_contract',prediction)
    for k, v in gold.get('observed_contract', {}).items():
        passed = passed and isinstance(observed_contract,dict) and observed_contract.get(k) == v
    if not gold.get('requires_numeric', True) and not gold.get('observed_contract'):
        passed = False
    valid = review_valid(case, prediction, review)
    approved = gold_approved(case)
    status = 'failed' if not passed else 'passed' if valid and approved else 'pending_review'
    return dict(id=case['id'], status=status, quantitative_pass=bool(passed), numeric=numeric,
                qualitative_scores=review['scores'] if valid else None)


def summary(cases, predictions, scores):
    times = sorted(float(p['elapsed_ms']) for p in predictions if p.get('execution_status') != 'not_executed' and p.get('elapsed_ms') is not None)
    attempts=[p for p in predictions if p.get('execution_status')!='not_executed']
    def measured_total(key, parent=None):
        values=[(p.get(parent) or {}).get(key) if parent else p.get(key) for p in attempts]
        if not values or any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
            return None
        return sum(values)
    cost=measured_total('cost') if all(p.get('cost_currency')=='USD' for p in attempts) else None
    quantitative_success=sum(s['quantitative_pass'] for s in scores)
    return dict(cases=len(cases), observed=sum(p.get('execution_status')=='observed' for p in predictions),
                attempted=len(attempts),passed=sum(s['status']=='passed' for s in scores),
                quantitative_pass=sum(s['quantitative_pass'] for s in scores),
                pending_review=sum(s['status']=='pending_review' for s in scores),
                not_executed=sum(s['status']=='not_executed' for s in scores),
                median_ms=statistics.median(times) if times else None,
                first_attempt_success=sum(p['first_attempt_success'] is True for p in attempts) if attempts and all('first_attempt_success' in p for p in attempts) else None,
                user_confirmation_count=measured_total('user_confirmation_count'),
                model_retry_count=measured_total('model_retry_count'),fallback_count=measured_total('fallback_count'),
                input_tokens=measured_total('input_tokens','usage'),output_tokens=measured_total('output_tokens','usage'),
                total_cost_usd=cost,cost_per_quantitative_success_usd=cost/quantitative_success if cost is not None and quantitative_success else None,
                p95_ms=times[max(0, math.ceil(len(times)*.95)-1)] if len(times)>=20 else None,
                p95_note='not reported with fewer than 20 observations',
                official_performance=False, blind_performance=False)
