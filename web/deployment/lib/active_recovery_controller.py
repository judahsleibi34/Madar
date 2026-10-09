"""Freshly authorized active-rollback controller installation component.

Reuses the canonical installer and exact-main staging/attestation operations.
Historical transaction/credential/witness records are not refreshed or reset.
Public sustained READ_ONLY handoff must precede every installed-code mutation.
"""
import json
import os
from pathlib import Path
from deployment.lib.active_recovery_resumption import ROOT
from deployment.lib.active_recovery_inputs import INPUTS
from deployment.lib.emergency_routing_repair import Runtime,UPSTREAM,exclusive,encoded
from deployment.lib.provider_recovery_runtime import protected,file_digest,digest
from deployment.lib.control_plane_upgrade import SystemOperations,BACKUP_TIMERS,validate_backup_timer_states,BACKUP_BUSY_STATES

def prior_backup_timer_states(plan):
    """Previous failed-attempt timer snapshot is data, never reused authority."""
    binding=getattr(plan,'prior_backup_timer_preimage',None)
    if binding is None:return None
    root=ROOT/binding['plan_sha256']
    if root==ROOT/plan.digest:raise RuntimeError('retry_timer_same_attempt_denied')
    names=('authorization.json','plan.json','events.jsonl','backup-timer-preimage.json')
    paths={name:protected(root/name,private=True) for name in names}
    hashes={name:file_digest(path) for name,path in paths.items()}
    if (digest(hashes)!=binding['evidence_sha256']
            or hashes['plan.json']!=binding['plan_sha256']
            or hashes['backup-timer-preimage.json']!=binding['timer_preimage_sha256']):
        raise RuntimeError('retry_timer_evidence_changed')
    saved=json.loads(paths['plan.json'].read_text())
    receipt=json.loads(paths['authorization.json'].read_text())
    events=[json.loads(line) for line in paths['events.jsonl'].read_text().splitlines()]
    if (receipt.get('operation')!='active-local-rollback-resumption'
            or receipt.get('plan_sha256')!=binding['plan_sha256']
            or receipt.get('source_bundle_sha256')!=saved.get('source_bundle_sha256')
            or saved.get('retained_inputs')!=plan.retained_inputs
            or [row.get('phase') for row in events]!=['authorized','detached_candidate_pending','detached_candidate_failed']
            or any(row.get('plan_sha256')!=binding['plan_sha256'] for row in events)
            or (root/'candidate-contract.json').exists() or (root/'candidate-identities.json').exists()):
        raise RuntimeError('retry_timer_prior_attempt_not_applicable')
    return validate_backup_timer_states(json.loads(paths['backup-timer-preimage.json'].read_text()))


class ActiveRecoveryControllerRepair:
    def __init__(self,plan,candidate,root,source_guard,*,operations=None,runtime=None):
        if not callable(source_guard):raise RuntimeError('controller_resume_source_guard_required')
        self.plan,self.candidate,self.root,self.source_guard=plan,candidate,Path(root),source_guard
        self.ops=operations or SystemOperations();self.runtime=runtime or Runtime()
    def guard(self):
        self.source_guard()
        if os.geteuid()!=0 or self.root!=ROOT/self.plan.digest:raise RuntimeError('controller_resume_fresh_root_required')
        receipt=json.loads(protected(self.root/'authorization.json',private=True).read_text())
        if (receipt.get('operation')!='active-local-rollback-resumption' or receipt.get('plan_sha256')!=self.plan.digest
                or receipt.get('source_bundle_sha256')!=self.plan.source_bundle_sha256):raise RuntimeError('controller_resume_authorization_changed')
        events=[json.loads(line) for line in protected(self.root/'events.jsonl',private=True).read_text().splitlines()]
        if (not events or any(row.get('plan_sha256')!=self.plan.digest for row in events)
                or events[-1].get('phase')!='controller_resume_pending'
                or 'read_only_serving' not in [row.get('phase') for row in events]):
            raise RuntimeError('controller_resume_read_only_handoff_required')
        route=(f'upstream madar_backend_active {{ server 127.0.0.1:{self.candidate.backend_port}; }}\n'
            f'upstream madar_frontend_active {{ server 127.0.0.1:{self.candidate.frontend_port}; }}\n').encode()
        if UPSTREAM.read_bytes()!=route:raise RuntimeError('controller_resume_public_route_changed')
        self.candidate.require_write_authority(self.candidate.contract,'READ_ONLY')
        for base in ('http://127.0.0.1:8001','http://127.0.0.1:3000/api'):
            version=self.runtime.json_http(base+'/health/version')
            if version.get('release_sha')!=self.plan.source_sha or version.get('release_slot')!=self.candidate.slot:
                raise RuntimeError('controller_resume_serving_source_changed')
            self.runtime.denied(base)
        return route
    def quiesce_backup_timers(self):
        # Called at install for backwards-compatible component use. A complete
        # continuation quiesces earlier, before publishing its backup marker.
        self.guard()
        path=self.root/'backup-timer-preimage.json'
        if path.exists() or path.is_symlink():
            try:
                saved=json.loads(protected(path,private=True).read_text())
                validate_backup_timer_states(saved)
            except (ValueError,RuntimeError):
                raise FileExistsError('controller_resume_timer_preimage_unusable') from None
            ActiveRecoveryBackupTimers(self.plan,self.root,self.source_guard,operations=self.ops).require_quiesced()
            return
        ActiveRecoveryBackupTimers(self.plan,self.root,self.source_guard,operations=self.ops).quiesce()
    def install(self):
        route=self.guard();bundle=self.source_guard()
        if not isinstance(bundle,dict) or bundle.get('source_sha')!=self.plan.source_sha or not isinstance(bundle.get('files'),dict):
            raise RuntimeError('controller_resume_frozen_bundle_missing')
        self.quiesce_backup_timers()
        # Fetch/checkout changes occur only through existing governed exact-main
        # operations after approval. No source is developed in the staging tree.
        self.ops.resolve_candidate(self.plan.source_sha,dry_run=False)
        transaction,staged=self.ops.stage_candidate(self.plan.source_sha)
        tree=self.ops.static_preflight(staged)
        for relative,expected in bundle['files'].items():
            path=Path(relative)
            if path.is_absolute() or '..' in path.parts or file_digest(protected(staged/path))!=expected:
                raise RuntimeError('controller_resume_staged_bundle_mismatch')
        if file_digest(staged/'web/deployment/proxy/nginx.conf')!=self.plan.retained_inputs['proxy_configuration']:
            raise RuntimeError('controller_resume_nginx_handoff_incompatible')
        # The original live proxy keeps its mounted nginx inode. Replacing the
        # controller is safe here only when the old/new bytes are identical.
        backup=self.root/'controller-backup';backup.mkdir(mode=0o700)
        self.ops.installer_dry_run(staged,backup)
        self.guard();self.source_guard()
        if self.ops.protected_tree_digest(staged)!=tree:raise RuntimeError('controller_resume_staged_source_changed')
        self.ops.installer_apply(staged,backup,self.plan.source_sha)
        self.ops.advance_production_checkout(self.plan.source_sha)
        self.ops.verify_install(self.plan.source_sha,backup)
        if UPSTREAM.read_bytes()!=route:raise RuntimeError('controller_resume_installer_changed_route')
        exclusive(self.root/'installed-controller.json',encoded({'version':1,'plan_sha256':self.plan.digest,
            'source_sha':self.plan.source_sha,'source_bundle_sha256':self.plan.source_bundle_sha256,
            'staged_tree_sha256':tree,'backup_path':str(backup),'staging_transaction':str(transaction),
            'historical_authorization_reused':False,'volatile_credential_reconstructed':False}))
        self.guard()
    def restore_configured_backup_timers(self):
        self.source_guard()
        events=[json.loads(line) for line in protected(self.root/'events.jsonl',private=True).read_text().splitlines()]
        if not events or events[-1].get('phase')!='normal':raise RuntimeError('controller_resume_backup_timers_before_normal')
        states=validate_backup_timer_states(json.loads(protected(self.root/'backup-timer-preimage.json',private=True).read_text()))
        for name,row in states.items():
            if row['active']=='active':self.ops.command('continuation_backup_timer_restore',['/usr/bin/systemctl','start',name])
        # Automatic deployment intentionally remains disabled until a separately
        # attested recovery-interlock supersession; no historical receipt deletion.


class ActiveRecoveryBackupTimers:
    """Save exact timer states once before marker/staging, without /run repair."""
    def __init__(self,plan,root,source_guard,*,operations=None):
        if not callable(source_guard):raise RuntimeError('backup_quiesce_source_guard_required')
        self.plan,self.root,self.source_guard=plan,Path(root),source_guard
        self.ops=operations or SystemOperations()
    def guard(self):
        self.source_guard()
        if os.geteuid()!=0 or self.root!=ROOT/self.plan.digest:raise RuntimeError('backup_quiesce_fresh_root_required')
        receipt=json.loads(protected(self.root/'authorization.json',private=True).read_text())
        if (receipt.get('operation')!='active-local-rollback-resumption' or receipt.get('plan_sha256')!=self.plan.digest
                or receipt.get('source_bundle_sha256')!=self.plan.source_bundle_sha256):
            raise RuntimeError('backup_quiesce_authorization_changed')
        events=[json.loads(line) for line in protected(self.root/'events.jsonl',private=True).read_text().splitlines()]
        if (not events or any(row.get('plan_sha256')!=self.plan.digest for row in events)
                or events[-1].get('phase') not in {'detached_candidate_pending','controller_resume_pending'}):
            raise RuntimeError('backup_quiesce_phase_denied')
        self.require_idle_services()
    def require_idle_services(self):
        services={name:self.ops.systemctl_state(name.replace('.timer','.service')) for name in BACKUP_TIMERS}
        if any(row['active'] in BACKUP_BUSY_STATES or row['active'] not in {'inactive','failed'} for row in services.values()):
            raise RuntimeError('controller_resume_backup_operation_busy')
        if (self.ops.systemctl_state('madar-auto-deploy.timer')!={'enabled':'disabled','active':'inactive'}
                or self.ops.systemctl_state('madar-auto-deploy.service')['active']!='inactive'):
            raise RuntimeError('controller_resume_automation_not_quiesced')
    def require_quiesced(self):
        self.guard()
        validate_backup_timer_states(json.loads(protected(self.root/'backup-timer-preimage.json',private=True).read_text()))
        if any(self.ops.systemctl_state(name)['active']!='inactive' for name in BACKUP_TIMERS):
            raise RuntimeError('controller_resume_timer_quiesce_failed')
    def quiesce(self):
        self.guard()
        current=validate_backup_timer_states({name:self.ops.systemctl_state(name) for name in BACKUP_TIMERS})
        prior=prior_backup_timer_states(self.plan)
        if prior is not None and any(row['active']!='inactive' for row in current.values()):
            raise RuntimeError('retry_timer_not_quiesced')
        states=prior if prior is not None else current
        exclusive(self.root/'backup-timer-preimage.json',encoded(states))
        if prior is not None:
            exclusive(self.root/'backup-timer-retry-observation.json',encoded({'prior':self.plan.prior_backup_timer_preimage,'observed_current':current}))
        for name,row in current.items():
            if row['active']=='active':self.ops.command('continuation_backup_timer_stop',['/usr/bin/systemctl','stop',name])
        self.require_quiesced()
