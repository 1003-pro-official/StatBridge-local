def test_invalid_attachment_returns_small_error_without_echoing_image(tmp_path,monkeypatch):
    import base64
    import bridge_api as api
    from fastapi.testclient import TestClient
    monkeypatch.setattr(api.account_auth,'STORE',api.account_auth.AccountStore(tmp_path/'accounts.sqlite3'))
    encoded=base64.b64encode(b'not an image'*10000).decode()
    with TestClient(api.app) as http:
        login=http.post('/api/auth/login',json={'username':'test1','password':'1234'})
        assert login.status_code==200
        api.account_auth.STORE.bind('edit','validation-only',login.json()['user']['id'])
        response=http.post('/api/output/edit',json={'edit_session_id':'validation-only','instruction':'이렇게 그려줘','reference_files':[{'name':'example.png','mime':'image/png','data_url':'data:image/png;base64,'+encoded}]})
    assert response.status_code==422
    assert len(response.content)<2000
    assert encoded not in response.text
    assert response.json()['detail'][0]['loc']==['body','reference_files',0]
