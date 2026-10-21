"""Synthetic input contracts, never reported as live KOSIS evidence."""
import copy,csv,io,json
from types import SimpleNamespace
import pytest
from derived_catalog_tools import DerivedCatalogTools
from derived_indicator_runtime import DerivedIndicatorRuntime
from derived_supplement import DerivedSupplementService,SupplementalCatalog
from expression_tree_validator import DerivedValidationError
from statbridge_mcp.metadata_store import MetadataStore
from test_dynamic_derived_indicators import plan,response,Model

@pytest.fixture
def setup(tmp_path):
    catalog=DerivedCatalogTools(MetadataStore());p=plan(catalog,'inverse').model_dump();s=p['sources'][0]
    slot={'alias':'cost','required_data':'사용자 비용지수','reason':'승인 API에서 확인되지 않음','unit':'지수','frequency':'M','lookback':0}
    partial={'action':'request_inputs','available_sources':[s],'missing':[slot],'start_period':'202001','end_period':'202004'}
    final=copy.deepcopy(p);final['sources'].append({'alias':'cost','table_id':'USER_FILE:cost','item_id':'value','classifications':{},'frequency':'M','required_data':'사용자 비용지수'})
    final['nodes']=[{'id':'ratio','operator':'divide','inputs':['x','cost']}];final['outputs']=[{'node':'ratio','label':'명시한 두 지수의 비율'}]
    calls=[]
    def fetch(**kwargs):calls.append(kwargs);return response(plan(catalog,'inverse'))
    gateway=SimpleNamespace(service=SimpleNamespace(store=catalog.store),get_statistics=fetch)
    model=Model([{'action':'metadata','table_id':s['table_id']},partial,{'action':'metadata','table_id':s['table_id']},
                 {'action':'plan','plan':final},{'approved':True,'reason':'synthetic mathematical ratio'}])
    runtime=DerivedIndicatorRuntime(gateway,model,tmp_path/'evidence');service=DerivedSupplementService(runtime,tmp_path/'uploads')
    return service,calls,slot,final

def csv_text(value='2',unit='지수',frequency='M'):
    return 'period,value,unit,frequency,source\n'+''.join(f'20200{i},{value},{unit},{frequency},독립 시험 자료\n' for i in range(1,5))

def test_partial_api_then_upload_resume_preserves_real_source_labels(setup):
    service,calls,slot,final=setup
    initial=service.start(1,'2020년 1월부터 2020년 4월까지 경제심리지수를 사용자 비용지수로 나누어 계산해 주세요.')
    assert len(calls)==1 and calls[0]['allow_fallback'] is False
    assert initial['supplement']['available'][0]['origin']=='kosis_api'
    wid=initial['supplement']['workspaceId'];template=service.template(1,wid,'cost')
    assert len(list(csv.DictReader(io.StringIO(template))))==4
    with pytest.raises(DerivedValidationError):service.upload(1,wid,'cost','cost.csv',template)
    assert not service.load(1,wid)['files']
    uploaded=service.upload(1,wid,'cost','cost.csv',csv_text());assert not uploaded['supplement']['missing']
    result=service.resume(1,wid)['result']
    assert len(calls)==1 # confirmed API data reused, no duplicate query
    assert result['execution']['rows'][-1]['DT']==pytest.approx(66.55) # synthetic 133.1 / 2
    assert {r['source'] for r in result['execution']['sources']}=={'kosis_api','user_file'}
    f=next(s for s in result['derivedEvidence']['sourceSelections'] if s['origin']=='user_file')
    assert f['filename']=='cost.csv' and len(f['sha256'])==64
    assert result['_derived']['record']['source_data']['cost']['source']=='user_file'
    assert 'ORG_ID' not in result['_derived']['record']['source_data']['cost']['rows'][0]
    from output_agent import OutputAgent
    from output_schema import ChartSpec
    output=OutputAgent()._build(result,ChartSpec(chart_type='line'),generate_explanation=False)
    assert len(output['table']['rows'])==4
    assert any(e['source']=='user_file' and e['organizationId']=='user_file' for e in output['evidence'])

@pytest.mark.parametrize('change',[
    'period,value,unit,frequency,source\n202001,=1+1,지수,M,시험\n',
    csv_text(unit='원'),csv_text(frequency='Q'),csv_text()+'202001,2,지수,M,시험\n',
    csv_text(value='NaN'),csv_text(value='1e999'),csv_text().replace('독립 시험 자료',''),
])
def test_invalid_file_preserves_workspace(setup,change):
    service,_,_,_=setup;wid=service.start(1,'2020년 1월부터 2020년 4월까지 경제심리지수를 사용자 비용지수로 나눈 비율 계산')['supplement']['workspaceId']
    before=service.load(1,wid)
    with pytest.raises((ValueError,TypeError)):service.upload(1,wid,'cost','cost.csv',change)
    assert service.load(1,wid)==before

def test_other_account_and_path_traversal_are_blocked(setup):
    service,_,_,_=setup;wid=service.start(1,'2020년 1월부터 2020년 4월까지 경제심리지수와 파일 비율 계산')['supplement']['workspaceId']
    with pytest.raises(KeyError):service.template(2,wid,'cost')
    with pytest.raises(KeyError):service.upload(2,wid,'cost','cost.csv',csv_text())
    with pytest.raises(KeyError):service.load(1,'../../x')
    with pytest.raises(DerivedValidationError):service.upload(1,wid,'cost','../cost.csv',csv_text())
    with pytest.raises(DerivedValidationError):service.base.catalog.get_table_metadata('USER_FILE:cost')
    with pytest.raises(DerivedValidationError):SupplementalCatalog(service.base.catalog,{}).get_table_metadata('USER_FILE:cost')

def test_http_upload_requires_owner_and_feeds_existing_output_agent(tmp_path,monkeypatch,setup):
    import bridge_api as api
    from authenticated_client import TestClient
    service,_,_,_=setup;monkeypatch.setattr(api,'derived_supplements',service)
    client=TestClient(api.app)
    r=client.post('/api/derived/supplement',json={'query':'2020년 1월부터 2020년 4월까지 경제심리지수와 사용자 비용지수의 비율 계산'})
    assert r.status_code==200,r.text
    wid=r.json()['supplement']['workspaceId']
    assert client.get(f'/api/derived/supplement/{wid}/template/cost').status_code==200
    r=client.post(f'/api/derived/supplement/{wid}/upload',json={'alias':'cost','filename':'cost.csv','content':csv_text()});assert r.status_code==200,r.text
    r=client.post(f'/api/derived/supplement/{wid}/resume',json={});assert r.status_code==200,r.text
    assert r.json()['status']=='need_output_config'
    r=client.post('/api/output',json={'session_ids':[r.json()['outputSessionId']],'chart_type':'line'});assert r.status_code==200,r.text
    assert len(r.json()['outputSpec']['table']['rows'])==4
    chart=r.json();old_hash=next(s['sha256'] for s in chart['derivedEvidence']['sourceSelections'] if s['origin']=='user_file')
    changed=client.post(f'/api/derived/supplement/{wid}/upload',json={'alias':'cost','filename':'corrected.csv','content':csv_text(value='4')})
    assert changed.status_code==200,changed.text
    assert changed.json()['supplement']['uploaded'][0]['sha256']!=old_hash
    previous=client.post('/api/output/edit',json={'edit_session_id':chart['editSessionId'],'instruction':'기간을 2020-02-01부터 2020-04-30까지로 변경해줘'})
    assert previous.status_code==200,previous.text
    pinned=next(s for s in previous.json()['derivedEvidence']['sourceSelections'] if s['origin']=='user_file')
    assert pinned['sha256']==old_hash
    assert previous.json()['outputSpec']['table']['rows'][-1]['value']==pytest.approx(66.55)

def test_zero_denominator_can_be_corrected_in_same_workspace(setup):
    service,calls,_,final=setup
    wid=service.start(1,'2020년 1월부터 2020년 4월까지 경제심리지수를 사용자 비용지수로 나눈 비율 계산')['supplement']['workspaceId']
    service.upload(1,wid,'cost','zero.csv',csv_text(value='0'))
    with pytest.raises(DerivedValidationError):service.resume(1,wid)
    assert service.load(1,wid)['last_plan'] and service.load(1,wid)['files']
    service.upload(1,wid,'cost','corrected.csv',csv_text(value='2'))
    service.base.planner.client=Model([{'action':'metadata','table_id':final['sources'][0]['table_id']},
        {'action':'plan','plan':final},{'approved':True,'reason':'corrected synthetic fixture'}])
    result=service.resume(1,wid)['result']
    assert result['execution']['rows'][-1]['DT']==pytest.approx(66.55) and len(calls)==1
    folder=service.path(1,wid).parent/'files'
    assert len(list(folder.glob('*.csv')))==2


def test_pending_upload_is_session_only_and_not_written_to_disk(setup):
    service,_,_,_=setup
    wid=service.start(1,'2020년 1월부터 4월까지 경제심리지수와 추가 비용지수 비율')['supplement']['workspaceId']
    assert not service.path(1,wid).exists()
    service.upload(1,wid,'cost','cost.csv',csv_text())
    assert service.load(1,wid)['files']['cost']['rows']
    assert not list(service.directory.rglob('*'))
    restarted=DerivedSupplementService(service.base,service.directory)
    with pytest.raises(KeyError):restarted.load(1,wid)


def test_completed_upload_keeps_reproducible_inputs_after_restart(setup):
    service,_,_,_=setup
    wid=service.start(1,'2020년 1월부터 4월까지 경제심리지수와 추가 비용지수 비율')['supplement']['workspaceId']
    service.upload(1,wid,'cost','cost.csv',csv_text())
    service.resume(1,wid)
    restarted=DerivedSupplementService(service.base,service.directory)
    assert restarted.load(1,wid)['calculation_id']
    assert len(list((service.path(1,wid).parent/'files').glob('*.csv')))==1


def test_legacy_cleanup_only_removes_unfinished_workspace_cache(tmp_path):
    pending=tmp_path/'user-1'/('a'*32);pending.mkdir(parents=True)
    (pending/'workspace.json').write_text(json.dumps({'owner':1,'id':'a'*32}),encoding='utf8')
    (pending/'revision-1.json').write_text('{}')
    completed=tmp_path/'user-1'/('b'*32);completed.mkdir()
    (completed/'workspace.json').write_text(json.dumps({'owner':1,'id':'b'*32,'calculation_id':'saved'}),encoding='utf8')
    unrelated=tmp_path/'original.csv';unrelated.write_text('keep')
    DerivedSupplementService(None,tmp_path)
    assert not pending.exists() and completed.exists() and unrelated.read_text()=='keep'


def test_pending_expiration_discards_in_memory_uploads(setup,monkeypatch):
    import derived_supplement as module
    service,_,_,_=setup
    wid=service.start(1,'2020년 1월부터 4월까지 경제심리지수와 추가 비용지수 비율')['supplement']['workspaceId']
    service.upload(1,wid,'cost','cost.csv',csv_text())
    now=module.time.time();monkeypatch.setattr(module.time,'time',lambda:now+12*3600+1)
    with pytest.raises(KeyError):service.load(1,wid)
    assert not service.pending and not service.raw_uploads
