"""Explicit completed-NORMAL migration boundary using the existing executor.

The root coordinator must capture/restore/replicate the actual current-data
backup before issuing the child witnesses. This module neither captures a
backup nor grants writes; it cannot invoke the old115 fallback or rebuild images.
"""
from dataclasses import replace
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from deployment.lib.completed_normal_profile import maintenance_role

from deployment.lib.completed_normal_admission import (
    ADMISSIONS,OPERATION,digest,encoded,require_fresh_authorization,require_candidate_authority,credential_witness,
)
from deployment.lib.emergency_routing_repair import exclusive
from deployment.lib.provider_recovery_runtime import protected,readonly_configuration,file_digest
from deployment.lib.migration_executor import MigrationManifest,LockedMigrationExecutor
from deployment.lib.completed_normal_profile import profile, MANUAL, FENCED, OUTBOX

def verify_migration_backup(actual,witness,sha,operations, *, expected_schema=115):
    """Verify through the ordinary controller's measured installed CLI.

    Installed helpers live in deployment/scripts rather than a top-level
    scripts package. Never emit their private output or import mutable source.
    """
    actual=Path(actual)
    maintenance=witness.get('maintenance_manifest_sha256')
    if ((expected_schema in (150,160) or 'maintenance_manifest_sha256' in witness)
            and (not isinstance(maintenance,str) or not re.fullmatch('[0-9a-f]{64}',maintenance))):
        raise RuntimeError('completed_migration_maintenance_binding_invalid')
    helper=protected(operations.recovery_helper_root()/'backup_support.py')
    arguments=[sys.executable,'-I','-B',str(helper),'verify',str(actual)]
    if maintenance is not None:arguments.append(maintenance)
    try:
        result=subprocess.run(arguments,capture_output=True,timeout=180)
    except (OSError,subprocess.TimeoutExpired):
        raise RuntimeError('completed_migration_backup_verification_failed') from None
    if result.returncode:
        raise RuntimeError('completed_migration_backup_verification_failed')
    manifest=readonly_configuration(actual/'manifest.json',private=False)
    observed=json.loads(manifest.read_text())
    if (observed.get('maintenance_backup') is not None)!=(maintenance is not None):
        raise RuntimeError('completed_migration_maintenance_binding_invalid')
    if (file_digest(manifest)!=witness['backup_manifest_sha256']
            or file_digest(readonly_configuration(actual/'SHA256SUMS',private=False))!=witness['backup_checksums_sha256']
            or int(observed['database']['schema_version'])!=expected_schema or observed['release']['git_sha']!=sha):
        raise RuntimeError('completed_migration_backup_binding_changed')

def intent_document(contract):
    # Pure preparation validation creates no executor or operational admission.
    from deployment.lib.completed_normal_profile import DELETION, RECONCILED
    if isinstance(contract,dict) and contract.get('operation') in {DELETION.operation, RECONCILED.operation}:
        from deployment.lib.completed_normal_admission import validate_provider_preparation
        from deployment.lib import schema150_release, schema160_release
        selected=validate_provider_preparation(contract)
        module=schema150_release if selected is DELETION else schema160_release
        if contract['migration_manifest_sha256']!=module.MANIFEST_SHA256:
            raise RuntimeError('completed_migration_manifest_changed')
    else:selected=profile(contract)
    return {'operation':selected.operation,'context_sha256':digest(contract),'source_sha':contract['candidate']['source_sha'],
        'manifest_sha256':contract['migration_manifest_sha256'],'source_schema':selected.source,'target_schema':selected.target,
        'database_restored':False}

def issue_database_lease(contract):
    """Existing root issuer only: measure the exact native address before use."""
    if os.geteuid()!=0:raise RuntimeError('completed_migration_root_required')
    from deployment.lib.completed_normal_database import observe_native
    from deployment.lib.emergency_routing_repair import Runtime
    from deployment.lib.environment_file import load_environment_file
    runtime=Runtime();observe_native(contract,runtime)
    row=next(iter(runtime.inspect([contract['database']['container_id']]).values()))
    if (row['HostConfig'].get('PortBindings') or len(row['NetworkSettings']['Networks'])!=1
            or row['Config'].get('Labels',{}).get('com.docker.compose.service')!='db'
            or row['Config'].get('Labels',{}).get('com.docker.compose.project.working_dir')!='/opt/madar/local-supabase'):
        raise RuntimeError('completed_migration_native_configuration_changed')
    endpoint=next(iter(row['NetworkSettings']['Networks'].values()))
    if not endpoint.get('NetworkID'):raise RuntimeError('completed_migration_native_network_changed')
    address=ipaddress.ip_address(endpoint['IPAddress'])
    if (address.version!=4 or not address.is_private or address.is_loopback or address.is_link_local
            or address.is_unspecified or address.is_multicast):
        raise RuntimeError('completed_migration_native_address_invalid')
    configuration={}
    config_path=readonly_configuration(Path('/etc/madar/backup.env'),private=True)
    if file_digest(config_path)!=contract['database']['backup_configuration_sha256']:
        raise RuntimeError('completed_migration_backup_configuration_changed')
    load_environment_file(config_path,environ=configuration)
    if (any(configuration.get(k)!=v for k,v in {'PGHOST':'supabase-db','PGPORT':'5432','PGUSER':maintenance_role(contract),
            'PGDATABASE':'postgres','PGSSLMODE':'disable'}.items()) or not configuration.get('PGPASSWORD')):
        raise RuntimeError('completed_migration_native_credentials_invalid')
    return {'context_sha256':digest(contract),'database':contract['database'],'address':str(address),
        'expires':time.monotonic()+7200,'password':configuration['PGPASSWORD']}

def seal_intent(contract, *, source_guard, runtime_guard, backup_guard, admissions=ADMISSIONS):
    """Root intent precedes ALL migration connections, including schema probes."""
    if os.geteuid()!=0:raise RuntimeError('completed_migration_root_required')
    source_guard();require_fresh_authorization(contract)
    require_candidate_authority(contract,mode='READ_ONLY',admissions=admissions)
    if runtime_guard()!=profile(contract).source:raise RuntimeError('completed_migration_source_schema_changed')
    backup_guard()
    root=Path(admissions)/digest(contract)
    exclusive(root/'migration-intent.json',encoded(intent_document(contract)))

def connection_factory(contract):
    """Fresh credential contains the root-resolved native endpoint, never DNS.

    Credentials stay inside systemd LoadCredential; no DSN/password is placed in
    argv, environment, public interlock, backup manifest, or error diagnostics.
    Validate the connected database's actual identity before returning it to SQL.
    """
    require_fresh_authorization(contract)
    require_candidate_authority(contract,mode='READ_ONLY')
    lease=credential_witness('migration_database','migration_database_sha256')
    if (set(lease)!={'context_sha256','database','address','expires','password'}
            or lease['context_sha256']!=digest(contract) or lease['database']!=contract['database']
            or not isinstance(lease['password'],str) or not lease['password']
            or type(lease['expires']) not in {int,float} or not 0<lease['expires']-time.monotonic()<=7200):
        raise RuntimeError('completed_migration_database_lease_invalid')
    try:
        address=ipaddress.ip_address(lease['address'])
        if (address.version!=4 or not address.is_private or address.is_loopback or address.is_link_local
                or address.is_unspecified or address.is_multicast):raise ValueError()
    except (ValueError,TypeError):
        raise RuntimeError('completed_migration_database_lease_invalid') from None
    import psycopg
    connection=None
    try:
        connection=psycopg.connect(host=str(address),port=5432,user=maintenance_role(contract),dbname='postgres',
            password=lease['password'],sslmode='disable',connect_timeout=5,application_name='madar-governed-schema'+str(profile(contract).target),
            options='-c search_path=pg_catalog,public,extensions')
        connection.autocommit=True
        with connection.cursor() as cursor:
            cursor.execute("BEGIN READ ONLY")
            cursor.execute("SET LOCAL search_path=pg_catalog")
            cursor.execute("SELECT system_identifier::text,schema_version FROM pg_catalog.pg_control_system(),public.application_schema_state WHERE contract_key='core'")
            row=cursor.fetchone()
            if row is None or str(row[0])!=contract['database']['system_identifier'] or not profile(contract).supports(row[1]):
                raise RuntimeError('completed_migration_connected_database_changed')
            if maintenance_role(contract)=='supabase_admin':
                cursor.execute("SELECT current_user,session_user,rolsuper FROM pg_catalog.pg_roles WHERE rolname=current_user")
                if cursor.fetchone()!=('supabase_admin','supabase_admin',True):
                    raise RuntimeError('completed_migration_maintenance_identity_changed')
        connection.rollback()
        return connection
    except Exception as error:
        if connection is not None:connection.close()
        # PostgreSQL diagnostics can contain data or credentials. Retain only
        # the fixed operation and exception TYPE at this credential boundary.
        if isinstance(error,RuntimeError):raise
        raise RuntimeError('completed_migration_database_connection_failed_'+type(error).__name__) from None

def bind_manifest(manifest,contract):
    """Bind reviewed metadata, never issue migration or write authority.

    The caller still authenticates the manifest digest, SQL, current operation,
    backup, fresh credentials and locks. Only the historical manual profile uses
    the immutable STAGING marker; other profiles retain their existing markers.
    """
    selected=profile(contract);sha=contract['candidate']['source_sha']
    allowed_releases={'CURRENT',sha}
    if selected is MANUAL:allowed_releases.add('STAGING')
    if (manifest.release_sha not in allowed_releases
            or [m.number for m in manifest.migrations]!=list(selected.migrations)
            or (manifest.release_sha=='STAGING' and manifest.excluded_schemas!=MANUAL.excluded)):
        raise RuntimeError('completed_migration_chain_invalid')
    return replace(manifest,release_sha=sha)


def _parent_migration_binding(parent,provider,contract,release_root,state_root):
    """Bind the existing executor to its root coordinator, never a child packet.

    Operational admission is still required by run_migration. This check does
    not register150, supply authority, or accept a replacement SQL/backup path.
    The parent executes only the governed SQL; runtime promotion remains in the
    existing madar service. In particular, this path never adopts a candidate.
    """
    from deployment.lib.completed_normal_execution import CompletedNormalUpgrade
    from deployment.lib.completed_normal_profile import DELETION, RECONCILED
    from deployment.lib.schema150_provider_adapter import Schema150ProviderAdapter,require_owned_lock
    if (os.geteuid()!=0 or type(parent) is not CompletedNormalUpgrade
            or type(provider) is not Schema150ProviderAdapter
            or parent.profile not in (DELETION, RECONCILED) or parent.contract!=contract
            or provider.contract!=contract or provider.runtime is not parent.actor.runtime
            or parent.root!=provider.root or parent.root!=ADMISSIONS/digest(contract)
            or Path(state_root)!=parent.ops.state_root
            or Path(release_root)!=Path(state_root)/'releases'/contract['candidate']['source_sha']
            or provider.lock_descriptors!=(parent.lock,parent.ops.deploy_lock_descriptor)):
        raise RuntimeError('completed_migration_parent_binding_invalid')
    require_owned_lock(parent.lock,parent.ops.upgrade_root/'upgrade.lock')
    require_owned_lock(parent.ops.deploy_lock_descriptor,Path(state_root)/'deploy.lock')
    parent.actor.guard();parent.artifact_guard()
    provider.require_authority(provider.binding,purpose='observe_quiescence')


def _private_migration_candidate(parent,provider,contract,state_root,witness):
    """Reobserve exact stopped containers against the independently sealed model."""
    from deployment.lib.completed_normal_runtime import validate_model
    from deployment.lib.schema150_provider_lifecycle import (ProviderMaintenance150,
        ProtectedProviderJournal,FENCE_STEPS)
    from deployment.lib.completed_normal_resources import candidate_roles,allocation
    parent.actor.guard()
    require_candidate_authority(contract,mode='READ_ONLY')
    provider.require_authority(provider.binding,purpose='observe_quiescence')
    lifecycle=ProviderMaintenance150(provider.binding,ProtectedProviderJournal(provider.root/'provider-journal'),provider)
    with lifecycle._locked():
        records,completed,pending,ready=lifecycle._state()
        # These are completed_normal_backup's credential witness hashes, not
        # the provider journal's distinct compact hash-chain encoding.
        expected={'version':1,'binding':provider.binding,'journal_sha256':digest(records),
            'preimage_sha256':digest(records[0]['payload']['preimage'])} if records else None
        if pending or ready or completed!=list(FENCE_STEPS) or witness.get('provider_maintenance')!=expected:
            raise RuntimeError('completed_migration_provider_witness_changed')
    stage=json.loads(protected(parent.root/'candidate-staged-runtime.json',private=True).read_bytes())
    credential=credential_witness('candidate_stage','candidate_stage_sha256')
    if (stage!=credential or set(stage)!={'operation','context_sha256','source_sha','images','runtimes',
            'networks','worker_generation','origin_workers','preparation_mode'}
            or stage.get('preparation_mode')!='created-fenced'
            or stage['operation']!=parent.profile.operation or stage['context_sha256']!=digest(contract)
            or stage['source_sha']!=contract['candidate']['source_sha'] or stage['images']!=contract['candidate']['images']
            or not isinstance(stage['runtimes'],dict) or set(stage['runtimes'])!=set(candidate_roles(contract))):
        raise RuntimeError('completed_migration_private_stage_changed')
    runtimes,networks=validate_model(contract,parent.model_loader(),provider.runtime,phase='provisional')
    names=allocation(contract,contract['candidate']['slot'],preparation150=True)['containers']
    runtimes={role:dict(record,name=names[role]) for role,record in runtimes.items()}
    if stage['runtimes']!=runtimes or stage['networks']!=networks:
        raise RuntimeError('completed_migration_private_candidate_changed')
    provider.observe_quiescence(provider.binding)
    parent.actor.guard()


def run_migration(contract,release_root,state_root,operations,*,parent=None,provider_adapter=None):
    """Existing SQL executor, from the madar child or the protected150 parent.

    A maintenance parent owns both coordinator locks for the entire SQL window.
    It validates a sealed stopped candidate instead of making it public NORMAL
    or known-good. No caller flag, preparation profile or fake receipt admits150.
    """
    require_fresh_authorization(contract)
    selected=profile(contract)
    from deployment.lib.completed_normal_profile import DELETION, RECONCILED
    private=parent is not None or provider_adapter is not None
    if private:
        _parent_migration_binding(parent,provider_adapter,contract,release_root,state_root)
    elif selected in (DELETION, RECONCILED):
        raise RuntimeError('completed_migration_maintenance_parent_required')
    require_candidate_authority(contract,mode='READ_ONLY')
    sha=contract['candidate']['source_sha'];release_root=Path(release_root);state_root=Path(state_root)
    witness=credential_witness('migration_inputs','migration_inputs_sha256')
    if (set(witness)!={'intent','backup','backup_manifest_sha256','backup_checksums_sha256',
            'restore_execution_sha256','replica_execution_sha256'} | ({'notification_cutover'} if selected in (FENCED, OUTBOX) else set()) | ({'provider_maintenance'} if selected is OUTBOX else set()) | ({'provider_maintenance','maintenance_manifest_sha256'} if private else set()) or witness['intent']!=intent_document(contract)
            or any(not isinstance(witness[k],str) or len(witness[k])!=64 or any(c not in '0123456789abcdef' for c in witness[k])
                for k in ('backup_manifest_sha256','backup_checksums_sha256','restore_execution_sha256','replica_execution_sha256'))):
        raise RuntimeError('completed_migration_inputs_invalid')
    state=json.loads(readonly_configuration(state_root/'state.json',private=True).read_text())
    known=state.get('known_good_release') or {}
    expected_slot=contract['origin']['slot'] if private else contract['candidate']['slot']
    expected_sha=contract['source_roles']['application_sha'] if private else sha
    if (state.get('active_slot')!=expected_slot or known.get('slot')!=state['active_slot']
            or known.get('sha')!=expected_sha or state.get('in_progress_release') or state.get('rollback_failure')):
        raise RuntimeError('completed_migration_bridge_not_known_good')
    if not selected.supports(operations.schema_version()):raise RuntimeError('completed_migration_native_schema_invalid')
    from deployment.lib.emergency_routing_repair import Runtime
    runtime=Runtime();base='http://127.0.0.1:'+('8201' if state['active_slot']=='green' else '8101')
    if private:
        _private_migration_candidate(parent,provider_adapter,contract,state_root,witness)
    else:
        version=runtime.json_http(base+'/health/version')
        if (version.get('release_sha')!=sha or version.get('release_slot')!=state['active_slot']
            or version.get('schema_compatible_min')!=selected.source or version.get('schema_compatible_max')!=selected.target
            or tuple(version.get('schema_excluded_versions',[]))!=selected.excluded
            or runtime.json_http(base+'/health/recovery')!={'restricted':True,'business_writes_enabled':False}):
            raise RuntimeError('completed_migration_actual_bridge_fence_changed')
        operations.validate_candidate_core(sha,state['active_slot'])
    path=release_root/'web/deployment/releases'/selected.manifest
    if file_digest(readonly_configuration(path,private=False))!=contract['migration_manifest_sha256']:
        raise RuntimeError('completed_migration_manifest_changed')
    if private:
        from deployment.lib.schema150_provider_lifecycle import release_contract
        manifest=release_contract(provider_adapter.binding).admitted_manifest(release_root,contract)
    elif selected is OUTBOX:
        from deployment.lib.schema149_release import admitted_manifest
        manifest=admitted_manifest(release_root,contract)
    elif selected is FENCED:
        from deployment.lib.schema148_release import admitted_manifest
        manifest=admitted_manifest(release_root,contract)
    else:
        manifest=MigrationManifest.load(path,release_root)
    manifest=bind_manifest(manifest,contract)
    backup=Path(witness['backup'])
    if not backup.is_absolute() or not backup.name.startswith('madar-'):
        raise RuntimeError('completed_migration_backup_path_invalid')
    def verify_backup(actual):
        if actual!=backup:raise RuntimeError('completed_migration_backup_changed')
        verify_migration_backup(actual,witness,sha,operations,expected_schema=selected.source)
    root=state_root/'migrations'/sha
    execution=root/'execution.json'
    expected_origin=selected.source
    from deployment.lib.control_plane_upgrade_authorization import UPGRADE_INTERLOCK
    if json.loads(protected(UPGRADE_INTERLOCK).read_text()).get('migration_resumption_sha256') is not None:
        from deployment.lib.completed_normal_forward import authorized_executor
        resumption,execution=authorized_executor(contract,state_root)
        expected_origin=resumption['observed_schema']
        if operations.schema_version()!=resumption['observed_schema']:
            raise RuntimeError('completed_forward_source_schema_changed')
    # Never overwrite a failed/completed executor record on automatic retry.
    if execution.exists():raise RuntimeError('completed_migration_attempt_already_consumed')
    extra={}
    if private:
        extra.update(migration_guard=provider_adapter.migration_guard,
            completion_guard=provider_adapter.migration_completion_guard,expected_origin=expected_origin)
    if selected in (FENCED, OUTBOX):
        from deployment.lib.schema148_release import migration_guard,consumer_inventory,live_consumer_inventory
        policy=witness['notification_cutover']
        if digest(policy)!=contract['notification_cutover_sha256']:
            raise RuntimeError('schema148_cutover_policy_changed')
        def consumers():
            require_candidate_authority(contract,mode='READ_ONLY')
            operations.validate_candidate_core(sha,state['active_slot'])
            ids=runtime.command(['docker','ps','--all','--quiet','--no-trunc']).split()
            rows=list(runtime.inspect(ids).values())
            observed=consumer_inventory(rows,contract['origin']['images']['backend'],contract['candidate']['images']['backend'])
            candidates={key for key,row in observed.items() if row['image']==contract['candidate']['images']['backend'] and key not in policy['legacy_consumers']}
            if len(candidates)!=1:raise RuntimeError('schema148_candidate_consumer_ambiguous')
            live_consumer_inventory(runtime,contract,policy,candidates,rows=rows)
        if selected is OUTBOX:
            from deployment.lib.schema149_release import migration_guard as successor_guard
            # No implicit legacy fallback: the child only accepts the exact
            # protected adapter selected by the installed coordinator.
            from deployment.lib.schema149_controller import migration_provider_guard
            provider = migration_provider_guard(contract, witness['provider_maintenance'], runtime)
            extra['migration_guard']=lambda cursor,migration:successor_guard(
                contract,cursor,migration,consumer_guard=consumers,provider_guard=provider)
        else:
            extra['migration_guard']=lambda cursor,migration:migration_guard(contract,cursor,migration,consumer_guard=consumers)
    executor=LockedMigrationExecutor(connection_factory=lambda:connection_factory(contract),manifest=manifest,
        state_file=execution,backup_dir=backup,backup_verifier=verify_backup,
        failure_formatter=lambda error:'completed_migration_error_'+type(error).__name__,**extra)
    try:result=executor.run()
    except Exception as error:
        # SQL error details may contain customer rows. Keep numeric migration
        # phase/checksum in the durable executor; emit only the exception type.
        raise RuntimeError('completed_migration_error_'+type(error).__name__) from None
    if operations.schema_version()!=selected.target:raise RuntimeError('completed_migration_target_not_observed')
    if private:
        # The old runtime is still the recorded active slot, but is fenced and
        # incompatible. Never relabel it as schema150, start providers, publish
        # a route, consume queues or grant writes here. The root coordinator
        # must perform private recovery and its independent handoff separately.
        _parent_migration_binding(parent,provider_adapter,contract,release_root,state_root)
        if json.loads(readonly_configuration(state_root/'state.json',private=True).read_text())!=state:
            raise RuntimeError('completed_migration_release_changed_during_execution')
        return result
    if selected.maintenance:
        #144 must become visible to the already-running native PostgREST too.
        # This cache notification changes no customer rows or SQL checksums.
        connection=connection_factory(contract)
        try:
            with connection.cursor() as cursor:cursor.execute("SELECT pg_notify('pgrst','reload schema')")
        finally:connection.close()
    operations.validate_candidate_core(sha,state['active_slot'])
    # Update only mutable ordinary observed state. Historical source115
    # adoption/publication and executor journals remain intact. The caller
    # holds deploy.lock and the real grant is still READ_ONLY.
    after=json.loads(readonly_configuration(state_root/'state.json',private=True).read_text())
    if (after.get('active_slot')!=state['active_slot'] or after.get('known_good_release')!=known
            or after.get('in_progress_release') or after.get('rollback_failure')):
        raise RuntimeError('completed_migration_release_changed_during_execution')
    from deployment.lib.release_deployer import atomic_json
    after['known_good_release']=dict(known,schema=selected.target)
    atomic_json(state_root/'state.json',after)
    return result

def seal_completion(contract,release_root,state_root, *, source_guard,runtime_guard,admissions=ADMISSIONS,execution_path=None):
    """Copy genuine child evidence as historical DATA, never create a PASS claim."""
    if os.geteuid()!=0:raise RuntimeError('completed_migration_root_required')
    selected=profile(contract)
    source_guard();require_fresh_authorization(contract)
    require_candidate_authority(contract,mode='READ_ONLY',admissions=admissions)
    root=Path(admissions)/digest(contract)
    if json.loads(protected(root/'migration-intent.json',private=True).read_text())!=intent_document(contract):
        raise RuntimeError('completed_migration_intent_changed')
    if runtime_guard()!=selected.target:raise RuntimeError('completed_migration_target_not_observed')
    expected=Path(state_root)/'migrations'/contract['candidate']['source_sha']/'execution.json'
    if execution_path is not None:
        from deployment.lib.completed_normal_forward import authorized_executor
        _,expected=authorized_executor(contract,state_root)
        if Path(execution_path)!=expected:raise RuntimeError('completed_forward_execution_path_changed')
    execution=readonly_configuration(expected,private=True)
    manifest=readonly_configuration(Path(release_root)/'web/deployment/releases'/selected.manifest,private=False)
    if file_digest(manifest)!=contract['migration_manifest_sha256']:raise RuntimeError('completed_migration_manifest_changed')
    result=json.loads(execution.read_text());rows=result.get('migrations',[])
    expected=json.loads(manifest.read_text())['migrations']
    if (result.get('release_sha')!=contract['candidate']['source_sha'] or result.get('status')!='completed'
            or result.get('phase')!='complete' or result.get('observed_schema')!=selected.target
            or (result.get('backup') or {}).get('verified') is not True or len(rows)!=len(selected.migrations)
            or any(row.get('number')!=sql['number'] or row.get('checksum')!=sql['sha256']
                or row.get('status') not in {'applied','already_applied'} for row,sql in zip(rows,expected))):
        raise RuntimeError('completed_migration_child_execution_invalid')
    body=execution.read_bytes();exclusive(root/'migration-execution.json',body)
    exclusive(root/'migration-manifest.json',manifest.read_bytes())
    source_guard()
    if runtime_guard()!=selected.target:raise RuntimeError('completed_migration_target_not_observed')
    record=dict(intent_document(contract),execution_sha256=hashlib.sha256(body).hexdigest(),observed_schema=selected.target)
    exclusive(root/'migration-completion.json',encoded(record))
    return record
