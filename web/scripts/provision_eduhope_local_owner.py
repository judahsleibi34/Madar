#!/usr/bin/env python3
"""Provision only a fictional isolated local owner via native email verification."""
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import dotenv_values
import argparse
import html
import json
import re
import secrets
import time
import psycopg
import requests

FOLDER=Path('/tmp/madar-eduhope-preview')
API='http://127.0.0.1:8010'
ORIGIN='http://127.0.0.1:5180'


def save_private(path,record):
    import os
    descriptor=os.open(path,os.O_CREAT|os.O_WRONLY|os.O_TRUNC,0o600)
    with os.fdopen(descriptor,'w') as out:json.dump(record,out)
    path.chmod(0o600)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--provision',action='store_true');args=parser.parse_args()
    if not args.provision:print('Dry-run: native local signup → actual Mailpit verification → native login/provisioning.');return
    env=dotenv_values(FOLDER/'backend.env')
    assert env['APP_ENV']=='development' and env['SUPABASE_URL']=='http://127.0.0.1:55440'
    with psycopg.connect(env['SUPABASE_DB_URL']) as db:
        db.execute('set transaction read only')
        assert db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()").fetchone()[0]=='madar-eduhope-local-preview-v1'
    credential_file=FOLDER/'owner-credentials.json'
    s=requests.Session();s.headers['Origin']=ORIGIN
    if credential_file.exists():
        record=json.loads(credential_file.read_text());assert record['demo_only'] and record['logical_academy']=='eduhope'
    else:
        record={'email':'eduhope-owner-'+secrets.token_hex(3)+'@example.com','password':secrets.token_urlsafe(26)+'!9aZ','logical_academy':'eduhope','demo_only':True}
        r=s.post(API+'/auth/signup',json={**{k:record[k] for k in ['email','password']},'first_name':'Local','last_name':'Owner','business_name':'EduHope local preview','business_type':'Education','subdomain':'eduhope-local','terms_accepted':True},timeout=30)
        if r.status_code!=200:raise RuntimeError('Local signup failed:'+str(r.status_code))
        save_private(credential_file,record)
    r=s.post(API+'/auth/login',json={k:record[k] for k in ['email','password']},timeout=30)
    if not r.ok:
        r=requests.post(env['SUPABASE_URL']+'/auth/v1/resend',headers={'apikey':env['SUPABASE_ANON_KEY']},json={'type':'signup','email':record['email']},timeout=15)
        if not r.ok:raise RuntimeError('Local verification resend failed')
        link=None
        for _ in range(20):
            messages=requests.get('http://127.0.0.1:54324/api/v1/messages',timeout=5).json()
            for item in messages.get('messages',[]):
                if not any(person.get('Address')==record['email'] for person in item.get('To',[])):continue
                msg=requests.get('http://127.0.0.1:54324/api/v1/message/'+item['ID'],timeout=5).json()
                for candidate in re.findall(r'https?://[^\s"<>]+',html.unescape(msg.get('HTML','')+'\n'+msg.get('Text',''))):
                    u=urlsplit(candidate)
                    if u.hostname=='127.0.0.1' and u.port==55440 and u.path=='/auth/v1/verify':link=candidate;break
                if link:break
            if link:break
            time.sleep(1)
        if not link:raise RuntimeError('Correct isolated verification email not received; check configured Auth mailer URL paths')
        r=requests.get(link,allow_redirects=False,timeout=15)
        if r.status_code not in (302,303):raise RuntimeError('Actual local email verification failed')
        r=s.post(API+'/auth/login',json={k:record[k] for k in ['email','password']},timeout=30)
    if not r.ok:raise RuntimeError('Verified native login failed:'+str(r.status_code))
    with psycopg.connect(env['SUPABASE_DB_URL']) as db:
        db.execute('set transaction read only')
        row=db.execute("select u.id,u.tenant_id from public.users u join public.tenant_memberships m on(m.tenant_id,m.user_id,m.auth_id)=(u.tenant_id,u.id,u.auth_id) where u.email=%s and u.email_verified and u.account_status='active' and m.role='owner' and m.status='active'",(record['email'],)).fetchone()
        if not row:raise RuntimeError('Native owner provisioning not complete')
        record.update(user_id=row[0],tenant_id=row[1])
    save_private(credential_file,record);save_private(FOLDER/'owner-cookies.json',requests.utils.dict_from_cookiejar(s.cookies))
    print('Native local owner provisioned and verified. Tenant:',record['tenant_id'],'. Private access file:',credential_file)


if __name__=='__main__':main()
