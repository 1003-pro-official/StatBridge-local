"""Opt-in isolated UI evaluation with frozen attachment observations, never KOSIS.

Creates a dedicated disposable auth DB; does not use real saved analyses.
Run with the UI pointing at port 8005. No provider calls are permitted.
"""
import os
from pathlib import Path
import sys
import json

ROOT=Path(__file__).resolve().parents[1]
CACHE=Path(os.getenv('STATBRIDGE_TABLE_PREVIEW_DIR',str(ROOT/'.venv/cache/table-editor-20261019/preview')))
CACHE.mkdir(parents=True,exist_ok=True)
API_PORT=int(os.getenv('STATBRIDGE_PREVIEW_API_PORT','8005'))
UI_PORT=int(os.getenv('STATBRIDGE_PREVIEW_UI_PORT','5175'))
for key in ['OPENAI_API_KEY','NCP_CLOVA_API_KEY','NCP_API_KEY','CLOVA_STUDIO_API_KEY','JEV_API_KEY','TYPESAFE_API_KEY']:os.environ[key]=''
os.environ['LANGFUSE_ENABLED']='false'
os.environ.update(STATBRIDGE_DERIVED_SUPPLEMENT_DIR=str(CACHE/'supplements'),STATBRIDGE_AUTH_DB=str(CACHE/'accounts.sqlite3'),STATBRIDGE_COOKIE_NAME='statbridge_table_preview_'+str(API_PORT),STATBRIDGE_API_PORT=str(API_PORT),STATBRIDGE_UI_PORT=str(UI_PORT),STATBRIDGE_HYBRID_RETRIEVAL='0')
sys.path[:0]=[str(ROOT/'src/agent'),str(ROOT/'src/backend')]
import requests
def no_external(*args,**kwargs):raise AssertionError('External HTTP blocked in attachment preview')
requests.sessions.Session.send=no_external
import bridge_api as api
import account_auth as auth
from derived_indicator_evidence import DerivedIndicatorEvidence
api.agent.workflow.derived_runtime.evidence=DerivedIndicatorEvidence(CACHE/'evidence')
from output_agent import OutputAgent
from output_schema import ChartSpec
from report_table import TableOptions
from fastapi.testclient import TestClient

api._saved_workspace_path=lambda identifier:CACHE/'workspaces'/('user-'+str(auth.current_user()['id']))/(identifier+'.json.gz')
api._table_card=lambda table:{'tableId':table,'name':'첨부 PDF 평가 자료 · 실시간 API 조회 아님','organization':'첨부 참조','frequency':'원자료','source':'frozen_reference'}
client=TestClient(api.app)
login=client.post('/api/auth/login',json={'username':'test1','password':'1234'});login.raise_for_status();user=login.json()['user']
for case in json.loads((ROOT/'eval/report_table/reference_cases.json').read_text(encoding='utf8')):
    source='REFERENCE_'+case['id'];rows=[]
    for s in case['series']:
        for p in s['points']:rows.append({'PRD_DE':p['date'],'DT':str(p['value']),'ITM_NM':s['label'],'UNIT_NM':s['unit'],'_SOURCE_SERIES_ID':source,'_FREQUENCY':s['frequency']})
    result={'query':case['title']+' 보고서용 표를 만들어줘','api_plan':{'table_id':source,'table_name':case['title']+' [첨부 참조 자료]','org_id':'REFERENCE','item_id':'FROZEN','frequency':'M'},'execution':{'status':'success','rows':rows,'sources':[{'table_id':source,'source':'첨부 PDF 고정 관측값 · 실시간 KOSIS 아님','row_count':len(rows)}]}}
    spec=ChartSpec(layout='separate',title=case['title']+' · 첨부 PDF 편집 평가',report_table=TableOptions.model_validate(case['options']))
    output=OutputAgent()._build(result,spec,generate_explanation=False)
    session={'result':result,'output':output,'sessions':[{'query':result['query'],'table_name':case['title'],'frequency':'M','period':{'start':'2023-01-01','end':'2026-09-30'}}],'undo':[],'redo':[],'account_id':user['id']}
    api.EDIT_SESSIONS[case['id']]=session;auth.STORE.bind('edit',case['id'],user['id'])
    saved=client.post('/api/workspace/'+case['id']+'/save',json={'edit_session_id':case['id'],'format':'json','revision':0});saved.raise_for_status()
if __name__=='__main__':
    import uvicorn
    uvicorn.run(api.app,host='127.0.0.1',port=API_PORT)
