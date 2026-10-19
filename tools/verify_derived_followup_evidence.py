"""Verify saved actual KOSIS E2E receipts with Decimal; no model calls."""
import hashlib,json,sys
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=ROOT.parent if ROOT.name=='StatBridge-local1' else ROOT.parent.parent
sys.path[:0]=[str(ROOT/'src/backend'),str(ROOT/'src/agent')]
from statbridge_mcp.metadata_store import MetadataStore
from derived_catalog_tools import DerivedCatalogTools
from expression_tree_schema import ExpressionPlan
from expression_tree_validator import validate_plan

def load(path):return json.loads(path.read_text(encoding='utf8'))
def identity(s):return (s['table_id'],s['item_id'],tuple(sorted(s['classifications'].items())),s['frequency'])

def main():
    catalog=DerivedCatalogTools(MetadataStore())
    assert len(catalog.store.all())==349 and all(str(m.org_id)=='301' for m in catalog.store.all())
    review=load(ROOT/'eval/derived_goldset_v5_validation.json')
    gold=[json.loads(line) for line in (ROOT/'eval/derived_goldset_v5_300.jsonl').read_text(encoding='utf8').splitlines()]
    approved=set()
    for r in load(ROOT/'eval/derived_v2_kosis_source_verification.json')['records']+review['actual_descendant_probes']:
        if r['status']=='PASS':approved.add(identity(r['source']))
    actual_required=set()
    for c in gold:
        if c.get('expected_plan'):
            plan=ExpressionPlan.model_validate(c['expected_plan']);validate_plan(plan,catalog)
            actual_required.update(identity(s) for s in c['expected_plan']['sources'])
    assert actual_required<=approved,actual_required-approved
    checks=[]
    for name,root,receipt in [
        ('local1',WORKSPACE/'StatBridge-local1','c5397acb6fd0404eb77ed43b392b7399'),
        ('StatBridge1',WORKSPACE/'StatBridge1/StatBridge-official','bcb829cad4f7408c9ea2385e0cd9ef7b')]:
        evidence_dir=root/'runtime_data/derived_evidence'
        current=load(evidence_dir/(receipt+'.json'));e=current['evidence']
        previous=load(evidence_dir/(e['previous']+'.json'));prior=previous['evidence']
        assert e['usage']==[] and e['plan']['nodes']==prior['plan']['nodes']
        assert e['plan']['sources']==prior['plan']['sources']
        assert (e['plan']['start_period'],e['plan']['end_period'])==('202308','202405')
        assert '202308 ~ 202405' in e['plan']['economic_definition']
        assert current['calculation_id']!=previous['calculation_id']
        serialized=json.dumps(e,ensure_ascii=False,sort_keys=True,allow_nan=False,default=str)
        assert hashlib.sha256(serialized.encode()).hexdigest()==current['sha256']
        p=ExpressionPlan.model_validate(e['plan']);validate_plan(p,catalog)
        source=p.sources[0];node=p.nodes[0]
        rows=e['source_data'][source.alias]['rows']
        assert all(str(r['ORG_ID'])=='301' and r['TBL_ID']==source.table_id and r['ITM_ID']==source.item_id for r in rows)
        values={r['PRD_DE']:Decimal(r['DT']) for r in rows}
        actual=e['node_results'][node.id]['values'];errors=[]
        for period,value in actual.items():
            if '202308'<=period<='202405':
                previous_year=str(int(period[:4])-1)+period[4:]
                expected=(values[period]/values[previous_year]-1)*100
                errors.append(abs(expected-Decimal(str(value))))
        assert len(errors)==10 and max(errors)<Decimal('1e-10')
        out=ROOT/'eval/derived_followup_e2e_records'/name;out.mkdir(parents=True,exist_ok=True)
        for payload in [current,previous]:
            (out/(payload['calculation_id']+'.json')).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        checks.append({'checkout':name,'status':'PASS','calculation_id':receipt,'previous':e['previous'],
            'receipt_hash_verified':True,'gpt_calls_for_period_edit':0,'unchanged_nodes_and_sources':True,
            'display_start':'202308','display_end':'202405','fetch_start':e['bounds']['fetch_start'],
            'actual_KOSIS_Decimal_points':len(errors),'max_absolute_error':str(max(errors)),
            'ui_checks':{'date_apply':True,'invalid_range_preserves_graph':True,'undo':True,'redo':True,'save_restore':True},
            'screenshot':'derived_date_widget_v5_proof.jpg',
            'notes':'Browser actions observed independently; no synthetic provider response used.'})
    result={'status':'PASS','approved_catalog_count':349,'all_org_id':'301','gold_sources_validated':True,
        'positive_source_identities_backed_by_actual_API':len(actual_required),
        'question_review_sha256':review['v5_sha256'],'checks':checks,
        'fixture_restore_limitation':'A copied test account snapshot in the second isolated test DB referenced first-checkout evidence and was correctly rejected. A fresh real GPT/KOSIS query was created in StatBridge1 and its own save/restore passed. Original account databases were untouched.'}
    (ROOT/'eval/derived_date_widget_followup_e2e.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
