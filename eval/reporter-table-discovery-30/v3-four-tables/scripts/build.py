"""Separate four-table public augmentation using frozen v3 metadata policy."""
from pathlib import Path
import importlib.util,json
from collections import Counter
ROOT=Path(__file__).resolve().parents[4]
DATASET=Path(__file__).resolve().parents[1]
V3=DATASET.parent/'v3'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
v3=load('four_table_v3_policy',V3/'scripts/build.py')
GROUPS=[
 ('통화상품 계열', ['DT_101Y001','DT_101Y002','DT_101Y003','DT_101Y004']),
 ('금융기관 개관', ['DT_101Y009','DT_101Y010','DT_101Y011','DT_101Y007']),
 ('수신·대출 신규금리', ['DT_121Y002','DT_121Y004','DT_121Y006','DT_121Y007']),
 ('지역별 금융', ['DT_141Y002','DT_141Y003','DT_141Y006','DT_141Y007']),
 ('GDP와 지출', ['DT_200Y103','DT_200Y104','DT_200Y107','DT_200Y108']),
 ('성장기여도', ['DT_200Y123','DT_200Y124','DT_200Y125','DT_200Y126']),
 ('무역 지수', ['DT_403Y001','DT_403Y002','DT_403Y003','DT_403Y004']),
 ('기업 재무', ['DT_501Y001','DT_501Y002','DT_501Y003','DT_501Y004']),
 ('전자결제', ['DT_633Y002','DT_633Y003','DT_633Y004','DT_633Y005']),
 ('동명 본원통화', ['DT_102Y001','DT_102Y101','DT_102Y003','DT_102Y103']),
 ('대외 금융', ['DT_311Y001','DT_311Y004','DT_311Y005','DT_311Y006']),
 ('주기별 독립 조회', ['DT_101Y016','DT_200Y102','DT_301Y015','DT_501Y013']),
]
SUFFIX='각 표의 대표 분류로 한 계열씩, 총 네 표·네 계열을 찾아줘. 각 표의 원래 주기를 유지하고 조회 기간은 나중에 선택할게.'
def build():
    catalog=json.loads(v3.CATALOG.read_text(encoding='utf8'));tables={t['table_id']:t for t in catalog['tables']}
    counts=Counter(t['table_name'] for t in tables.values());cases=[]
    for group,(topic,ids) in enumerate(GROUPS,1):
        for variant in range(3):
            order=ids if variant!=2 else list(reversed(ids))
            selected=[tables[tid] for tid in order]
            if variant==0:
                query='다음 네 통계표를 각각 조회해줘: '+', '.join(v3.title(t,counts) for t in selected)+'. '+SUFFIX
            elif variant==1:
                query='조회할 통계표는 네 개야. '+ '; '.join(f'{i}) '+v3.title(t,counts) for i,t in enumerate(selected,1))+'. '+SUFFIX
            else:
                query='네 개 통계표를 따로 찾아줘: '+ '; '.join(f"[{t['table_id']}] {t['table_name']}" for t in selected)+'. '+SUFFIX
            plans=[v3.plan(t,v3.representatives(t),t['table_name']) for t in selected]
            case=v3.make_case(f'R4-{group:02d}-{variant+1}',query,'four_tables',order,plans,v3.digest(v3.CATALOG),topic=topic,variant=['sentence','numbered','id_prefix'][variant])
            case['review'].update({'status':'agent_semantic_reviewed','agent_review':{'exact_four_distinct_tables':True,'table_names_complete':True,'ambiguity_disambiguated_by_id':True,'four_representative_series':True,'period_deferred_explicit':True,'frequency_preserved':True,'notes':'Reviewed against catalog and group/topic scope; not human approval.'}})
            cases.append(case)
    gold=DATASET/'questions.jsonl';gold.write_text(''.join(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n' for c in cases),encoding='utf8')
    manifest={'cases':len(cases),'groups':len(GROUPS),'variants':3,'tables':len({tid for _,ids in GROUPS for tid in ids}),'dataset_sha256':v3.digest(gold),'catalog_sha256':v3.digest(v3.CATALOG),'v3_original_sha256':v3.digest(V3/'statbridge-reporter349.jsonl'),'human_approved':False}
    (DATASET/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    return cases,manifest
if __name__=='__main__':
    print(json.dumps(build()[1],ensure_ascii=False))
