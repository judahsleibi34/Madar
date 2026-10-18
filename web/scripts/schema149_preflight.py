#!/usr/bin/env python3
"""INSPECT source149 manifest/readiness only. No production mutation interface."""
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.lib.schema149_readiness import evaluate
from deployment.lib.schema149_release import source_manifest


def read_evidence(path):
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(descriptor,'rb') as stream:
        metadata=os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size>1024**2:raise ValueError('Evidence must be bounded regular JSON')
        data=stream.read(1024**2+1)
    if len(data)>1024**2:raise ValueError('Evidence exceeds bound')
    return json.loads(data)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('INSPECT',),nargs='?',default='INSPECT')
    parser.add_argument('--evidence',type=Path);args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip())
    source_manifest(root)
    result=evaluate(sha,read_evidence(args.evidence) if args.evidence else None)
    result['source_metadata_verified']=True;result['source_tree_clean']=not dirty
    if dirty:result['gates']['source_integrity']={'status':'FAIL','reason':'Working source differs from the named commit'}
    print(json.dumps(result,sort_keys=True))
