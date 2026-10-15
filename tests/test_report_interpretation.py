"""Only synthetic reviewed excerpts; never private answers or research OCR gold."""
import json
from types import SimpleNamespace

from report_interpretation import build_draft, retrieve_passages
from report_summary import explain


def explanation():
    return explain([{'label':'검증 지표','frequency':'M','unit':'개','points':[{'date':'202411','value':10},{'date':'202412','value':12}]}])


def test_verified_original_passages_respect_publication_and_analysis_period(tmp_path):
    base=dict(id='p1',title='공식 설명',publication_date='2024-12-01',period_start='2024-01-01',period_end='2024-12-31',page=2,text='검증 지표가 증가했습니다.',reference='보고서.pdf#page=2',verified=True,kind='observation')
    rows=[base,{**base,'id':'future','publication_date':'2026-01-01'},
          {**base,'id':'ocr','verified':False},{**base,'id':'wrong_period','period_start':'2020-01-01','period_end':'2020-12-31'}]
    path=tmp_path/'index.jsonl';path.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows),encoding='utf-8')
    found=retrieve_passages(path,'검증 지표',start='2024-01-01',end='2024-12-31',as_of='2024-12-31')
    assert [p['id'] for p in found]==['p1']


class Model:
    configured=True
    def __init__(self,claim):self.claim=claim
    def chat_main(self,*args,**kwargs):return json.dumps({'claims':self.claim if isinstance(self.claim,list) else [self.claim]}),{}


def test_unsupported_cause_number_or_citation_falls_back_to_observations():
    for text,ids in [('정책 효과 때문에 증가했습니다.',['s0-latest']),('999개입니다.',['s0-latest']),('12개입니다.',['fake'])]:
        draft=build_draft(explanation(),'지표 설명',[],Model(dict(text=text,kind='observation',fact_ids=ids,passage_ids=[])),as_of='2024-12-31')
        assert draft['method']=='validated_observations'
        assert draft['needsHumanReview']
        assert not any('999' in c['text'] or '정책 효과' in c['text'] for c in draft['claims'])


def test_grounded_draft_records_fact_ids_and_missing_original_limit():
    claim=dict(text='최신 관측값은 12개입니다.',kind='observation',fact_ids=['s0-latest'],passage_ids=[])
    draft=build_draft(explanation(),'질문',[],Model(claim),as_of='2024-12-31')
    assert draft['method']=='grounded_model_draft'
    assert draft['claims'][0]['fact_ids']==['s0-latest']
    assert any('원문 근거가 없어' in s for s in draft['limitations'])


def test_draft_endpoint_checks_auth_revision_and_uses_current_snapshot(monkeypatch,tmp_path):
    import account_auth as auth
    import bridge_api as api
    from fastapi.testclient import TestClient
    from test_account_auth import login,fixture_graph
    store=auth.AccountStore(tmp_path/'accounts.sqlite3');monkeypatch.setattr(auth,'STORE',store)
    payload={'edit_session_id':'report-draft','revision':0}
    assert TestClient(api.app).post('/api/report/interpret',json=payload).status_code==401
    client,user=login('test1');session=fixture_graph(monkeypatch,store,user,'report-draft')
    session['sessions']=[{'period':{'start':'2024-01-01','end':'2024-12-31'}}]
    monkeypatch.setattr(api.agent.output_agent,'ncp_client',None)
    monkeypatch.setenv('STATBRIDGE_REPORT_PASSAGES',str(tmp_path/'missing.jsonl'))
    revision=session['output'].get('editVersion',0)
    assert client.post('/api/report/interpret',json={**payload,'revision':revision+1}).status_code==409
    response=client.post('/api/report/interpret',json={**payload,'revision':revision})
    assert response.status_code==200,response.text
    assert response.json()['needsHumanReview'] is True


def test_factor_uses_server_exact_quote_and_never_extends_its_period():
    passage=dict(id='p',title='공식 설명',publication_date='2024-12-24',page=2,
                 period_start='2024-07-01',period_end='2024-11-30',kind='factor',
                 text='은행의 포트폴리오 관리가 해당 기간 가산금리 조정 요인으로 작용하였습니다.')
    claim=dict(text='임의 해석은 그대로 사용하지 않습니다.',kind='factor',fact_ids=[],passage_ids=['p'],
               quote_index=0,analysis_period={'start':'2024-07-01','end':'2024-11-30'})
    observation=dict(text='최신 관측값은 12개입니다.',kind='observation',fact_ids=['s0-latest'],passage_ids=[])
    draft=build_draft(explanation(),'당시 설명',[passage],Model([observation,claim]),as_of='2024-12-31')
    assert draft['method']=='grounded_model_draft'
    assert '공식 설명(2024-12-24, PDF 2쪽)' in draft['claims'][1]['text']
    assert '임의 해석' not in draft['claims'][1]['text']
    claim['analysis_period']['end']='2024-12-31'
    rejected=build_draft(explanation(),'당시 설명',[passage],Model(claim),as_of='2024-12-31')
    assert rejected['method']=='validated_observations'


def test_numeric_formatting_does_not_reject_equal_decimal_values():
    facts={'facts':[{'id':'gap','text':'격차는 0.1 %p입니다.'}],'factIds':['gap']}
    claim=dict(text='격차는 0.10%p입니다.',kind='observation',fact_ids=['gap'],passage_ids=[])
    assert build_draft(facts,'비교',[],Model(claim),as_of='2024-12-31')['method']=='grounded_model_draft'
