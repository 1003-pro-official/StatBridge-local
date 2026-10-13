"""Local account authentication and per-account graph ownership (ai-assisted)."""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from contextvars import ContextVar
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

TTL = 12 * 60 * 60
COOKIE = os.environ.get('STATBRIDGE_COOKIE_NAME','statbridge_session')
USER = ContextVar('statbridge_account', default=None)
def allowed_origins():
    ports = {5173, 5174, 5175, 8000, 8001, 8005}
    for name in ('STATBRIDGE_UI_PORT', 'STATBRIDGE_API_PORT'):
        value = os.getenv(name, '')
        if value.isdigit() and 1 <= int(value) <= 65535:
            ports.add(int(value))
    return {f'http://{host}:{port}' for host in ('localhost', '127.0.0.1') for port in ports}


ALLOWED_ORIGINS = allowed_origins()

def digest(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

class AccountStore:
    def __init__(self, path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=RLock(); self.attempts={}
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,name TEXT,email TEXT UNIQUE,salt TEXT,password_hash TEXT);
            CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER,expires REAL);
            CREATE TABLE IF NOT EXISTS resources(kind TEXT,id TEXT,user_id INTEGER,PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS graphs(user_id INTEGER,id TEXT,title TEXT,saved_at REAL,content BLOB,PRIMARY KEY(user_id,id));
            ''')
            for username in ('test1','test2','test3'):
                if not db.execute('SELECT id FROM users WHERE username=?',(username,)).fetchone():
                    salt=secrets.token_hex(16)
                    db.execute('INSERT INTO users(username,name,email,salt,password_hash) VALUES(?,?,?,?,?)',(username,username,username+'@example.invalid',salt,digest('1234',salt)))
        self.dummy_salt=secrets.token_hex(16); self.dummy_hash=digest('invalid-password',self.dummy_salt)
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=30)
        db.row_factory=sqlite3.Row
        try:
            with db:
                yield db
        finally:
            # sqlite's transaction context commits/rolls back but does not close.
            # Close explicitly so Windows can release the database file handle.
            db.close()
    def signup(self, username, name, email, password):
        username=username.strip().lower(); name=name.strip(); email=email.strip().lower()
        if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{2,31}',username):raise HTTPException(422,'아이디는 영문 소문자·숫자 등 3~32자로 입력하세요.')
        if not name or len(name)>80 or any(ord(c)<32 for c in name):raise HTTPException(422,'이름을 확인해 주세요.')
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254:raise HTTPException(422,'이메일 형식을 확인해 주세요.')
        if not 8<=len(password)<=128:raise HTTPException(422,'가입 비밀번호는 8~128자로 입력하세요.')
        salt=secrets.token_hex(16)
        try:
            with self.connect() as db:db.execute('INSERT INTO users(username,name,email,salt,password_hash) VALUES(?,?,?,?,?)',(username,name,email,salt,digest(password,salt)))
        except sqlite3.IntegrityError:raise HTTPException(409,'이미 사용 중인 아이디 또는 이메일입니다.')
    def login(self, username, password, ip):
        username=username.strip().lower(); key=(ip,username); now=time.time()
        with self.lock:
            for old in list(self.attempts):
                if now-self.attempts[old][0]>900:del self.attempts[old]
            started,count=self.attempts.get(key,(now,0))
            if count>=10:raise HTTPException(429,'로그인 시도가 많습니다. 15분 후 다시 시도해 주세요.')
            self.attempts[key]=(started,count+1)
        with self.connect() as db:
            row=db.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
            hashed=digest(password,row['salt'] if row else self.dummy_salt)
            if not hmac.compare_digest(hashed,row['password_hash'] if row else self.dummy_hash):raise HTTPException(401,'아이디 또는 비밀번호를 확인해 주세요.')
            token=secrets.token_urlsafe(32); expires=now+TTL
            db.execute('DELETE FROM sessions WHERE expires<=?',(now,))
            db.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),row['id'],expires))
        with self.lock:self.attempts.pop(key,None)
        return token,expires
    def account(self, token):
        if not token:return None
        with self.connect() as db:
            row=db.execute('SELECT u.id,u.username,u.name,u.email,s.expires FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        return dict(row) if row else None
    def logout(self, token):
        with self.connect() as db:db.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256((token or '').encode()).hexdigest(),))
    def owner(self, kind, identifier):
        with self.connect() as db:row=db.execute('SELECT user_id FROM resources WHERE kind=? AND id=?',(kind,identifier)).fetchone()
        return row[0] if row else None
    def bind(self, kind, identifier, user_id):
        with self.connect() as db:db.execute('INSERT OR IGNORE INTO resources VALUES(?,?,?)',(kind,identifier,user_id))
    def save_graph(self,user_id,identifier,title,content,commit_file=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            exists=db.execute('SELECT 1 FROM graphs WHERE user_id=? AND id=?',(user_id,identifier)).fetchone()
            if not exists and db.execute('SELECT COUNT(*) FROM graphs WHERE user_id=?',(user_id,)).fetchone()[0]>=5:raise HTTPException(409,'그래프는 계정당 최대 5개입니다. 저장 목록에서 기존 그래프를 삭제한 뒤 저장하세요.')
            db.execute('INSERT INTO graphs VALUES(?,?,?,?,?) ON CONFLICT(user_id,id) DO UPDATE SET title=excluded.title,saved_at=excluded.saved_at,content=excluded.content',(user_id,identifier,title,time.time(),content))
            if commit_file:commit_file()
    def graphs(self,user_id):
        with self.connect() as db:return [dict(r) for r in db.execute('SELECT id,title,saved_at FROM graphs WHERE user_id=? ORDER BY saved_at DESC',(user_id,))]
    def graph_content(self,user_id,identifier):
        with self.connect() as db:row=db.execute('SELECT content FROM graphs WHERE user_id=? AND id=?',(user_id,identifier)).fetchone()
        return row[0] if row else None
    def delete_graph(self,user_id,identifier):
        with self.connect() as db:
            cursor=db.execute('DELETE FROM graphs WHERE user_id=? AND id=?',(user_id,identifier))
            if not cursor.rowcount:raise HTTPException(404,'저장한 그래프를 찾을 수 없습니다.')

STORE=None
def current_user():
    user=USER.get()
    if not user:raise HTTPException(401,'로그인이 필요합니다.')
    return user

class Login(BaseModel):
    username:str=Field(min_length=1,max_length=32)
    password:str=Field(min_length=1,max_length=128)
class Signup(Login):
    name:str=Field(min_length=1,max_length=80)
    email:str=Field(min_length=3,max_length=254)

def install(app,root,output_sessions,edit_sessions):
    global STORE
    STORE=AccountStore(os.environ.get('STATBRIDGE_AUTH_DB',str(Path(root)/'.venv/cache/accounts.sqlite3')))

    @app.middleware('http')
    async def protect(request:Request,call_next):
        path=request.url.path
        if request.method=='OPTIONS' or not path.startswith('/api/'):return await call_next(request)
        origin=request.headers.get('origin')
        if request.method not in ('GET','HEAD') and origin and origin not in ALLOWED_ORIGINS:return JSONResponse({'detail':'허용되지 않은 요청 출처입니다.'},403)
        user=STORE.account(request.cookies.get(COOKIE))
        public={'/api/health','/api/auth/login','/api/auth/signup','/api/auth/me','/api/auth/logout'}
        if path not in public and not user:return JSONResponse({'detail':'로그인이 만료되었거나 필요합니다. 다시 로그인해 주세요.'},401)
        references=[]
        if path.startswith('/api/workspace/'):references.append(('edit',path.split('/')[3]))
        if path.startswith('/api/account/graphs/'):
            identifier=path.split('/')[4]
            if not user or not STORE.graph_content(user['id'],identifier):return JSONResponse({'detail':'저장한 그래프를 찾을 수 없습니다.'},404)
        if path not in public and request.method=='POST':
            try:body=await request.json()
            except (ValueError,UnicodeDecodeError):body={}
            if isinstance(body,dict):
                if body.get('edit_session_id'):references.append(('edit',body['edit_session_id']))
                for field in ('session_ids','append_session_ids','replace_session_ids'):
                    value=body.get(field,[])
                    if isinstance(value,list):references.extend(('output',v) for v in value)
        for kind,identifier in references:
            if not isinstance(identifier,str) or not user or STORE.owner(kind,identifier)!=user['id']:return JSONResponse({'detail':'요청한 그래프 또는 조회 세션을 찾을 수 없습니다.'},404)
        context=USER.set(user)
        try:
            response=await call_next(request)
            if user and response.status_code==200:
                for kind,sessions in (('output',output_sessions),('edit',edit_sessions)):
                    # Sessions created by this request carry an explicit owner.
                    for identifier,item in list(sessions.items()):
                        if item.get('account_id')==user['id']:STORE.bind(kind,identifier,user['id'])
            return response
        finally:USER.reset(context)

    @app.post('/api/auth/signup')
    def signup(payload:Signup):
        STORE.signup(payload.username,payload.name,payload.email,payload.password)
        return {'status':'created'}
    @app.post('/api/auth/login')
    def login(payload:Login,request:Request,response:Response):
        token,expires=STORE.login(payload.username,payload.password,request.client.host if request.client else 'unknown')
        response.set_cookie(COOKIE,token,max_age=TTL,httponly=True,samesite='lax',secure=request.url.scheme=='https',path='/')
        return {'user':STORE.account(token),'expires_at':expires}
    @app.get('/api/auth/me')
    def me(request:Request):
        user=STORE.account(request.cookies.get(COOKIE))
        if not user:raise HTTPException(401,'로그인이 필요합니다.')
        return {'user':user,'expires_at':user['expires']}
    @app.post('/api/auth/logout')
    def logout(request:Request,response:Response):
        STORE.logout(request.cookies.get(COOKIE));response.delete_cookie(COOKIE,path='/')
        return {'status':'logged_out'}
    @app.get('/api/account/graphs')
    def graphs():return {'items':STORE.graphs(current_user()['id']),'limit':5}
    @app.delete('/api/account/graphs/{identifier}')
    def delete_graph(identifier:str):
        STORE.delete_graph(current_user()['id'],identifier)
        from bridge_api import _saved_workspace_path
        _saved_workspace_path(identifier).unlink(missing_ok=True)
        return {'status':'deleted'}
