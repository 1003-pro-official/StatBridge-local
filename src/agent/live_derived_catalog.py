"""API-backed selection metadata. Local registry supplies allowlist/search only."""
import hashlib,json,time
from threading import RLock
from derived_catalog_tools import DerivedCatalogTools
from expression_tree_validator import DerivedValidationError
from statbridge_mcp.kosis_client import META_URL
from statbridge_mcp.metadata_store import normalize_frequency,normalize_period

class LiveDerivedCatalog(DerivedCatalogTools):
    def __init__(self,store,client):
        super().__init__(store);self.client=client;self.cache={};self.lock=RLock()

    def get_table_metadata(self,table_id):
        super().get_table_metadata(table_id) # Reject before any network access.
        with self.lock:
            cached=self.cache.get(table_id)
            if cached and time.monotonic()-cached[0]<3600:return cached[1]
            raw={}
            for kind in ['TBL','ITM','PRD']:
                try:
                    rows=self.client._get(META_URL,dict(method='getMeta',type=kind,apiKey=self.client.api_key,orgId='301',tblId=table_id,format='json',jsonVD='Y',detail='N'))
                    if not isinstance(rows,list) or not rows:raise ValueError('Empty metadata')
                    raw[kind]=rows
                except Exception as exc:
                    raise DerivedValidationError(f'{table_id}: 실제 KOSIS {kind} 메타데이터 조회에 실패했습니다 ({type(exc).__name__}, 코드 {getattr(exc,"code","")}). 자료 부재로 단정하지 않습니다.',failure_kind='source_api_error') from None
            if any(str(r.get('ORG_ID'))!='301' or r.get('TBL_ID')!=table_id for r in raw['ITM']):
                raise DerivedValidationError('실제 메타데이터의 기관·통계표가 요청과 다릅니다.')
            items=[{'item_id':r['ITM_ID'],'item_name':r.get('ITM_NM') or r['ITM_ID']} for r in raw['ITM'] if r.get('OBJ_ID')=='ITEM']
            dimensions=[]
            for obj in dict.fromkeys(r['OBJ_ID'] for r in raw['ITM'] if r.get('OBJ_ID')!='ITEM'):
                values=[r for r in raw['ITM'] if r['OBJ_ID']==obj]
                index=int(values[0]['OBJ_ID_SN'])
                dimensions.append({'dimension_index':index,'mcp_param':f'objL{index}','obj_id':obj,'obj_name':values[0].get('OBJ_NM',''),
                    'values':[{'class_id':r['ITM_ID'],'class_name':r.get('ITM_NM') or r['ITM_ID'],'parent_id':r.get('UP_ITM_ID'),'unit':r.get('UNIT_NM')} for r in values]})
            periods=[{'frequency':normalize_frequency(r['PRD_SE']),'start_period':normalize_period(r['PRD_SE'],r['STRT_PRD_DE']),
                      'end_period':normalize_period(r['PRD_SE'],r['END_PRD_DE'])} for r in raw['PRD'] if r.get('STRT_PRD_DE') and r.get('END_PRD_DE')]
            if not items or not periods:raise DerivedValidationError('실제 KOSIS 메타데이터에서 항목·기간을 확인하지 못했습니다.')
            meta={'table_id':table_id,'table_name':raw['TBL'][0]['TBL_NM'],'items':items,'dimensions':sorted(dimensions,key=lambda d:d['dimension_index']),
                  'frequencies':[p['frequency'] for p in periods],'periods':periods,'comments':[],
                  'metadata_origin':'actual_KOSIS_metadata_API','metadata_sha256':hashlib.sha256(json.dumps(raw,ensure_ascii=False,sort_keys=True).encode()).hexdigest()}
            self.cache[table_id]=(time.monotonic(),meta);return meta
