"""Final metadata/split review. No evaluated model outputs are read here."""
import copy,hashlib,json,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from prepare_derived_eval_v2 import audit,MetadataStore,DerivedCatalogTools


def answer_digest(cases):
    keys=['id','category','query','expected_result','accepted_statuses','expected_plan','previous_plan','allowed_sources','observation_condition','post_plan_probe']
    return hashlib.sha256(json.dumps([{k:c.get(k) for k in keys} for c in cases],ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def main():
    catalog=DerivedCatalogTools(MetadataStore())
    v2=[json.loads(x) for x in (ROOT/'eval/derived_goldset_v2_300.jsonl').read_text(encoding='utf8').splitlines()]
    availability=json.loads((ROOT/'eval/derived_v2_kosis_source_verification.json').read_text(encoding='utf8'))
    assert availability['status']=='COMPLETE','Complete actual API availability review first'
    cases=copy.deepcopy(v2);overlap=defaultdict(set)
    for c in v2:overlap[c['family']].add(c['split'])
    for c in cases:
        c['goldset_version']='3.0'
        c['split']='holdout' if int(hashlib.sha256(c['family'].encode()).hexdigest()[:8],16)%5<2 else 'dev'
        if not c.get('allowed_sources'):c['evidence_basis']['source_metadata']=[]
        c['execution_scope']='Planning answer only. Actual observed values/units must be verified by server; missing/unverified values block execution.'
        c['source_availability_evidence']=[{'id':r['id'],'status':r['status'],'failure_kind':r.get('failure_kind')} for r in availability['records'] if any(
            (r['source']['table_id'],r['source']['item_id'],r['source']['classifications'],r['source']['frequency'])==
            (s['table_id'],s['item_id'],s['classifications'],s['frequency']) for s in c.get('allowed_sources',[]))]
    assert answer_digest(cases)==answer_digest(v2),'Never change questions/answers from model results'
    assert not [c['id'] for c in cases if audit(c,catalog)]
    families=defaultdict(set)
    for c in cases:families[c['family']].add(c['split'])
    assert all(len(v)==1 for v in families.values())
    body=''.join(json.dumps(c,ensure_ascii=False,sort_keys=True)+'\n' for c in cases);destination=ROOT/'eval/derived_goldset_v3_300.jsonl'
    if destination.exists() and destination.read_text(encoding='utf8')!=body:raise RuntimeError('v3 sealed; create a new version')
    destination.write_text(body,encoding='utf8',newline='\n')
    report={'version':'3.0','status':'PASS_MACHINE_CATALOG_AND_QUESTION_CHECKS_EXPERT_PENDING','cases':300,
        'v2_sha256':hashlib.sha256((ROOT/'eval/derived_goldset_v2_300.jsonl').read_bytes()).hexdigest(),
        'v3_sha256':hashlib.sha256(body.encode()).hexdigest(),'catalog_version':catalog.version,
        'question_answer_sha256':answer_digest(cases),'questions_and_answers_unchanged_from_v2':True,
        'pre_evaluation_validation_errors':[],'category_counts':dict(Counter(c['category'] for c in cases)),
        'split_counts':dict(Counter(c['split'] for c in cases)),'v2_family_overlap_corrected':[k for k,v in overlap.items() if len(v)>1],
        'family_disjoint':True,'approved_table_count':349,'registered_tables_used':availability['table_count'],
        'actual_KOSIS_source_availability':availability['summary'],'human_expert_approval':False,
        'limitations':['API missing units/failures remain recorded, not silently substituted','all model runs are planning, not 300 successful real-data computations',
                       'retrospective holdout; v2 dev findings used before v3 split repair, not blind'],
        'negative_case_evidence':'Removed legacy positive-table metadata hints from negative cases; no allowed source or answer changed'}
    (ROOT/'eval/derived_goldset_v3_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
