#!/usr/bin/env python3
"""Serve the NEW fail-closed fallback listeners from frozen root-private code."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import signal
import sys
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.lib.active_recovery_resumption import ROOT,ResumptionPlan,load_saved_resumption_plan
from deployment.lib.active_recovery_source import FrozenContinuationSource
from deployment.lib.active_recovery_fallback import CurrentDataFallback,restricted_listeners
from deployment.lib.provider_recovery_runtime import protected

def main():
    if os.geteuid()!=0 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise RuntimeError('fallback_listener_frozen_root_required')
    parser=argparse.ArgumentParser();parser.add_argument('--plan-root',required=True);parser.add_argument('--source-package',required=True)
    parser.add_argument('--approved-plan',required=True);parser.add_argument('--approved-source',required=True);args=parser.parse_args()
    root=Path(args.plan_root)
    plan=load_saved_resumption_plan(root)
    if root!=ROOT/plan.digest or args.approved_plan!=plan.digest or args.approved_source!=plan.source_bundle_sha256:
        raise RuntimeError('fallback_listener_binding_changed')
    guard=FrozenContinuationSource(plan,Path(args.source_package)).verify;guard()
    receipt=json.loads(protected(root/'authorization.json',private=True).read_text())
    if (receipt.get('operation')!='active-local-rollback-resumption' or receipt.get('plan_sha256')!=plan.digest
            or receipt.get('source_bundle_sha256')!=plan.source_bundle_sha256):
        raise RuntimeError('fallback_listener_fresh_authorization_required')
    verifier=CurrentDataFallback(plan,root);servers=restricted_listeners(verifier,guard)
    stopped=threading.Event()
    def terminate(*_):stopped.set()
    signal.signal(signal.SIGTERM,terminate);signal.signal(signal.SIGINT,terminate)
    threads=[threading.Thread(target=server.serve_forever,daemon=True) for server in servers]
    try:
        for thread in threads:thread.start()
        stopped.wait()
    finally:
        for server in servers:server.shutdown();server.server_close()
        for thread in threads:thread.join(timeout=5)

if __name__=='__main__':
    try:main()
    except Exception as error:
        # Filesystem/Docker/HTTP messages may contain secrets; retain type only.
        print(json.dumps({'operation':'active-recovery-fallback-listener','status':'failed','exception_type':type(error).__name__}),flush=True)
        raise SystemExit(1)
