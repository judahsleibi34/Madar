#!/usr/bin/env python3
"""Fresh locked CI images and portable archives; creates no deployment authority."""
from datetime import datetime,timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]
INPUTS=('web/backend/Dockerfile','web/backend/requirements.txt','web/backend/constraints.txt',
        'web/frontend/Dockerfile','web/frontend/package.json','web/frontend/package-lock.json')


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):value.update(chunk)
    return value.hexdigest()


def main():
    source=os.environ.get('CI_SOURCE_SHA','')
    if (os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('GITHUB_REPOSITORY')!='judahsleibi34/Madar'
            or not re.fullmatch('[0-9a-f]{40}',source)
            or subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=source
            or subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()):
        raise RuntimeError('Fresh CI source identity required')
    subprocess.run(['python3','web/scripts/check_dependency_locks.py'],cwd=ROOT,check=True)
    timestamp=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    destination=ROOT/'candidate-artifacts';destination.mkdir(mode=0o700,exist_ok=False)
    images={};archives={}
    for role in ('backend','frontend'):
        tag='madar-schema148-'+role+':'+source
        args=['docker','build','--pull','--no-cache','--build-arg','MADAR_RELEASE_SHA='+source,
              '--build-arg','MADAR_BUILD_TIMESTAMP='+timestamp,'--label','com.madar.release.sha='+source,
              '--label','com.madar.release.built_at='+timestamp,'--label','com.madar.build.mode=fresh-locked-ci',
              '--tag',tag]
        if role=='backend':args+=['--target','runtime']
        else:args+=['--build-arg','VITE_API_URL=/api','--build-arg','MADAR_REQUIRE_PRODUCTION_API_URL=true',
                    '--label','com.madar.frontend.api_origin=/api']
        subprocess.run(args+['web/'+role],cwd=ROOT,check=True)
        images[role]=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip()
        if not re.fullmatch('sha256:[0-9a-f]{64}',images[role]):raise RuntimeError('Invalid built image identity')
        path=destination/(role+'.tar.gz')
        with path.open('xb') as target,gzip.GzipFile(fileobj=target,mode='wb',compresslevel=1,mtime=0) as compressed:
            process=subprocess.Popen(['docker','image','save',tag],stdout=subprocess.PIPE)
            try:
                for chunk in iter(lambda:process.stdout.read(1024*1024),b''):compressed.write(chunk)
            finally:process.stdout.close()
            if process.wait()!=0:raise RuntimeError('Image export failed')
        archives[role]={'file':path.name,'sha256':digest(path),'bytes':path.stat().st_size}
    receipt={'version':1,'repository':'judahsleibi34/Madar','source_sha':source,'build_mode':'fresh-locked-ci',
        'images':images,'archives':archives,'inputs_sha256':{name:digest(ROOT/name) for name in INPUTS},
        'run_id':int(os.environ['GITHUB_RUN_ID']),'run_attempt':int(os.environ['GITHUB_RUN_ATTEMPT']),
        'build_timestamp':timestamp,'production_authorized':False}
    (destination/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps(receipt,sort_keys=True))


if __name__=='__main__':main()
