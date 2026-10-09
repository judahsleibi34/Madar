"""Bounded read-only routing handoff; no controller, database or write mutation.

The caller must hold the governed locks and the fresh exact-plan authority.
This component may restore the emergency route only while EVERY retained binding
other than the route still matches. Later controller/worker compensation belongs
to the complete continuation adapter; otherwise this component fails safely to
maintenance. It never treats an old routing pre-image as unconditional rollback.
"""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import time

from deployment.lib.active_recovery_resumption import ROOT
from deployment.lib.active_recovery_inputs import observe_retained_inputs
from deployment.lib.emergency_routing_repair import (
    Runtime,AvailabilityFailure,verification_window,exclusive,encoded,UPSTREAM,
)
from deployment.lib.provider_recovery_runtime import protected,file_digest

class ReadOnlyRoutingHandoff:
    def __init__(self,plan,candidate,root,*,runtime=None,observer=observe_retained_inputs):
        self.plan,self.candidate,self.root=plan,candidate,Path(root)
        self.runtime=runtime or Runtime();self.observer=observer
        self.runtime.expected_nginx_sha256=plan.retained_inputs['proxy_configuration']
        self.route=(f'upstream madar_backend_active {{ server 127.0.0.1:{candidate.backend_port}; }}\n'
            f'upstream madar_frontend_active {{ server 127.0.0.1:{candidate.frontend_port}; }}\n').encode()

    def authorize_phase(self,phase):
        if os.geteuid()!=0 or self.root!=ROOT/self.plan.digest:
            raise RuntimeError('handoff_fresh_root_required')
        record=json.loads(protected(self.root/'authorization.json',private=True).read_text())
        if (record.get('operation')!='active-local-rollback-resumption' or record.get('plan_sha256')!=self.plan.digest
                or record.get('source_bundle_sha256')!=self.plan.source_bundle_sha256):
            raise RuntimeError('handoff_fresh_authorization_changed')
        events=[json.loads(line) for line in protected(self.root/'events.jsonl',private=True).read_text().splitlines()]
        if not events or any(e.get('plan_sha256')!=self.plan.digest for e in events) or events[-1].get('phase')!=phase:
            raise RuntimeError('handoff_phase_not_authorized')

    def event(self,name,**fields):
        # This is a separate append-only observation journal, not a transaction
        # phase or protected PASS receipt. Never copy a result from older source.
        with (self.root/'routing-events.jsonl').open('a') as output:
            os.fchmod(output.fileno(),0o600)
            json.dump({'event':name,'observed_at':datetime.now(timezone.utc).isoformat(),**fields},output,sort_keys=True)
            output.write('\n');output.flush();os.fsync(output.fileno())

    def prepare(self):
        self.authorize_phase('detached_candidate_ready')
        self.candidate.verify_read_only()
        if self.observer()!=self.plan.retained_inputs:raise RuntimeError('handoff_retained_inputs_changed')
        previous=UPSTREAM.read_bytes()
        # Exclusive exact pre-image; collisions cannot refresh approval scope.
        exclusive(self.root/'routing-preimage.conf',previous)
        if file_digest(self.root/'routing-preimage.conf')!=self.plan.retained_inputs['upstream']:
            raise RuntimeError('handoff_preimage_changed')

    def publish(self,verify_round):
        self.authorize_phase('read_only_handoff_pending')
        with verification_window(self.runtime,180):
            self.candidate.verify_read_only()
            if self.observer()!=self.plan.retained_inputs:raise RuntimeError('handoff_retained_inputs_changed')
            from deployment.lib.active_recovery_proxy import worker_snapshot
            previous=worker_snapshot(self.runtime)
            exclusive(self.root/'proxy-worker-preimage.json',encoded(previous))
            self.runtime.nginx_preflight(self.route,self.root)
            self.runtime.publish(self.route)
            self.runtime.reload()
            self.sustain(verify_round)
            self.drain_previous_workers(verify_round,previous)

    def sustain(self,verify_round):
        first=None;consecutive=0;rounds=0;started=time.monotonic()
        while True:
            self.runtime.budget(1);rounds+=1
            self.authorize_phase('read_only_handoff_pending')
            self.candidate.verify_identities()
            self.candidate.verify_recorded_runtime()
            # Only explicit availability failures reset convergence. Unknown
            # images, fences, ownership and route changes fail immediately.
            try:
                self.candidate.verify_read_only()
                verify_round(self.route)
            except AvailabilityFailure as error:
                first=None;consecutive=0
                self.event('activation_pending',round=rounds,exception_type=type(error).__name__,elapsed_seconds=round(time.monotonic()-started,3))
            else:
                consecutive+=1
                if first is None:first=time.monotonic()
                if consecutive>=3 and time.monotonic()-first>=5:
                    self.event('activation_sustained',rounds=rounds,successful_rounds=consecutive,
                        sustained_seconds=round(time.monotonic()-first,3),elapsed_seconds=round(time.monotonic()-started,3))
                    return
            time.sleep(self.runtime.budget(1))

    def drain_previous_workers(self,verify_round,previous):
        from deployment.lib.active_recovery_proxy import worker_snapshot,previous_workers_drained
        started=time.monotonic()
        while True:
            self.runtime.budget(1)
            self.authorize_phase('read_only_handoff_pending')
            drained=previous_workers_drained(previous,worker_snapshot(self.runtime))
            try:
                self.candidate.verify_read_only();verify_round(self.route)
            except AvailabilityFailure as error:
                self.event('worker_drain_activation_pending',exception_type=type(error).__name__,
                    elapsed_seconds=round(time.monotonic()-started,3))
            else:
                if drained:
                    self.event('previous_workers_drained',elapsed_seconds=round(time.monotonic()-started,3))
                    return
            time.sleep(self.runtime.budget(1))

    def restore_emergency_before_controller_change(self,verify_previous):
        """Narrow compensation: preserve current data and all consumer fences."""
        with verification_window(self.runtime,60):
            self.candidate.require_write_authority(self.candidate.contract,'READ_ONLY')
            observed=self.observer()
            expected={k:v for k,v in self.plan.retained_inputs.items() if k!='upstream'}
            if {k:v for k,v in observed.items() if k!='upstream'}!=expected:
                raise RuntimeError('handoff_previous_route_no_longer_safe')
            previous=protected(self.root/'routing-preimage.conf',private=True).read_bytes()
            if file_digest(self.root/'routing-preimage.conf')!=self.plan.retained_inputs['upstream']:
                raise RuntimeError('handoff_preimage_changed')
            self.runtime.nginx_preflight(previous,self.root)
            self.runtime.publish(previous);self.runtime.reload()
            verify_previous()
            self.event('emergency_route_restored')
