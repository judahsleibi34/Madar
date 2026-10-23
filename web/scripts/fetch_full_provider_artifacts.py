#!/usr/bin/env python3
"""Read-only exact-source CI download for an owned staging attempt.

No production credential, deployment endpoint, source override or authority
receipt is accepted. Workflow tokens need only contents/actions read access.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.lib.schema148_artifacts import REPOSITORY,WORKFLOW,verify_archive,verify_required_ci,INPUTS
import hashlib


def api(endpoint):
    result=subprocess.run(['gh','api','repos/'+REPOSITORY+'/actions/'+endpoint],capture_output=True,timeout=30)
    if result.returncode or len(result.stdout)>8*1024**2:raise RuntimeError('full_staging_ci_query_failed')
    return json.loads(result.stdout)


def select_run(packet,source,path):
    rows=packet.get('workflow_runs',[])
    if not rows:return None
    if any(type(row.get('id')) is not int for row in rows):raise RuntimeError('full_staging_ci_run_invalid')
    latest=max(rows,key=lambda row:row['id'])
    if (latest.get('head_sha')!=source or latest.get('path')!=path
            or latest.get('repository',{}).get('full_name')!=REPOSITORY
            or latest.get('head_repository',{}).get('full_name')!=REPOSITORY):
        raise RuntimeError('full_staging_ci_identity_mismatch')
    if latest.get('status')!='completed':return None
    if latest.get('conclusion')!='success':raise RuntimeError('full_staging_ci_failed')
    return latest


def write(path,value):
    with path.open('xb') as stream:
        os.fchmod(stream.fileno(),0o600);stream.write(json.dumps(value,sort_keys=True,indent=2).encode()+b'\n')
        stream.flush();os.fsync(stream.fileno())


def fetch(source,directory):
    if not re.fullmatch('[0-9a-f]{40}',source or ''):raise RuntimeError('full_staging_ci_exact_source_required')
    directory=Path(directory)
    if directory.parent not in {Path.home(), Path('/opt/madar-development/evidence/integration')} or directory.name!='madar-provider-artifacts-'+source[:12]:
        raise RuntimeError('full_staging_ci_directory_scope')
    directory.mkdir(mode=0o700)
    deadline=time.monotonic()+600
    while True:
        packets={workflow:api('workflows/'+workflow+'/runs?head_sha='+source+'&per_page=100') for workflow in
            ('backend-check.yml','frontend-check.yml','schema148-artifacts.yml','migration-safety.yml')}
        selected={workflow:select_run(packet,source,'.github/workflows/'+workflow) for workflow,packet in packets.items()}
        if all(selected.values()):break
        if time.monotonic()>=deadline:raise RuntimeError('full_staging_ci_completion_timeout')
        time.sleep(10)
    ci={workflow:packets[workflow] for workflow in ('backend-check.yml','frontend-check.yml')}
    verify_required_ci(ci,source)
    run=selected['schema148-artifacts.yml']
    artifacts=api('runs/'+str(run['id'])+'/artifacts')['artifacts']
    name=f"schema148-candidate-{source}-{run['id']}-{run['run_attempt']}"
    matches=[row for row in artifacts if row.get('name')==name and row.get('expired') is False]
    if len(matches)!=1 or type(matches[0].get('id')) is not int or not 0<matches[0].get('size_in_bytes',0)<=6*1024**3:
        raise RuntimeError('full_staging_ci_artifact_missing_or_unbounded')
    artifact=api('artifacts/'+str(matches[0]['id']))
    archive=directory/'candidate.zip'
    with archive.open('xb') as stream:
        os.fchmod(stream.fileno(),0o600)
        result=subprocess.run(['gh','api','repos/'+REPOSITORY+'/actions/artifacts/'+str(artifact['id'])+'/zip'],
            stdout=stream,stderr=subprocess.PIPE,timeout=300)
        stream.flush();os.fsync(stream.fileno())
    if result.returncode or archive.stat().st_size!=artifact['size_in_bytes']:raise RuntimeError('full_staging_ci_download_failed')
    root=Path(__file__).resolve().parents[2]
    inputs={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in INPUTS}
    receipt=verify_archive(archive,artifact,run,source_sha=source,images=None,expected_inputs=inputs)
    for name,value in {'artifact.json':artifact,'run.json':run,'receipt.json':receipt,
            **{name+'.json':value for name,value in ci.items()}}.items():write(directory/name,value)
    return {'source_sha':source,'artifact_id':artifact['id'],'run_id':run['id'],'archive_sha256':artifact['digest'],
        'staging_directory':str(directory),'production_authorized':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-sha',required=True);parser.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(fetch(args.source_sha,args.directory),sort_keys=True))
