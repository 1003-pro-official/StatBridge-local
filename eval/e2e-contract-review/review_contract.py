"""Post-execution contract checks; no datasets, answers, or runtime imports.

These checks do not approve qualitative reviews or silently replace oracles.
The caller must record any corrected oracle separately from the original.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
import re


def frequency(value):
    return {'A': 'Y', 'H': 'S'}.get(value, value)


def period(value, freq):
    freq = frequency(freq)
    text = str(value)
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', text) or re.fullmatch(r'\d{8}', text):
        day = date.fromisoformat(text if '-' in text else f'{text[:4]}-{text[4:6]}-{text[6:]}')
        if freq == 'Y': return str(day.year)
        if freq == 'Q': return f'{day.year}Q{(day.month-1)//3+1}'
        if freq == 'S': return f'{day.year}S{(day.month-1)//6+1}'
        return day.strftime('%Y%m%d' if freq == 'D' else '%Y%m')
    text = text.replace('-', '').upper()
    if freq == 'Y' and re.fullmatch(r'\d{4}', text): return text
    if freq == 'M' and re.fullmatch(r'\d{6}', text) and 1 <= int(text[4:]) <= 12: return text
    if freq in ('Q', 'S'):
        match = re.fullmatch(r'(\d{4})(?:' + freq + r'|0)([1-' + ('4' if freq == 'Q' else '2') + r'])', text)
        if match: return match[1] + freq + match[2]
    raise ValueError(f'invalid {freq} period: {value}')


def identity(source):
    return (source['table_id'], source['item_id'],
            tuple(sorted(source['classifications'].items())), frequency(source['frequency']))


def decimal(value):
    number = Decimal(str(value))
    if not number.is_finite(): raise ValueError('nonfinite value')
    return number


def points(rows, freq):
    result = {}
    for row in rows:
        key = period(row['period'], freq)
        if key in result: raise ValueError('duplicate period')
        result[key] = None if row['value'] is None else decimal(row['value'])
    return result


def review_derived(prediction, expected, oracle, tolerance='0.000001'):
    """Check output values plus receipt-defined missing history, never fill values."""
    if prediction.get('decision') != 'resolved':
        return {'status': 'blocked', 'reasons': ['source or calculation not resolved']}
    try:
        evidence = prediction['response']['derivedEvidence']
        plan = evidence['plan']
        freq = plan['sources'][0]['frequency']
        reasons = []
        if {identity(s) for s in plan['sources']} != {identity(s) for s in expected['sources']}:
            reasons.append('source identity mismatch')
        expected_op = {'difference':'subtract', 'growth':'pct_change', 'yoy':'yoy_pct'}[expected['operation']]
        output = plan['outputs'][0]['node']
        node = next(n for n in plan['nodes'] if n['id'] == output)
        if len(plan['outputs']) != 1 or node['operator'] != expected_op:
            reasons.append('operation or output count mismatch')
        aliases = {s['alias']: s for s in plan['sources']}
        if [identity(aliases[a]) for a in node['inputs']] != [identity(s) for s in expected['sources']]:
            reasons.append('operand order mismatch')
        if expected_op == 'pct_change' and node.get('lag') not in (None, 1):
            reasons.append('growth lag mismatch')
        if len(prediction['series']) != 1: raise ValueError('unexpected series count')
        if expected_op in ('pct_change', 'yoy_pct') and prediction['series'][0].get('unit') != '%':
            reasons.append('output unit mismatch')
        if expected_op == 'subtract':
            source_units = {s.get('unit') for s in oracle.get('sources', [])}
            if source_units == {'%'} and prediction['series'][0].get('unit') != '%p':
                reasons.append('spread must use percentage points')
        observed = points(prediction['series'][0]['points'], freq)
        gold = points(oracle['points'], freq)
        required = {period(v, freq) for v in expected['periods']}
        missing = {period(i['period'], freq) for i in evidence.get('issues', [])
                   if i['node'] == output and i['reason'] == 'missing_input_or_history'}
        if set(gold) != required or set(observed) - required:
            reasons.append('period set mismatch')
        for key, want in gold.items():
            got = observed.get(key)
            if want is None:
                if got is not None or key not in missing: reasons.append('null evidence mismatch')
            elif got is None or abs(want-got) > decimal(tolerance):
                reasons.append('numeric mismatch')
        return {'status':'failed' if reasons else 'pending_review', 'reasons':sorted(set(reasons))}
    except (KeyError, ValueError, TypeError, StopIteration, InvalidOperation) as exc:
        return {'status':'failed', 'reasons':[str(exc)]}


def subtract_sources(left, right, freq):
    """Proposed two-source oracle, invoked only by a separate review step."""
    a, b = points(left, freq), points(right, freq)
    if a.keys() != b.keys(): raise ValueError('source period mismatch')
    return [{'period': key, 'value': None if a[key] is None or b[key] is None else str(a[key]-b[key])}
            for key in sorted(a)]
