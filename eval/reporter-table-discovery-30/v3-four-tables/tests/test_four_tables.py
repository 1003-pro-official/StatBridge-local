from pathlib import Path
import importlib.util,json,sys,copy
import pytest
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE/'scripts'))
spec=importlib.util.spec_from_file_location('four_audit',HERE/'scripts/validate.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
@pytest.fixture
def data():
 return ([json.loads(l) for l in (HERE/'questions.jsonl').read_text(encoding='utf8').splitlines()],json.loads(v.v3.CATALOG.read_text(encoding='utf8')),json.loads((HERE/'manifest.json').read_text(encoding='utf8')))
def test_all_four_table_questions_are_valid(data):
 assert v.audit(*data)['error_count']==0
@pytest.mark.parametrize('mutation',['missing','id','title','params','duplicate'])
def test_tampered_question_or_gold_is_rejected(data,mutation):
 rows,catalog,manifest=data
 if mutation=='missing':rows[0]['workflow_gold']['classification_and_plan']['series'].pop()
 elif mutation=='id':rows[2]['query']=rows[2]['query'].replace('DT_101Y004','DT_101Y001')
 elif mutation=='title':rows[0]['query']=rows[0]['query'].replace('M2 商品','잘못된 표').replace('M2 상품별 구성내역(말잔 계절조정계열)','잘못된 표')
 elif mutation=='params':rows[0]['workflow_gold']['classification_and_plan']['series'][0]['exact_params']['prdSe']='Q'
 else:rows[1]['query']=rows[0]['query']
 with pytest.raises((AssertionError,ValueError)):v.audit(rows,catalog,manifest)
def test_failed_run_does_not_publish_report(tmp_path):
 spec=importlib.util.spec_from_file_location('four_runtime',HERE/'scripts/evaluate_runtime.py')
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 m.save_result(tmp_path,{'summary':{'cases':36,'passed':35,'failed':1},'cases':[]},{})
 assert (tmp_path/'diagnostic_scores.json').exists() and not (tmp_path/'REPORT.md').exists()
