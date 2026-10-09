#!/usr/bin/env python3
"""Read-only fixed-path preflight; hashes are observations, not authorization."""
import json
import os
import re
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.lib.active_recovery_inputs import observe_retained_inputs,observe_runtime_dependencies
from deployment.lib.emergency_routing_repair import Runtime,verify

if __name__=='__main__':
    if os.geteuid()!=0 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise SystemExit('frozen_root_source_entry_required')
    stage='retained_inputs_before'
    try:
        before=observe_retained_inputs()
        stage='restricted_runtime'
        observation,_=verify(Runtime())
        stage='retained_inputs_after'
        after=observe_retained_inputs()
        dependencies,dependency_hash=observe_runtime_dependencies()
        if dependency_hash!=after['runtime_dependencies']:raise RuntimeError('resumption_dependencies_changed_during_observation')
        if before!=after:raise RuntimeError('resumption_inputs_changed_during_observation')
        print(json.dumps({'operation':'read-only-active-recovery-preflight','retained_inputs':after,
            'source_sha':observation['source_sha'],'runtimes':observation['runtimes'],'networks':observation['networks'],
            'runtime_dependencies':dependencies,'schema':115,'business_writes_enabled':False,'consumers_started':False,'production_modified':False}))
    except Exception as error:
        print(json.dumps({'operation':'read-only-active-recovery-preflight','status':'failed','stage':stage,'exception_type':type(error).__name__,
            'failure_category':str(error) if type(error) is RuntimeError and re.fullmatch('[a-z_]+',str(error)) else 'preflight_failed'}))
        raise SystemExit(1)
