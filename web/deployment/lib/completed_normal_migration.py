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
import subprocess
import sys
import time

from deployment.lib.completed_normal_admission import (
    ADMISSIONS,OPERATION,digest,encoded,require_fresh_authorization,require_candidate_authority,credential_witness,
)
from deployment.lib.emergency_routing_repair import exclusive
from deployment.lib.provider_recovery_runtime import protected,readonly_configuration,file_digest
from deployment.lib.migration_executor import MigrationManifest,LockedMigrationExecutor
from deployment.lib.completed_normal_profile import profile, MANUAL

def verify_migration_backup(actual,witness,sha,operations, *, expected_schema=115):
    """Verify through the ordinary controller's measured installed CLI.

    Installed helpers live in deployment/scripts rather than a top-level
    scripts package. Never emit their private output or import mutable source.
    """
    actual=Path(actual)
    helper=protected(operations.recovery_helper_root()/'backup_support.py')
    try:
        result=subprocess.run([sys.executable,'-I','-B',str(helper),'verify',str(actual)],
            capture_output=True,timeout=180)
    except (OSError,subprocess.TimeoutExpired):
        raise RuntimeError('completed_migration_backup_verification_failed') from None
    if result.returncode:
        raise RuntimeError('completed_migration_backup_verification_failed')
    manifest=readonly_configuration(actual/'manifest.json',private=False)
    observed=json.loads(manifest.read_text())
    if (file_digest(manifest)!=witness['backup_manifest_sha256']
            or file_digest(readonly_configuration(actual/'SHA256SUMS',private=False))!=witness['backup_checksums_sha256']
            or int(observed['database']['schema_version'])!=expected_schema or observed['release']['git_sha']!=sha):
        raise RuntimeError('completed_migration_backup_binding_changed')

def intent_document(contract):
    selected=profile(contract)
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
    if (any(configuration.get(k)!=v for k,v in {'PGHOST':'supabase-db','PGPORT':'5432','PGUSER':'postgres',
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
        connection=psycopg.connect(host=str(address),port=5432,user='postgres',dbname='postgres',
            password=lease['password'],sslmode='disable',connect_timeout=5,application_name='madar-governed-schema'+str(profile(contract).target))
        connection.autocommit=True
        with connection.cursor() as cursor:
            cursor.execute("BEGIN READ ONLY")
            cursor.execute("SELECT system_identifier::text,schema_version FROM pg_control_system(),public.application_schema_state WHERE contract_key='core'")
            row=cursor.fetchone()
            if row is None or str(row[0])!=contract['database']['system_identifier'] or not profile(contract).supports(row[1]):
                raise RuntimeError('completed_migration_connected_database_changed')
        connection.rollback()
        return connection
    except Exception as error:
        if connection is not None:connection.close()
        # PostgreSQL diagnostics can contain data or credentials. Retain only
        # the fixed operation and exception TYPE at this credential boundary.
        if isinstance(error,RuntimeError):raise
        raise RuntimeError('completed_migration_database_connection_failed_'+type(error).__name__) from None

def bind_manifest(manifest,contract):
    """A reviewed placeholder never substitutes for fresh release authority."""
    selected=profile(contract);sha=contract['candidate']['source_sha']
    allowed_releases={'CURRENT',sha}
    if selected is MANUAL:allowed_releases.add('STAGING')
    if manifest.release_sha not in allowed_releases or [m.number for m in manifest.migrations]!=list(selected.migrations):
        raise RuntimeError('completed_migration_chain_invalid')
    return replace(manifest,release_sha=sha)

def run_migration(contract,release_root,state_root,operations):
    """Actual madar deployment child; called only by explicit migrate stage."""
    require_fresh_authorization(contract)
    selected=profile(contract)
    require_candidate_authority(contract,mode='READ_ONLY')
    sha=contract['candidate']['source_sha'];release_root=Path(release_root);state_root=Path(state_root)
    witness=credential_witness('migration_inputs','migration_inputs_sha256')
    if (set(witness)!={'intent','backup','backup_manifest_sha256','backup_checksums_sha256',
            'restore_execution_sha256','replica_execution_sha256'} or witness['intent']!=intent_document(contract)
            or any(not isinstance(witness[k],str) or len(witness[k])!=64 or any(c not in '0123456789abcdef' for c in witness[k])
                for k in ('backup_manifest_sha256','backup_checksums_sha256','restore_execution_sha256','replica_execution_sha256'))):
        raise RuntimeError('completed_migration_inputs_invalid')
    state=json.loads(readonly_configuration(state_root/'state.json',private=True).read_text())
    known=state.get('known_good_release') or {}
    if (state.get('active_slot')!=contract['candidate']['slot'] or known.get('slot')!=state['active_slot']
            or known.get('sha')!=sha or state.get('in_progress_release') or state.get('rollback_failure')):
        raise RuntimeError('completed_migration_bridge_not_known_good')
    if not selected.supports(operations.schema_version()):raise RuntimeError('completed_migration_native_schema_invalid')
    from deployment.lib.emergency_routing_repair import Runtime
    runtime=Runtime();base='http://127.0.0.1:'+('8201' if state['active_slot']=='green' else '8101')
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
    manifest=MigrationManifest.load(path,release_root)
    # The reviewed learning manifest retains its immutable STAGING marker.
    # It is usable only inside the checksum-bound manual profile; the fresh
    # candidate authority supplies the actual release identity below.
    manifest=bind_manifest(manifest,contract)
    backup=Path(witness['backup'])
    if not backup.is_absolute() or not backup.name.startswith('madar-'):
        raise RuntimeError('completed_migration_backup_path_invalid')
    def verify_backup(actual):
        if actual!=backup:raise RuntimeError('completed_migration_backup_changed')
        verify_migration_backup(actual,witness,sha,operations,expected_schema=selected.source)
    root=state_root/'migrations'/sha
    execution=root/'execution.json'
    from deployment.lib.control_plane_upgrade_authorization import UPGRADE_INTERLOCK
    if json.loads(protected(UPGRADE_INTERLOCK).read_text()).get('migration_resumption_sha256') is not None:
        from deployment.lib.completed_normal_forward import authorized_executor
        resumption,execution=authorized_executor(contract,state_root)
        if operations.schema_version()!=resumption['observed_schema']:
            raise RuntimeError('completed_forward_source_schema_changed')
    # Never overwrite a failed/completed executor record on automatic retry.
    if execution.exists():raise RuntimeError('completed_migration_attempt_already_consumed')
    executor=LockedMigrationExecutor(connection_factory=lambda:connection_factory(contract),manifest=manifest,
        state_file=execution,backup_dir=backup,backup_verifier=verify_backup,
        failure_formatter=lambda error:'completed_migration_error_'+type(error).__name__)
    try:result=executor.run()
    except Exception as error:
        # SQL error details may contain customer rows. Keep numeric migration
        # phase/checksum in the durable executor; emit only the exception type.
        raise RuntimeError('completed_migration_error_'+type(error).__name__) from None
    if operations.schema_version()!=selected.target:raise RuntimeError('completed_migration_target_not_observed')
    if selected is MANUAL:
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
