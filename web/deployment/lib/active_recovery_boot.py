"""Prospective exact-plan normal boot resumption component.

Historical recovery receipts remain unchanged. A completed fresh normal
continuation plus independently executed evidence and live identities are required.
Boot fences writes before starting bound IDs and only restores NORMAL after
sustained actual direct-runtime checks. This is not a standalone bootstrap.
"""
import json
from datetime import datetime,timezone
import os
from pathlib import Path
import time
from deployment.lib.active_recovery_resumption import ROOT
from deployment.lib.emergency_routing_repair import AvailabilityFailure,Runtime,verification_window
from deployment.lib.provider_recovery_runtime import protected

class ActiveRecoveryNormalBoot:
    def __init__(self,plan,root,candidate,runtime_verifier,source_guard,completed_evidence,
                 live_native_verifier,compensate_current_data,*,runtime=None):
        if not all(callable(check) for check in (source_guard,completed_evidence,live_native_verifier,compensate_current_data)):
            raise RuntimeError('normal_boot_independent_guards_required')
        self.plan,self.root,self.candidate,self.runtime_verifier=plan,Path(root),candidate,runtime_verifier
        self.source_guard,self.completed_evidence=source_guard,completed_evidence
        self.live_native_verifier,self.compensate_current_data=live_native_verifier,compensate_current_data
        self.runtime=runtime or Runtime()
    def guard(self):
        self.source_guard()
        if os.geteuid()!=0 or self.root!=ROOT/self.plan.digest:raise RuntimeError('normal_boot_fresh_root_required')
        receipt=json.loads(protected(self.root/'authorization.json',private=True).read_text())
        events=[json.loads(line) for line in protected(self.root/'events.jsonl',private=True).read_text().splitlines()]
        if (receipt.get('operation')!='active-local-rollback-resumption' or receipt.get('plan_sha256')!=self.plan.digest
                or receipt.get('source_bundle_sha256')!=self.plan.source_bundle_sha256
                or not events or events[-1].get('phase')!='normal'
                or any(row.get('plan_sha256')!=self.plan.digest for row in events)):
            raise RuntimeError('normal_boot_completed_continuation_required')
        self.completed_evidence()
        self.runtime_verifier.identities(workers_started=True,require_running=False)
        self.source_guard()
    def event(self,stage,**fields):
        path=self.root/'boot-events.jsonl'
        if path.exists():protected(path,private=True)
        descriptor=os.open(path,os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,'a') as stream:
            json.dump({'version':1,'plan_sha256':self.plan.digest,'stage':stage,
                'observed_at':datetime.now(timezone.utc).isoformat(),**fields},stream,sort_keys=True)
            stream.write('\n');stream.flush();os.fsync(stream.fileno())

    def execute(self):
        self.guard()
        # A retained NORMAL journal must not replay a previously revoked grant
        # after compensation or an interrupted earlier boot. Such recovery is
        # handled by the current-data restricted actor, not another write grant.
        self.candidate.require_write_authority(self.candidate.contract,'NORMAL')
        self.event('begin')
        effect_started=False
        try:
            with verification_window(self.runtime,180):
                # Treat reboot as a fresh live verification boundary, not replay
                # of a historical acceptance marker. Bound processes cannot start
                # consuming business work while startup is being validated.
                effect_started=True
                self.candidate._publish_write_authority(self.candidate.contract,'READ_ONLY')
                self.candidate.require_write_authority(self.candidate.contract,'READ_ONLY')
                while True:
                    self.runtime.budget(1)
                    try:self.live_native_verifier();break
                    except AvailabilityFailure:time.sleep(self.runtime.budget(1))
                bound=self.runtime_verifier.identities(workers_started=True,require_running=False)
                for kind in ('parser','backend','frontend','notification','calendar-sync','data-deletion'):
                    self.source_guard()
                    row=self.candidate.inspect(bound[kind]['Id'])
                    if not row['State']['Running']:self.candidate.command(['docker','start',row['Id']])
                first=None;successes=0
                while True:
                    self.runtime.budget(1)
                    try:
                        self.live_native_verifier()
                        self.runtime_verifier.read_only(workers_started=True,require_public=False)
                    except AvailabilityFailure:
                        first=None;successes=0
                    else:
                        successes+=1
                        if first is None:first=time.monotonic()
                        if successes>=3 and time.monotonic()-first>=5:break
                    time.sleep(self.runtime.budget(1))
                self.guard();self.live_native_verifier()
                self.candidate.require_write_authority(self.candidate.contract,'READ_ONLY')
                self.candidate._publish_write_authority(self.candidate.contract,'NORMAL')
                self.candidate.require_write_authority(self.candidate.contract,'NORMAL')
                while True:
                    self.runtime.budget(1)
                    try:
                        self.live_native_verifier()
                        self.runtime_verifier.normal(require_public=False);break
                    except AvailabilityFailure:time.sleep(self.runtime.budget(1))
                self.event('normal_verified')
        except Exception as error:
            try:self.event('failed',exception_type=type(error).__name__)
            except OSError:pass
            if effect_started:
                # The adapter must revoke/stop first, append its NEW compensation
                # event and choose current-data fallback or maintenance/proxy-stop.
                # No source checkpoint/database restoration is a boot operation.
                self.compensate_current_data()
            raise
        return {'plan_sha256':self.plan.digest,'schema':115,'mode':'NORMAL'}
