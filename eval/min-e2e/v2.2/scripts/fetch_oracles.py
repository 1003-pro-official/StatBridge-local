"""Read-only official KOSIS retrieval, separate from product execution. No keys persisted."""
import argparse,json,time,re,hashlib
from pathlib import Path
from datetime import datetime,timezone
import requests
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1]
def normalize_period(p,f):
    s=str(p)
    if f=='Y':return s[:4]
    if f=='Q':
        m=re.fullmatch(r'(\d{4})([1-4])/4',s)
        if m:return m[1]+'0'+m[2]
    return re.sub(r'[^0-9]','',s)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--env',required=True);args=parser.parse_args()
    key=dotenv_values(args.env).get('KOSIS_API_KEY');assert key,'KOSIS key not configured'
    specs=json.loads((ROOT/'oracle/da_sources.json').read_text(encoding='utf-8'))
    out=ROOT/'oracle/source_snapshots';out.mkdir(exist_ok=True)
    summary={}
    for cid,s in specs.items():
        path=out/(cid+'.json')
        if path.exists():
            d=json.loads(path.read_text(encoding='utf-8'))
            if d.get('status')=='fetched':summary[cid]={'status':'fetched','rows':len(d['rows'])};continue
        params={'method':'getList','format':'json','jsonVD':'Y','smblChk':'Y','orgId':'301','tblId':s['table_id'],'itmId':s['item_id'],'prdSe':s['frequency'],'startPrdDe':s['start_period'],'endPrdDe':s['end_period'],**s['classifications']}
        data={'source':s,'origin':'direct_official_KOSIS_API','endpoint':'https://kosis.kr/openapi/Param/statisticsParameterData.do','request_params_without_key':params,'checked_at':datetime.now(timezone.utc).isoformat(),'status':'unavailable','rows':[]}
        for attempt in range(3):
            try:
                resp=requests.get(data['endpoint'],params={**params,'apiKey':key},timeout=20);resp.raise_for_status();resp.encoding='utf-8'
                payload=json.loads(re.sub(r'\\(?!["\\/bfnrtu])',r'\\\\',resp.text))
                if not isinstance(payload,list) or not payload:
                    data['failure_kind']='provider_error' if isinstance(payload,dict) and 'err' in payload else 'empty_observations'
                    data['provider_error_code']=str(payload.get('err','')) if isinstance(payload,dict) else ''
                else:
                    rows=[]
                    for r in payload:
                        rows.append({'period':normalize_period(r['PRD_DE'],s['frequency']),'raw_period':r['PRD_DE'],'value':str(r['DT']),'unit':r.get('UNIT_NM'),'org_id':r.get('ORG_ID'),'table_id':r.get('TBL_ID'),'item_id':r.get('ITM_ID'),'frequency':r.get('PRD_SE'),'classifications':{k:r.get('C'+k[4:]) for k in s['classifications']},'source_last_changed':r.get('LST_CHN_DE')})
                    data.update(status='fetched',rows=rows,response=payload,response_sha256=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest())
                    break
            except Exception as exc:data['failure_kind']=type(exc).__name__
            time.sleep(1)
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        summary[cid]={'status':data['status'],'rows':len(data['rows']),'failure_kind':data.get('failure_kind')}
        print(cid,summary[cid],flush=True);time.sleep(0.6)
    (ROOT/'validation/source_fetch.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if all(v['status']=='fetched' for v in summary.values()) else 2
if __name__=='__main__':raise SystemExit(main())
