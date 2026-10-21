import copy,json
from decimal import Decimal
import pytest
import account_auth as auth
import bridge_api as api
from test_account_auth import login,fixture_graph

@pytest.fixture
def setup(monkeypatch,tmp_path):
    store=auth.AccountStore(tmp_path/'accounts.sqlite3');monkeypatch.setattr(auth,'STORE',store)
    client,user=login('test1');session=fixture_graph(monkeypatch,store,user,'report-dialog-test')
    class NoModel:
        configured=True
        def request(self,*a,**k):raise AssertionError('unnecessary GPT')
    monkeypatch.setattr(api.agent.output_agent,'ncp_client',NoModel())
    return client,session,store


def ask(client,q,revision=0,version=None):
    return client.post('/api/report/question',json={'edit_session_id':'report-dialog-test','revision':revision,'question':q,'conversational':True,'conversation_version':version})


def test_private_history_and_followup_recomputed_after_graph_change(setup):
    client,session,store=setup
    other,_=login('test2')
    assert other.get('/api/report/conversation/report-dialog-test').status_code==404
    assert other.post('/api/report/question',json={'edit_session_id':'report-dialog-test','revision':0,'question':'그래프 변화를 설명해줘','conversational':True}).status_code==404
    first=ask(client,'그래프 변화를 설명해줘').json()
    assert len(first['conversation']['turns'])==1 and first['modelCalls']==0
    second=ask(client,'그중 가장 많이 상승한 것은?',version=1).json()
    assert len(second['conversation']['turns'])==2 and second['modelCalls']==0
    old=Decimal(second['facts'][0]['result'])
    session['result']['execution']['rows'][-1]['DT']='34'
    session['output']['editVersion']=1
    history=client.get('/api/report/conversation/report-dialog-test').json()
    assert history['revision']==1 and len(history['turns'])==2
    assert Decimal(history['turns'][-1]['answer']['facts'][0]['result'])!=old
    assert all(t['verifiedRevision']==1 for t in history['turns'])
    assert ask(client,'표로 정리해줘',revision=0).status_code==409
    assert ask(client,'표로 정리해줘',revision=1,version=1).status_code==409
    third=ask(client,'표로 정리해줘',revision=1,version=2)
    assert third.status_code==200,third.text
    assert third.json()['table']['rows']
    assert len(client.get('/api/report/conversation/report-dialog-test').json()['turns'])==3


def test_provider_error_does_not_erase_conversation_or_invent_missing_data(setup,monkeypatch):
    client,session,store=setup
    ask(client,'그래프 변화를 설명해줘')
    before=copy.deepcopy(session['report_conversation'])
    response=ask(client,'생소하고 자유로운 표현으로 요청하기')
    assert response.status_code==503
    assert session['report_conversation']==before
    assert '자료가 없' not in str(response.json())


def test_race_with_graph_edit_rejects_uncommitted_answer(setup,monkeypatch):
    client,session,store=setup
    from report_conversation import reply
    def racing(*a,**k):
        result=reply(*a,**k);session['output']['editVersion']=1;return result
    monkeypatch.setattr('report_conversation.reply',racing)
    assert ask(client,'그래프 변화를 설명해줘').status_code==409
    assert 'report_conversation' not in session


def test_race_between_questions_does_not_overwrite_first_answer(setup,monkeypatch):
    client,session,store=setup
    ask(client,'그래프 변화를 설명해줘')
    from report_conversation import reply
    def racing(*a,**k):
        result=reply(*a,**k);session['report_conversation']['version']+=1;return result
    monkeypatch.setattr('report_conversation.reply',racing)
    assert ask(client,'표로 정리해줘',version=1).status_code==409
    assert len(session['report_conversation']['turns'])==1


def test_saved_analysis_restores_report_conversation_with_same_owner(setup,monkeypatch,tmp_path):
    client,session,store=setup
    monkeypatch.setattr(api,'_saved_workspace_path',lambda identifier:tmp_path/(identifier+'.json.gz'))
    ask(client,'그래프 변화를 설명해줘')
    response=client.post('/api/workspace/report-dialog-test/save',json={'edit_session_id':'report-dialog-test','revision':0,'format':'json'})
    assert response.status_code==200,response.text
    monkeypatch.delitem(api.EDIT_SESSIONS,'report-dialog-test')
    loaded=client.get('/api/workspace/report-dialog-test')
    assert loaded.status_code==200,loaded.text
    restored=client.get('/api/report/conversation/report-dialog-test')
    assert restored.status_code==200 and restored.json()['turns'][0]['question']=='그래프 변화를 설명해줘'
    follow=ask(client,'그중 가장 많이 상승한 것은?',version=1)
    assert follow.status_code==200 and follow.json()['modelCalls']==0

def test_markdown_collection_order_privacy_revision_and_refresh(setup):
    client,session,store=setup
    ask(client,'그래프 변화를 설명해줘')
    ask(client,'그중 가장 많이 상승한 것은?',version=1)
    payload={'edit_session_id':'report-dialog-test','revision':0}
    other,_=login('test2')
    for route in ['append','export']:
        assert other.post('/api/report/markdown/'+route,json={**payload,'turn_id':1}).status_code==404
    for turn in [2,1,2]:
        response=client.post('/api/report/markdown/append',json={**payload,'turn_id':turn})
        assert response.status_code==200,response.text
    entries=client.get('/api/report/conversation/report-dialog-test').json()['markdownEntries']
    assert [e['turnId'] for e in entries]==[2,1]
    exported=client.post('/api/report/markdown/export',json=payload)
    assert exported.status_code==200 and 'text/markdown' in exported.headers['content-type']
    assert exported.text.count('## ')==2
    ask(client,'표로 정리해줘',version=2)
    assert len(client.get('/api/report/conversation/report-dialog-test').json()['markdownEntries'])==2
    session['output']['editVersion']=1
    refreshed=client.get('/api/report/conversation/report-dialog-test').json()
    assert refreshed['markdownEntries']==entries
    assert client.post('/api/report/markdown/append',json={**payload,'turn_id':1}).status_code==409
