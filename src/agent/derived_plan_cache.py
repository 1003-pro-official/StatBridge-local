"""Bounded, account-scoped reuse of semantically approved API-only plans."""
import copy
import hashlib
import json
from collections import OrderedDict
from threading import RLock
from time import monotonic


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class VerifiedPlanCache:
    def __init__(self, ttl=300, capacity=64, clock=monotonic):
        self.ttl, self.capacity, self.clock = ttl, capacity, clock
        self.entries, self.lock = OrderedDict(), RLock()

    def get(self, key):
        with self.lock:
            entry = self.entries.get(key)
            if not entry:
                return None
            if self.clock() - entry['created'] >= self.ttl:
                self.entries.pop(key, None)
                return None
            self.entries.move_to_end(key)
            return copy.deepcopy(entry)

    def put(self, key, result, metadata_hash):
        with self.lock:
            self.entries[key] = {'created': self.clock(), 'result': copy.deepcopy(result),
                                 'metadata_hash': metadata_hash}
            self.entries.move_to_end(key)
            while len(self.entries) > self.capacity:
                self.entries.popitem(last=False)

    def discard(self, key):
        with self.lock:
            self.entries.pop(key, None)
