#!/usr/bin/env python3
"""PREPARE authenticated CI archives in a new private directory; never deploy/load."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.lib.schema148_artifacts import INPUTS,REPOSITORY,verify_archive

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True,type=int);parser.add_argument('--source-sha',required=True)
    parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    if args.run_id<=0 or not re.fullmatch('[0-9a-f]{40}',args.source_sha):raise RuntimeError('Explicit CI identity required')
    def api(endpoint):return json.loads(subprocess.check_output(['gh','api','repos/'+REPOSITORY+'/actions/'+endpoint],text=True,timeout=30))
    run=api('runs/'+str(args.run_id))
    entries=api('runs/'+str(args.run_id)+'/artifacts')['artifacts']
    expected=f"schema148-candidate-{args.source_sha}-{args.run_id}-{run.get('run_attempt')}"
    matches=[row for row in entries if row.get('name')==expected]
    if len(matches)!=1 or matches[0].get('expired') is not False or matches[0].get('size_in_bytes',0)>6*1024**3:
        raise RuntimeError('Unique current CI artifact unavailable')
    artifact=api('artifacts/'+str(matches[0]['id']))
    if (args.output.exists() or args.output.is_symlink() or not args.output.is_absolute()
            or args.output.parent.resolve()!=Path.home().resolve()):
        raise RuntimeError('Use a new private artifact scope directly under the operator home')
    args.output.mkdir(mode=0o700,parents=False)
    archive=args.output/'candidate.zip'
    descriptor=os.open(archive,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'wb') as stream:
        subprocess.run(['gh','api','repos/'+REPOSITORY+'/actions/artifacts/'+str(artifact['id'])+'/zip'],stdout=stream,check=True,timeout=900)
    inputs={name:hashlib.sha256(subprocess.check_output(['git','show',args.source_sha+':'+name],cwd=ROOT)).hexdigest() for name in INPUTS}
    receipt=verify_archive(archive,artifact,run,source_sha=args.source_sha,images=None,expected_inputs=inputs)
    documents={'artifact.json':artifact,'run.json':run,'receipt.json':receipt,
        'provenance-binding.json':{'archive':str(archive),'artifact_id':artifact['id'],'run_id':args.run_id},
        'verification.json':{'source_sha':args.source_sha,'images':receipt['images'],'run_id':args.run_id,
            'artifact_id':artifact['id'],'archive_sha256':artifact['digest'],'status':'PASS','scope':'authenticated fresh CI artifacts; not production admission','production_authorized':False}}
    for name,value in documents.items():
        descriptor=os.open(args.output/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,'w') as stream:json.dump(value,stream,indent=2,sort_keys=True);stream.write('\n')
    print(json.dumps(documents['verification.json'],sort_keys=True))


if __name__=='__main__':main()
