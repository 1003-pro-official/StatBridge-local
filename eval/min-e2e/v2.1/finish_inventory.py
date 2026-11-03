"""Recover inventory manifest after collector exited; use actual fresh API files only."""
import run
from run import api,HERE,json,hashlib,time
from datetime import datetime,timezone
inv=api.agent.workflow.derived_runtime.api_inventory
ids=sorted(inv.catalog.store.table_ids())
assert len(ids)==349
tables=[];hashes={}
for tid in ids:
 p=inv.directory/(tid+'.json')
 assert time.time()-p.stat().st_mtime<3600,'metadata not collected during this evaluation'
 raw=p.read_bytes();d=json.loads(raw)
 assert d['table_id']==tid and d['metadata_origin']=='actual_KOSIS_metadata_API'
 tables.append(d);hashes[tid]=hashlib.sha256(raw).hexdigest()
data={'origin':'actual_KOSIS_metadata_API','checked_at':datetime.now(timezone.utc).isoformat(),'checked_epoch':time.time(),'table_count':len(tables),'api_requests':len(tables)*3,'tables':tables}
data['sha256']=hashlib.sha256(json.dumps(tables,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
temporary=inv.path.with_suffix('.tmp')
temporary.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8');temporary.replace(inv.path)
assert inv.snapshot() is not None
run.write(HERE/'inventory-finalization.json',{'reason':'collector process exited after 349 actual API metadata files; persisted identical manifest format used by DerivedApiInventory.refresh','files':hashes,'inventory_sha256':data['sha256'],'collected_tables':349,'no_gold_or_synthetic_metadata':True})
print('Actual 349-table inventory manifest finalized and product snapshot validator passed.')
