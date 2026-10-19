"""Immutable per-calculation evidence; only explicitly selected safe fields."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class DerivedIndicatorEvidence:
    def __init__(self, directory):
        self.directory = Path(directory)

    def save(self, record):
        content = json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False, default=str)
        if len(content.encode()) > 64000000:
            raise ValueError('계산 근거 저장 용량 한도를 초과했습니다.')
        digest = hashlib.sha256(content.encode()).hexdigest()
        calculation_id = uuid4().hex
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = {'calculation_id': calculation_id, 'created_at': datetime.now(timezone.utc).isoformat(),
                   'sha256': digest, 'evidence': record}
        path = self.directory / f'{calculation_id}.json'
        # Exclusive create; no previous evidence is replaced.
        with path.open('x', encoding='utf-8') as target:
            json.dump(payload, target, ensure_ascii=False, allow_nan=False, default=str)
            target.flush()
            os.fsync(target.fileno())
        return {'calculationId': calculation_id, 'sha256': digest}
