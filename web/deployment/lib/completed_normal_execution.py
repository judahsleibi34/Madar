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
import re
import traceback

from deployment.lib.completed_normal_admission import ADMISSIONS,OPERATION,digest,encoded,publish_admission,require_candidate_authority
from deployment.lib.completed_normal_backup import CompletedNormalBackupContext
from deployment.lib.completed_normal_boot_installation import CompletedNormalBootInstallation
from deployment.lib.completed_normal_boot_actor import verify_live_configuration
from deployment.lib.completed_normal_database import (customer_baseline,observe_native,
    migration_customer_snapshot,verify_migration_customer_preservation)
from deployment.lib.completed_normal_migration import seal_intent,seal_completion
from deployment.lib.completed_normal_resources import verify_allocation
from deployment.lib.completed_normal_runtime import seal_candidate_stage,seal_candidate_runtime
from deployment.lib.completed_normal_write_handoff import CompletedNormalWriteHandoff,atomic_public_authority
from deployment.lib.control_plane_upgrade import acquire_lock,BACKUP_TIMERS,require_root_directory
from deployment.lib.emergency_routing_repair import exclusive
from deployment.lib.provider_recovery_runtime import protected,readonly_configuration,file_digest
from deployment.lib.completed_normal_profile import profile, LEGACY, MANUAL, APPLICATION

FAILED_BOOT_RECORDS=frozenset({'operator-authorization.json','admission.json','failure.json',
    'boot-preimages.json','boot-installation.json','boot-installation-failed.json',
    'events.jsonl','boot-events.jsonl','backup-timer-preimages.json'})
SOURCE_PACKAGES=Path('/var/lib/madar-control-plane/normal-local-preparation')
BOOT_UNITS=Path('/etc/systemd/system')
PROC_ROOT=Path('/proc')


def verify_failed_boot_interlock(document,contract,ops):
    """Read-only admission for an exact compensated, consumed boot failure.

    Current NORMAL source/database/worker/customer and boot preimages are also
    verified by the surrounding full preflight. Old receipts are historical
    data only, never credentials or permission to execute a successor.
    """
    binding=document.get('failed_boot_interlock')
    present=ops.interlock_file.exists() or ops.interlock_file.is_symlink()
    if binding is None:
        if present:raise RuntimeError('completed_upgrade_existing_interlock_requires_reconciliation')
        return None
    keys={'interlock_sha256','context_sha256','controller_sha','plan_sha256',
        'source_bundle_sha256','invocation_wrapper_sha256','records'}
    if (profile(contract) is not MANUAL or not isinstance(binding,dict) or set(binding)!=keys
            or any(not re.fullmatch('[0-9a-f]{64}',str(binding[k])) for k in keys-{'records','controller_sha'})
            or not re.fullmatch('[0-9a-f]{40}',str(binding['controller_sha']))
            or not isinstance(binding['records'],dict) or set(binding['records'])!=FAILED_BOOT_RECORDS or not present):
        raise RuntimeError('completed_upgrade_failed_interlock_binding_invalid')
    body=protected(ops.interlock_file).read_bytes()
    if hashlib.sha256(body).hexdigest()!=binding['interlock_sha256']:
        raise RuntimeError('completed_upgrade_failed_interlock_changed')
    interlock=json.loads(body);old_root=ADMISSIONS/binding['context_sha256']
    records={}
    for name,expected in binding['records'].items():
        path=protected(old_root/name,private=name!='admission.json')
        if not re.fullmatch('[0-9a-f]{64}',str(expected)) or file_digest(path)!=expected:
            raise RuntimeError('completed_upgrade_failed_attempt_evidence_changed')
        if name.endswith('.json'):records[name]=json.loads(path.read_text())
    old=records['admission.json']['contract']
    from deployment.lib.completed_normal_admission import validate_contract
    validate_contract(old)
    expected_auth={'operation':MANUAL.operation,'context_sha256':binding['context_sha256'],
        'plan_sha256':binding['plan_sha256'],'source_bundle_sha256':binding['source_bundle_sha256'],
        'controller_sha':binding['controller_sha'],'application_sha':old['candidate']['source_sha']}
    failure=records['failure.json'];failed_boot=records['boot-installation-failed.json']
    if (digest(old)!=binding['context_sha256'] or old['plan_sha256']!=binding['plan_sha256']
            or old['candidate']['controller_sha']!=binding['controller_sha']
            or old['source_roles']!=contract['source_roles'] or old['origin']!=contract['origin']
            or old['database']!=contract['database']
            or records['operator-authorization.json']!=expected_auth
            or interlock.get('version')!=2 or interlock.get('status')!='authorized_cycle'
            or interlock.get('approved_sha')!=binding['controller_sha']
            or interlock.get('operation')!=MANUAL.operation or interlock.get('schema')!=136
            or interlock.get('context_sha256')!=binding['context_sha256']
            or interlock.get('admission_sha256')!=digest(records['admission.json'])
            or failure.get('operation')!=MANUAL.operation or failure.get('context_sha256')!=binding['context_sha256']
            or failure.get('phase')!='boot_supersession_pending' or failure.get('exception_type')!='RuntimeError'
            or failure.get('customer_database_restored') is not False or 'compensation_exception_type' in failure
            or not any(f.get('source')=='completed_normal_boot_installation.py' and f.get('function')=='installed'
                for f in failure.get('frames',[]))
            or failed_boot.get('phase')!='boot_resource_installation'
            or failed_boot.get('context_sha256')!=binding['context_sha256']
            or failed_boot.get('operation')!=MANUAL.operation or failed_boot.get('database_restored') is not False
            or records['boot-installation.json'].get('historical_units_deleted') is not False
            or records['backup-timer-preimages.json']!=document['backup_timer_states']
            or interlock.get('backup_timer_states')!=document['backup_timer_states']):
        raise RuntimeError('completed_upgrade_failed_attempt_not_reconciliable')
    if any((old_root/name).exists() for name in ('controller-installation-intent.json',
            'candidate-stage.json','candidate-runtime.json','migration-intent.json','normal-completion.json')):
        raise RuntimeError('completed_upgrade_failed_attempt_advanced')
    # Prove compensation from real current resources, not an agent PASS marker.
    baseline=records['boot-preimages.json']
    if baseline!=document['boot_resources']:
        raise RuntimeError('completed_upgrade_failed_boot_compensation_incomplete')
    for raw,expected in baseline['files'].items():
        path=protected(Path(raw));st=path.stat()
        if {'sha256':file_digest(path),'uid':st.st_uid,'mode':st.st_mode&0o7777}!=expected:
            raise RuntimeError('completed_upgrade_failed_boot_compensation_incomplete')
    for name,state in baseline['unit_states'].items():
        if ops.systemctl_state(name)!=state:
            raise RuntimeError('completed_upgrade_failed_boot_compensation_incomplete')
    generated=failed_boot.get('retained_generated_resources',{})
    if not generated or generated!=records['boot-installation.json']['resources']:
        raise RuntimeError('completed_upgrade_failed_boot_compensation_incomplete')
    for raw,expected in generated.items():
        path=Path(raw)
        if not path.is_relative_to(BOOT_UNITS) or path.exists() or path.is_symlink():
            raise RuntimeError('completed_upgrade_failed_boot_compensation_incomplete')
        retained=old_root/('retained-'+path.relative_to(BOOT_UNITS).as_posix().replace('/','_'))
        if file_digest(protected(retained,private=True))!=expected:
            raise RuntimeError('completed_upgrade_failed_boot_compensation_incomplete')
    if ops.authorization_file.exists() or ops.authorization_file.is_symlink():
        raise RuntimeError('completed_upgrade_failed_attempt_authorization_active')
    wrapper=SOURCE_PACKAGES/('normal-invocation-'+binding['invocation_wrapper_sha256']+'.py')
    if file_digest(protected(wrapper,private=True))!=binding['invocation_wrapper_sha256']:
        raise RuntimeError('completed_upgrade_failed_attempt_wrapper_changed')
    entry=SOURCE_PACKAGES/('normal-source-'+binding['source_bundle_sha256'])/'source/web/scripts/continue_completed_normal_upgrade.py'
    for process in PROC_ROOT.glob('[0-9]*'):
        try:args=process.joinpath('cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError,ProcessLookupError):continue
        if b'execute' in args and any(str(p).encode() in args for p in (entry,wrapper)):
            raise RuntimeError('completed_upgrade_failed_attempt_still_running')
    active=ops.command('completed_failed_attempt_units',['systemctl','list-units','--all','--type=service',
        '--state=active,activating,deactivating','--plain','--no-legend',
        'madar-control-plane-upgrade-*.service','madar-compatible-normal-boot-'+binding['context_sha256'][:12]+'.service']).stdout
    if active.strip():raise RuntimeError('completed_upgrade_failed_attempt_still_running')
    return body


def manual_maintenance_route(contract):
    """Existing maintenance listener, with only read-only version probes.

    Ordinary backup verifies the actual release through the stable proxy. Keep
    that nonmutating endpoint available while customer/Auth traffic is fenced.
    """
    if profile(contract) is not MANUAL:
        raise RuntimeError('completed_manual_maintenance_contract_required')
    port=8101 if contract['candidate']['slot']=='blue' else 8201
    return (f'upstream madar_backend_active {{ server 127.0.0.1:29402; }}\n'
        f'upstream madar_frontend_active {{ server 127.0.0.1:29402; }}\n'
        f'server {{ listen 127.0.0.1:29402; access_log off; '
        f'location = /health/version {{ proxy_pass http://127.0.0.1:{port}/health/version; }} '
        f'location = /api/health/version {{ proxy_pass http://127.0.0.1:{port}/health/version; }} '
        f'location / {{ return 503; }} }}\n').encode()


def enter_manual_maintenance(actor):
    from deployment.lib.emergency_routing_repair import verification_window, UPSTREAM
    from deployment.lib.runtime_authority import runtime_mutation_lock
    from deployment.lib.completed_normal_admission import require_fresh_authorization
    from deployment.lib.completed_normal_resources import ROLES, measured_spec_matches
    from deployment.lib.completed_normal_profile import expected_origin_grant
    contract=actor.contract;actor.guard();require_fresh_authorization(contract)
    origin=Path(contract['source_roles']['completion_root'])
    if json.loads(protected(origin/'write-authority/authority.json').read_text())!=expected_origin_grant(contract,'READ_ONLY'):
        raise RuntimeError('completed_manual_origin_not_fenced')
    record=json.loads(protected(origin/'candidate-runtime.json',private=True).read_text())
    if (record.get('source_sha')!=contract['source_roles']['application_sha']
            or record.get('context_sha256')!=origin.name or set(record.get('runtimes',{}))!=set(ROLES)):
        raise RuntimeError('completed_manual_origin_runtime_changed')
    body=manual_maintenance_route(contract)
    with verification_window(actor.runtime,180):
        with runtime_mutation_lock(actor.ops.state_root):
            actor.guard();actor.proxy_identity()
            exclusive(actor.root/'migration-maintenance-route-preimage.conf',readonly_configuration(UPSTREAM,private=False).read_bytes())
            actor.runtime.nginx_preflight(body,actor.root)
            actor.runtime.publish(body);actor.runtime.reload();actor.runtime.verify_maintenance()
            # No old schema136 application may query advanced schema, including
            # through draining proxy workers. Preserve its containers/data and
            # Redis; stop only exact independently measured application IDs.
            for kind in ('backend','frontend','parser-worker','remote-ingestion-worker'):
                identity=record['runtimes'][kind]
                rows=actor.runtime.inspect([identity['id']]);row=next(iter(rows.values())) if len(rows)==1 else None
                if (row is None or row['Id']!=identity['id'] or row['Image']!=identity['image']
                        or not measured_spec_matches(row,identity['spec_sha256'])
                        or row['HostConfig']['RestartPolicy']['Name']!='no'):
                    raise RuntimeError('completed_manual_origin_application_changed')
                if row['State']['Running']:actor.runtime.command(['docker','stop',identity['id']])
            actor.guard();actor.proxy_identity()
            if UPSTREAM.read_bytes()!=body:raise RuntimeError('completed_manual_maintenance_route_changed')
            return {'frontend_http':503,'api_http':503,'version_probe_preserved':True,'customer_database_restored':False}


def verify_serving(actor, *, schema,normal):
    """Observe the exact candidate and stable routes; no customer mutation.

    Authenticated application cases are independently pinned by the artifact
    and complete-private-rehearsal gates. This runtime check does not claim a
    live customer login or mutation when no approved credential is available.
    """
    import time
    from deployment.lib.emergency_routing_repair import verification_window,AvailabilityFailure
    selected=profile(actor.contract)
    if schema not in {selected.source,selected.target} or type(normal) is not bool:
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
                            or version.get('schema_compatible_min')!=selected.minimum or version.get('schema_compatible_max')!=selected.target
                            or tuple(version.get('schema_excluded_versions',[]))!=selected.excluded
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
        self.profile=profile(self.contract)
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

    def verify_candidate_remote(self):
        # Read-only: production refs are fetched only by the approved installer.
        # A moving main must reject before timer, boot or controller effects.
        remote=self.ops.madar_git('completed_upgrade_candidate_remote','ls-remote',
            '--exit-code','origin','refs/heads/main').stdout.split()
        selection=self.document.get('immutable_release_selection')
        from deployment.lib.control_plane_upgrade import validate_immutable_release_selection
        expected=self.controller if selection is None else validate_immutable_release_selection(selection,self.controller)
        if remote!=[expected,'refs/heads/main']:
            raise RuntimeError('completed_upgrade_candidate_remote_changed')

    def preflight(self, *, locked=False):
        """No authorization consumption, service effects, or live SQL writes."""
        self.preparation_source();self.verify_candidate_remote();self.artifact_guard();self.rehearsal_guard()
        before=self.ops.current_preflight(lock_deployment=locked)
        if self.profile is APPLICATION:
            from deployment.lib.control_plane_upgrade import validate_immutable_release_selection
            selection=self.document.get('rollback_source_selection')
            if validate_immutable_release_selection(selection,self.contract['source_roles']['controller_sha'])!=self.controller:
                raise RuntimeError('application_rollback_source_binding_invalid')
        if (before['schema']!=self.profile.source or before['slot']!=self.contract['origin']['slot']
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
        verify_failed_boot_interlock(self.document,self.contract,self.ops)
        if self.document.get('failed_boot_interlock') is not None and self.reconciliation_root().exists():
            raise RuntimeError('completed_upgrade_interlock_reconciliation_already_consumed')
        observe_native(self.contract,self.actor.runtime)
        from deployment.lib.active_recovery_backup import verify_backup_execution_context
        if self.profile is not LEGACY:
            verify_backup_execution_context(self.package,expected_schema=self.profile.source)
        else:verify_backup_execution_context(self.package)
        baseline=customer_baseline(self.contract,self.actor.runtime)
        if (baseline['table_roots_sha256']!=self.contract['customer_table_roots_sha256']
                or baseline['identity_roots_sha256']!=self.contract['customer_identity_roots_sha256']):
            raise RuntimeError('completed_upgrade_current_customer_data_changed')
        allocation=verify_allocation(self.contract,self.contract['candidate']['slot'],self.actor.runtime,
            prospective_retirement=self.profile is not LEGACY)
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
        return {'operation':self.profile.operation,'schema':self.profile.source,'candidate':allocation,'production_modified':False,'authorization_consumed':False}

    def reconciliation_root(self):
        return self.ops.upgrade_root/'failed-boot-interlock-reconciliations'/digest(self.document)

    def reconcile_failed_interlock(self):
        """One plan-bound retirement under both existing deployment locks."""
        if self.document.get('failed_boot_interlock') is None:return
        if self.lock is None or self.ops.deploy_lock_descriptor is None:
            raise RuntimeError('completed_upgrade_interlock_reconciliation_locks_required')
        self.preparation_source()
        body=verify_failed_boot_interlock(self.document,self.contract,self.ops)
        archive=self.reconciliation_root()
        require_root_directory(archive.parent,create=True)
        if archive.exists() or archive.is_symlink():
            raise RuntimeError('completed_upgrade_interlock_reconciliation_already_consumed')
        archive.mkdir(mode=0o700);require_root_directory(archive)
        exclusive(archive/'previous-interlock.json',body)
        exclusive(archive/'intent.json',encoded({'operation':'exact-failed-boot-interlock-reconciliation',
            'replacement_plan_sha256':digest(self.document),'replacement_context_sha256':digest(self.contract),
            'controller_sha':self.controller,'source_bundle_sha256':self.document['source_bundle_sha256'],
            'binding':self.document['failed_boot_interlock'],'origin':self.contract['source_roles'],
            'customer_database_restored':False}))
        self.preparation_source()
        if verify_failed_boot_interlock(self.document,self.contract,self.ops)!=body:
            raise RuntimeError('completed_upgrade_failed_interlock_changed')
        self.ops.clear_interlock()
        if self.ops.interlock_file.exists() or self.ops.interlock_file.is_symlink():
            raise RuntimeError('completed_upgrade_failed_interlock_retirement_failed')
        exclusive(archive/'completion.json',encoded({'replacement_plan_sha256':digest(self.document),
            'retired_interlock_sha256':hashlib.sha256(body).hexdigest(),'historical_attempt_preserved':True}))

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
        selection=self.document.get('immutable_release_selection')
        options={} if selection is None else {'immutable_selection':selection}
        self.ops.resolve_candidate(self.controller,dry_run=False,**options)
        transaction,staged=self.ops.stage_candidate(self.controller,**options)
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
        intent={'operation':self.profile.operation,'context_sha256':digest(self.contract),
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
        evidence={'operation':self.profile.operation,'context_sha256':digest(self.contract),'phase':self.phase,
            'exception_type':type(error).__name__,'frames':[{'source':Path(f.filename).name,'line':f.lineno,'function':f.name}
                for f in traceback.extract_tb(error.__traceback__)[-24:]],'customer_database_restored':False}
        # Failure diagnostics must never prevent write revocation/compensation.
        # Preserve both exception types when compensation itself fails.
        try:
            if self.fenced or self.controller_installed or (self.root/'controller-installation-intent.json').exists():
                if self.profile is APPLICATION:
                    try:self.rollback_application_origin()
                    except Exception:
                        # A rejected rollback must not leave either grant or
                        # consumer generation active. Use the existing fenced
                        # compensation path; never retry the consumed attempt.
                        try:self.actor.compensate()
                        finally:self.ops.requiesce_backup_timers_for_failure()
                        raise
                    evidence['compensation']='original_schema144_normal_restored'
                    return evidence
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
            elif self.document.get('failed_boot_interlock') is not None and self.reconciliation_root().exists():
                exclusive(self.reconciliation_root()/'failure.json',encoded(evidence))
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
            if self.document.get('failed_boot_interlock') is not None:self.phase='failed_interlock_reconciliation'
            self.reconcile_failed_interlock()
            self.quiesced=True;self.ops.quiesce(self.controller)
            with self.root_credential():
                publish_admission(self.contract,self.ops,self.ops.state_root)
            self.admitted=True
            authorization={'operation':self.profile.operation,'context_sha256':digest(self.contract),'plan_sha256':digest(self.document),
                'source_bundle_sha256':self.document['source_bundle_sha256'],'controller_sha':self.controller,
                'application_sha':self.contract['candidate']['source_sha']}
            exclusive(self.root/'operator-authorization.json',encoded(authorization))
            if self.profile is APPLICATION:
                from deployment.lib.runtime_authority import load_worker_authority
                exclusive(self.root/'application-origin-state.json',readonly_configuration(self.ops.state_root/'state.json',private=True).read_bytes())
                exclusive(self.root/'application-origin-workers.json',encoded(load_worker_authority(self.ops.state_root)))
                worker_stat=readonly_configuration(self.ops.state_root/'worker-ownership.json',private=True).stat()
                exclusive(self.root/'application-origin-worker-owner.json',encoded({
                    'uid':worker_stat.st_uid,'gid':worker_stat.st_gid,'mode':worker_stat.st_mode & 0o777}))
                route=readonly_configuration(Path('/var/lib/madar/proxy/active-upstreams.conf'),private=False).read_bytes()
                if hashlib.sha256(route).hexdigest()!=self.document['origin_routing_sha256']:
                    raise RuntimeError('application_rollback_origin_route_changed')
                exclusive(self.root/'application-origin-route.conf',route)
                # Resolve/freeze rollback objects before replacing boot or
                # controller resources. Compensation must not need GitHub or
                # a still-moving main after the handoff has started.
                self.ops.resolve_candidate(self.controller,dry_run=False)
                _,rollback_source=self.ops.stage_candidate(self.contract['source_roles']['controller_sha'],
                    immutable_selection=self.document['rollback_source_selection'])
                exclusive(self.root/'application-rollback-source.json',encoded({
                    'path':str(rollback_source),'tree_sha256':self.ops.protected_tree_digest(rollback_source)}))
            exclusive(self.root/'backup-timer-preimages.json',encoded(self.document['backup_timer_states']))
            with self.root_credential():
                self.event('boot_supersession_pending');self.actor.installation.install();self.actor.guard()
                self.event('controller_installation_pending');self.install_controller()
            # Existing deploy.lock must be released before the User=madar
            # service obtains it. The protected upgrade interlock stays armed.
            self.ops.release_deployment_lock()
            if self.profile is not LEGACY:
                with self.root_credential():
                    self.event('retained_blue_retirement_pending')
                    from deployment.lib.completed_normal_resources import retire_bound_resources
                    retirement=retire_bound_resources(self.contract,self.actor.runtime,source_guard=self.actor.guard)
                    exclusive(self.root/'retained-resource-retirement.json',encoded(retirement))
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
            if self.profile is APPLICATION:
                return self.complete_application(handoff, kernel)
            with self.root_credential():
                self.acceptance_guard(schema=self.profile.source,normal=False)
                if self.profile is not MANUAL:
                    self.event('bridge_normal_grant_pending');handoff.grant(schema=self.profile.source)
            self.service('adopt')
            with self.root_credential():
                self.acceptance_guard(schema=self.profile.source,normal=self.profile is not MANUAL)
                if self.profile is MANUAL:
                    self.event('migration_maintenance_pending')
                    receipt=enter_manual_maintenance(self.actor)
                    exclusive(self.root/'migration-maintenance.json',encoded(receipt))
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
                preservation=(verify_migration_customer_preservation(original,after,contract=self.contract)
                    if self.profile is MANUAL else verify_migration_customer_preservation(original,after))
                exclusive(self.root/'migration-customer-preservation.json',encoded(preservation))
                self.event('migration_completion_pending')
                seal_completion(self.contract,self.ops.state_root/'releases'/self.contract['candidate']['source_sha'],self.ops.state_root,
                    source_guard=self.actor.guard,runtime_guard=self.actor.native)
                if self.profile is MANUAL:
                    self.event('verified_target_read_only_routing_pending')
                    self.actor.publish_restricted_bridge()
            self.service('refresh')
            with self.root_credential():
                self.acceptance_guard(schema=self.profile.target,normal=False)
                self.event('target_normal_grant_pending');handoff.grant(schema=self.profile.target)
                self.acceptance_guard(schema=self.profile.target,normal=True)
                self.event('post_migration_backup_pending')
                backup=CompletedNormalBackupContext(self.contract,self.document,self.package,kernel,
                    stage='post-migration',source_guard=self.actor.guard,artifact_guard=self.artifact_guard)
                receipt=backup.capture()
                self.event('backup_timer_restore_pending');self.ops.restore_backup_timers()
                kernel.round(normal=True);self.acceptance_guard(schema=self.profile.target,normal=True)
                self.event('normal_completed',schema=self.profile.target,mode='NORMAL')
                result={'operation':self.profile.operation,'context_sha256':digest(self.contract),'schema':self.profile.target,'mode':'NORMAL',
                    'application_sha':self.contract['candidate']['source_sha'],'controller_sha':self.controller,
                    'images':self.contract['candidate']['images'],'backup':receipt,
                    'backup_timers':{n:self.ops.systemctl_state(n) for n in BACKUP_TIMERS},'customer_database_restored':False}
                exclusive(self.root/'normal-completion.json',encoded(result))
                from deployment.lib.completed_normal_baseline import seal_compatible_release
                seal_compatible_release(self.contract,self.root,self.ops.state_root)
            self.ops.clear_interlock()
            return result
        except Exception as error:
            self.failure(error)
            raise
        finally:
            self.ops.clear_authorization();self.ops.close_locks()
            if self.lock is not None:os.close(self.lock);self.lock=None

    def complete_application(self, handoff, kernel):
        """The existing handoff at144, with no migration intent or SQL child.

        The candidate is published and adopted READ_ONLY. An ordinary backup
        and independent restore/replica complete before the single NORMAL
        grant. Interrupted execution uses the existing fenced compensation.
        """
        with self.root_credential():
            self.acceptance_guard(schema=144,normal=False)
        self.service('adopt')
        with self.root_credential():
            self.acceptance_guard(schema=144,normal=False)
            self.event('pre_activation_backup_pending')
            backup=CompletedNormalBackupContext(self.contract,self.document,self.package,kernel,
                stage='pre-migration',source_guard=self.actor.guard,artifact_guard=self.artifact_guard)
            backup.capture()
            self.event('application_normal_grant_pending');handoff.grant(schema=144)
            self.acceptance_guard(schema=144,normal=True)
            self.event('post_activation_backup_pending')
            backup=CompletedNormalBackupContext(self.contract,self.document,self.package,kernel,
                stage='post-migration',source_guard=self.actor.guard,artifact_guard=self.artifact_guard)
            receipt=backup.capture()
            self.ops.restore_backup_timers()
            kernel.round(normal=True);self.acceptance_guard(schema=144,normal=True)
            result={'operation':self.profile.operation,'context_sha256':digest(self.contract),
                'schema':144,'mode':'NORMAL','application_sha':self.contract['candidate']['source_sha'],
                'controller_sha':self.controller,'images':self.contract['candidate']['images'],
                'backup':receipt,'backup_timers':{n:self.ops.systemctl_state(n) for n in BACKUP_TIMERS},
                'customer_database_restored':False,'sql_executed':False}
            exclusive(self.root/'normal-completion.json',encoded(result))
            from deployment.lib.completed_normal_baseline import seal_compatible_release
            seal_compatible_release(self.contract,self.root,self.ops.state_root)
            self.event('normal_completed',schema=144,mode='NORMAL')
        self.ops.clear_interlock()
        return result

    def rollback_application_origin(self):
        """Back out an authorized app-only attempt; never restore database data.

        Existing installer, boot preimages and boot kernel are used. The old
        controller is an explicitly pinned canonical ancestor in this plan.
        Old receipts are integrity DATA; this active fresh transaction supplies
        permission for the compensation, including restoring the old grant.
        """
        from deployment.lib.completed_normal_admission import verify_history
        from deployment.lib.active_recovery_inputs import controller_tree_digest
        from deployment.lib.runtime_authority import runtime_mutation_lock,write_worker_authority
        from deployment.lib.compatible_normal_boot import CompatibleNormalBoot,WORKERS
        from deployment.lib.completed_normal_resources import measured_spec_matches
        from deployment.lib.completed_normal_baseline import compatible_package
        from deployment.lib.control_plane_upgrade import atomic_json,validate_immutable_release_selection
        from deployment.lib.completed_normal_profile import expected_origin_grant
        if self.profile is not APPLICATION or self.lock is None or not self.admitted:
            raise RuntimeError('application_rollback_active_transaction_required')
        def guard():
            self.preparation_source();verify_history(self.contract)
            if self.actor.native()!=144 or any((self.root/name).exists() for name in ('migration-intent.json','migration-completion.json')):
                raise RuntimeError('application_rollback_schema_changed')
        guard()
        original=json.loads(protected(self.root/'application-origin-state.json',private=True).read_text())
        workers=json.loads(protected(self.root/'application-origin-workers.json',private=True).read_text())
        worker_owner=json.loads(protected(self.root/'application-origin-worker-owner.json',private=True).read_text())
        if (set(worker_owner)!={'uid','gid','mode'} or worker_owner['mode']!=0o600
                or any(type(worker_owner[k]) is not int or worker_owner[k]<0 for k in ('uid','gid'))):
            raise RuntimeError('application_rollback_worker_file_owner_changed')
        def restore_workers(owner):
            write_worker_authority(self.ops.state_root,generation=workers['generation'],owner=owner,
                old=workers['old'],candidate=workers['candidate'])
            path=self.ops.state_root/'worker-ownership.json'
            os.chown(path,worker_owner['uid'],worker_owner['gid'])
            os.chmod(path,worker_owner['mode'])
        roles=self.contract['source_roles'];old_root=Path(roles['completion_root'])
        old_sha=roles['controller_sha'];selection=self.document['rollback_source_selection']
        if (validate_immutable_release_selection(selection,old_sha)!=self.controller
                or original.get('active_slot')!=self.contract['origin']['slot']
                or (original.get('known_good_release') or {}).get('sha')!=roles['application_sha']
                or workers.get('generation')!=self.contract['origin']['worker_generation']
                or workers.get('owner')!='CANDIDATE' or workers.get('candidate')!={'sha':roles['application_sha'],'slot':self.contract['origin']['slot']}):
            raise RuntimeError('application_rollback_origin_changed')
        exclusive(self.root/'application-rollback-intent.json',encoded({'context_sha256':digest(self.contract),
            'controller_sha':old_sha,'application_sha':roles['application_sha'],'schema':144,'database_restored':False}))
        with self.root_credential():
            new=require_candidate_authority(self.contract)
            atomic_public_authority(self.root/'write-authority/authority.json',dict(new,mode='READ_ONLY'))
            old_grant=protected(old_root/'write-authority/authority.json')
            current=json.loads(old_grant.read_text())
            if current not in (expected_origin_grant(self.contract,'NORMAL'),expected_origin_grant(self.contract,'READ_ONLY')):
                raise RuntimeError('application_rollback_origin_grant_changed')
            atomic_public_authority(old_grant,expected_origin_grant(self.contract,'READ_ONLY'))
            with runtime_mutation_lock(self.ops.state_root):
                for path in (old_root/'candidate-runtime.json',self.root/'candidate-runtime.json',self.root/'candidate-staged-runtime.json'):
                    if not path.exists():continue
                    record=json.loads(protected(path,private=True).read_text())
                    for kind in WORKERS:
                        identity=record['runtimes'][kind];rows=self.actor.runtime.inspect([identity['id']])
                        row=next(iter(rows.values())) if len(rows)==1 else None
                        if row is None or row['Image']!=identity['image'] or not measured_spec_matches(row,identity['spec_sha256'],started_worker=True):
                            raise RuntimeError('application_rollback_worker_identity_changed')
                        if row['State']['Running']:self.actor.runtime.command(['docker','stop',identity['id']])
                restore_workers('NONE')
            # Source objects and full tree are independently revalidated by the
            # existing immutable-selection staging and root installer.
            saved=json.loads(protected(self.root/'application-rollback-source.json',private=True).read_text())
            staged=Path(saved['path'])
            if (not staged.is_relative_to(self.ops.staging_root)
                    or self.ops.staging_git('application_rollback_source_head','rev-parse','HEAD',cwd=staged).stdout!=old_sha
                    or self.ops.protected_tree_digest(staged)!=saved['tree_sha256']):
                raise RuntimeError('application_rollback_frozen_source_changed')
            backup=self.root/'rollback-controller-backup';backup.mkdir(mode=0o700)
            self.ops.installer_dry_run(staged,backup)
            self.ops.installer_apply(staged,backup,old_sha)
            self.ops.madar_git('application_rollback_checkout','checkout','--detach',old_sha)
            self.ops.verify_install(old_sha,backup)
            if controller_tree_digest()!=self.document['installed_controller_tree_sha256']:
                raise RuntimeError('application_rollback_controller_tree_changed')
            previous=self.actor.installation.source_guard
            self.actor.installation.source_guard=guard
            try:self.actor.installation.restore_application_preimages()
            finally:self.actor.installation.source_guard=previous
            # Preserve every appended release event; restore only the exact
            # origin identity/owner, never replace customer or database state.
            state_path=self.ops.state_root/'state.json';state=json.loads(readonly_configuration(state_path,private=True).read_text())
            state['known_good_release']=original['known_good_release'];state['active_slot']=original['active_slot']
            state.pop('in_progress_release',None);state.pop('rollback_failure',None)
            state.setdefault('history',[]).append({'operation':self.profile.operation,'phase':'application_rollback',
                'context_sha256':digest(self.contract),'schema':144,'database_restored':False})
            stat=state_path.stat();atomic_json(state_path,state,owner=(stat.st_uid,stat.st_gid))
            restore_workers('CANDIDATE')
            receipt=json.loads(protected(old_root/'operator-authorization.json',private=True).read_text())
            package=SOURCE_PACKAGES/('normal-source-'+receipt['source_bundle_sha256'])
            doc,_=compatible_package(package,receipt['source_bundle_sha256'],receipt['plan_sha256'])
            old_contract=dict(doc['admission_contract'],plan_sha256=digest(doc))
            def publish(mode):
                guard();atomic_public_authority(old_grant,expected_origin_grant(self.contract,mode))
            kernel=CompatibleNormalBoot(old_contract,source_guard=guard,native_verifier=lambda:self.actor.native(),
                publish_authority=publish,compensate_current_data=lambda:publish('READ_ONLY'),
                runtime=self.actor.runtime,state_root=self.ops.state_root)
            kernel.execute_read_only()
            route=protected(self.root/'application-origin-route.conf').read_bytes()
            if hashlib.sha256(route).hexdigest()!=self.document['origin_routing_sha256']:
                raise RuntimeError('application_rollback_origin_route_changed')
            self.actor.proxy_identity()
            self.actor.runtime.nginx_preflight(route,self.root)
            self.actor.runtime.publish(route);self.actor.runtime.reload()
            publish('NORMAL');kernel.verify_mode(normal=True)
            self.ops.current_preflight(lock_deployment=False);self.ops.restore_backup_timers()
            exclusive(self.root/'application-rollback-completion.json',encoded({'schema':144,'mode':'NORMAL',
                'application_sha':roles['application_sha'],'controller_sha':old_sha,'customer_database_restored':False}))
        self.ops.clear_interlock()
