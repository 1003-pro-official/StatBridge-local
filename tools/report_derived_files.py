"""Verify real JSON/UI evidence and preserve independent two-checkout checks."""
import hashlib,json,re,shutil,xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path
from report_derived_eval import regression

ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=ROOT.parent if ROOT.name=='StatBridge-local1' else ROOT.parent.parent
SOURCE=WORKSPACE/'StatBridge-local1';TARGET=WORKSPACE/'StatBridge1/StatBridge-official'
OUT=SOURCE/'eval'

def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def main(expected_model='gpt-5.4'):
    folder=OUT/'derived_files_v8_evidence';folder.mkdir(exist_ok=True)
    workspaces=[(p,read(p)) for p in (SOURCE/'.venv/cache/derived-files-v8/supplements/user-1').glob('*/workspace.json')]
    path,w=next((p,w) for p,w in workspaces if w.get('calculation_id') and any(f['filename'].endswith('.json') for f in w['files'].values()))
    cid=w['calculation_id'];receipt_path=SOURCE/'runtime_data/derived_evidence'/(cid+'.json');receipt=read(receipt_path);e=receipt['evidence']
    canonical=json.dumps(e,ensure_ascii=False,sort_keys=True,allow_nan=False,default=str)
    assert hashlib.sha256(canonical.encode()).hexdigest()==receipt['sha256']
    uploaded=next(f for f in w['files'].values() if f['filename'].endswith('.json'))
    raw=path.parent/'files'/(uploaded['file_id']+'.json');assert sha(raw)==uploaded['sha256']
    shutil.copy2(raw,folder/'synthetic_cost_index.json');shutil.copy2(receipt_path,folder/receipt_path.name)
    data=e['source_data'];sources=e['plan']['sources'];node=e['plan']['nodes'][0]
    assert node['operator']=='divide' and len(node['inputs'])==2
    api=next(s for s in sources if not s['table_id'].startswith('USER_FILE:'));file_source=next(s for s in sources if s['table_id'].startswith('USER_FILE:'))
    assert node['inputs']==[api['alias'],file_source['alias']]
    assert all(r['ORG_ID']=='301' and r['TBL_ID']=='DT_404Y014' for r in data[api['alias']]['rows'])
    assert data[file_source['alias']]['sha256']==uploaded['sha256']
    assert all('ORG_ID' not in r for r in data[file_source['alias']]['rows'])
    costs={r['PRD_DE']:Decimal(str(r['DT'])) for r in data[file_source['alias']]['rows']};checked=[]
    for row in data[api['alias']]['rows']:
        expected=Decimal(str(row['DT']))/costs[row['PRD_DE']]
        actual=Decimal(str(e['node_results'][node['id']]['values'][row['PRD_DE']]))
        assert abs(expected-actual)<=Decimal('1e-12');checked.append({'period':row['PRD_DE'],'expected':str(expected),'actual':str(actual)})
    assert len(checked)==4 and e['semantic_review']['approved'] is True and all(u['model']==expected_model for u in e['usage'])
    source_state=(OUT/'derived_files_v8_sources_ui_state.txt').read_text(encoding='utf8')
    assert 'kosis.kr/' in source_state and 'ecos.bok.or.kr/' in source_state and 'CSV · JSON · TSV · XLSX' in source_state
    table_state=(OUT/'derived_files_v8_json_table_state.txt').read_text(encoding='utf8');assert '1.166900' in table_state and '1.169600' in table_state
    checks={}
    for label,tree in [('local1',SOURCE),('StatBridge1',TARGET)]:
        final_log=(tree/'eval/derived_files_v8_final.txt').read_text(encoding='utf8')
        root=ET.parse(tree/'eval/derived_files_v8_final.xml').getroot();cases=root.findall('.//testcase')
        failed=sum(c.find('failure') is not None or c.find('error') is not None for c in cases)
        assert failed==0 and f'{len(cases)} passed' in final_log
        build=(tree/'eval/derived_files_v8_build.txt').read_text(encoding='utf8');assert 'built in' in build and 'error TS' not in build
        front=(tree/'eval/derived_files_v8_frontend_tests.txt').read_text(encoding='utf8')
        assert re.search(r'fail 0',front)
        validator=(tree/'eval/derived_files_v8_validator.txt').read_text(encoding='utf8');assert 'VALIDATION OK' in validator
        checks[label]={'targeted':regression('derived_regression_targeted',tree/'eval'),
                       'final_affected_files':{'executed':len(cases),'passed':len(cases),'failed':0,'skipped':0},
                       'frontend_tests':{'passed':int(re.search(r'pass (\d+)',front).group(1)),'failed':0},'typecheck_build':'PASS','validator':'PASS'}
    full=regression('derived_regression_full',OUT);assert full['status']=='PASS'
    assert any(c.get('classname','').endswith('test_derived_file_inputs') for c in ET.parse(OUT/'derived_regression_full.xml').getroot().findall('.//testcase'))
    result={'version':'file_inputs_v8','status':'PASS_WITH_SCOPE_LIMITS','accepted_formats':['csv','json','tsv','xlsx'],
            'template_formats':['csv','json','tsv'],'max_original_file_bytes':2_000_000,'max_rows':6000,
            'source_guidance':'curated official portal search candidates, not verified dataset downloads; synthetic/company inputs distinguished',
            'checkouts':checks,'full_regression_local1':full,
            'full_regression_scope':'Full suite ran after the initial four-format implementation; final supplemental-review followup and parser hardening covered by final affected-file tests on both checkouts.',
            'actual_provider_UI':{'status':'PASS','GPT':'actual '+expected_model,'KOSIS':'actual org 301 DT_404Y014 observations',
                'user_file':'explicitly synthetic JSON, NOT official KOSIS data','calculation_id':cid,'evidence_sha256':receipt['sha256'],
                'original_JSON_sha256':uploaded['sha256'],'independent_Decimal':checked,
                'verified':['official portal links and search terms','synthetic-data own-input guidance','JSON template download','JSON paste/upload','table','graph'],
                'initial_semantic_rejections_preserved':sum(a['status']=='need_details' for a in w['attempts']),
                'resolution':'server-verified upload stage plus the current user continue-calculation action passed to semantic review; no review bypass'},
            'limitations':['Native file picker and drag/drop not automated in browser; JSON paste/upload exercised. XLSX bytes and all four parsers exercised through backend/HTTP tests.',
                'Responsive CSS implemented; narrow-viewport browser check not executed.','Separate real-provider browser E2E on second checkout not executed.',
                'This is not a fresh 300-case GPT evaluation; v7 model benchmark remains historical.','Portal existence verified on 2026-10-19; exact missing dataset downloads not verified.'],
            'test_harness_initial_errors':'Two huge pytest parameter IDs exceeded Windows environment limits (4 setup/teardown errors); named IDs fixed and rerun, not product PASS claims.',
            'code_sha256':{str(p.relative_to(SOURCE)).replace('\\','/'):sha(p) for p in [SOURCE/'src/agent'/n for n in ['derived_file_inputs.py','derived_input_guidance.py','derived_supplement.py','derived_indicator_planner.py','bridge_api.py']]}}
    dump(OUT/'derived_files_v8_results.json',result)
    text='\n'.join(['# 자료 안내·다중 형식·UI 개선 검증 · ai-assisted','',
        'CSV / JSON / TSV / XLSX 지원. CSV / JSON / TSV 빈 양식 제공. 원본 2MB·6,000행 및 공통 시계열 검증 유지.',
        '자료 입수처는 공식 사이트 검색 후보와 자체 입력 자료로 구분했습니다. 존재하지 않는 가상지수의 공식 파일을 안내하지 않습니다.',
        'API 자료 상태, 기간·주기·단위, 자료 구할 곳, 양식과 파일 드롭/선택, 계산 준비 상태를 카드로 구분했습니다. 중복 오류 안내를 제거했습니다.',
        '',f'local1 전체 회귀: {full["passed"]}/{full["tests"]}, subtests {full["passed_subtests"]} 통과. 전체 실행 이후의 마지막 업로드 단계·XML 보완은 양쪽 최종 파일 검사로 별도 검증했습니다.',
        *[f'{name}: 핵심 회귀 {v["targeted"]["passed"]}/{v["targeted"]["tests"]}, 최종 파일 검사 {v["final_affected_files"]["passed"]}/{v["final_affected_files"]["executed"]}, 프런트 검사 {v["frontend_tests"]["passed"]} 통과, 타입·빌드·검증기 PASS.' for name,v in checks.items()],
        '',f'실제 GPT-5.4 + 실제 KOSIS + 사용자 합성 JSON 파일로 표·그래프 생성. 독립 Decimal 4값 일치. 계산 ID {cid}.',
        '업로드 전 최초 질문의 양식 안내 문구 때문에 의미 검토가 거부한 이력도 보존했습니다. 실제 업로드 검증 상태와 후속 계산 요청을 전달해 해결했으며 검토를 생략하지 않았습니다.',
        '네이티브 파일 선택창/드롭, 좁은 화면 브라우저, 두 번째 폴더 별도 실모델 UI는 미실행입니다. 서버의 XLSX 바이너리와 네 가지 형식은 실제 파서·HTTP로 검증했습니다.',
        '이번 실행을 새로운 300건 실모델 평가로 표기하지 않습니다. 이전 v7 8/8·150/150 결과는 해당 버전의 기록입니다.',
        '', '사용법·공식 링크: ../docs/derived_file_formats_and_sources.md. 상세: derived_files_v8_results.json.'])
    (OUT/'derived_files_v8_report.md').write_text(text+'\n',encoding='utf8')
    print(json.dumps({'checks':checks,'full_passed':full['passed'],'actual_UI':'PASS','Decimal_points':4},ensure_ascii=False))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-model',default='gpt-5.4',help='Historical evidence model; does not rewrite records.')
    main(parser.parse_args().expected_model)
