"""ai-assisted: complete live KOSIS metadata inventory, separate from local search."""
import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path


class DerivedApiInventory:
    TTL = 86400

    def __init__(self, catalog, directory):
        self.catalog = catalog
        self.directory = Path(directory)
        self.path = self.directory / 'inventory.json'
        self.lock = threading.Lock()
        self.running = False
        self.progress = 0
        self.error = None

    def snapshot(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf8'))
            ids = set(self.catalog.store.table_ids())
            if (data['origin'] == 'actual_KOSIS_metadata_API' and
                    0 <= time.time() - data['checked_epoch'] < self.TTL and
                    {m['table_id'] for m in data['tables']} == ids and
                    len(data['tables']) == len(ids) and
                    all(m.get('metadata_origin') == data['origin'] for m in data['tables']) and
                    data.get('sha256') == hashlib.sha256(json.dumps(data['tables'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()):
                return data
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return None

    def ensure(self):
        data = self.snapshot()
        if data:
            return data
        with self.lock:
            if not self.running:
                self.running = True
                threading.Thread(target=self.refresh, daemon=True).start()
        return None

    def refresh(self):
        """A single refresh owner; persist each actual response for inspection."""
        from live_derived_catalog import LiveDerivedCatalog
        from statbridge_mcp.kosis_client import KosisClient
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            ids = sorted(self.catalog.store.table_ids())
            self.progress = 0
            # Independent catalog locks, shared client limiter: bounded parallel IO.
            client = KosisClient()
            def one(tid):
                meta = LiveDerivedCatalog(self.catalog.store, client).get_table_metadata(tid)
                (self.directory / (tid + '.json')).write_text(json.dumps(meta, ensure_ascii=False), encoding='utf8')
                with self.lock:
                    self.progress += 1
                return meta
            with ThreadPoolExecutor(max_workers=3) as pool:
                tables = list(pool.map(one, ids))
            data = {'origin':'actual_KOSIS_metadata_API', 'checked_at':datetime.now(timezone.utc).isoformat(),
                    'checked_epoch':time.time(), 'table_count':len(tables), 'api_requests':len(tables)*3,
                    'tables':tables}
            data['sha256'] = hashlib.sha256(json.dumps(tables,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
            temporary.replace(self.path)
            self.error = None
        except Exception as exc:
            # Never persist request URLs/credentials or turn API failure into absence.
            self.error = type(exc).__name__
        finally:
            with self.lock:
                self.running = False
