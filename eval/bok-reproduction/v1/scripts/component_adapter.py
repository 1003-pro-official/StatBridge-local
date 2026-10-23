"""Execute explicit product component boundaries; never emulates model behavior."""
import sys
import json
from decimal import Decimal

from core import ROOT, digest_file


def run_input(payload, provider, profile):
    setup=payload.get('setup',{})
    if setup.get('fault',{}).get('boundary')=='report_summary.model_response':
        return summary_fallback(payload,provider)
    if not setup.get('component_boundary') or 'user_rows' not in setup:
        return {'execution_status':'not_executed','model_called':False,
                'error':'this component adapter only executes the synthetic calendar-growth boundary'}
    for rel in ('src/backend','src/agent'):
        sys.path.insert(0,str(ROOT/rel))
    from dynamic_expression_executor import DynamicExpressionExecutor, Series, finite
    from expression_tree_schema import ExpressionPlan
    values={}
    for row in setup['user_rows']:
        if row['period'] in values:
            raise ValueError('duplicate synthetic period')
        values[row['period']]=finite(row['value'])
    plan=ExpressionPlan.model_validate({
        'plan_version':'1.0','indicator_name':'synthetic growth boundary',
        'economic_definition':'Calendar growth; component test, not supported standalone product analysis',
        'sources':[{'alias':'input','table_id':'synthetic','item_id':'synthetic','classifications':{},
                    'frequency':'M','required_data':'explicit synthetic component fixture'}],
        'nodes':[{'id':'growth','operator':'pct_change','inputs':['input'],'lag':1}],
        'outputs':[{'node':'growth','label':'growth'}],
        'start_period':min(values),'end_period':max(values)})
    result=DynamicExpressionExecutor().execute(plan,{'input':Series(values,'지수','M',['input'])})
    output=result['series']['growth']
    return {'execution_status':'observed','decision':'resolved','model_called':False,'actual_models':[],
            'usage':None,'cost':None,'statistics_requests':[],
            'calculated_points':[{'period':p,'value':output.values[p]} for p in sorted(values)],
            'output_unit':output.unit,'output_frequency':output.frequency,
            'controlled_execution_evidence':{'boundary':'DynamicExpressionExecutor.execute',
                'plan':plan.model_dump(),'issues':result['issues'],
                'calendar_grid':output.values,
                'implementation_sha256':{name:digest_file(ROOT/'src/agent'/name) for name in
                    ('dynamic_expression_executor.py','expression_tree_schema.py','expression_tree_validator.py')}},
            'explanation':'합성 입력의 달력 전월 대비 계산입니다. 결측 및 0 분모를 보간하지 않습니다.'}


def summary_fallback(payload, provider):
    for rel in ('src/backend','src/agent'):
        sys.path.insert(0,str(ROOT/rel))
    from report_summary import explain
    setup=payload['setup']
    series=[]
    for selection in setup['summary_sources']:
        response=provider.get_statistics(**selection)
        rows=response['rows']
        series.append({'label':rows[0]['_SERIES_LABEL'],'unit':rows[0]['UNIT_NM'],
            'frequency':selection['frequency'],'sourceId':selection['table_id'],
            'points':[{'date':r['PRD_DE'],'value':float(r['DT'])} for r in rows]})
    class InjectedClient:
        configured=True
        calls=0
        def chat_main(self,*args,**kwargs):
            self.calls+=1
            return json.dumps(setup['fault']['response']),None
    client=InjectedClient()
    result=explain(series,client,query=payload['query'])
    lookup={f['id']:f for f in result['facts']}
    selected=[lookup[key] for key in result['factIds']]
    supported=bool(selected)
    for fact in selected:
        original=series[fact['series']]['points']
        supported=supported and all(p in original for p in fact['observations'])
        if 'result' in fact:
            a,b=fact['observations'][:2]
            supported=supported and Decimal(fact['result'])==Decimal(str(b['value']))-Decimal(str(a['value']))
    supported=supported and result['text']==' '.join(f['text'] for f in selected)
    fallback=result['source']=='rules' and client.calls==1
    return {'execution_status':'observed','decision':'resolved','model_called':False,'actual_models':[],
        'usage':None,'cost':None,'explanation':result['text'],'series':series,
        'statistics_requests':provider.calls,
        'observed_contract':{'facts_supported':supported,'request_satisfied':fallback and supported},
        'controlled_execution_evidence':{'boundary':'report_summary.model_response',
            'injection_calls':client.calls,'summary':result,
            'implementation_sha256':{'report_summary.py':digest_file(ROOT/'src/agent/report_summary.py')}}}
