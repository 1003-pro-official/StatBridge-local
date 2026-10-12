import hashlib
import time
import pytest
from fastapi.testclient import TestClient
import account_auth as auth
import bridge_api as api
from test_chart_edit_period_and_box import fixture_session

@pytest.fixture
def store(monkeypatch,tmp_path):
    instance=auth.AccountStore(tmp_path/'accounts.sqlite3')
    monkeypatch.setattr(auth,'STORE',instance)
    monkeypatch.setattr(api,'_saved_workspace_path',lambda identifier:tmp_path/(identifier+'.json.gz'))
    return instance

def login(username):
    client=TestClient(api.app)
    r=client.post('/api/auth/login',json={'username':username,'password':'1234'})
    assert r.status_code==200,r.text
    cookie=r.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=lax' in cookie and 'max-age=43200' in cookie
    return client,r.json()['user']

def fixture_graph(monkeypatch,store,user,identifier):
    _,session=fixture_session()
    session['account_id']=user['id']
    monkeypatch.setitem(api.EDIT_SESSIONS,identifier,session)
    store.bind('edit',identifier,user['id'])
    return session

def test_login_signup_expiry_logout_and_password_hash(store,monkeypatch):
    client=TestClient(api.app)
    assert client.get('/api/catalog').status_code==401
    assert client.post('/api/auth/login',json={'username':'test1','password':'wrong'}).status_code==401
    client,user=login('test1')
    assert 43190<=user['expires']-time.time()<=43200
    assert client.get('/api/auth/me').status_code==200
    token=client.cookies.get(auth.COOKIE)
    with store.connect() as db:
        row=db.execute("SELECT password_hash FROM users WHERE username='test1'").fetchone()
        assert row[0]!='1234' and len(row[0])==128
        db.execute('UPDATE sessions SET expires=? WHERE token_hash=?',(time.time()-1,hashlib.sha256(token.encode()).hexdigest()))
    assert client.get('/api/auth/me').status_code==401
    assert client.get('/api/catalog').status_code==401
    signup={'username':'new-user','name':'가입 검증','email':'signup@example.invalid','password':'password123'}
    assert client.post('/api/auth/signup',json=signup).status_code==200
    assert client.post('/api/auth/signup',json=signup).status_code==409
    assert client.post('/api/auth/signup',json={**signup,'username':'other','email':'bad','password':'1234'}).status_code==422
    assert client.post('/api/auth/login',json={'username':'new-user','password':'password123'}).status_code==200
    assert client.post('/api/auth/logout').status_code==200
    assert client.get('/api/account/graphs').status_code==401
    denied=client.post('/api/auth/login',headers={'Origin':'https://untrusted.example'},json={'username':'test1','password':'1234'})
    assert denied.status_code==403

def test_graph_limit_and_cross_account_idor(store,monkeypatch):
    one,u1=login('test1');two,u2=login('test2');three,u3=login('test3')
    monkeypatch.setattr(api,'_table_card',lambda table:{'tableId':table})
    for index in range(6):
        identifier=f'private-{index}';fixture_graph(monkeypatch,store,u1,identifier)
        r=one.post(f'/api/workspace/{identifier}/save',json={'edit_session_id':identifier,'format':'json','revision':0})
        assert r.status_code==(200 if index<5 else 409),r.text
    assert len(one.get('/api/account/graphs').json()['items'])==5
    assert one.post('/api/workspace/private-0/save',json={'edit_session_id':'private-0','format':'json','revision':0}).status_code==200
    assert two.get('/api/account/graphs').json()['items']==[]
    assert three.get('/api/account/graphs').json()['items']==[]
    for foreign in (two,three):
        for path,body in [('/api/output/edit',{'edit_session_id':'private-0','commands':[{'operation':'set_title','kind':'STYLE_EDIT','value':'공격'}]}),('/api/report/export',{'edit_session_id':'private-0','format':'json'}),('/api/report/recommend',{'edit_session_id':'private-0','format':'json'}),('/api/workspace/private-0/save',{'edit_session_id':'private-0','format':'json'})]:
            assert foreign.post(path,json=body).status_code==404
        assert foreign.get('/api/workspace/private-0').status_code==404
        assert foreign.delete('/api/account/graphs/private-0').status_code==404
    store.bind('output','owned-query',u1['id'])
    assert two.post('/api/output',json={'session_ids':['owned-query'],'chart_type':'line'}).status_code==404
    assert two.post('/api/output/options',json={'session_ids':['owned-query']}).status_code==404
    assert two.post('/api/output/edit',json={'edit_session_id':'private-0','append_session_ids':['owned-query']}).status_code==404
    assert one.get('/api/workspace/private-0').status_code==200
    assert one.delete('/api/account/graphs/private-0').status_code==200
    assert len(one.get('/api/account/graphs').json()['items'])==4
    assert one.post('/api/workspace/private-5/save',json={'edit_session_id':'private-5','format':'json','revision':0}).status_code==200

def test_owner_registry_and_sessions_survive_store_restart(store):
    token,_=store.login('test1','1234','test')
    user=store.account(token);store.bind('edit','persisted',user['id'])
    restored=auth.AccountStore(store.path)
    assert restored.account(token)['id']==user['id']
    assert restored.owner('edit','persisted')==user['id']

def test_failed_file_commit_does_not_consume_save_slot(store):
    def fail():raise OSError('test-only storage failure')
    with pytest.raises(OSError):store.save_graph(1,'failed','제목',b'hash',fail)
    assert store.graphs(1)==[]

def test_concurrent_saves_cannot_exceed_five_per_account(store):
    from concurrent.futures import ThreadPoolExecutor
    from fastapi import HTTPException
    def save(index):
        try:store.save_graph(1,f'parallel-{index}','제목',b'hash');return 200
        except HTTPException as exc:return exc.status_code
    with ThreadPoolExecutor(max_workers=8) as pool:statuses=list(pool.map(save,range(8)))
    assert statuses.count(200)==5 and statuses.count(409)==3
    store.save_graph(2,'independent','다른 계정',b'hash')
    assert len(store.graphs(1))==5 and len(store.graphs(2))==1
