"""Refresh approved-table metadata directly through KOSIS TBL/ITM/PRD APIs."""
import json, sys, threading, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/backend'),str(ROOT/'src/agent')]
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
from statbridge_mcp.metadata_store import MetadataStore
from statbridge_mcp.kosis_client import KosisClient
from live_derived_catalog import LiveDerivedCatalog
from derived_api_inventory import DerivedApiInventory

if __name__=='__main__':
    inventory=DerivedApiInventory(LiveDerivedCatalog(MetadataStore(),KosisClient()),ROOT/'runtime_data/derived_api_inventory')
    inventory.running=True
    thread=threading.Thread(target=inventory.refresh)
    thread.start()
    while thread.is_alive():
        thread.join(15)
        print(json.dumps({'completed':inventory.progress,'total':349,'origin':'actual_KOSIS_metadata_API'}),flush=True)
    result=inventory.snapshot()
    print(json.dumps({'status':'PASS' if result else 'FAIL','tables':result['table_count'] if result else 0,'error':inventory.error}),flush=True)
    sys.exit(0 if result else 1)
