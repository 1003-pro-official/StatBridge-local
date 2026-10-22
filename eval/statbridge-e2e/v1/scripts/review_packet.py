"""Create blank human review rows for executed cases. Never overwrites an existing review file."""
from __future__ import annotations

import argparse
import sys

from e2e_common import BASE, read, review_packet, rows, write_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('predictions')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    from pathlib import Path
    if Path(args.output).exists():
        raise SystemExit('refusing to overwrite an existing review file')
    cases = {c['id']: c for c in rows(BASE / 'cases' / 'dev.jsonl') + rows(BASE / 'cases' / 'test.jsonl')}
    packets = []
    for prediction in rows(args.predictions):
        case = cases[prediction['id']]
        if not case['eligible_for_scoring']:
            continue
        packets.append(review_packet(case, prediction))
    write_rows(args.output, packets)
    print(f'review rows: {len(packets)}; author and reviewer must fill them by hand')


if __name__ == '__main__':
    main()
