"""TEST SERVER ONLY: synthetic planner + REAL KOSIS API. Never live GPT evidence."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/agent'),str(ROOT/'src/backend')]
import bridge_api as api
from expression_tree_validator import canonical_bound

class FixturePlanner:
    configured=True
    def request(self,system,user,**kwargs):
        c=json.loads(user)
        meta={'model':'synthetic_UI_fixture_NOT_GPT','usage':{}}
        if system.startswith('경제학적 의미 검토자'):
            return json.dumps({'approved':True,'reason':'Synthetic planner fixture, mathematical test ratio only'}),meta
        if 'partial_input_schema' not in c:
            return json.dumps({'action':'unavailable','missing':[{'required_data':'검증용 가상비용지수','reason':'사용자가 파일로 제공하는 시험 자료입니다.'}]},ensure_ascii=False),meta
        table='DT_404Y014'
        selected=next((t['result'] for t in c['tools'] if t.get('action')=='metadata' and isinstance(t.get('result'),dict) and t['result'].get('table_id')==table),None)
        if not selected:return json.dumps({'action':'metadata','table_id':table}),meta
        source={'alias':'ppi','table_id':table,'item_id':selected['items'][0]['item_id'],'frequency':'M','required_data':'생산자물가지수 총지수',
                'classifications':{d['mcp_param']:next(v['class_id'] for v in d['values'] if v['class_name']=='총지수') for d in selected['dimensions']}}
        first=canonical_bound(c.get('start_period') or '202301','M');last=canonical_bound(c.get('end_period') or '202304','M')
        if not c['authorized_file_metadata']:
            answer={'action':'request_inputs','available_sources':[source],'missing':[{'alias':'cost','required_data':'검증용 가상비용지수','reason':'UI 검증에서 사용자가 제공하는 합성 자료입니다. KOSIS 자료가 아닙니다.','unit':'지수','frequency':'M','lookback':0}],'start_period':first,'end_period':last}
        else:
            source_file={'alias':'cost','table_id':'USER_FILE:cost','item_id':'value','classifications':{},'frequency':'M','required_data':'검증용 가상비용지수'}
            answer={'action':'plan','plan':{'plan_version':'1.0','indicator_name':'생산자물가 / 사용자 가상비용지수 (UI 검증)',
                'economic_definition':'실제 KOSIS 생산자물가 수준을 사용자 제공 합성 비용지수로 나누는 UI 시험용 수학적 비율입니다. 공식 경제지표가 아닙니다.',
                'sources':[source,source_file],'nodes':[{'id':'ratio','operator':'divide','inputs':['ppi','cost']}],
                'outputs':[{'node':'ratio','label':'생산자물가 / 사용자 가상비용지수'}],'start_period':first,'end_period':last}}
        return json.dumps(answer,ensure_ascii=False),meta

api.agent.workflow.derived_runtime.planner.client=FixturePlanner()
api.agent.output_agent.ncp_client=None
app=api.app
