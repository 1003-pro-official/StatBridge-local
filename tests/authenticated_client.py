"""Explicit login adapter for pre-authentication API regression fixtures."""
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient as BaseClient
import account_auth

class TestClient(BaseClient):
    __test__=False
    def __init__(self,app,*args,**kwargs):
        # Windows에서는 sqlite 파일이 열린 채로 남아 종료 시 정리 오류가 난다.
        self.account_temp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        account_auth.STORE=account_auth.AccountStore(Path(self.account_temp.name)/'accounts.sqlite3')
        super().__init__(app,*args,**kwargs)
        response=super().request('POST','/api/auth/login',json={'username':'test1','password':'1234'})
        assert response.status_code==200,response.text
        # Only explicitly seeded legacy fixtures receive ownership here.
        # Normal requests still use the production authentication middleware.
        import bridge_api
        for kind,sessions in (('output',bridge_api.OUTPUT_SESSIONS),('edit',bridge_api.EDIT_SESSIONS)):
            for identifier in list(sessions):
                if account_auth.STORE.owner(kind,identifier) is None:account_auth.STORE.bind(kind,identifier,1)
