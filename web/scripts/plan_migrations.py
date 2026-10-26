#!/usr/bin/env python3
"""INSPECT/PREPARE only: immutable Git inventory/plan to stdout; no DB credentials."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.lib.migration_inventory import canonical, discover
from deployment.lib.migration_plan import generate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-sha',required=True)
    parser.add_argument('--history-base-sha',required=True,help='Independently verified immutable ancestor, not inferred from live DB')
    parser.add_argument('--origin-schema',required=True,type=int)
    parser.add_argument('--target-schema',type=int)
    parser.add_argument('--inventory-only',action='store_true')
    args=parser.parse_args()
    try:
        root=Path(__file__).resolve().parents[2]
        inventory=discover(root,source_sha=args.source_sha,history_base_sha=args.history_base_sha)
        body=canonical(inventory.document()) if args.inventory_only else generate(root,inventory,origin=args.origin_schema,target=args.target_schema).encoded
    except (RuntimeError,ValueError,OSError,KeyError) as error:
        # Bound errors to fixed codes; parser SQL, credentials and Git stderr never printed.
        code=str(error) if isinstance(error,RuntimeError) else type(error).__name__
        print(json.dumps({'status':'BLOCKED','code':code[:160],'authority_issued':False}),file=sys.stderr)
        return 1
    sys.stdout.buffer.write(body)
    return 0


if __name__=='__main__': raise SystemExit(main())
