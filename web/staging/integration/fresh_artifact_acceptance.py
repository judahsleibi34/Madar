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
import tempfile

import manage
import independent_recovery as recovery
import smoke

ROOT=manage.REPOSITORY
import sys
sys.path.insert(0,str(ROOT/'web'))
from deployment.lib.schema148_artifacts import INPUTS,authenticated_archive,verify_archive


def import_authenticated_image(archive,role,metadata,path):
    """Load the verified member through a private fd, never an operator path."""
    manage.require_staging_host()
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'wb') as destination,tempfile.TemporaryFile(mode='w+b') as frozen:
        value=hashlib.sha256();size=0
        with archive.open(role+'.tar.gz') as source:
            while chunk:=source.read(1024*1024):
                size+=len(chunk)
                if size>metadata['bytes'] or size>3*1024**3:raise RuntimeError('Fresh image archive size changed')
                destination.write(chunk);frozen.write(chunk);value.update(chunk)
        if size!=metadata['bytes'] or value.hexdigest()!=metadata['sha256']:
            raise RuntimeError('Fresh image archive digest changed')
        destination.flush();frozen.seek(0)
        result=subprocess.run(manage.DOCKER+['image','load'],stdin=frozen,capture_output=True,timeout=600,
            env={'PATH':os.defpath,'HOME':str(Path.home())})
        if result.returncode:raise RuntimeError('Fresh staging image import failed')


def main(directory,source_sha,attempt,mode,*,resume=False):
    manage.require_staging_host()
    if (not directory.is_relative_to(Path.home()) or directory.is_symlink() or not re.fullmatch('[0-9a-f]{40}',source_sha)):
        raise RuntimeError('Fresh artifact scope invalid')
    project='madar-independent-recovery-20261017'+('' if attempt==1 else '-attempt'+str(attempt))
    recovery.TARGET_PROJECT=project;runtime=Path.home()/project
    with recovery.target_context(runtime):
        state=manage.state();manage.attest_resources();manage.require_database_marker()
        if resume and (mode!='REHEARSE' or state['source_sha']!=source_sha):
            raise RuntimeError('Explicit resume requires the already selected exact synthetic source')
        if manage.sql("select schema_version from public.application_schema_state where contract_key='core';")!='148':raise RuntimeError('Fresh image acceptance requires schema148')
        run=json.loads((directory/'run.json').read_text());artifact=json.loads((directory/'artifact.json').read_text())
        images=json.loads((directory/'receipt.json').read_text())['images']
        inputs={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in INPUTS}
        receipt=verify_archive(directory/'candidate.zip',artifact,run,source_sha=source_sha,images=images,expected_inputs=inputs)
        if mode=='INSPECT':
            print(json.dumps({'mode':mode,'source_sha':source_sha,'images':images,'target_project':project,'production_authorized':False}));return
        output=runtime/('fresh-images-'+source_sha)
        if output.is_symlink() or (output.exists() and not resume):raise RuntimeError('Fresh image acceptance scope already consumed')
        if resume:
            if not output.is_dir():raise RuntimeError('Previously imported scope missing')
        else:output.mkdir(mode=0o700)
        sizes=[item['bytes'] for item in receipt['archives'].values()]
        required=max(8*1024**3,(directory/'candidate.zip').stat().st_size+sum(sizes)+max(sizes)+256*1024**2)
        if __import__('shutil').disk_usage(output).free<required:raise RuntimeError('Fresh image disk headroom insufficient')
        started=time.monotonic()
        with authenticated_archive(directory/'candidate.zip',artifact['digest']) as archive:
            for role in ('backend','frontend'):
                path=output/(role+'.tar.gz')
                if resume:
                    if path.is_symlink() or not path.is_file() or path.stat().st_size!=receipt['archives'][role]['bytes']:
                        raise RuntimeError('Imported archive scope changed')
                    from deployment.lib.schema148_artifacts import digest
                    with path.open('rb') as source:
                        if digest(source)!=receipt['archives'][role]['sha256']:raise RuntimeError('Imported archive bytes changed')
                else:
                    import_authenticated_image(archive,role,receipt['archives'][role],path)
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
 fastcgi_temp_path /tmp/fastcgi; uwsgi_temp_path /tmp/uwsgi; scgi_temp_path /tmp/scgi;
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
            'source_overlay_used':False,'explicit_imported_scope_resume':resume,'elapsed_seconds':round(time.monotonic()-started,3),'production_modified':False,
            'production_authorized':False,'limitations':['synthetic same-VM native integration','not complete product E2E','not protected controller installation/current-data acceptance or production authorization']}
        manage.private_write('fresh-image-acceptance.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report,sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('INSPECT','REHEARSE'),nargs='?',default='INSPECT');parser.add_argument('--artifacts',required=True,type=Path)
    parser.add_argument('--source-sha',required=True);parser.add_argument('--attempt',type=int,choices=(1,2,3),default=3)
    parser.add_argument('--resume-imported',action='store_true',help='Explicitly revalidate an interrupted synthetic import; never replay production effects')
    args=parser.parse_args();main(args.artifacts.resolve(),args.source_sha,args.attempt,args.mode,resume=args.resume_imported)
