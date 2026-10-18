#!/usr/bin/env python3
"""INSPECT one root-private schema150 journal; never execute or issue authority."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.lib.schema150_status import inspect_maintenance

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context',required=True)
    args=parser.parse_args()
    try:
        print(json.dumps(inspect_maintenance(args.context),sort_keys=True))
    except Exception as error:
        # Private journals/roles/provider errors must never reach public output.
        print(json.dumps({'capability':'INSPECT','status':'FAIL',
            'error_type':type(error).__name__,'authority_issued':False,
            'mutations_executed':False}),file=sys.stderr)
        raise SystemExit(1)
