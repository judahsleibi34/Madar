"""Loopback Auth/Storage-compatible HTTP fixture backed by disposable PG/files.

This is not production GoTrue/S3 acceptance. Auth sessions, refresh tokens,
storage metadata and provider bytes are independently observable in tests.
"""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path, PurePosixPath
import threading
import time
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import httpx
import jwt

from tests.disposable_database_support import connect_disposable_database


class ProviderFixture:
    def __init__(self, root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.fail_storage=None;self.fail_auth=None;self.fail_complete_ack=False;self.fail_storage_list=False;self.storage_removes=0;self.auth_removes=0;self.storage_upload_attempts=0
        self.dsn=os.environ['DELETION_FENCING_SYNTHETIC_DATABASE_DSN']
        self.rest=os.environ['DELETION166_REST_URL']
        self.key=os.environ['DELETION166_SERVICE_JWT'];self.secret=os.environ['DELETION166_JWT_SECRET']
        fixture=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_args):pass
            def do_GET(self):self.handle_request()
            def do_POST(self):self.handle_request()
            def do_PUT(self):self.handle_request()
            def do_DELETE(self):self.handle_request()
            def do_PATCH(self):self.handle_request()
            def send_body(self,status,value,headers=None):
                body=json.dumps(value,default=str).encode() if not isinstance(value,bytes) else value
                self.send_response(status)
                for name,val in (headers or {}).items():
                    if name.lower() not in {'content-length','connection','transfer-encoding','server','date'}:self.send_header(name,val)
                self.send_header('Content-Length',str(len(body)));self.send_header('Content-Type','application/json')
                self.end_headers();self.wfile.write(body)
            def handle_request(self):
                size=int(self.headers.get('Content-Length','0'))
                if size>2*1024*1024:return self.send_body(413,{'error':'fixture_body_limit'})
                raw=self.rfile.read(size);path=urlsplit(self.path).path
                if path.startswith('/rest/v1/'):
                    with httpx.Client(trust_env=False,timeout=15) as proxy:
                        response=proxy.request(self.command,fixture.rest+self.path[len('/rest/v1'):],headers={k:v for k,v in self.headers.items() if k.lower() not in {'host','content-length','connection'}},content=raw)
                    if fixture.fail_complete_ack and path.endswith('/rpc/complete_account_erasure167') and response.is_success:
                        fixture.fail_complete_ack=False
                        return self.send_body(503,{'message':'Lost completion acknowledgement'})
                    return self.send_body(response.status_code,response.content,response.headers)
                if path.startswith('/storage/v1/object/') and self.command=='POST' and not path.startswith('/storage/v1/object/list/'):
                    if self.headers.get('Authorization')!='Bearer '+fixture.key:return self.send_body(403,{'message':'Service authority required'})
                    fixture.storage_upload_attempts+=1
                    bucket,_,key=unquote(path[len('/storage/v1/object/'):]).partition('/')
                    content=raw
                    if self.headers.get('Content-Type','').startswith('multipart/'):
                        from email.parser import BytesParser
                        from email.policy import default
                        message=BytesParser(policy=default).parsebytes(('Content-Type: '+self.headers['Content-Type']+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+raw)
                        content=next(part.get_payload(decode=True) for part in message.iter_parts() if part.get_param('name',header='content-disposition')=='file')
                    target=fixture.safe_path(bucket,key)
                    if target.exists():return self.send_body(409,{'message':'Object exists'})
                    try:
                        with fixture.connect() as db:
                            owner=db.execute('select u.auth_id from public.storage_objects r join public.users u on u.id=r.user_id where r.storage_bucket=%s and r.provider_object_key=%s',(bucket,key)).fetchone()
                            db.execute('insert into storage.objects(bucket_id,name,owner_id) values(%s,%s,%s)',(bucket,key,owner[0] if owner else None))
                        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
                    except Exception:return self.send_body(409,{'message':'account_provider_frozen'})
                    return self.send_body(200,{'Key':bucket+'/'+key})
                try:body=json.loads(raw) if raw else {}
                except ValueError:return self.send_body(400,{'error':'invalid_fixture_json'})
                if path=='/auth/v1/token':
                    with fixture.connect() as db:
                        if 'grant_type=refresh_token' in self.path:
                            user=db.execute('select u.id,u.email,u.banned_until from auth.refresh_tokens r join auth.users u on u.id=r.user_id where r.token=%s',(body.get('refresh_token'),)).fetchone()
                        else:
                            user=db.execute('select id,email,banned_until from auth.users where email=%s',(body.get('email'),)).fetchone() if body.get('password')=='fixture-password' else None
                        if not user or user[2] and user[2]>datetime.now(timezone.utc):return self.send_body(400,{'msg':'Account unavailable','error_code':'invalid_credentials'})
                        sid=uuid4();refresh=str(uuid4());db.execute('insert into auth.sessions(id,user_id) values(%s,%s)',(sid,user[0]));db.execute('insert into auth.refresh_tokens(token,user_id,session_id) values(%s,%s,%s)',(refresh,user[0],sid))
                        token=jwt.encode({'role':'authenticated','sub':str(user[0]),'session_id':str(sid),'exp':int(time.time())+3600},fixture.secret,algorithm='HS256')
                    return self.send_body(200,{'access_token':token,'refresh_token':refresh,'token_type':'bearer','expires_in':3600,'user':fixture.user_payload(user[0],user[1])})
                if path=='/auth/v1/user':
                    try:claims=jwt.decode(self.headers.get('Authorization','').removeprefix('Bearer '),fixture.secret,algorithms=['HS256'])
                    except Exception:return self.send_body(401,{'msg':'Invalid token'})
                    with fixture.connect() as db:user=db.execute('select id,email from auth.users where id=%s',(claims['sub'],)).fetchone()
                    return self.send_body(200,fixture.user_payload(*user)) if user else self.send_body(404,{'msg':'User not found','error_code':'user_not_found'})
                if self.headers.get('Authorization')!='Bearer '+fixture.key:return self.send_body(403,{'msg':'Service authority required'})
                if path.startswith('/auth/v1/admin/users/'):
                    uid=path.rsplit('/',1)[-1]
                    with fixture.connect() as db:
                        user=db.execute('select id,email from auth.users where id=%s',(uid,)).fetchone()
                        if not user:return self.send_body(404,{'msg':'User not found','error_code':'user_not_found'})
                        if self.command=='DELETE':
                            fixture.auth_removes+=1
                            mode=fixture.fail_auth;fixture.fail_auth=None
                            if mode=='before':return self.send_body(503,{'msg':'Uncertain provider failure'})
                            if db.execute('select count(*) from storage.objects where owner_id=%s',(uid,)).fetchone()[0]:return self.send_body(409,{'msg':'Storage objects remain'})
                            db.execute('delete from auth.users where id=%s',(uid,))
                            if mode=='after':return self.send_body(503,{'msg':'Lost acknowledgement'})
                    return self.send_body(200,fixture.user_payload(*user))
                if path.startswith('/storage/v1/object/list/'):
                    if fixture.fail_storage_list:
                        fixture.fail_storage_list=False;return self.send_body(503,{'message':'Temporary verification unavailable'})
                    bucket=unquote(path.rsplit('/',1)[-1]);prefix=body.get('prefix','');folder=fixture.safe_path(bucket,prefix)
                    entries=[]
                    if folder.exists():
                        entries=[{'name':p.name,'id':str(uuid4()),'metadata':{'size':p.stat().st_size}} for p in folder.iterdir() if p.is_file() and body.get('search','') in p.name]
                    entries.sort(key=lambda x:x['name']);offset=int(body.get('offset',0));limit=min(100,int(body.get('limit',100)))
                    return self.send_body(200,entries[offset:offset+limit])
                if path.startswith('/storage/v1/object/') and self.command=='DELETE':
                    bucket=unquote(path[len('/storage/v1/object/'):]);fixture.storage_removes+=1
                    mode=fixture.fail_storage;fixture.fail_storage=None
                    if mode=='before':return self.send_body(503,{'message':'Uncertain provider failure'})
                    removed=[]
                    for key in body.get('prefixes',[]):
                        fixture.safe_path(bucket,key).unlink(missing_ok=True)
                        with fixture.connect() as db:db.execute('delete from storage.objects where bucket_id=%s and name=%s',(bucket,key))
                        removed.append({'name':key})
                    if mode=='after':return self.send_body(503,{'message':'Lost acknowledgement'})
                    return self.send_body(200,removed)
                return self.send_body(404,{'error':'fixture_route_unavailable'})
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_address[1]}'

    def connect(self):
        return connect_disposable_database(self.dsn,markers={'madar-notification-synthetic-rehearsal'})
    def user_payload(self,uid,email):
        return {'id':str(uid),'email':email,'aud':'authenticated','role':'authenticated','app_metadata':{},'user_metadata':{},'created_at':'2026-01-01T00:00:00Z','email_confirmed_at':'2026-01-01T00:00:00Z'}
    def safe_path(self,bucket,key):
        if not bucket or '/' in bucket or bucket in {'.','..'}:raise ValueError('unsafe fixture bucket')
        parts=PurePosixPath(key).parts
        if key.startswith('/') or '..' in parts or '\\' in key:raise ValueError('unsafe fixture path')
        return self.root/bucket/key
    def put_object(self,bucket,key,content,owner):
        path=self.safe_path(bucket,key)
        with self.connect() as db:
            db.execute('insert into storage.buckets(id,name) values(%s,%s) on conflict do nothing',(bucket,bucket))
            db.execute('insert into storage.objects(bucket_id,name,owner_id) values(%s,%s,%s)',(bucket,key,owner))
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
        return path
    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)
