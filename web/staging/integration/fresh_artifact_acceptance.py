#!/usr/bin/env python3
"""REHEARSE fresh CI application images only on the attested restored staging stack."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import zipfile

import manage
import independent_recovery as recovery
import smoke

ROOT=manage.REPOSITORY
import sys
sys.path.insert(0,str(ROOT/'web'))
from deployment.lib.schema148_artifacts import INPUTS,verify_archive


def main(directory,source_sha,attempt,mode):
    manage.require_staging_host()
    if (not directory.is_relative_to(Path.home()) or directory.is_symlink() or not re.fullmatch('[0-9a-f]{40}',source_sha)):
        raise RuntimeError('Fresh artifact scope invalid')
    project='madar-independent-recovery-20261017'+('' if attempt==1 else '-attempt'+str(attempt))
    recovery.TARGET_PROJECT=project;runtime=Path.home()/project
    with recovery.target_context(runtime):
        manage.state();manage.attest_resources();manage.require_database_marker()
        if manage.sql("select schema_version from public.application_schema_state where contract_key='core';")!='148':raise RuntimeError('Fresh image acceptance requires schema148')
        run=json.loads((directory/'run.json').read_text());artifact=json.loads((directory/'artifact.json').read_text())
        images=json.loads((directory/'receipt.json').read_text())['images']
        inputs={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in INPUTS}
        receipt=verify_archive(directory/'candidate.zip',artifact,run,source_sha=source_sha,images=images,expected_inputs=inputs)
        if mode=='INSPECT':
            print(json.dumps({'mode':mode,'source_sha':source_sha,'images':images,'target_project':project,'production_authorized':False}));return
        output=runtime/('fresh-images-'+source_sha)
        if output.exists():raise RuntimeError('Fresh image acceptance scope already consumed')
        output.mkdir(mode=0o700)
        if __import__('shutil').disk_usage(output).free<8*1024**3:raise RuntimeError('Fresh image disk headroom insufficient')
        started=time.monotonic()
        with zipfile.ZipFile(directory/'candidate.zip') as archive:
            for role in ('backend','frontend'):
                path=output/(role+'.tar.gz')
                descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(descriptor,'wb') as destination,archive.open(role+'.tar.gz') as source:
                    __import__('shutil').copyfileobj(source,destination,1024*1024)
                result=subprocess.run(manage.DOCKER+['image','load','--input',str(path)],capture_output=True,timeout=600,
                    env={'PATH':os.defpath,'HOME':str(Path.home())})
                if result.returncode:raise RuntimeError('Fresh staging image import failed')
                row=json.loads(manage.docker('image','inspect',images[role]))[0];labels=row['Config'].get('Labels',{})
                if (row['Id']!=images[role] or labels.get('com.madar.release.sha')!=source_sha
                        or labels.get('org.opencontainers.image.revision')!=source_sha
                        or labels.get('com.madar.build.mode')!='fresh-locked-ci' or labels.get('com.madar.staging.build_mode')):
                    raise RuntimeError('Imported fresh image identity invalid')
        # Retain the existing loopback TLS edge, while the exact production
        # frontend image serves its own compiled files and Nginx configuration.
        gateway='''pid /tmp/nginx.pid;
error_log /dev/stderr warn;
events { worker_connections 128; }
http { access_log off; client_body_temp_path /tmp/client; proxy_temp_path /tmp/proxy;
 server { listen 8080; listen 8443 ssl; ssl_certificate /staging/tls.crt; ssl_certificate_key /staging/tls.key;
 location / { proxy_pass http://accepted-frontend:8080; proxy_set_header Host $http_host; proxy_set_header X-Forwarded-Proto $scheme; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; } } }
'''
        manage.private_write('fresh-edge.conf',gateway,mounted=True)
        common={'restart':'no','networks':['isolated'],'read_only':True,'user':'nginx','security_opt':['no-new-privileges:true'],
            'cap_drop':['ALL'],'labels':{'com.madar.staging.owner':manage.OWNER},'mem_limit':'128m','cpus':0.5,'pids_limit':128,
            'logging':{'driver':'json-file','options':{'max-size':'2m','max-file':'2'}}}
        configuration={'services':{'backend':{'image':images['backend']},'notification-worker':{'image':images['backend']},
            'accepted-frontend':{**common,'image':images['frontend'],'pull_policy':'never',
                'tmpfs':['/tmp:rw,noexec,nosuid,size=32m','/var/cache/nginx:rw,noexec,nosuid,uid=101,gid=101,size=32m','/etc/nginx/conf.d:rw,noexec,nosuid,uid=101,gid=101,size=2m'],
                'environment':{'APP_ENV':'staging','MADAR_RELEASE_SHA':source_sha,'MADAR_PUBLIC_SITE_DOMAIN':'hardening.test','MADAR_CSP_CONNECT_SRC':"'self'",'MADAR_HSTS':''},
                'depends_on':{'backend':{'condition':'service_healthy'}}},
            'frontend':{'volumes':[str(runtime/'fresh-edge.conf')+':/staging/nginx.conf:ro'],
                'depends_on':{'accepted-frontend':{'condition':'service_started'}}}}}
        manage.private_write('fresh-compose.json',json.dumps(configuration))
        manage.compose('stop','--timeout','30','frontend','backend','notification-worker')
        manage.select_source(source_sha)
        app=(runtime/'application.env').read_text()
        app=re.sub(r'^MADAR_BUILD_TIMESTAMP=.*$', 'MADAR_BUILD_TIMESTAMP='+receipt['build_timestamp'],app,flags=re.M)
        manage.private_write('application.env',app)
        manage.compose('--file',str(runtime/'fresh-compose.json'),'up','--detach','--wait','--wait-timeout','120')
        manage.attest_resources();manage.require_database_marker()
        smoke.main()
        report={'scope':'fresh authenticated CI images on independent synthetic native restore','source_sha':source_sha,
            'images':images,'artifact_id':artifact['id'],'run_id':run['id'],'schema':148,'target_project':project,
            'native_auth_mfa_storage_worker_api':True,'production_frontend_image_and_nginx':True,
            'source_overlay_used':False,'elapsed_seconds':round(time.monotonic()-started,3),'production_modified':False,
            'production_authorized':False,'limitations':['synthetic same-VM native integration','not complete product E2E','not protected controller installation/current-data acceptance or production authorization']}
        manage.private_write('fresh-image-acceptance.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report,sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('INSPECT','REHEARSE'),nargs='?',default='INSPECT');parser.add_argument('--artifacts',required=True,type=Path)
    parser.add_argument('--source-sha',required=True);parser.add_argument('--attempt',type=int,choices=(1,2,3),default=3)
    args=parser.parse_args();main(args.artifacts.resolve(),args.source_sha,args.attempt,args.mode)
