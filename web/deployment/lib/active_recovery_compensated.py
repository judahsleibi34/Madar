"""Read-only proof of a published NORMAL release compensated to recovery.

Historical execution is DATA, never authority for another operation. This
observer imports no installed source, makes no repairs and grants no writes.
All comparison material must be included in a freshly approved continuation.
"""
import json
import re
from pathlib import Path

from deployment.lib.provider_recovery_runtime import protected, readonly_configuration, file_digest, digest

HISTORY_FILES = (
    'authorization.json', 'plan.json', 'events.jsonl', 'runtime-dependencies.json',
    'candidate-contract.json', 'candidate-identities.json', 'write-authority/authority.json',
    'installed-controller.json', 'boot-installation.json', 'fallback-listener-installation.json',
    'normal-publication.json', 'normal-acceptance.json', 'write-boundary.json',
    'worker-owner.json', 'backup-timer-preimage.json', 'fenced-local-reconciliation.json', 'retained-writer-fence.json', 'worker-ownership-preimage.json',
    'pre-normal-release_state', 'pre-normal-traffic', 'pre-normal-production_configuration',
)
EXPECTED_PHASES = (
    'authorized', 'detached_candidate_pending', 'detached_candidate_ready',
    'read_only_handoff_pending', 'read_only_serving', 'controller_resume_pending',
    'controller_resumed', 'standby_ready', 'write_grant_pending',
    'compensation_pending', 'restricted_fallback',
)
HASH = re.compile(r'[0-9a-f]{64}')


def validate_history(plan, records):
    """Validate durable chronology and actual observations, never a PASS label."""
    auth = records['authorization.json']
    events = records['events.jsonl']
    installed = records['installed-controller.json']
    normal = records['normal-acceptance.json']
    boundary = records['write-boundary.json']
    authority = records['write-authority/authority.json']
    from deployment.lib.active_recovery_resumption import controller_revision
    if (auth.get('operation') != 'active-local-rollback-resumption'
            or auth.get('plan_sha256') != plan.digest
            or auth.get('source_bundle_sha256') != plan.source_bundle_sha256
            or [row.get('phase') for row in events] != list(EXPECTED_PHASES)
            or any(row.get('plan_sha256') != plan.digest for row in events)
            or any(events[i]['observed_at'] >= events[i+1]['observed_at'] for i in range(len(events)-1))):
        raise RuntimeError('compensated_history_invalid')
    if (installed.get('plan_sha256') != plan.digest
            or installed.get('source_sha') != plan.source_sha
            or installed.get('controller_source_sha',plan.source_sha) != controller_revision(plan)
            or installed.get('source_bundle_sha256') != plan.source_bundle_sha256
            or installed.get('historical_authorization_reused') is not False
            or installed.get('volatile_credential_reconstructed') is not False):
        raise RuntimeError('compensated_installation_not_bound')
    observations = normal.get('observations', {})
    version = observations.get('version', {}).get('body', {})
    if (normal.get('operation') != 'actual-normal-runtime-verification'
            or normal.get('plan_sha256') != plan.digest
            or normal.get('source_sha') != plan.source_sha
            or normal.get('images') != plan.candidate_images
            or normal.get('schema') != 115 or normal.get('database_restore_performed') is not False
            or normal.get('artifact_acceptance_execution_sha256') != plan.acceptance_execution_sha256
            or any(observations.get(key, {}).get('http_status') != 200
                   for key in ('frontend', 'api', 'readiness', 'recovery', 'version'))
            or observations['readiness']['body'].get('ready') is not True
            or observations['recovery']['body'] != {'restricted': False, 'business_writes_enabled': True}
            or version.get('release_sha') != plan.source_sha
            or version.get('release_slot') != plan.candidate_destination['slot']
            or version.get('schema_compatible_min') != 115 or version.get('schema_compatible_max') != 115
            or boundary.get('plan_sha256') != plan.digest
            or boundary.get('source_sha') != plan.source_sha
            or boundary.get('source_bundle_sha256') != plan.source_bundle_sha256
            or boundary.get('customer_database_restore_permitted') is not False
            or boundary.get('normal_writes_may_have_occurred') is not True
            or not events[8]['observed_at'] <= boundary['began_at'] <= normal['started_at'] < normal['finished_at'] < events[9]['observed_at']):
        raise RuntimeError('compensated_normal_execution_not_proven')
    if (authority.get('mode') != 'READ_ONLY' or authority.get('schema') != 115
            or authority.get('release_sha') != plan.source_sha):
        raise RuntimeError('compensated_write_grant_not_revoked')


def inspect_history(plan_sha256):
    """Measure historical bytes without executing or renewing their authorization."""
    from deployment.lib.active_recovery_resumption import ROOT, load_saved_resumption_plan
    if not isinstance(plan_sha256, str) or not HASH.fullmatch(plan_sha256):
        raise RuntimeError('compensated_previous_plan_invalid')
    root = ROOT / plan_sha256
    plan = load_saved_resumption_plan(root)
    hashes = {}; records = {}
    for name in HISTORY_FILES:
        path = protected(root / name, private=name != 'write-authority/authority.json')
        hashes[name] = file_digest(path)
        if name == 'events.jsonl':
            records[name] = [json.loads(line) for line in path.read_text().splitlines()]
        elif name.endswith('.json'):
            records[name] = json.loads(path.read_text())
    if (root / 'normal-completion.json').exists() or (root / 'post-cutover-backup.json').exists():
        raise RuntimeError('compensated_history_already_completed')
    validate_history(plan, records)
    from deployment.lib.active_recovery_artifact_evidence import verify_artifact_acceptance
    verify_artifact_acceptance(plan)  # Genuine old exact-image execution, historical scope only.
    return plan, root, records, hashes


def measured_controller(plan, records):
    """Verify original installed source bytes against the frozen approved package.

    Extra installed files/bytecode remain separately measured DATA; they cannot
    be imported as a new execution source or substitute for source attestation.
    """
    from deployment.lib.active_recovery_inputs import CONTROL, controller_tree_digest
    from deployment.lib.active_recovery_resumption import controller_revision
    package = Path('/var/lib/madar-control-plane/normal-local-preparation') / ('normal-source-' + plan.source_bundle_sha256)
    manifest_path = protected(package / 'source-bundle.json', private=True)
    if file_digest(manifest_path) != plan.source_bundle_sha256:
        raise RuntimeError('compensated_original_source_package_changed')
    bundle = json.loads(manifest_path.read_text())
    if bundle.get('source_sha') != controller_revision(plan) or bundle.get('version') != 1:
        raise RuntimeError('compensated_original_source_package_invalid')
    measured = {}
    for relative, expected in bundle['files'].items():
        rel = Path(relative)
        if rel.is_absolute() or '..' in rel.parts or not HASH.fullmatch(str(expected)):
            raise RuntimeError('compensated_original_source_inventory_invalid')
        if file_digest(protected(package / 'source' / rel, private=True)) != expected:
            raise RuntimeError('compensated_original_source_bytes_changed')
        if relative.startswith('web/deployment/') and relative != 'web/deployment/bin/madar-install-control-plane':
            installed = CONTROL / rel.relative_to('web/deployment')
            if file_digest(protected(installed)) != expected:
                raise RuntimeError('compensated_installed_source_not_attested')
            measured[relative] = expected
    if not measured or protected(CONTROL / 'CONTROL_PLANE_SOURCE_SHA').read_text().strip() != controller_revision(plan):
        raise RuntimeError('compensated_installed_revision_changed')
    return {'source_sha': controller_revision(plan), 'source_files': measured,
            'complete_tree_sha256': controller_tree_digest(),
            'installation_receipt_sha256': digest(records['installed-controller.json'])}


def measured_startup(plan, records, runtime, *, backup_preparation=False):
    """Bind ALL current proxy controls and retained continuation boot resources."""
    units = Path('/etc/systemd/system')
    proxy = units / 'madar-release-proxy.service'
    directory = units / 'madar-release-proxy.service.d'
    if directory.is_symlink() or not directory.is_dir():
        raise RuntimeError('compensated_proxy_dropins_untrusted')
    files = {str(proxy): file_digest(protected(proxy))}
    for path in sorted(directory.iterdir()):
        if path.suffix != '.conf':
            raise RuntimeError('compensated_proxy_unexpected_control')
        files[str(path)] = file_digest(protected(path))
    boot = records['boot-installation.json']; listener = records['fallback-listener-installation.json']
    names = ('madar-normal-local-boot-' + plan.digest[:12] + '.service',
             'madar-normal-local-fallback-' + plan.digest[:12] + '.service')
    for receipt, name in zip((boot, listener), names):
        if (receipt.get('service') != name or receipt.get('plan_sha256') != plan.digest
                or receipt.get('source_bundle_sha256') != plan.source_bundle_sha256):
            raise RuntimeError('compensated_boot_receipt_changed')
        path = protected(units / name)
        if file_digest(path) != receipt.get('unit_sha256'):
            raise RuntimeError('compensated_boot_unit_changed')
        files[str(path)] = file_digest(path)
    dropin = str(directory / '92-normal-local-continuation.conf')
    if files.get(dropin) != boot.get('dropin_sha256'):
        raise RuntimeError('compensated_boot_dropin_changed')
    states = {}
    for name in names:
        values = runtime.command(['systemctl', 'show', name, '--property=ActiveState,UnitFileState,FragmentPath,DropInPaths,ExecStart,MainPID', '--no-pager'])
        fields = dict(line.split('=', 1) for line in values.splitlines() if '=' in line)
        expected_active = 'inactive' if name == names[0] else 'active'
        if (fields.get('ActiveState') != expected_active or fields.get('UnitFileState') != 'enabled'
                or fields.get('FragmentPath') != str(units / name) or fields.get('DropInPaths') != ''):
            raise RuntimeError('compensated_boot_effective_state_changed')
        process=None
        if name==names[1]:
            pid=fields.get('MainPID','')
            if not re.fullmatch('[1-9][0-9]*',pid):raise RuntimeError('compensated_listener_process_missing')
            package=Path('/var/lib/madar-control-plane/normal-local-preparation')/('normal-source-'+plan.source_bundle_sha256)
            root=Path('/var/lib/madar-control-plane/normal-local-resumption')/plan.digest
            expected=[b'/usr/bin/python3',b'-I',b'-B',str(package/'source/web/scripts/serve_active_recovery_fallback.py').encode(),
                b'--plan-root',str(root).encode(),b'--source-package',str(package).encode(),
                b'--approved-plan',plan.digest.encode(),b'--approved-source',plan.source_bundle_sha256.encode()]
            command=(Path('/proc')/pid/'cmdline').read_bytes().rstrip(b'\0').split(b'\0')
            if command!=expected:raise RuntimeError('compensated_listener_process_changed')
            status=(Path('/proc')/pid/'status').read_text()
            if not re.search(r'^NoNewPrivs:\s+1$',status,re.M):raise RuntimeError('compensated_listener_privileges_changed')
            sockets=runtime.command(['ss','-ltnp']).splitlines()
            for port in listener['loopback_ports'].values():
                if not any(re.search(r'127\.0\.0\.1:'+str(port)+r'\s',line) and 'pid='+pid+',' in line for line in sockets):
                    raise RuntimeError('compensated_listener_owner_changed')
            if not backup_preparation:runtime.denied('http://127.0.0.1:29501')
            if not backup_preparation and runtime.json_http('http://127.0.0.1:29501/health/recovery')!={'restricted':True,'business_writes_enabled':False}:
                raise RuntimeError('compensated_listener_not_readonly')
            if not backup_preparation:runtime.http_status('http://127.0.0.1:39501/')
            process={'pid':int(pid),'command_sha256':digest([arg.decode() for arg in command]),'no_new_privileges':True}
        states[name] = {'active': expected_active, 'enabled': 'enabled', 'effective_sha256': digest(fields),'process':process}
    effective = runtime.command(['systemctl', 'show', 'madar-release-proxy.service',
        '--property=FragmentPath,DropInPaths,Requires,After,ExecStartPre,ExecStart,User,Group', '--no-pager'])
    fields = dict(line.split('=', 1) for line in effective.splitlines() if '=' in line)
    expected_dropins = sorted(p for p in files if '/madar-release-proxy.service.d/' in p)
    if fields.get('FragmentPath') != str(proxy) or fields.get('DropInPaths', '').split() != expected_dropins:
        raise RuntimeError('compensated_proxy_effective_controls_changed')
    return {'files': files, 'services': states, 'proxy_effective_sha256': digest(fields)}


def observe_compensated_state(plan_sha256, runtime=None, *, backup_preparation=False, retained_route=False):
    """No mutation, old authorization consumed; all current safety gates enforced."""
    from deployment.lib.emergency_routing_repair import Runtime, legacy_installation, spec
    from deployment.lib.active_recovery_inputs import INPUTS, PRIVATE_CONFIGURATION, observe_runtime_dependencies
    from deployment.lib.active_recovery_fallback import CurrentDataFallback, FALLBACK_ROUTE
    from deployment.lib.control_plane_upgrade import BACKUP_TIMERS, validate_backup_timer_states
    runtime = runtime or Runtime()
    plan, root, records, history = inspect_history(plan_sha256)
    fallback = CurrentDataFallback(plan, root, runtime=runtime)
    fallback.verify(backup_preparation=backup_preparation)  # Actual revoked grant, ALL stopped consumers, native and role checks.
    route = FALLBACK_ROUTE
    route_evidence = None
    if retained_route:
        from deployment.lib.active_recovery_retained_fallback import measure_routing_restoration
        route, route_evidence = measure_routing_restoration(plan, root, records, runtime)
    if readonly_configuration(INPUTS['upstream'], private=False).read_bytes() != route:
        raise RuntimeError('compensated_registered_route_changed')
    installed = measured_controller(plan, records)
    startup = measured_startup(plan, records, runtime,backup_preparation=backup_preparation)
    # Verify original emergency installation bytes as retained evidence. Its live
    # effective proxy controls are verified by measured_startup, not the A gate.
    emergency = legacy_installation(runtime, live=False)
    head = runtime.command(['runuser', '-u', 'madar', '--', 'git', '--no-optional-locks', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false', '-C', '/srv/madar/production', 'rev-parse', 'HEAD'])
    from deployment.lib.active_recovery_resumption import controller_revision
    if head != controller_revision(plan):
        raise RuntimeError('compensated_production_checkout_changed')
    status = runtime.command(['runuser', '-u', 'madar', '--', 'git', '--no-optional-locks', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false', '-C', '/srv/madar/production', 'status', '--porcelain', '--untracked-files=no'])
    if status:
        raise RuntimeError('compensated_production_checkout_dirty')
    publication = records['normal-publication.json']
    if (publication.get('plan_sha256')!=plan.digest or publication.get('source_sha')!=plan.source_sha
            or publication.get('database_restore') is not False
            or set(publication.get('published_sha256',{}))!={'production_configuration','backup_configuration','release_state','traffic'}):
        raise RuntimeError('compensated_publication_not_bound')
    for key, expected in publication.get('published_sha256', {}).items():
        path = INPUTS.get(key)
        if path is None or file_digest(readonly_configuration(path, private=key in PRIVATE_CONFIGURATION)) != expected:
            raise RuntimeError('compensated_publication_changed')
    owner = records['worker-owner.json']
    if json.loads(readonly_configuration(INPUTS['worker_authority'], private=True).read_text()) != owner['authority']:
        raise RuntimeError('compensated_worker_authority_changed')
    current = runtime.inspect(list(owner['active'].values()))
    by_id = {r['Id']: r for r in current.values()}
    for role, cid in owner['active'].items():
        row = by_id[cid]
        kind = role if role in ('backend', 'frontend') else role + '-worker'
        if (row['Name'] != '/madar-' + owner['authority']['candidate']['slot'] + '-' + kind
                or row['Image'] != plan.candidate_images['frontend' if role == 'frontend' else 'backend']
                or row['Config'].get('Labels', {}).get('org.opencontainers.image.revision') != plan.source_sha
                or (role not in ('backend', 'frontend') and
                    (row['State']['Running'] is not False or row['HostConfig']['RestartPolicy']['Name'] != 'no'))):
            raise RuntimeError('compensated_retained_candidate_changed')
    timers = {};backup_controls={}
    for name in (*BACKUP_TIMERS,*(n.replace('.timer','.service') for n in BACKUP_TIMERS),'madar-auto-deploy.timer','madar-auto-deploy.service'):
        unit=Path('/etc/systemd/system')/name
        backup_controls[str(unit)]=file_digest(protected(unit))
        directory=unit.with_name(unit.name+'.d')
        if directory.exists():
            if directory.is_symlink():raise RuntimeError('compensated_backup_controls_untrusted')
            for path in sorted(directory.iterdir()):backup_controls[str(path)]=file_digest(protected(path))
    automation=dict(line.split('=',1) for line in runtime.command(['systemctl','show','madar-auto-deploy.timer','--property=ActiveState,UnitFileState']).splitlines())
    if automation!={'ActiveState':'inactive','UnitFileState':'disabled'}:raise RuntimeError('compensated_automation_not_quiesced')
    for name in BACKUP_TIMERS:
        text = runtime.command(['systemctl', 'show', name, '--property=ActiveState,UnitFileState', '--no-pager'])
        values = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
        timers[name] = {'active': values['ActiveState'], 'enabled': values['UnitFileState']}
        service = runtime.command(['systemctl', 'show', name.replace('.timer', '.service'), '--property=ActiveState', '--value'])
        if timers[name]['active'] != 'inactive' or service not in ('inactive', 'failed'):
            raise RuntimeError('compensated_backup_not_quiesced')
    validate_backup_timer_states(timers)
    dependencies, dependency_hash = observe_runtime_dependencies(runtime, fallback_names=True)
    # Include retained Docker resources, not only canonical names. Config/spec
    # digests exclude secrets; resource status/restart/network objects are bound.
    names = sorted(n for n in runtime.names() if n.startswith(('madar-', 'supabase-')))
    rows = runtime.inspect(names)
    proxy=rows.get('madar-release-proxy',{})
    compose=protected(INPUTS['proxy_compose']).read_bytes()
    image=re.search(rb'image:\s*nginx:alpine@(sha256:[0-9a-f]{64})',compose)
    if (image is None or proxy.get('Image')!=image[1].decode()
            or proxy.get('State',{}).get('Running') is not True
            or (not backup_preparation and proxy.get('State',{}).get('Health',{}).get('Status')!='healthy')
            or proxy.get('HostConfig',{}).get('NetworkMode')!='host'):
        raise RuntimeError('compensated_serving_proxy_not_verified')
    fallback_backend=next(r for r in rows.values() if r['Id']==plan.fallback['backend']['container_id'])
    if not backup_preparation:runtime.verify_public({'source_sha':fallback_backend['Config']['Labels']['org.opencontainers.image.revision']})
    else:
        for url in ('https://madarportal.com/','https://api.madarportal.com/'):
            status,_=runtime.fetch(url)
            if status not in (200,503):raise RuntimeError('compensated_backup_preparation_public_status_invalid')
    resources = {name: {'container_id': row['Id'], 'image_id': row['Image'], 'spec_sha256': spec(row),
        'running': row['State']['Running'], 'status': row['State']['Status'],
        'restart': row['HostConfig']['RestartPolicy']['Name'],
        'networks': {k: v['NetworkID'] for k, v in row['NetworkSettings']['Networks'].items()}}
        for name, row in rows.items()}
    from deployment.lib.active_recovery_reconciliation import CurrentLocalReconciliation
    reconciliation=CurrentLocalReconciliation(plan,root,runtime,lambda:None,lambda:fallback.verify_registered_runtime(backup_preparation=backup_preparation))
    snapshot,snapshot_hash=reconciliation.snapshot()
    if len(snapshot['table_roots'])!=96:raise RuntimeError('compensated_public_table_inventory_changed')
    # Customer credentials remain inside PostgreSQL. Hash complete Auth,
    # storage and authorization catalogs; emit no passwords, factors or rows.
    security_sql="""SELECT json_build_object('security_root',encode(sha256(convert_to(
      jsonb_build_object(
        'users',(SELECT jsonb_agg(to_jsonb(t)-'last_sign_in_at'-'updated_at' ORDER BY id) FROM auth.users t),
        'identities',(SELECT jsonb_agg(to_jsonb(t)-'last_sign_in_at'-'updated_at' ORDER BY id) FROM auth.identities t),
        'mfa_factors',(SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM auth.mfa_factors t),
        'storage_objects',(SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM storage.objects t),
        'storage_buckets',(SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM storage.buckets t),
        'tables',(SELECT jsonb_agg(jsonb_build_object('schema',n.nspname,'name',c.relname,
          'owner',pg_get_userbyid(c.relowner),'acl',c.relacl,'rls',c.relrowsecurity,'force_rls',c.relforcerowsecurity)
          ORDER BY n.nspname,c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname IN ('public','auth','storage') AND c.relkind IN ('r','p')),
        'policies',(SELECT jsonb_agg(to_jsonb(t) ORDER BY schemaname,tablename,policyname)
          FROM pg_policies t WHERE schemaname IN ('public','auth','storage'))
      )::text,'UTF8')),'hex'))::text;"""
    metadata=reconciliation.query("SELECT json_build_object('users',(SELECT count(*) FROM auth.users),'identities',(SELECT count(*) FROM auth.identities),'mfa_factors',(SELECT count(*) FROM auth.mfa_factors),'storage_objects',(SELECT count(*) FROM storage.objects),'audit_max_created_at',(SELECT max(created_at)::text FROM public.audit_logs))::text;")
    security=reconciliation.query(security_sql)
    if len(security)!=1 or not HASH.fullmatch(str(security[0].get('security_root'))):
        raise RuntimeError('compensated_security_catalog_invalid')
    if len(metadata)==1:metadata[0].update(security[0])
    if len(metadata)!=1:raise RuntimeError('compensated_database_metadata_invalid')
    result = {'version': 1, 'state': 'post_normal_compensated_recovery', 'previous_plan_sha256': plan_sha256,
        'historical_evidence': history, 'installed_controller': installed, 'startup': startup,
        'emergency_installation_sha256': digest(emergency), 'production_checkout': head,
        'worker_authority_sha256': digest(owner['authority']), 'resources': resources,
        'runtime_dependencies_sha256': dependency_hash, 'backup_timers': timers,'backup_controls':backup_controls,
        'resource_policy':{'reuse':'verified restricted listener, native provider and Redis only',
            'replace':'controller exact-source installer and attested continuation boot drop-in',
            'retain':'all historical records, candidate images, containers, units, volumes and checkpoints',
            'obsolete':'stopped hosted application resources and consumed boot actor; never restart old writers'},
        'database_authority': 'current_local', 'database_snapshot_sha256':snapshot_hash,'database_snapshot':snapshot,
        'audit_append_only_permitted':True,
        'database_metadata':metadata[0], 'public_tables':96, 'schema': 115, 'restore_customer_database': False}
    if retained_route:
        result['routing_restoration'] = route_evidence
    return result


def verify_compensated_binding(binding, runtime=None, *, staged_plan=None, recovery_backup=None):
    if not isinstance(binding, dict) or set(binding) not in ({'baseline','baseline_sha256'},{'baseline','baseline_sha256','pre_grant_backup'},{'baseline','baseline_sha256','retained_fallback'}):
        raise RuntimeError('compensated_binding_invalid')
    baseline = binding['baseline']
    if not isinstance(baseline, dict) or digest(baseline) != binding['baseline_sha256']:
        raise RuntimeError('compensated_baseline_hash_changed')
    kwargs={'backup_preparation':bool({'pre_grant_backup','retained_fallback'}&set(binding))}
    if 'retained_fallback' in binding:kwargs['retained_route']=True
    observed = observe_compensated_state(baseline.get('previous_plan_sha256'),runtime,**kwargs)
    if recovery_backup is not None:
        plan,resource=recovery_backup
        name='madar-recovery-backup-'+plan.digest[:12]
        if (plan.candidate_destination.get('post_compensation')!=binding or 'pre_grant_backup' not in binding
                or not HASH.fullmatch(str(plan.digest)) or staged_plan is not None
                or resource.get('image_id')!=baseline['resources']['madar-green-frontend']['image_id']
                or resource.get('running') is not True or resource.get('status')!='running' or resource.get('restart')!='no'
                or set(observed['resources'])-set(baseline['resources'])!={name}
                or observed['resources'].get(name)!=resource):
            raise RuntimeError('compensated_recovery_backup_resource_changed')
        observed=dict(observed,resources={k:v for k,v in observed['resources'].items() if k!=name})
    if staged_plan is not None:
        extra=set(observed['resources'])-set(baseline['resources'])
        prefix='madar-normal-'+staged_plan.digest[:12]
        allowed={prefix+'-'+kind for kind in ('backend','frontend','parser','notification-standby','calendar-sync-standby','data-deletion-standby')}
        if not extra.issubset(allowed):raise RuntimeError('compensated_unexpected_new_resource')
        from deployment.lib.active_recovery_resumption import ROOT
        saved=json.loads(protected(ROOT/staged_plan.digest/'candidate-identities.json',private=True).read_text())
        if saved.get('plan_sha256')!=staged_plan.digest or saved.get('source_sha')!=staged_plan.source_sha:
            raise RuntimeError('compensated_new_candidate_not_bound')
        approved={v['id']:v for v in saved['runtimes'].values()}
        if any(observed['resources'][name]['container_id'] not in approved
                or observed['resources'][name]['image_id']!=approved[observed['resources'][name]['container_id']]['image']
                or observed['resources'][name]['spec_sha256']!=approved[observed['resources'][name]['container_id']]['spec_sha256']
                for name in extra):
            raise RuntimeError('compensated_new_resource_identity_changed')
        observed=dict(observed,resources={k:v for k,v in observed['resources'].items() if k not in extra})
    if baseline.get('audit_append_only_permitted') is True:
        observed=verify_audit_extension(baseline,observed,runtime,backup_preparation=bool({"pre_grant_backup","retained_fallback"}&set(binding)))
    if observed != baseline:
        raise RuntimeError('compensated_current_state_changed')
    return observed


def resolve_compensated_destination(binding, runtime=None):
    """Resolve allocation from the verified F owner, never historical origin_slot.

    Retained stopped canonical reservations are admissible only when they match
    the original protected dependency inventory and the newly measured F
    contract. Historical hosted resources are retained evidence, not rollback. No container is stopped, renamed or displaced by this observer.
    """
    from deployment.lib.emergency_routing_repair import Runtime, spec
    from deployment.lib.active_recovery_candidate import DetachedRecoveryCandidate, require_unreserved_ports, KINDS
    from deployment.lib.active_recovery_inputs import registered_fallback_names, observe_runtime_dependencies
    runtime = runtime or Runtime()
    baseline = verify_compensated_binding(binding, runtime)
    plan, root, records, _ = inspect_history(baseline['previous_plan_sha256'])
    owner = records['worker-owner.json']['authority']
    retained = owner['candidate']['slot']; slot = 'blue' if retained == 'green' else 'green'
    historical=records['runtime-dependencies.json']
    if digest(historical)!=plan.retained_inputs['runtime_dependencies'] or owner['old']['slot']!=slot:
        raise RuntimeError('compensated_target_historical_ownership_changed')
    names = [f'madar-{slot}-'+(kind+'-worker' if kind in KINDS else kind) for kind in ('backend','frontend',*KINDS)]
    rows = runtime.inspect(names)
    ports = {'blue':(8101,3100),'green':(8201,3200)}[slot]
    retired = {}
    for name in names:
        row = rows[name]; expected = baseline['resources'][name]; original=historical['runtimes'][name]
        if (row['Id'] != expected['container_id'] or row['Image'] != expected['image_id']
                or spec(row) != expected['spec_sha256'] or row['State']['Running'] is not False
                or row['HostConfig']['RestartPolicy']['Name'] != 'no'
                or row['Config'].get('Labels',{}).get('org.opencontainers.image.revision') != owner['old']['sha']
                or row['Id']!=original['container_id'] or row['Image']!=original['image_id']
                or not historical_retained_spec_matches(row,original,records['retained-writer-fence.json'],plan.digest)):
            raise RuntimeError('compensated_target_resource_changed')
    for role, port in zip(('backend','frontend'),ports):
        name=f'madar-{slot}-{role}';row=rows[name]
        image=historical['runtimes'][name]['image_id']
        container_port={'backend':'8000/tcp','frontend':'8080/tcp'}[role]
        if row['Image'] != image or row['HostConfig'].get('PortBindings') != {container_port:[{'HostIp':'127.0.0.1','HostPort':str(port)}]}:
            raise RuntimeError('compensated_target_reservation_changed')
        retired[name]={'container_id':row['Id'],'image_id':row['Image'],'spec_sha256':spec(row)}
    prior_destination=plan.candidate_destination
    redis_name=prior_destination['redis_name'];network=prior_destination['redis_network']
    packet,_=observe_runtime_dependencies(runtime,fallback_names=True)
    net=runtime.network(network);redis=runtime.inspect([redis_name])[redis_name]
    retained_backend=packet['runtimes'][f'madar-{retained}-backend']
    if (net['Id']!=prior_destination['redis_network_id'] or net['Driver']!='bridge' or net['Internal'] is not True
            or packet['networks'].get(network,{}).get('Id')!=net['Id']
            or network not in redis['NetworkSettings']['Networks'] or network not in retained_backend['networks']
            or redis['State']['Running'] is not True
            or runtime.command(['docker','exec',redis_name,'redis-cli','PING'])!='PONG'):
        raise RuntimeError('compensated_redis_network_changed')
    require_unreserved_ports(runtime,ports,retired)
    probe=DetachedRecoveryCandidate.__new__(DetachedRecoveryCandidate);probe.command=runtime.command
    return {'slot':slot,'backend_port':ports[0],'frontend_port':ports[1],
        'retained_slot':retained,'retained_source_sha':plan.source_sha,
        'redis_name':redis_name,'redis_network':network,'redis_network_id':net['Id'],
        'subnet':probe.free_subnet(),'retired_port_declarations':retired,'post_compensation':binding}


def historical_retained_spec_matches(row, original, fence, plan_digest):
    """Only the recorded retained-writer restart=no update may differ.

    The new baseline always binds current bytes exactly. This comparison merely
    explains the historical change; it grants no authority to start old writers.
    """
    import copy
    from deployment.lib.emergency_routing_repair import spec
    if spec(row)==original['spec_sha256']:return True
    if (fence.get('plan_sha256')!=plan_digest or fence.get('database_restore') is not False
            or row['Id'] not in fence.get('retained_container_ids',{}).values()
            or row['State']['Running'] is not False or row['HostConfig']['RestartPolicy']['Name']!='no'):
        return False
    historical=copy.deepcopy(row);historical['HostConfig']['RestartPolicy']['Name']='unless-stopped'
    return spec(historical)==original['spec_sha256']


def lifecycle_state(records):
    """Classify durable execution without mistaking a classification for proof.

    Entry to the state-F authorization path STILL requires validate_history and
    independent live measurement; this function never creates authority.
    """
    events=records.get('events.jsonl',[])
    phase=events[-1].get('phase') if events else None
    if phase=='restricted_fallback' and 'normal-acceptance.json' in records:return 'F_COMPENSATED_RECOVERY'
    if (phase=='normal' and all(name in records for name in
            ('normal-completion.json','post-cutover-backup.json','backup-timers-resumed.json'))):
        return 'G_COMPLETED_NORMAL'
    if 'normal-acceptance.json' in records:return 'E_NORMAL_ACTIVATED'
    if 'installed-controller.json' in records:return 'D_CONTROLLER_INSTALLED'
    if any(e.get('phase')=='read_only_serving' for e in events):return 'C_READ_ONLY_PUBLIC'
    if 'candidate-identities.json' in records:return 'B_CANDIDATE_STAGED'
    if phase in {'authorized','detached_candidate_pending','detached_candidate_failed'}:return 'A_ORIGINAL_RESTRICTED_RECOVERY'
    raise RuntimeError('compensated_lifecycle_not_classifiable')


def verify_audit_extension(baseline,observed,runtime=None, *, backup_preparation=False):
    """Permit only new audit rows, after proving every bound old row unchanged.

    Preparation snapshot metadata remains immutable historical DATA. Later
    source-fence reconciliation records the complete latest live snapshot.
    Native identity, all other tables and security-critical controls stay exact.
    """
    if baseline['database_snapshot_sha256']==observed['database_snapshot_sha256']:
        return observed
    from datetime import datetime
    from deployment.lib.emergency_routing_repair import Runtime
    from deployment.lib.active_recovery_fallback import CurrentDataFallback
    from deployment.lib.active_recovery_reconciliation import CurrentLocalReconciliation
    expected={r['table']:r for r in baseline['database_snapshot']['table_roots']}
    actual={r['table']:r for r in observed['database_snapshot']['table_roots']}
    if (set(expected)!=set(actual) or any(expected[k]!=actual[k] for k in expected if k!='audit_logs')
            or actual['audit_logs']['count']<expected['audit_logs']['count']):
        raise RuntimeError('compensated_non_audit_customer_data_changed')
    before=baseline['database_metadata'];after=observed['database_metadata']
    if {k:v for k,v in before.items() if k!='audit_max_created_at'}!={k:v for k,v in after.items() if k!='audit_max_created_at'}:
        raise RuntimeError('compensated_database_metadata_changed')
    cutoff=before['audit_max_created_at']
    if not isinstance(cutoff,str) or not re.fullmatch(r'[0-9T :+.Z-]{10,40}',cutoff) or datetime.fromisoformat(cutoff).tzinfo is None:
        raise RuntimeError('compensated_audit_cutoff_invalid')
    previous,root,_,_=inspect_history(baseline['previous_plan_sha256'])
    runtime=runtime or Runtime();fallback=CurrentDataFallback(previous,root,runtime=runtime)
    reconciliation=CurrentLocalReconciliation(previous,root,runtime,lambda:None,lambda:fallback.verify_registered_runtime(backup_preparation=backup_preparation))
    sql="SELECT json_build_object('table','audit_logs','count',count(*),'sha256',encode(sha256(convert_to(coalesce(string_agg(row_sha,'' ORDER BY row_sha COLLATE \"C\"),''),'UTF8')),'hex'))::text FROM (SELECT encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') AS row_sha FROM public.audit_logs t WHERE created_at <= '"+cutoff+"'::timestamptz) rows;"
    prefix=reconciliation.query(sql)
    if prefix!=[expected['audit_logs']]:raise RuntimeError('compensated_preexisting_audit_data_changed')
    # Comparison projects only the explicitly permitted append extension. This
    # does not relabel the old snapshot as current execution or create evidence.
    return dict(observed,database_snapshot=baseline['database_snapshot'],
        database_snapshot_sha256=baseline['database_snapshot_sha256'],database_metadata=before)
