#!/usr/bin/env python3
"""Observe current local business roots; never fence, migrate or grant writes."""
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.lib.active_recovery_reconciliation import CurrentLocalReconciliation
from deployment.lib.active_recovery_inputs import observe_retained_inputs
from deployment.lib.emergency_routing_repair import Runtime,verify,verification_window

def execute():
    if os.geteuid()!=0 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise RuntimeError('reconciliation_frozen_root_required')
    runtime=Runtime()
    with verification_window(runtime,180):
        before=observe_retained_inputs()
        context,_=verify(runtime)
        candidate=SimpleNamespace(command=runtime.command)
        observation=CurrentLocalReconciliation(None,Path(__file__).parent,candidate,lambda:None,lambda:verify(runtime))
        packet,root_hash=observation.snapshot()
        after=observe_retained_inputs()
        if before!=after:raise RuntimeError('reconciliation_active_inputs_changed')
        return {'operation':'actual-current-local-read-only-reconciliation','retained_inputs':after,
            'source_sha':context['source_sha'],'schema':115,'business_writes_enabled':False,
            'snapshot':packet,'snapshot_sha256':root_hash,'production_modified':False,
            'consumers_started':False,'authorization_issued':False}

if __name__=='__main__':
    try:print(json.dumps(execute(),sort_keys=True))
    except Exception as error:
        print(json.dumps({'operation':'actual-current-local-read-only-reconciliation','status':'failed',
            'exception_type':type(error).__name__,
            'failure_category':str(error) if type(error) is RuntimeError and re.fullmatch('[a-z_]+',str(error)) else 'reconciliation_failed'}))
        raise SystemExit(1)
