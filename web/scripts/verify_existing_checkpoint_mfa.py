#!/usr/bin/env python3
"""Verify original MFA factors only in NEW disposable restored targets.

Original customer passwords are not known or used. A private restored account's
password is replaced temporarily in memory-scoped test targets, then its exact
original verifier is restored. Factor secrets never leave the test process or
appear in evidence. No production auth state or customer database is changed.
"""
import json
import re
import signal
from pathlib import Path
import secrets
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.verify_restored_native_platform import execute,fetch,require,totp
from scripts.restore_coordinated_checkpoint import psql,run,IMAGE


def existing_factors(db,endpoints,config):
    require(re.fullmatch('madar-checkpoint-native-[0-9a-f]{12}-db',db) is not None,'existing_checkpoint_private_target_required')
    row=json.loads(run(['docker','inspect',db]))[0]
    source=json.loads(run(['docker','inspect','supabase-db']))[0]
    require(row['Id']!=source['Id'] and row['Image']==IMAGE and row['HostConfig']['ReadonlyRootfs'] is True
        and not any(row['NetworkSettings']['Ports'].values()) and set(row['NetworkSettings']['Networks'])=={db[:-3]+'-network'},
        'existing_checkpoint_private_target_required')
    factors=json.loads(psql(db,"SELECT COALESCE(jsonb_agg(jsonb_build_object('factor_id',f.id,'user_id',u.id,'secret',f.secret,'email',u.email,'password_verifier',u.encrypted_password)),'[]') FROM auth.mfa_factors f JOIN auth.users u ON u.id=f.user_id WHERE f.factor_type='totp' AND f.status='verified';"))
    require(len(factors)==2,'existing_checkpoint_factor_inventory_changed')
    admin={'apikey':config['SERVICE_ROLE_KEY'],'Authorization':'Bearer '+config['SERVICE_ROLE_KEY']}
    verified=0
    for factor in factors:
        identifier=factor['user_id'];password=secrets.token_urlsafe(32)
        try:
            status,_,_=fetch(endpoints['auth']+'/admin/users/'+identifier,headers=admin,method='PUT',body={'password':password})
            require(status==200,'existing_checkpoint_private_password_setup_failed')
            status,_,body=fetch(endpoints['auth']+'/token?grant_type=password',headers={'apikey':config['ANON_KEY']},body={'email':factor['email'],'password':password})
            require(status==200,'existing_checkpoint_private_account_login_failed');session=json.loads(body)
            headers={'apikey':config['ANON_KEY'],'Authorization':'Bearer '+session['access_token']}
            prefix=endpoints['auth']+'/factors/'+factor['factor_id']
            status,_,body=fetch(prefix+'/challenge',headers=headers,body={})
            require(status==200,'existing_checkpoint_original_factor_challenge_failed');challenge=json.loads(body)
            status,_,body=fetch(prefix+'/verify',headers=headers,body={'challenge_id':challenge['id'],'code':totp(factor['secret'])})
            require(status==200,'existing_checkpoint_original_factor_verify_failed');session=json.loads(body)
            import base64
            segment=session['access_token'].split('.')[1];claims=json.loads(base64.urlsafe_b64decode(segment+'='*((-len(segment))%4)))
            require(claims.get('sub')==identifier and claims.get('aal')=='aal2','existing_checkpoint_original_factor_aal2_failed')
            verified+=1
        finally:
            # Only the NEW disposable database. No SQL is issued against source.
            quote=lambda value:"'"+str(value).replace("'","''")+"'"
            psql(db,'UPDATE auth.users SET encrypted_password='+quote(factor['password_verifier'])+' WHERE id='+quote(identifier)+';')
    require(psql(db,'SELECT count(*) FROM auth.mfa_factors;')=='2','existing_checkpoint_original_factors_changed')
    return {'original_verified_factors_exercised':verified,'original_factor_aal2_verified':True,
        'original_password_verifiers_restored_in_private_copy':True,'customer_passwords_used':False,
        'production_authentication_attempted':False,'production_modified':False,'secrets_recorded':False}

if __name__=='__main__':
    def expired(*args):raise RuntimeError('existing_checkpoint_mfa_deadline')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,600)
    try:
        report=execute(existing_mfa_verifier=existing_factors)
        print(json.dumps(report))
    except Exception as error:
        print(json.dumps({'status':'failed','exception_type':type(error).__name__,
            'category':str(error) if type(error) is RuntimeError else 'existing_checkpoint_mfa_failed'}))
        raise SystemExit(1)
    finally:signal.setitimer(signal.ITIMER_REAL,0)
