"""Offline readiness checks only; never a browser E2E runner."""
from pathlib import Path
import sys,json,hashlib
from decimal import Decimal
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT/'src/agent'),str(ROOT/'src/backend')]
from expression_tree_schema import ExpressionPlan
from expression_tree_validator import validate_plan
from dynamic_expression_executor import DynamicExpressionExecutor,Series
from derived_catalog_tools import DerivedCatalogTools
from derived_request_period import requested_display_period
from derived_indicator_planner import is_derived_request
from statbridge_mcp.metadata_store import MetadataStore
data=json.loads((HERE/'cases.json').read_text(encoding='utf-8'))
cases=data['cases']; assert len(cases)==60
assert len({c['id'] for c in cases})==60
for prefix,group in [('E','edit'),('F','screen_file'),('D','derived')]:
    assert {c['id'] for c in cases if c['group']==group}=={f'{prefix}{i}' for i in range(21,41)}
inputs=[json.loads(x) for x in (HERE/'questions.jsonl').read_text(encoding='utf-8').splitlines()]
assert [{k:c[k] for k in ['id','group','query']} for c in cases]==inputs
assert all(set(c)=={'id','group','query'} for c in inputs)
md=(HERE/'질의와_정답_60문항.md').read_text(encoding='utf-8')
assert sum(line.startswith(('| E','| F','| D')) for line in md.splitlines())==60
catalog=DerivedCatalogTools(MetadataStore()); count=0
for c in cases:
    assert c['query'] and c['answer'] and c['purpose']
    assert md.count('| '+c['id']+' ·')==1
    if c['group']!='derived':continue
    plan=ExpressionPlan.model_validate(c['plan']); bounds=validate_plan(plan,catalog)
    assert bounds==c['history']
    assert is_derived_request(c['query'])
    period=requested_display_period(c['query'])
    assert period['start'][:7].replace('-','')==plan.start_period
    assert period['end'][:7].replace('-','')==plan.end_period
    fixture=data['fixture']; values={s.alias:Series(dict(zip(fixture['months'],map(float,fixture[s.alias]))),'연리%','M',[s.alias]) for s in plan.sources}
    result=DynamicExpressionExecutor().execute(plan,values)
    assert len(result['rows'])==len(c['expected'])
    for row,expected in zip(result['rows'],c['expected']):
        assert row['PRD_DE']==expected['period'] and row['UNIT_NM']==c['unit']
        assert abs(Decimal(str(row['DT']))-Decimal(expected['value']))<=Decimal(data['absolute_tolerance'])
    count+=1
print(json.dumps({'status':'PASS','cases':60,'groups':{'edit':20,'screen_file':20,'derived':20},'catalog_plan_period_route_numeric_verified':count,'ui_e2e_executed':False,'human_review':'pending'},ensure_ascii=False))
