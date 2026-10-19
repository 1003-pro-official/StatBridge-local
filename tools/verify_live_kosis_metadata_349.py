"""ai-assisted: direct KOSIS TBL/ITM/PRD checks, never local metadata as proof."""
import argparse,hashlib,json,sys,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/backend'),str(ROOT/'src/agent'),str(ROOT/'tools')]
from dotenv import load_dotenv
load_dotenv(ROOT/'.env',override=False)
from statbridge_mcp.kosis_client import KosisClient,META_URL
from statbridge_mcp.metadata_store import MetadataStore
from run_derived_eval import dump

def main():
    p=argparse.ArgumentParser();p.add_argument('--resume',action='store_true');args=p.parse_args()
    store=MetadataStore();ids=sorted(store.table_ids());assert len(ids)==349
    client=KosisClient();folder=ROOT/'eval/derived_api_metadata_349_records';folder.mkdir(exist_ok=True)
    def one(tid):
        path=folder/(tid+'.json')
        if args.resume and path.exists():return json.loads(path.read_text(encoding='utf8'))
        record={'table_id':tid,'org_id':'301','origin':'actual_KOSIS_metadata_API','checked_at':datetime.now(timezone.utc).isoformat(),'types':{}}
        for kind in ['TBL','ITM','PRD']:
            tick=time.perf_counter()
            try:
                rows=client._get(META_URL,dict(method='getMeta',type=kind,apiKey=client.api_key,orgId='301',tblId=tid,format='json',jsonVD='Y',detail='N'))
                if not isinstance(rows,list) or not rows:raise ValueError('Empty or invalid metadata response')
                record['types'][kind]={'status':'PASS','rows':rows,'sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),'seconds':time.perf_counter()-tick}
            except Exception as exc:
                record['types'][kind]={'status':'FAIL','error_type':type(exc).__name__,'code':str(getattr(exc,'code','')),'seconds':time.perf_counter()-tick}
        itm=record['types']['ITM'];diff=[]
        if itm['status']=='PASS':
            actual={(str(r.get('OBJ_ID')),str(r.get('ITM_ID'))) for r in itm['rows']}
            local=store.get(tid).canonical_dict()
            for item in local['items']:
                if ('ITEM',str(item['item_id'])) not in actual:diff.append({'item_id':item['item_id']})
            for dimension in local['dimensions']:
                for value in dimension['values']:
                    if not any(i==str(value['class_id']) for _,i in actual):diff.append({'classification':value['class_id']})
        record['local_ids_not_in_live_response']=diff
        record['status']='PASS' if all(r['status']=='PASS' for r in record['types'].values()) and not diff else 'FAIL'
        dump(path,record);return record
    records=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(one,t) for t in ids]):
            row=future.result();records.append(row)
            if len(records)%25==0:print(json.dumps({'completed':len(records),'passed':sum(r['status']=='PASS' for r in records)}),flush=True)
    result={'origin':'actual_KOSIS_metadata_API','endpoint':META_URL,'api_key_recorded':False,'tables_requested':349,
            'summary':{'executed':len(records),'passed':sum(r['status']=='PASS' for r in records),'failed':sum(r['status']=='FAIL' for r in records),'unexecuted':349-len(records)},
            'api_request_summary':{'executed':sum(len(r['types']) for r in records),'passed':sum(t['status']=='PASS' for r in records for t in r['types'].values()),
                'failed':sum(t['status']!='PASS' for r in records for t in r['types'].values())},
            'tables_with_local_catalog_id_drift':[r['table_id'] for r in records if r['local_ids_not_in_live_response']],
            'records':sorted(records,key=lambda r:r['table_id'])}
    dump(ROOT/'eval/derived_api_metadata_349.json',result);print(json.dumps(result['summary']))

if __name__=='__main__':main()
