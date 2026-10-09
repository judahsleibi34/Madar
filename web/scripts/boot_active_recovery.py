#!/usr/bin/env python3
"""Approved frozen boot entry; never creates fresh authorization."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.lib.active_recovery_resumption import ResumptionPlan,ROOT,load_saved_resumption_plan
from deployment.lib.provider_recovery_runtime import protected
from deployment.lib.active_recovery_boot_actor import ActiveRecoveryBootActor

def main():
    if os.geteuid()!=0 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise RuntimeError('boot_entry_frozen_root_required')
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['resume-boot','check-proxy-gate'])
    for name in ('plan-root','source-package','approved-plan','approved-source'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args();root=Path(args.plan_root)
    plan=load_saved_resumption_plan(root)
    if root!=ROOT/plan.digest or args.approved_plan!=plan.digest or args.approved_source!=plan.source_bundle_sha256:
        raise RuntimeError('boot_entry_approved_binding_changed')
    actor=ActiveRecoveryBootActor(plan,root,Path(args.source_package))
    result=actor.resume() if args.mode=='resume-boot' else actor.proxy_gate()
    print(json.dumps({'operation':args.mode,'plan_sha256':plan.digest,'result':result}))

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'operation':'active-recovery-boot','status':'failed','exception_type':type(error).__name__}),flush=True)
        raise SystemExit(1)
