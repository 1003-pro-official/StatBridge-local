"""Resolve genuinely ambiguous catalog labels before the FINAL real GPT run.

Reads only sealed gold, registered metadata and actual API source evidence.
Does not read any evaluated model answers, scores, or failure lists.
"""
import copy,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from prepare_derived_eval_v2 import audit,MetadataStore,DerivedCatalogTools


def main():
    previous=[json.loads(x) for x in (ROOT/'eval/derived_goldset_v3_300.jsonl').read_text(encoding='utf8').splitlines()]
    cases=copy.deepcopy(previous);catalog=DerivedCatalogTools(MetadataStore())
    availability=json.loads((ROOT/'eval/derived_v2_kosis_source_verification.json').read_text(encoding='utf8'))
    assert availability['status']=='COMPLETE'
    changed=[]
    for c in cases:
        notes=[]
        for source in c.get('allowed_sources',[]):
            metadata=catalog.get_table_metadata(source['table_id'])
            for dimension in metadata['dimensions']:
                selected=next((v for v in dimension['values'] if v['class_id']==source['classifications'].get(dimension['mcp_param'])),None)
                if selected and sum(v['class_name']==selected['class_name'] for v in dimension['values'])>1:
                    notes.append(f'{metadata["table_name"]}의 {dimension["obj_name"]}에서 {selected["class_name"]}는 분류 ID {selected["class_id"]}를 뜻합니다')
        if notes:
            before=c['query'];c['query']+=' 동명 분류가 있으므로 다음을 구분해 주세요: '+'; '.join(notes)+'.'
            c['question_style']='natural_request_with_ambiguous_catalog_class_disambiguated'
            changed.append({'id':c['id'],'before':before,'after':c['query'],'basis':'duplicate class_name in the registered dimension; exact same source ID as original answer'})
        c['goldset_version']='4.0'
        c['source_availability_evidence']=[{'id':r['id'],'status':r['status'],'failure_kind':r.get('failure_kind'),'observed_unit_set':r.get('observed_unit_set')} for r in availability['records'] if any(
            (r['source']['table_id'],r['source']['item_id'],r['source']['classifications'],r['source']['frequency'])==
            (s['table_id'],s['item_id'],s['classifications'],s['frequency']) for s in c.get('allowed_sources',[]))]
    answer_keys=['id','expected_plan','previous_plan','allowed_sources','expected_result','accepted_statuses','observation_condition','post_plan_probe']
    digest=lambda rows:hashlib.sha256(json.dumps([{k:c.get(k) for k in answer_keys} for c in rows],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    assert digest(cases)==digest(previous),'Only disambiguate catalog names; never change answers to match the model'
    errors=[{'id':c['id'],'errors':audit(c,catalog)} for c in cases if audit(c,catalog)]
    assert not errors
    families={}
    for c in cases:families.setdefault(c['family'],set()).add(c['split'])
    assert all(len(v)==1 for v in families.values())
    body=''.join(json.dumps(c,sort_keys=True,ensure_ascii=False)+'\n' for c in cases);p=ROOT/'eval/derived_goldset_v4_300.jsonl'
    if p.exists() and p.read_text(encoding='utf8')!=body:raise RuntimeError('v4 sealed; version any further change')
    p.write_text(body,encoding='utf8',newline='\n')
    prior=json.loads((ROOT/'eval/derived_goldset_v3_validation.json').read_text(encoding='utf8'))
    report={**prior,'version':'4.0','v4_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'questions_and_answers_unchanged_from_v2':False,
        'answers_unchanged_from_v3':True,'answer_sha256_excluding_question_text':digest(cases),'changed_questions':changed,
        'question_changes_count':len(changed),'unchanged_question_comparison_n':300-len(changed),
        'actual_KOSIS_source_availability':availability['summary'],'pre_evaluation_validation_errors':errors,
        'question_review_checks':['exact table/item/class IDs exist in 349 org301 registry','frequency and required history/base dates inside metadata coverage',
            'duplicate class names disambiguated','explicit prior graph supplied for edit requests','hypothetical data conditions labelled, not claimed as actual observations',
            'natural security requests separated from injected adapter probes','family-disjoint frozen split','answers independent of evaluated GPT outputs'],
        'evaluation_contract':'300 actual GPT planning questions. API unit/data absence blocks runtime. Not 300 successful actual-data calculations.'}
    (ROOT/'eval/derived_goldset_v4_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'version':report['version'],'cases':300,'source_tables':report['registered_tables_used'],'changed_questions':len(changed),'validation_errors':len(errors),'sha256':report['v4_sha256']},ensure_ascii=False))

if __name__=='__main__':main()
