"""One exact completed-NORMAL bridge-first operation, using installed services.

No automatic replay or database rollback. Durable boot is a READ_ONLY forward
repair mechanism after SQL intent; it cannot finish this operation unattended.
The full isolated execution and a fresh operator-approved package are required
before this coordinator can be invoked against production.
"""
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import traceback

from deployment.lib.completed_normal_admission import ADMISSIONS,OPERATION,digest,encoded,publish_admission
from deployment.lib.completed_normal_backup import CompletedNormalBackupContext
from deployment.lib.completed_normal_boot_installation import CompletedNormalBootInstallation
from deployment.lib.completed_normal_boot_actor import verify_live_configuration
from deployment.lib.completed_normal_database import (customer_baseline,observe_native,
    migration_customer_snapshot,verify_migration_customer_preservation)
from deployment.lib.completed_normal_migration import seal_intent,seal_completion
from deployment.lib.completed_normal_resources import verify_allocation
from deployment.lib.completed_normal_runtime import seal_candidate_stage,seal_candidate_runtime
from deployment.lib.completed_normal_write_handoff import CompletedNormalWriteHandoff,atomic_public_authority
from deployment.lib.control_plane_upgrade import acquire_lock,BACKUP_TIMERS
from deployment.lib.emergency_routing_repair import exclusive
from deployment.lib.provider_recovery_runtime import protected,readonly_configuration,file_digest


def verify_serving(actor, *, schema,normal):
    """Observe the exact candidate and stable routes; no customer mutation.

    Authenticated application cases are independently pinned by the artifact
    and complete-private-rehearsal gates. This runtime check does not claim a
    live customer login or mutation when no approved credential is available.
    """
    import time
    from deployment.lib.emergency_routing_repair import verification_window,AvailabilityFailure
    if schema not in {115,136} or type(normal) is not bool:
        raise RuntimeError('completed_upgrade_serving_mode_invalid')
    first=None;successes=0
    with verification_window(actor.runtime,180):
        while True:
            actor.runtime.budget(1);actor.guard();actor.proxy_identity()
            try:
                actor.candidate().round(normal=normal)
                if actor.native()!=schema:raise RuntimeError('completed_upgrade_serving_schema_changed')
                for base in ('http://127.0.0.1:8001','http://127.0.0.1:3000/api'):
                    version=actor.runtime.json_http(base+'/health/version')
                    if (version.get('release_sha')!=actor.contract['candidate']['source_sha']
                            or version.get('release_slot')!=actor.contract['candidate']['slot']
                            or version.get('schema_compatible_min')!=115 or version.get('schema_compatible_max')!=136
                            or actor.runtime.json_http(base+'/health/recovery')!={'restricted':not normal,'business_writes_enabled':normal}):
                        raise RuntimeError('completed_upgrade_stable_serving_identity_changed')
                    if not normal:actor.runtime.denied(base)
                actor.runtime.http_status('http://127.0.0.1:3000/')
                actor.guard();actor.proxy_identity()
            except AvailabilityFailure:first=None;successes=0
            else:
                successes+=1
                if first is None:first=time.monotonic()
                if successes>=3 and time.monotonic()-first>=5:break
            time.sleep(actor.runtime.budget(1))
    return {'schema':schema,'mode':'NORMAL' if normal else 'READ_ONLY','stable_frontend_http':200,
        'stable_api_verified':True,'complete_rounds':successes,'authenticated_customer_mutation_executed':False}


@contextmanager
def protected_creation_mode():
    """Root staging must not inherit a permissive launcher umask."""
    previous=os.umask(0o077)
    try:yield
    finally:os.umask(previous)


class CompletedNormalUpgrade:
    """Root orchestrates; actual release mutation remains User/Group madar.

    Artifact/model verifiers are supplied by the measured entrypoint. A caller
    summary or an old acceptance grant cannot substitute for these verifiers.
    """
    def __init__(self,actor,*,artifact_guard,model_loader,acceptance_guard,rehearsal_guard):
        if not all(callable(f) for f in (artifact_guard,model_loader,acceptance_guard,rehearsal_guard)):
            raise RuntimeError('completed_upgrade_independent_execution_guards_required')
        self.actor=actor;self.contract=actor.contract;self.document=actor.document
        self.ops=actor.ops;self.root=actor.root;self.package=actor.package
        self.artifact_guard=artifact_guard;self.model_loader=model_loader
        self.acceptance_guard=acceptance_guard;self.rehearsal_guard=rehearsal_guard
        self.controller=self.contract['candidate']['controller_sha']
        self.phase='preflight';self.quiesced=False;self.admitted=False;self.fenced=False
        self.controller_installed=False;self.lock=None

    def preparation_source(self):
        measured,_=self.actor.measure()
        if os.geteuid()!=0 or measured!=self.document:
            raise RuntimeError('completed_upgrade_preparation_source_changed')
        verify_live_configuration(self.document)

    def preflight(self, *, locked=False):
        """No authorization consumption, service effects, or live SQL writes."""
        self.preparation_source();self.artifact_guard();self.rehearsal_guard()
        before=self.ops.current_preflight(lock_deployment=locked)
        if (before['schema']!=115 or before['slot']!=self.contract['origin']['slot']
                or before['installed_sha']!=self.contract['source_roles']['controller_sha']
                or before['production_sha']!=self.contract['source_roles']['controller_sha']
                or before.get('source_roles')!=self.contract['source_roles']):
            raise RuntimeError('completed_upgrade_origin_binding_changed')
        from deployment.lib.completed_normal_admission import verify_history
        from deployment.lib.active_recovery_inputs import controller_tree_digest
        verify_history(self.contract)
        if controller_tree_digest()!=self.document['installed_controller_tree_sha256']:
            raise RuntimeError('completed_upgrade_installed_preimage_changed')
        # A fresh operation must not inherit an unrelated volatile upgrade
        # interlock, or discover a missing root lock after authorization.
        protected(self.ops.upgrade_root/'upgrade.lock',private=True)
        if self.ops.interlock_file.exists() or self.ops.interlock_file.is_symlink():
            raise RuntimeError('completed_upgrade_existing_interlock_requires_reconciliation')
        observe_native(self.contract,self.actor.runtime)
        from deployment.lib.active_recovery_backup import verify_backup_execution_context
        verify_backup_execution_context(self.package)
        baseline=customer_baseline(self.contract,self.actor.runtime)
        if (baseline['table_roots_sha256']!=self.contract['customer_table_roots_sha256']
                or baseline['identity_roots_sha256']!=self.contract['customer_identity_roots_sha256']):
            raise RuntimeError('completed_upgrade_current_customer_data_changed')
        allocation=verify_allocation(self.contract,self.contract['candidate']['slot'],self.actor.runtime)
        # Render the exact staging builder before authorization. Its dedicated
        # read-only mode rejects every command except Compose config and does
        # not invent an admission, grant, worker owner or historical credential.
        from deployment.lib.completed_normal_model import render_candidate_model
        model=render_candidate_model(self.actor,read_only=True)
        if set(model.get('services',{}))!=set(allocation['containers']):
            raise RuntimeError('completed_upgrade_candidate_model_inventory_changed')
        # No fake systemd credential is created for this read-only inspection.
        installer=CompletedNormalBootInstallation(self.contract,self.document,self.package,
            self.preparation_source,self.ops)
        installer.preflight(read_only=True)
        self.actor.proxy_identity()
        if file_digest(readonly_configuration(Path('/var/lib/madar/proxy/active-upstreams.conf'),private=False))!=self.document['origin_routing_sha256']:
            raise RuntimeError('completed_upgrade_origin_route_changed')
        if self.root.exists() or self.root.is_symlink():raise RuntimeError('completed_upgrade_attempt_already_consumed')
        states={n:self.ops.systemctl_state(n) for n in BACKUP_TIMERS}
        if states!=self.document['backup_timer_states']:
            raise RuntimeError('completed_upgrade_backup_timer_preimages_changed')
        if any(self.ops.systemctl_state(n.replace('.timer','.service'))['active'] not in {'inactive','failed'} for n in BACKUP_TIMERS):
            raise RuntimeError('completed_upgrade_backup_service_running')
        self.preparation_source()
        return {'operation':OPERATION,'schema':115,'candidate':allocation,'production_modified':False,'authorization_consumed':False}

    @contextmanager
    def root_credential(self, *, migration_resumption=None):
        """New root-issued credential, never reconstruction of expired tokens."""
        extra={} if migration_resumption is None else {'migration_resumption':migration_resumption}
        self.ops.write_authorization(self.controller,completed_normal_contract=self.contract,**extra)
        # Use the existing systemd credential name without making the token
        # public or copying it into protected historical transaction records.
        directory=self.ops.runtime_root/('root-credentials-'+digest(self.contract)[:16])
        directory.mkdir(mode=0o700,exist_ok=True)
        path=directory/'madar-control-plane-upgrade'
        if path.exists() or path.is_symlink():raise RuntimeError('completed_upgrade_root_credential_collision')
        previous=os.environ.get('CREDENTIALS_DIRECTORY')
        try:
            exclusive(path,protected(self.ops.authorization_file,private=True).read_bytes())
            os.environ['CREDENTIALS_DIRECTORY']=str(directory)
            yield
        finally:
            if previous is None:os.environ.pop('CREDENTIALS_DIRECTORY',None)
            else:os.environ['CREDENTIALS_DIRECTORY']=previous
            path.unlink(missing_ok=True);self.ops.clear_authorization()

    def event(self,phase,**fields):
        self.phase=phase
        self.actor.event(phase,**fields)

    def service(self,mode):
        self.event('service_'+mode+'_pending')
        self.ops.run_deploy_service('completed_normal_'+mode,self.controller,
            completed_normal_contract=self.contract,completed_normal_mode=mode)
        self.event('service_'+mode+'_completed')

    def install_controller(self):
        self.actor.source();self.actor.installation.installed()
        self.ops.resolve_candidate(self.controller,dry_run=False)
        transaction,staged=self.ops.stage_candidate(self.controller)
        tree=self.ops.static_preflight(staged)
        manifest=json.loads(protected(self.package/'source-bundle.json',private=True).read_text())
        for relative,expected in manifest['files'].items():
            if file_digest(protected(staged/relative))!=expected:
                raise RuntimeError('completed_upgrade_staged_source_changed')
        if file_digest(protected(staged/'web/deployment/proxy/nginx.conf'))!=self.document['proxy_nginx_sha256']:
            raise RuntimeError('completed_upgrade_live_proxy_configuration_incompatible')
        # The ordinary installer publishes this base unit again. Prove its
        # bytes are already identical; do not invalidate the boot attestation.
        unit='web/deployment/systemd/madar-release-proxy.service'
        if file_digest(protected(staged/unit))!=self.document['boot_resources']['files']['/etc/systemd/system/madar-release-proxy.service']['sha256']:
            raise RuntimeError('completed_upgrade_proxy_base_unit_incompatible')
        backup=self.root/'controller-backup';backup.mkdir(mode=0o700)
        self.ops.installer_dry_run(staged,backup)
        intent={'operation':OPERATION,'context_sha256':digest(self.contract),
            'from_controller':self.contract['source_roles']['controller_sha'],'to_controller':self.controller,
            'old_tree_sha256':self.document['installed_controller_tree_sha256'],
            'new_tree_sha256':self.contract['candidate']['controller_tree_sha256']}
        exclusive(self.root/'controller-installation-intent.json',encoded(intent))
        self.actor.source()
        if self.ops.protected_tree_digest(staged)!=tree:raise RuntimeError('completed_upgrade_staged_source_changed')
        # Source/checkout role reconciliation is one governed installation
        # boundary. Interruption fails closed through the new boot actor.
        self.ops.installer_apply(staged,backup,self.controller)
        self.controller_installed=True
        self.ops.advance_production_checkout(self.controller)
        self.ops.verify_install(self.controller,backup)
        self.actor.guard()
        exclusive(self.root/'controller-installation.json',encoded(dict(intent,
            transaction=str(transaction),backup_path=str(backup),staged_tree_sha256=tree)))

    def failure(self,error):
        # Fixed stage/type and frame coordinates only. Never serialize exception
        # text, command output, configurations, SQL or customer values.
        evidence={'operation':OPERATION,'context_sha256':digest(self.contract),'phase':self.phase,
            'exception_type':type(error).__name__,'frames':[{'source':Path(f.filename).name,'line':f.lineno,'function':f.name}
                for f in traceback.extract_tb(error.__traceback__)[-24:]],'customer_database_restored':False}
        # Failure diagnostics must never prevent write revocation/compensation.
        # Preserve both exception types when compensation itself fails.
        try:
            if self.fenced or self.controller_installed or (self.root/'controller-installation-intent.json').exists():
                try:self.actor.compensate()
                finally:self.ops.requiesce_backup_timers_for_failure()
            elif self.quiesced:
                # Only independently attested unchanged old NORMAL may regain
                # its backup schedule. Never enable automatic deployment.
                # quiesce can reject a busy service or a foreign interlock
                # before capturing or mutating any timer. Do not mask that
                # original error with backup_timer_states_missing.
                if self.ops.durable_quiesce_snapshot_exists(self.controller):
                    self.ops.current_preflight(lock_deployment=False)
                    self.ops.restore_backup_timers()
        except Exception as compensation:
            evidence['compensation_exception_type']=type(compensation).__name__
            raise
        finally:
            if self.admitted:
                exclusive(self.root/'failure.json',encoded(evidence))
        return evidence

    def execute(self):
        if os.geteuid()!=0:raise RuntimeError('completed_upgrade_root_required')
        with protected_creation_mode():
            return self._execute()

    def _execute(self):
        self.preflight()
        self.lock=acquire_lock(self.ops.upgrade_root/'upgrade.lock',create=False)
        try:
            self.preflight(locked=True)
            self.quiesced=True;self.ops.quiesce(self.controller)
            with self.root_credential():
                publish_admission(self.contract,self.ops,self.ops.state_root)
            self.admitted=True
            authorization={'operation':OPERATION,'context_sha256':digest(self.contract),'plan_sha256':digest(self.document),
                'source_bundle_sha256':self.document['source_bundle_sha256'],'controller_sha':self.controller,
                'application_sha':self.contract['candidate']['source_sha']}
            exclusive(self.root/'operator-authorization.json',encoded(authorization))
            exclusive(self.root/'backup-timer-preimages.json',encoded(self.document['backup_timer_states']))
            with self.root_credential():
                self.event('boot_supersession_pending');self.actor.installation.install();self.actor.guard()
                self.event('controller_installation_pending');self.install_controller()
            # Existing deploy.lock must be released before the User=madar
            # service obtains it. The protected upgrade interlock stays armed.
            self.ops.release_deployment_lock()
            self.service('prepare')
            with self.root_credential():
                seal_candidate_stage(self.contract,source_guard=self.actor.guard,model_loader=self.model_loader,
                    runtime=self.actor.runtime,state_root=self.ops.state_root)
                kernel=self.actor.candidate()
                handoff=CompletedNormalWriteHandoff(self.contract,kernel,source_guard=self.actor.source,
                    boot_guard=self.actor.installation.installed,artifact_guard=self.artifact_guard)
                self.event('origin_write_fence_pending');self.fenced=True;handoff.fence_origin()
            self.service('activate')
            with self.root_credential():
                seal_candidate_runtime(self.contract,source_guard=self.actor.guard,model_loader=self.model_loader,
                    runtime=self.actor.runtime,state_root=self.ops.state_root)
                kernel.round(normal=False)
            self.service('publish')
            with self.root_credential():
                self.acceptance_guard(schema=115,normal=False)
                self.event('bridge_normal_grant_pending');handoff.grant(schema=115)
            self.service('adopt')
            with self.root_credential():
                self.acceptance_guard(schema=115,normal=True)
                # Stop consuming through the real grant, not by granting two
                # owners or relying on a status flag. The same healthy bridge
                # stays publicly available while the database is advanced.
                handoff.revoke();kernel.verify_mode(normal=False)
                self.event('pre_migration_backup_pending')
                backup=CompletedNormalBackupContext(self.contract,self.document,self.package,kernel,
                    stage='pre-migration',source_guard=self.actor.guard,artifact_guard=self.artifact_guard)
                receipt=backup.capture();backup.seal_migration_inputs(receipt)
                self.event('pre_migration_customer_snapshot_pending')
                customers=migration_customer_snapshot(self.contract,self.actor.runtime)
                exclusive(self.root/'pre-migration-customer-snapshot.json',encoded(customers))
                seal_intent(self.contract,source_guard=self.actor.guard,runtime_guard=self.actor.native,
                    backup_guard=lambda:backup.guard())
            self.service('migrate')
            with self.root_credential():
                self.event('migration_customer_preservation_pending')
                original=json.loads(protected(self.root/'pre-migration-customer-snapshot.json',private=True).read_text())
                after=migration_customer_snapshot(self.contract,self.actor.runtime,columns=original['columns'])
                exclusive(self.root/'post-migration-customer-snapshot.json',encoded(after))
                preservation=verify_migration_customer_preservation(original,after)
                exclusive(self.root/'migration-customer-preservation.json',encoded(preservation))
                self.event('migration_completion_pending')
                seal_completion(self.contract,self.ops.state_root/'releases'/self.contract['candidate']['source_sha'],self.ops.state_root,
                    source_guard=self.actor.guard,runtime_guard=self.actor.native)
            self.service('refresh')
            with self.root_credential():
                self.acceptance_guard(schema=136,normal=False)
                self.event('target_normal_grant_pending');handoff.grant(schema=136)
                self.acceptance_guard(schema=136,normal=True)
                self.event('post_migration_backup_pending')
                backup=CompletedNormalBackupContext(self.contract,self.document,self.package,kernel,
                    stage='post-migration',source_guard=self.actor.guard,artifact_guard=self.artifact_guard)
                receipt=backup.capture()
                self.event('backup_timer_restore_pending');self.ops.restore_backup_timers()
                kernel.round(normal=True);self.acceptance_guard(schema=136,normal=True)
                self.event('normal_completed',schema=136,mode='NORMAL')
                result={'operation':OPERATION,'context_sha256':digest(self.contract),'schema':136,'mode':'NORMAL',
                    'application_sha':self.contract['candidate']['source_sha'],'controller_sha':self.controller,
                    'images':self.contract['candidate']['images'],'backup':receipt,
                    'backup_timers':{n:self.ops.systemctl_state(n) for n in BACKUP_TIMERS},'customer_database_restored':False}
                exclusive(self.root/'normal-completion.json',encoded(result))
            self.ops.clear_interlock()
            return result
        except Exception as error:
            self.failure(error)
            raise
        finally:
            self.ops.clear_authorization();self.ops.close_locks()
            if self.lock is not None:os.close(self.lock);self.lock=None
