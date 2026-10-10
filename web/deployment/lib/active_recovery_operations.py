"""Concrete exact-source continuation adapter; invoked only by the frozen bootstrap.

All effects delegate to the reviewed guarded components. Historical transaction
receipts remain unchanged. There is no migration or customer-restore operation.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
import pwd
from pathlib import Path
import time

from deployment.lib.active_recovery_resumption import ROOT,controller_revision
from deployment.lib.active_recovery_source import FrozenContinuationSource
from deployment.lib.active_recovery_inputs import INPUTS, observe_retained_inputs, observe_runtime_dependencies, verify_native_continuation_dependencies
from deployment.lib.active_recovery_execution import CHECKPOINT, RESTORE, verify_original_factor_execution, verify_local_reconciliation_execution
from deployment.lib.checkpoint_execution_proof import verify_supervised_native_restore, coordinated_health_marker
from deployment.lib.active_recovery_candidate import DetachedRecoveryCandidate
from deployment.lib.active_recovery_controller import ActiveRecoveryControllerRepair, ActiveRecoveryBackupTimers
from deployment.lib.active_recovery_workers import ActiveRecoveryWorkerHandoff
from deployment.lib.active_recovery_runtime import ActiveRecoveryRuntime
from deployment.lib.active_recovery_handoff import ReadOnlyRoutingHandoff
from deployment.lib.active_recovery_reconciliation import CurrentLocalReconciliation
from deployment.lib.active_recovery_listener import ActiveRecoveryFallbackInstallation
from deployment.lib.active_recovery_boot_installation import ActiveRecoveryBootInstallation
from deployment.lib.active_recovery_boot_actor import ActiveRecoveryBootActor
from deployment.lib.active_recovery_publication import ActiveRecoveryNormalPublication
from deployment.lib.active_recovery_write_authority import ActiveRecoveryWriteAuthority
from deployment.lib.provider_local_transition import LocalTransitionContract
from deployment.lib.provider_recovery_bootstrap import exclusive_lock
from deployment.lib.provider_recovery_runtime import protected, readonly_configuration, digest, file_digest
from deployment.lib.emergency_routing_repair import Runtime, AvailabilityFailure, verification_window, verify, legacy_installation, identities, spec, exclusive, encoded, UPSTREAM
from deployment.lib.release_deployer import atomic_json


class ProductionActiveRecoveryOperations:
    def __init__(self, plan, package):
        self.plan, self.package, self.root = plan, Path(package), ROOT/plan.digest
        self.source = FrozenContinuationSource(plan, self.package)
        self.runtime = Runtime()
        self.runtime.expected_nginx_sha256 = plan.retained_inputs['proxy_configuration']
        from deployment.lib.active_recovery_retained_fallback import declaration
        self.backup_preparation=bool(declaration(plan))
        self.candidate = self.workers = self.kernel = self.handoff = self.controller = None

    def compensated_binding(self):
        return (getattr(self.plan,'candidate_destination',None) or {}).get('post_compensation')

    def verify_compensated_state(self):
        from deployment.lib.active_recovery_compensated import verify_compensated_binding
        return verify_compensated_binding(self.compensated_binding(),self.runtime,
            staged_plan=self.plan if self.candidate is not None else None)

    def observe_inputs(self):
        if self.compensated_binding() and (self.root/'boot-installation.json').exists():
            from deployment.lib.active_recovery_boot_installation import verify_post_compensation_boot
            verify_post_compensation_boot(self.plan,self.root,self.runtime)
        return observe_retained_inputs(post_compensation=bool(self.compensated_binding()))

    def verify_frozen_source(self, plan):
        if plan != self.plan: raise RuntimeError('continuation_plan_changed')
        return self.source.verify()

    def verify_actual_execution_evidence(self, plan):
        self.verify_frozen_source(plan)
        proof = verify_supervised_native_restore(CHECKPOINT, RESTORE,
            approved_execution_digest=plan.checkpoint_execution_sha256,
            protected_file=protected, now=datetime.now(timezone.utc))
        if proof['checkpoint_manifest_sha256'] != plan.checkpoint_manifest_sha256:
            raise RuntimeError('continuation_checkpoint_changed')
        verify_original_factor_execution(plan.checkpoint_manifest_sha256)
        verify_local_reconciliation_execution(plan)
        from deployment.lib.active_recovery_artifact_evidence import verify_artifact_acceptance
        return verify_artifact_acceptance(plan)

    def verify_active_rollback_inputs(self, plan):
        self.verify_frozen_source(plan)
        from deployment.lib.active_recovery_backup_freshness import declaration,require_publication
        if declaration(plan) and not self.backup_preparation:require_publication(plan,self.package,self.runtime)
        from deployment.lib.active_recovery_retained_fallback import declaration as retained,verify_backup
        if retained(plan):verify_backup(plan)
        from deployment.lib.active_recovery_controller import prior_backup_timer_states
        prior=prior_backup_timer_states(plan)
        if prior is not None:
            timers=ActiveRecoveryBackupTimers(plan,self.root,self.source.verify)
            timers.require_idle_services()
            if any(timers.ops.systemctl_state(name)['active']!='inactive' for name in prior):
                raise RuntimeError('retry_timer_not_quiesced')
        readonly_configuration(Path('/var/lib/madar/backup-state/latest.json'),private=False)
        from deployment.lib.active_recovery_backup import verify_backup_execution_context
        verify_backup_execution_context(self.package)
        if self.candidate is None:self.verify_candidate_feasibility(plan)
        if self.compensated_binding():self.verify_compensated_state()
        if self.observe_inputs() != plan.retained_inputs:
            raise RuntimeError('continuation_retained_inputs_changed')
        for key in ('local_transaction', 'recovery_transaction'):
            if json.loads(INPUTS[key].read_text()).get('phase') != 'local_rollback_active':
                raise RuntimeError('continuation_active_rollback_required')

    def verify_emergency_installation(self, plan):
        if self.compensated_binding():
            observed=self.verify_compensated_state()
            if observed['emergency_installation_sha256']!=plan.emergency_installation_sha256:
                raise RuntimeError('continuation_emergency_installation_changed')
            return
        # Exact existing files/process/listeners, including the successful retry.
        if digest(legacy_installation(self.runtime)) != plan.emergency_installation_sha256:
            raise RuntimeError('continuation_emergency_installation_changed')

    def verify_restricted_fallback(self, plan):
        from deployment.lib.active_recovery_retained_fallback import declaration,verify_runtime
        if declaration(plan):
            self.require_no_normal_write_authority()
            return verify_runtime(plan,self.runtime)
        if self.compensated_binding() and not (self.root/'installed-controller.json').exists():
            from deployment.lib.active_recovery_compensated import inspect_history
            from deployment.lib.active_recovery_fallback import CurrentDataFallback
            previous,previous_root,_,_=inspect_history(self.compensated_binding()['baseline']['previous_plan_sha256'])
            if previous.fallback!=plan.fallback:raise RuntimeError('continuation_fallback_changed')
            return CurrentDataFallback(previous,previous_root,runtime=self.runtime).verify_registered_runtime(backup_preparation=self.backup_preparation)
        if self.candidate is None or not (self.root/'installed-controller.json').exists():
            packet, _ = verify(self.runtime)
            _, _, names, _ = identities(self.runtime.input_bytes())
            observed = {role: {'container_id':packet['runtimes'][name]['id'],
                'image_id':packet['runtimes'][name]['image'], 'spec_sha256':packet['runtimes'][name]['spec_sha256']}
                for role, name in names.items()}
            if observed != plan.fallback: raise RuntimeError('continuation_fallback_changed')
        else:
            self.actor().fallback.verify_registered_runtime()

    def require_all_consumers_stopped(self):
        observe_runtime_dependencies(self.runtime,fallback_names=bool(self.compensated_binding()))

    def require_no_normal_write_authority(self):
        authority = json.loads(protected(INPUTS['write_authority']).read_text())
        if authority.get('mode') != 'READ_ONLY' or authority.get('schema') != 115:
            raise RuntimeError('continuation_old_write_authority_changed')
        self.runtime.schema()

    def capture_verified_runtime_dependencies(self, plan):
        packet, sha = observe_runtime_dependencies(self.runtime,fallback_names=bool(self.compensated_binding()))
        if sha != plan.retained_inputs['runtime_dependencies']:
            raise RuntimeError('continuation_dependency_changed')
        return packet

    def exclusive_private_namespace(self, root):
        if root != self.root: raise RuntimeError('continuation_namespace_changed')
        parent = ROOT
        existing=parent if parent.exists() else parent.parent
        for path in (existing,*existing.parents):
            st=path.lstat()
            if path.is_symlink() or not path.is_dir() or st.st_uid!=0 or st.st_mode&0o022:
                raise RuntimeError('continuation_namespace_untrusted')
        if not parent.exists():parent.mkdir(mode=0o700)
        if parent.stat().st_mode&0o077:raise RuntimeError('continuation_namespace_not_private')
        root.mkdir(mode=0o700)

    def upgrade_lock(self):
        return exclusive_lock(Path('/var/lib/madar-control-plane/upgrades/upgrade.lock'))

    def deploy_lock(self):
        return exclusive_lock(Path('/var/lib/madar/releases/deploy.lock'))

    def require_unused_attempt(self, root):
        rows = [json.loads(line) for line in protected(root/'events.jsonl',private=True).read_text().splitlines()]
        if len(rows) != 1 or rows[0]['phase'] != 'authorized':
            raise RuntimeError('continuation_attempt_already_consumed')

    def quiesce_backup_timers_before_staging(self, plan, root):
        ActiveRecoveryBackupTimers(plan,root,self.source.verify).quiesce()
        from deployment.lib.active_recovery_retained_fallback import declaration as retained,verify_backup
        if retained(plan):
            verify_backup(plan)
            return
        marker = Path('/var/lib/madar/backup-state/latest.json')
        exclusive(root/'backup-health-preimage.json',readonly_configuration(marker,private=False).read_bytes())
        from deployment.lib.active_recovery_backup_freshness import declaration,require_publication
        if declaration(plan):
            # Keep the genuinely fresh ordinary backup; never overwrite it with
            # the historical checkpoint marker after backup-first publication.
            require_publication(plan,self.package,self.runtime)
            return
        data = coordinated_health_marker(CHECKPOINT,RESTORE,
            approved_execution_digest=plan.checkpoint_execution_sha256,
            protected_file=protected,now=datetime.now(timezone.utc))
        atomic_json(marker,data)
        # Health data contains only hashes/time/schema, never authorization or
        # secrets. Preserve the existing readable runtime-data permission.
        operator=pwd.getpwnam('madar')
        os.chown(marker,operator.pw_uid,operator.pw_gid);os.chmod(marker,0o644)

    def candidate_contract(self,plan):
        old = json.loads(protected(INPUTS['recovery_contract'],private=True).read_text())
        mapping = {'environment':'production_configuration','state':'release_state','upstream':'upstream',
            'worker_authority':'worker_authority','controller':'controller','recovery':'recovery_transaction','traffic':'traffic'}
        return LocalTransitionContract(plan.source_sha,dict(plan.candidate_images),digest(old),
            plan.checkpoint_manifest_sha256,plan.reconciliation_execution_sha256,plan.acceptance_execution_sha256,
            {key:plan.retained_inputs[value] for key,value in mapping.items()})

    def verify_candidate_feasibility(self,plan):
        if plan.candidate_destination is None:raise RuntimeError('continuation_candidate_destination_required')
        result=DetachedRecoveryCandidate.read_only_feasibility(plan,self.candidate_contract(plan),self.root)
        from deployment.lib.active_recovery_candidate import require_unreserved_ports
        from deployment.lib.active_recovery_boot_installation import UNITS,DROPIN
        paths=[UNITS/('madar-normal-local-'+kind+'-'+plan.digest[:12]+'.service') for kind in ('boot','fallback')]
        controls=paths if self.compensated_binding() else [*paths,DROPIN]
        if any(path.exists() or path.is_symlink() for path in controls):
            raise RuntimeError('continuation_exclusive_service_already_exists')
        if self.compensated_binding():self.verify_compensated_state()
        else:require_unreserved_ports(self.runtime,(29501,39501,39502))
        return result

    def stage_detached_read_only_candidate(self, plan, root):
        self.verify_candidate_feasibility(plan)
        contract=self.candidate_contract(plan)
        self.candidate = DetachedRecoveryCandidate(plan,contract,root)
        self.candidate.stage()
        self.workers = ActiveRecoveryWorkerHandoff(plan,self.candidate,root,self.source.verify)
        self.kernel = ActiveRecoveryRuntime(plan,self.candidate,root,self.source.verify,self.workers,runtime=self.runtime)
        self.handoff = ReadOnlyRoutingHandoff(plan,self.candidate,root,runtime=self.runtime,observer=self.observe_inputs)
        self.controller = ActiveRecoveryControllerRepair(plan,self.candidate,root,self.source.verify,runtime=self.runtime)

    def converge(self, check, seconds):
        with verification_window(self.runtime,seconds):
            while True:
                try: return check()
                except AvailabilityFailure: time.sleep(self.runtime.budget(1))

    def verify_detached_candidate(self, plan, workers_required=False):
        if workers_required is not False: raise RuntimeError('continuation_detached_workers_denied')
        self.converge(self.candidate.verify_read_only,180)

    def prepare_current_data_compensation(self, plan, root):
        self.handoff.prepare()
        ActiveRecoveryFallbackInstallation(plan,root,self.package).install()
        ActiveRecoveryBootInstallation(plan,root,self.package).install()

    def read_only_public_round(self, route):
        if UPSTREAM.read_bytes() != route: raise RuntimeError('continuation_route_changed')
        verify_native_continuation_dependencies(self.plan,self.root,self.runtime)
        self.kernel.read_only(workers_started=False)

    def publish_read_only_handoff(self, plan, root):
        self.handoff.publish(self.read_only_public_round)

    def require_sustained_read_only_serving(self, plan, **limits):
        if limits != {'deadline_seconds':180,'consecutive_rounds':3,'minimum_span_seconds':5}:
            raise RuntimeError('continuation_convergence_policy_changed')
        self.require_emergency_routing_handoff_complete()
        self.read_only_public_round(self.handoff.route)

    def require_emergency_routing_handoff_complete(self):
        rows = [json.loads(line) for line in protected(self.root/'routing-events.jsonl',private=True).read_text().splitlines()]
        if (not rows or rows[-1].get('event') != 'previous_workers_drained'
                or not any(row.get('event') == 'activation_sustained' and row.get('successful_rounds',0)>=3
                    and row.get('sustained_seconds',0)>=5 for row in rows)):
            raise RuntimeError('continuation_worker_drain_incomplete')

    def install_and_attest_governed_controller(self, plan, root): self.controller.install()

    def establish_source_fence_and_reconcile(self, plan, root):
        reconcile = CurrentLocalReconciliation(plan,root,self.candidate,self.source.verify,
            lambda: verify_native_continuation_dependencies(plan,root,self.runtime))
        reconcile.fence_retained_hosted_writers()
        snapshot, sha = reconcile.snapshot()
        exclusive(root/'fenced-local-reconciliation.json',encoded({'plan_sha256':plan.digest,
            'observed_at':datetime.now(timezone.utc).isoformat(),'snapshot':snapshot,'snapshot_sha256':sha,
            'database_restore_performed':False}))

    def establish_single_worker_owner(self, plan, root): self.workers.establish_owner()
    def start_nonconsuming_standbys(self, plan, root): self.workers.start_standbys()
    def verify_standby_workers(self, plan): self.workers.verify_standbys()
    def verify_single_owner_and_standbys(self, plan):
        self.workers.verify_owner(); self.workers.verify_standbys()

    def verify_read_only_acceptance(self, plan):
        self.verify_actual_execution_evidence(plan)
        verify_native_continuation_dependencies(plan,self.root,self.runtime)
        self.kernel.read_only(workers_started=True)

    def require_exact_source_and_images(self, plan):
        self.source.verify(); self.candidate.verify_image_source()
        self.kernel.identities(workers_started=True)
        if protected(INPUTS['controller']).read_text().strip() != controller_revision(plan):
            raise RuntimeError('continuation_installed_source_changed')
        # Resolves current origin/main and forward ancestry without deployment.
        self.controller.ops.resolve_candidate(controller_revision(plan),dry_run=False)
        self.controller.ops.verify_installed_controller(controller_revision(plan))

    def verify_final_write_grant_prerequisites(self, plan):
        from deployment.lib.active_recovery_backup import verify_backup_execution_context
        verify_backup_execution_context(self.package)
        self.require_exact_source_and_images(plan)
        self.verify_read_only_acceptance(plan)
        self.verify_single_owner_and_standbys(plan)
        self.actor().fallback.verify_registered_runtime()
        for name in ('retained-writer-fence.json','fenced-local-reconciliation.json'):
            packet = json.loads(protected(self.root/name,private=True).read_text())
            if packet.get('plan_sha256') != plan.digest: raise RuntimeError('continuation_source_fence_missing')

    def commit_normal_release_and_grant_writes(self, plan, root):
        # Publication precedes grant but prerequisites independently reexecute.
        authority = ActiveRecoveryWriteAuthority(plan,self.candidate,root,self.source.verify,self.kernel,
            lambda:self.verify_final_write_grant_prerequisites(plan))
        authority.guard()
        ActiveRecoveryNormalPublication(plan,self.candidate,root,self.source.verify,self.kernel).publish()
        authority.grant()

    def sustained_normal_rounds(self, check):
        first=None;successes=0
        with verification_window(self.runtime,180):
            while True:
                self.runtime.budget(1)
                try:result=check()
                except AvailabilityFailure:first=None;successes=0
                else:
                    successes+=1
                    if first is None:first=time.monotonic()
                    if successes>=3 and time.monotonic()-first>=5:return result
                time.sleep(self.runtime.budget(1))

    def verify_normal_acceptance(self, plan):
        started = datetime.now(timezone.utc).isoformat()
        self.verify_actual_execution_evidence(plan)
        # Every round includes native identity, singleton workers, authority,
        # direct readiness and actual public requests. Only bounded availability
        # failures may reset convergence; integrity/security failures abort.
        from deployment.lib.active_recovery_artifact_evidence import public_normal_observations
        def round_check():
            verify_native_continuation_dependencies(plan,self.root,self.runtime)
            self.kernel.normal()
            return public_normal_observations(plan,self.candidate.slot)
        observations = self.sustained_normal_rounds(round_check)
        exclusive(self.root/'normal-acceptance.json',encoded({'operation':'actual-normal-runtime-verification',
            'plan_sha256':plan.digest,'source_sha':plan.source_sha,'images':plan.candidate_images,
            'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),
            'artifact_acceptance_execution_sha256':plan.acceptance_execution_sha256,'observations':observations,
            'schema':115,'database_restore_performed':False}))

    def capture_replicate_and_verify_post_cutover_backup(self, plan, root):
        from deployment.lib.active_recovery_backup import capture_and_replicate
        capture_and_replicate(plan,root,self.package,self.source.verify,self.kernel)
        names = ('normal-acceptance.json','post-cutover-backup.json','installed-controller.json','worker-owner.json','normal-publication.json')
        exclusive(root/'normal-completion.json',encoded({'operation':'completed-normal-local-continuation',
            'plan_sha256':plan.digest,'source_sha':plan.source_sha,'source_bundle_sha256':plan.source_bundle_sha256,
            'images':plan.candidate_images,'schema':115,'database_restore_performed':False,
            'retained_execution_files':{name:file_digest(protected(root/name,private=True)) for name in names}}))
        self.actor().completed_evidence()

    def restore_configured_backup_timers(self, plan, root): self.controller.restore_configured_backup_timers()
    def actor(self):
        actor = ActiveRecoveryBootActor(self.plan,self.root,self.package)
        actor.candidate,actor.workers,actor.kernel = self.candidate,self.workers,self.kernel
        return actor
    def fence_normal_writes_and_stop_consumers(self, plan):
        self.source.verify()
        # A failed fence cannot skip stopping the independently bound consumers.
        try: self.candidate._publish_write_authority(self.candidate.contract,'READ_ONLY')
        finally:
            try:self.workers.stop_consumers()
            finally:
                if self.compensated_binding():
                    ActiveRecoveryBackupTimers(plan,self.root,self.source.verify).quiesce_compensation()
        self.candidate.require_write_authority(self.candidate.contract,'READ_ONLY')
    def publish_verified_current_data_fallback(self, plan, root, deadline_seconds):
        if deadline_seconds != 60: raise RuntimeError('continuation_compensation_deadline_changed')
        actor = self.actor(); actor.compensation.publish(actor.fallback_public_round)
    def verify_restricted_fallback_serving(self, plan):
        from deployment.lib.active_recovery_fallback import FALLBACK_ROUTE
        self.actor().fallback_public_round(FALLBACK_ROUTE)
    def activate_maintenance_or_stop_proxy(self, plan, root):
        actor=self.actor()
        try:actor.stop_bound_runtimes_for_failed_compensation()
        finally:actor.compensation.maintenance_or_stop_proxy()
