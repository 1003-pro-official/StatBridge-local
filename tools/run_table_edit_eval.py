"""Attachment-based deterministic evaluation. Uses no paid/model judge calls."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=ROOT/'.venv/cache/table-editor-20261019/evaluation');args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True);env=os.environ.copy()
    env['PYTHONPATH']=os.pathsep.join(map(str,[ROOT/'src/backend',ROOT/'src/agent',args.out]))
    for key in ['OPENAI_API_KEY','NCP_CLOVA_API_KEY','NCP_API_KEY','CLOVA_STUDIO_API_KEY','JEV_API_KEY','TYPESAFE_API_KEY']:env[key]=''
    env['STATBRIDGE_HYBRID_RETRIEVAL']='0'
    env['STATBRIDGE_AUTH_DB']=str(args.out/'test-accounts.sqlite3')
    # Any accidental external requests fail before they leave the process.
    (args.out/'table_eval_guard.py').write_text('''import requests
original=requests.sessions.Session.send
def guarded(self,request,**kwargs):
    raise AssertionError('External HTTP forbidden in deterministic table evaluation')
requests.sessions.Session.send=guarded
''',encoding='utf8')
    start=time.perf_counter();xml=args.out/'junit.xml'
    result=subprocess.run([sys.executable,'-m','pytest','-p','table_eval_guard','tests/test_table_layout.py','tests/test_table_sheet.py','tests/test_report_tables.py','tests/test_bok_table_styles.py','tests/test_account_auth.py','-q','--disable-warnings','--tb=short',f'--junitxml={xml}'],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf8',errors='replace')
    (args.out/'pytest.txt').write_text(result.stdout+'\n'+result.stderr,encoding='utf8')
    cases=[]
    if xml.exists():
        for node in ET.parse(xml).iter('testcase'):
            cases.append({'id':node.get('name'),'suite':node.get('classname'),'seconds':float(node.get('time','0')),'status':'FAIL' if node.find('failure') is not None or node.find('error') is not None else 'SKIPPED' if node.find('skipped') is not None else 'PASS'})
    report={'evaluation':'attachment-based deterministic table editor','reference_pages':[5,13,18],'reference_kind':'frozen_report_observations_not_live_KOSIS','gpt_calls':0,'external_http':'blocked before send','return_code':result.returncode,'elapsed_seconds':round(time.perf_counter()-start,2),'total':len(cases),'passed':sum(c['status']=='PASS' for c in cases),'failed':sum(c['status']=='FAIL' for c in cases),'skipped':sum(c['status']=='SKIPPED' for c in cases),'cases':cases}
    (args.out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},ensure_ascii=False));return result.returncode

if __name__=='__main__':raise SystemExit(main())
