"""Fresh guarded positive write boundary for an active rollback continuation.

This is an effect component, not a standalone cutover or acceptance issuer.
Its caller must supply the exact frozen, independently executing prerequisite
verifier. Historical final-smoke PASS summaries and lost /run credentials are
never read. Revocation does not depend on successful compensation journaling.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from deployment.lib.active_recovery_resumption import ROOT
from deployment.lib.emergency_routing_repair import exclusive, encoded
from deployment.lib.provider_recovery_runtime import protected
from deployment.lib.runtime_authority import runtime_mutation_lock

class ActiveRecoveryWriteAuthority:
    def __init__(self,plan,candidate,root,source_guard,runtime_verifier,prerequisites):
        if not callable(source_guard) or not callable(prerequisites):
            raise RuntimeError('write_boundary_independent_guards_required')
        self.plan,self.candidate,self.root=plan,candidate,Path(root)
        self.source_guard,self.runtime_verifier,self.prerequisites=source_guard,runtime_verifier,prerequisites
    def authorization(self):
        self.source_guard()
        if os.geteuid()!=0 or self.root!=ROOT/self.plan.digest:
            raise RuntimeError('write_boundary_fresh_root_required')
        value=json.loads(protected(self.root/'authorization.json',private=True).read_text())
        if (value.get('operation')!='active-local-rollback-resumption'
                or value.get('plan_sha256')!=self.plan.digest
                or value.get('source_bundle_sha256')!=self.plan.source_bundle_sha256):
            raise RuntimeError('write_boundary_authorization_changed')
    def guard(self):
        self.authorization()
        events=[json.loads(line) for line in protected(self.root/'events.jsonl',private=True).read_text().splitlines()]
        required={'read_only_serving','controller_resumed','standby_ready'}
        if (not events or any(row.get('plan_sha256')!=self.plan.digest for row in events)
                or not required.issubset(row.get('phase') for row in events)
                or events[-1].get('phase')!='write_grant_pending'
                or events[-1].get('normal_writes_may_have_occurred') is not True):
            raise RuntimeError('write_boundary_phase_denied')
        installed=json.loads(protected(self.root/'installed-controller.json',private=True).read_text())
        if (installed.get('plan_sha256')!=self.plan.digest or installed.get('source_sha')!=self.plan.source_sha
                or installed.get('source_bundle_sha256')!=self.plan.source_bundle_sha256
                or installed.get('historical_authorization_reused') is not False
                or installed.get('volatile_credential_reconstructed') is not False):
            raise RuntimeError('write_boundary_controller_attestation_changed')
        self.candidate.require_write_authority(self.candidate.contract,'READ_ONLY')
        # Execute the fresh prerequisite verifier; no boolean/PASS packet supplied
        # by an agent is interpreted as an independently executed test.
        self.prerequisites()
        self.runtime_verifier.read_only(workers_started=True)
        self.source_guard()
    def grant(self):
        self.guard()
        with runtime_mutation_lock(self.candidate.state):
            self.guard()
            path=self.root/'write-authority'/'authority.json'
            exclusive(self.root/'pre-grant-authority.json',protected(path).read_bytes())
            exclusive(self.root/'write-boundary.json',encoded({'version':1,'plan_sha256':self.plan.digest,
                'source_sha':self.plan.source_sha,'source_bundle_sha256':self.plan.source_bundle_sha256,
                'began_at':datetime.now(timezone.utc).isoformat(),'normal_writes_may_have_occurred':True,
                'customer_database_restore_permitted':False}))
            # Reuse the independently reviewed umask/permissions correction, not
            # the legacy phase/credential/PASS-based authorization entrypoint.
            self.candidate._publish_write_authority(self.candidate.contract,'NORMAL')
            self.candidate.require_write_authority(self.candidate.contract,'NORMAL')
    def revoke(self):
        self.authorization()
        # Revocation is permitted even if the grant/report was interrupted. It
        # cannot enable writes and must not require a writable events.jsonl.
        self.candidate._publish_write_authority(self.candidate.contract,'READ_ONLY')
        self.candidate.require_write_authority(self.candidate.contract,'READ_ONLY')
