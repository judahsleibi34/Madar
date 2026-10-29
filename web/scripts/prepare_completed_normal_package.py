#!/usr/bin/env python3
"""Prepare a frozen test operation request; never execute or issue authority."""
import argparse,json,os,sys
from pathlib import Path
# No ambient Python injection into this privileged preparation command.
if __name__=='__main__' and (not sys.flags.isolated or not sys.flags.dont_write_bytecode or os.geteuid()!=0):
    raise SystemExit('completed_package_isolated_root_required')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.lib.provider_recovery_runtime import readonly_configuration
from deployment.lib.migration_inventory import strict_json
from deployment.lib.completed_normal_package import prepare

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True)
    args=parser.parse_args()
    path=readonly_configuration(args.input,private=True)
    if not 0<path.stat().st_size<=2*1024**2:raise RuntimeError('completed_package_input_limit')
    value=strict_json(path.read_bytes())
    if not isinstance(value,dict) or set(value)!={'plan','original_inventory','original_probes','candidate_model'}:
        raise RuntimeError('completed_package_input_inventory_invalid')
    result=prepare(Path('/opt/madar-development/repository'),value['plan'],value['original_inventory'],value['original_probes'],value['candidate_model'])
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':
    try:main()
    except Exception as error:
        import re
        code=str(error)
        print(json.dumps({'status':'REFUSED','code':code if isinstance(error,RuntimeError) and re.fullmatch('[a-z][a-z0-9_]{1,100}',code) else 'package_preparation_failed','authority_issued':False}))
        raise SystemExit(1)
