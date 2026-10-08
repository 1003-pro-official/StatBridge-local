"""Audit every four-table question and frozen metadata answer."""
from build import *
import re
validator=load('four_table_v3_validator',V3/'scripts/validate.py')
text_sha256=v3.digest
def audit(cases,catalog,manifest):
    details=validator.validate_cases(cases,catalog)
    tables={t['table_id']:t for t in catalog['tables']}
    assert len(cases)==36==manifest['cases']
    for case in cases:
        plans=case['workflow_gold']['classification_and_plan']['series']
        ids={p['table_id'] for p in plans}
        assert len(plans)==len(ids)==4,case['id']
        assert ids==set(case['augmentation']['anchor_table_ids']),case['id']
        for plan in plans:
            t=tables[plan['table_id']]
            assert t['table_name'] in case['query'],case['id']
            assert plan['classifications']=={k:v['value_id'] for k,v in v3.representatives(t).items()},case['id']
            same=[x for x in tables.values() if x['table_name']==t['table_name']]
            assert len(same)==1 or f"[{t['table_id']}]" in case['query'],case['id']
        variant=case['augmentation']['variant']
        if variant=='id_prefix':
            requested=re.findall(r'\[(DT_[0-9A-Za-z]+)\]\s+([^;]+?)(?=;|\. 각 표)',case['query'])
            assert len(requested)==4 and {tid for tid,_ in requested}==ids,case['id']
            assert all(name==tables[tid]['table_name'] for tid,name in requested),case['id']
        else:
            requested=re.findall(r'「([^」]+)」(?:\s+\[(DT_[0-9A-Za-z]+)\])?',case['query'])
            resolved=[]
            for name,tid in requested:
                matches=[t['table_id'] for t in tables.values() if t['table_name']==name and (not tid or t['table_id']==tid)]
                assert len(matches)==1,case['id']
                resolved.extend(matches)
            assert len(resolved)==4 and set(resolved)==ids,case['id']
        assert '네 표·네 계열' in case['query'] and '조회 기간은 나중에' in case['query']
        assert all(case['review']['agent_review'][k] for k in ['exact_four_distinct_tables','table_names_complete','ambiguity_disambiguated_by_id','four_representative_series','period_deferred_explicit','frequency_preserved'])
    assert v3.digest(DATASET/'questions.jsonl')==manifest['dataset_sha256']
    assert v3.digest(v3.CATALOG)==manifest['catalog_sha256']
    assert v3.digest(V3/'statbridge-reporter349.jsonl')==manifest['v3_original_sha256']
    return {'valid':True,'error_count':0,'checked_cases':len(cases),'coverage':details,'human_approved':False,'review':'Agent reviewed all questions against exact names/IDs, four series, frequency and deferred period.'}
if __name__=='__main__':
    cases=[json.loads(l) for l in (DATASET/'questions.jsonl').read_text(encoding='utf8').splitlines()]
    print(json.dumps(audit(cases,json.loads(v3.CATALOG.read_text(encoding='utf8')),json.loads((DATASET/'manifest.json').read_text(encoding='utf8'))),ensure_ascii=False))
