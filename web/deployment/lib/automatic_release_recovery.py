"""Known-good restart effects inside the EXISTING installed release controller.

Recovery consumes independently protected restart policy and actual completed
release evidence. It never calls the migration engine or publishes write grants.
Production installation/activation is deliberately not enabled by test enrollment.
"""
import hashlib,json,os,re,subprocess,time,uuid
from pathlib import Path
from .migration_inventory import canonical,digest,strict_json
from .provider_recovery_runtime import protected,readonly_configuration
from .migration_executor import atomic_json
from . import automatic_release_admission as admission
from .isolated_release_environment import observe_host,observe_effect_fence,required_rules,TABLE,run,verify_runtime_scope

POLICY=Path('/etc/madar/automatic-recovery-policy.json')
ROOT=Path('/var/lib/madar-control-plane/upgrades/automatic-recovery')
STATE=Path('/var/lib/madar/releases')
ROLES=('backend','frontend','redis','parser-worker','remote-ingestion-worker','notification-worker','calendar-sync-worker','data-deletion-worker')
CONSUMERS=('notification-worker','calendar-sync-worker','data-deletion-worker')
PROVIDERS=('supabase-db','supabase-auth','supabase-rest','supabase-storage','supabase-envoy')

def read(path,*,private=True):
    file=(protected(Path(path),private=True) if private else readonly_configuration(Path(path),private=False))
    if not 0<file.stat().st_size<=1024**2:raise RuntimeError('automatic_recovery_input_size')
    return strict_json(file.read_bytes())

def policy(system):
    p=read(POLICY);host=observe_host()
    fields={'version','kind','environment_id','guest_uuid','machine_id','root_filesystem_uuid',
        'controller_sha','controller_tree_sha256','expires_at','control_interface','control_mac',
        'control_address','control_gateway','max_recovery_seconds'}
    if (set(p)!=fields or type(p['version']) is not int or p['version']!=1
            or p['kind']!='isolated-known-good-recovery-policy'
            or p['environment_id']!='isolated-'+host['realm_id']
            or any(p[k]!=host[k] for k in ('guest_uuid','machine_id','root_filesystem_uuid'))
            or p['controller_sha']!=system.installed_sha()
            or type(p['expires_at']) is not int or not int(time.time())<p['expires_at']<=int(time.time())+14400
            or type(p['max_recovery_seconds']) is not int or not 30<=p['max_recovery_seconds']<=300
            or p['control_interface']!='ens3' or not re.fullmatch('[0-9a-f]{2}(:[0-9a-f]{2}){5}',str(p['control_mac']))
            or p['control_address']!='10.0.2.15/24' or p['control_gateway']!='10.0.2.2'):
        raise RuntimeError('automatic_recovery_independent_policy_invalid')
    from .active_recovery_inputs import controller_tree_digest
    if p['controller_tree_sha256']!=controller_tree_digest():raise RuntimeError('automatic_recovery_controller_changed')
    mac=Path('/sys/class/net',p['control_interface'],'address').read_text().strip()
    if mac!=p['control_mac']:raise RuntimeError('automatic_recovery_control_interface_changed')
    return p,host

def restore_isolation(system):
    """Early systemd step before network-pre and Docker; no DHCP exception."""
    p,host=policy(system);nic=p['control_interface']
    links=json.loads(run(['/usr/sbin/ip','-json','-details','link','show']))
    for row in links:
        if row['ifname'] in ('lo',nic):continue
        if row.get('linkinfo',{}).get('info_kind') not in {'bridge','veth'}:
            raise RuntimeError('automatic_recovery_unexpected_interface')
    existing=json.loads(run(['/usr/sbin/nft','--json','list','tables']))['nftables']
    found=[v['table'] for v in existing if 'table' in v and v['table'].get('family')=='inet' and v['table'].get('name')==TABLE]
    if found:
        # An existing unknown table is not repaired or replaced.
        verify_fence(nic)
    else:
        batch=[{'add':{'table':{'family':'inet','name':TABLE}}}]
        for chain,rules in required_rules(nic,execution=True).items():
            batch.append({'add':{'chain':{'family':'inet','table':TABLE,'name':chain,'type':'filter','hook':chain,'prio':200,'policy':'accept'}}})
            for expr in rules:batch.append({'add':{'rule':{'family':'inet','table':TABLE,'chain':chain,'expr':expr}}})
        subprocess.run(['/usr/sbin/nft','--json','-f','-'],input=canonical({'nftables':batch}),check=True,timeout=15,stdout=subprocess.DEVNULL)
        verify_fence(nic)
    return {'operation':'restore-isolated-effect-fence','guest_uuid':host['guest_uuid'],'policy_sha256':digest(p),'authority_issued':False}

def verify_fence(nic):
    # Early boot may not yet have a default route. Compare the same fixed rule
    # contract directly, without weakening ordinary full environment observation.
    table=json.loads(run(['/usr/sbin/nft','--stateless','--json','list','table','inet',TABLE]))['nftables']
    wanted=required_rules(nic,execution=True);chains={};rules={k:[] for k in wanted}
    for item in table:
        if 'chain' in item:chains[item['chain']['name']]=item['chain']
        if 'rule' in item:
            row=item['rule']
            if row['chain'] not in rules:raise RuntimeError('automatic_recovery_foreign_firewall_rule')
            rules[row['chain']].append(row['expr'])
    if set(chains)!=set(wanted) or rules!=wanted or any(chains[k].get('hook')!=k or chains[k].get('type')!='filter' or chains[k].get('prio')!=200 or chains[k].get('policy')!='accept' for k in wanted):
        raise RuntimeError('automatic_recovery_firewall_tampered')

def inspect_all():
    ids=run(['/usr/bin/docker','ps','-aq','--no-trunc']).decode().split()
    if not ids or len(ids)>128:raise RuntimeError('automatic_recovery_actor_count')
    return json.loads(run(['/usr/bin/docker','inspect',*ids]))

def grant(value):
    from .automatic_release_execution import grant_directory,runtime_context
    p=grant_directory(value)/'authority.json';body=protected(p).read_bytes();v=strict_json(body)
    expected={'version':4,'operation':admission.OPERATION,'operation_id':value['operation_id'],
        'attempt_id':value['attempt_id'],'schema':value['database']['target_schema'],
        'target_schema':value['database']['target_schema'],'release_sha':value['source_sha'],
        'contract_digest':runtime_context(value),'mode':'NORMAL','controller_sha':value['controller_sha'],
        'database_system_identifier':value['database']['system_identifier'],'plan_sha256':digest(value['plan']),
        'compatible_min':value['candidate']['compatible_min'],'compatible_max':value['candidate']['compatible_max']}
    if v!=expected:raise RuntimeError('automatic_recovery_existing_normal_authority_changed')
    return hashlib.sha256(body).hexdigest()

def completed(value):
    admission.sealed(value,allow_expired=True)
    path=admission.ROOT/'attempts'/value['attempt_id']/'completion.json'
    body=protected(path,private=True).read_bytes();receipt=strict_json(body)
    if (receipt.get('admission_sha256')!=digest(value) or receipt.get('attempt_id')!=value['attempt_id']
            or receipt.get('source_sha')!=value['source_sha'] or receipt.get('release',{}).get('status')!='known_good'
            or receipt['release'].get('traffic_target')!=value['candidate']['slot']):
        raise RuntimeError('automatic_recovery_completed_release_required')
    return receipt,hashlib.sha256(body).hexdigest()

def seal_known_good(system,value):
    """Called only after genuine completion, under the existing deploy lock.

    The policy is independently installed. A candidate cannot install this
    policy, seal itself, alter history, or create a deployment completion.
    """
    if not POLICY.exists() and not POLICY.is_symlink():return None
    p,host=policy(system);receipt,completion_sha=completed(value)
    state=read(STATE/'state.json',private=False)
    known=state.get('known_good_release');slot=value['candidate']['slot']
    if not isinstance(known,dict) or known.get('sha')!=value['source_sha'] or state.get('active_slot')!=slot or state.get('in_progress_release'):
        raise RuntimeError('automatic_recovery_known_good_state_changed')
    owner=read(STATE/'worker-ownership.json',private=False)
    if owner.get('owner')!='CANDIDATE' or owner.get('candidate')!={'sha':value['source_sha'],'slot':slot} or known.get('worker_generation')!=owner.get('generation'):
        raise RuntimeError('automatic_recovery_worker_generation_invalid')
    rows=inspect_all();verify_runtime_scope(host['runtime_scope'],rows)
    if any(r['HostConfig']['RestartPolicy']['Name']!='no' for r in rows):raise RuntimeError('automatic_recovery_automatic_restart_refused')
    byname={r['Name'].removeprefix('/'):r for r in rows}
    names=list(PROVIDERS)+['madar-'+slot+'-'+r for r in ROLES]+['madar-release-proxy']
    if any(n not in byname for n in names):raise RuntimeError('automatic_recovery_runtime_incomplete')
    from .control_plane_upgrade import require_root_directory
    require_root_directory(ROOT,create=True)
    history=read('/var/lib/madar-control-plane/automatic-history.json')
    if history.get('schema')!=value['database']['target_schema'] or history.get('system_identifier')!=host['database_system_identifier']:
        raise RuntimeError('automatic_recovery_history_changed')
    selection=read(Path('/etc/madar/automatic-selections')/(value['source_sha']+'.json')) if Path('/etc/madar/automatic-selections',value['source_sha']+'.json').exists() else None
    manifest={'version':1,'kind':'completed-known-good-recovery','policy_sha256':digest(p),'source_sha':value['source_sha'],
        'controller_sha':value['controller_sha'],'recovery_controller_sha':system.installed_sha(),
        'operator_configuration_sha256':hashlib.sha256(readonly_configuration(Path('/etc/madar/production.env')).read_bytes()).hexdigest(),
        'attempt_id':value['attempt_id'],'admission':value,'completion_sha256':completion_sha,
        'environment':host,'history':history,'selection':selection,'known_good_release':known,'worker_ownership':owner,
        'authority_sha256':grant(value),'actors':{n:byname[n]['Id'] for n in names},
        'route_sha256':hashlib.sha256(Path('/var/lib/madar/proxy/active-upstreams.conf').read_bytes()).hexdigest()}
    atomic_json(ROOT/'known-good.json',manifest)
    return {'operation':'seal-known-good-recovery','source_sha':value['source_sha'],'manifest_sha256':digest(manifest),'deployment_authority_issued':False}

def validate_manifest(system):
    p,host=policy(system);m=read(ROOT/'known-good.json')
    if (m.get('version')!=1 or m.get('kind')!='completed-known-good-recovery'
            or m.get('policy_sha256')!=digest(p) or m.get('recovery_controller_sha')!=system.installed_sha()
            or any(m['environment'].get(k)!=host.get(k) for k in ('guest_uuid','machine_id','root_filesystem_uuid','realm_id'))):
        raise RuntimeError('automatic_recovery_manifest_policy_changed')
    if hashlib.sha256(readonly_configuration(Path('/etc/madar/production.env')).read_bytes()).hexdigest()!=m.get('operator_configuration_sha256'):
        raise RuntimeError('automatic_recovery_operator_configuration_changed')
    receipt,sha=completed(m['admission'])
    if sha!=m['completion_sha256'] or grant(m['admission'])!=m['authority_sha256']:
        raise RuntimeError('automatic_recovery_completed_authority_changed')
    state=read(STATE/'state.json',private=False)
    if state.get('known_good_release')!=m['known_good_release'] or state.get('active_slot')!=m['admission']['candidate']['slot']:
        raise RuntimeError('automatic_recovery_current_source_changed')
    if read(STATE/'worker-ownership.json',private=False)!=m['worker_ownership']:
        raise RuntimeError('automatic_recovery_worker_ownership_ambiguous')
    if read('/var/lib/madar-control-plane/automatic-history.json')!=m['history']:
        raise RuntimeError('automatic_recovery_applied_history_changed')
    if hashlib.sha256(Path('/var/lib/madar/proxy/active-upstreams.conf').read_bytes()).hexdigest()!=m['route_sha256']:
        raise RuntimeError('automatic_recovery_recorded_route_changed')
    return p,m,state

def native(system,m):
    from .migration_inventory import discover,GitSource
    from .migration_drift import observe,history_digest
    from .automatic_release_selection import fixture_inventory
    value=m['admission'];inventory=discover(system.repo,source_sha=m['source_sha'],history_base_sha=value['plan']['history_base_sha'])
    selection=m['selection']
    if selection is not None:
        current=read(Path('/etc/madar/automatic-selections')/(m['source_sha']+'.json'))
        if current!=selection:raise RuntimeError('automatic_recovery_selection_changed')
        if selection['history'].get('kind')=='isolated-fixture':inventory=fixture_inventory(GitSource(system.repo),inventory,selection['history'])
    with admission.connect_database() as db:
        observed=observe(db,required_protocols=value['plan']['compatibility_intent']['worker_protocols'],expected_structure_sha256=m['history']['structure_sha256'])
    if observed.system_identifier!=m['history']['system_identifier'] or observed.schema!=m['history']['schema'] or history_digest(inventory,observed.schema)!=m['history']['history_sha256']:
        raise RuntimeError('automatic_recovery_database_history_or_identity_changed')
    return observed.document()

def pending_scope(m,state):
    pointer=admission.ROOT/'in-progress.json'
    if not pointer.exists() and not pointer.is_symlink():
        if state.get('in_progress_release'):raise RuntimeError('automatic_recovery_unbound_interrupted_state')
        return None
    scope=read(pointer);attempt=scope.get('attempt_id')
    try:
        if str(uuid.UUID(attempt))!=attempt:raise ValueError()
    except (ValueError,TypeError,AttributeError):raise RuntimeError('automatic_recovery_pending_scope_invalid') from None
    root=admission.ROOT/'attempts'/attempt
    if (root/'migration-execution.json').exists() or (root/'candidate-runtime.json').exists():
        raise RuntimeError('automatic_recovery_committed_or_effectful_operation_requires_authorized_recovery')
    # Only interrupted preparation with no SQL/candidate effects is admitted.
    candidates=[read(f) for f in admission.ROOT.glob('*/admission.json')]
    values=[v for v in candidates if v['attempt_id']==attempt]
    if len(values)!=1 or scope.get('admission_sha256')!=digest(values[0]) or values[0]['origin']['source_sha']!=m['source_sha']:
        raise RuntimeError('automatic_recovery_pending_origin_invalid')
    return scope

def recover(system,base_operations):
    """Restart only exact accepted IDs; never compose/build/migrate/issue grants."""
    from .control_plane_upgrade import acquire_lock
    from .runtime_authority import open_deployment_lock,runtime_mutation_lock
    from .environment_file import load_environment_file
    lock=acquire_lock(system.upgrade_root/'upgrade.lock',create=True)
    started=time.monotonic();journal=None;manifest=None
    try:
        with open_deployment_lock(STATE/'deploy.lock') as deploy:
            __import__('fcntl').flock(deploy.fileno(),__import__('fcntl').LOCK_EX)
            p,m,state=validate_manifest(system);manifest=m;verify_fence(p['control_interface'])
            pending=pending_scope(m,state);rows=inspect_all();verify_runtime_scope(m['environment']['runtime_scope'],rows)
            if any(r['HostConfig']['RestartPolicy']['Name']!='no' for r in rows):raise RuntimeError('automatic_recovery_restart_policy_changed')
            slot=m['admission']['candidate']['slot'];ids=m['actors'];deadline=started+p['max_recovery_seconds']
            boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();uuid.UUID(boot)
            journal=ROOT/('boot-'+boot+'.json')
            def record(phase,**details):
                atomic_json(journal,{'operation':'known-good-boot-recovery','boot_id':boot,'source_sha':m['source_sha'],'manifest_sha256':digest(m),'phase':phase,'deployment_authority_issued':False,'migration_sql_executed':False,**details})
            record('verified_identity_and_completed_scope')
            def command(args):return run(['/usr/bin/docker',*args])
            writing=[r['Id'] for r in rows if any(r['Name'].endswith('-'+role) for role in ('backend','parser-worker','remote-ingestion-worker',*CONSUMERS)) or r['Name']=='/madar-release-proxy']
            with runtime_mutation_lock(STATE):
                command(['stop','--time','15',*writing]);record('writers_and_public_proxy_fenced')
                command(['start',ids['supabase-db']]);record('database_started')
                while True:
                    try:observation=native(system,m);break
                    except (__import__('psycopg').OperationalError,ConnectionError):
                        if time.monotonic()>=deadline:raise RuntimeError('automatic_recovery_database_unavailable')
                        time.sleep(1)
                from .isolated_release_environment import observe as observe_environment
                observed_environment=observe_environment()
                if observed_environment['control_interface']!=p['control_interface']:
                    raise RuntimeError('automatic_recovery_network_identity_changed')
                routes=json.loads(run(['/usr/sbin/ip','-json','route','show','default']))
                addresses=json.loads(run(['/usr/sbin/ip','-json','address','show','dev',p['control_interface']]))
                if (len(routes)!=1 or routes[0].get('gateway')!=p['control_gateway']
                        or len(addresses)!=1 or not any(a.get('local')=='10.0.2.15' and a.get('prefixlen')==24 for a in addresses[0].get('addr_info',[]))):
                    raise RuntimeError('automatic_recovery_static_network_changed')
                record('database_identity_schema_history_protocols_verified',database=observation)
                if pending:
                    # Keep the consumed attempt; record a distinct root recovery
                    # abort, never a fictional release completion or SQL rollback.
                    abort={'operation':'abort-proven-pre-effect-preparation','scope':pending,'known_good_source':m['source_sha'],'boot_id':boot,'database':observation,'deployment_authority_issued':False}
                    atomic_json(admission.ROOT/'attempts'/pending['attempt_id']/'recovery-aborted.json',abort,exclusive=True)
                    state.pop('in_progress_release',None)
                    from .control_plane_upgrade import atomic_json as write_state
                    current=(STATE/'state.json').stat()
                    write_state(STATE/'state.json',state,owner=(current.st_uid,current.st_gid))
                    pointer=admission.ROOT/'in-progress.json'
                    if read(pointer)!=pending:raise RuntimeError('automatic_recovery_pending_changed')
                    pointer.unlink()
                for name in PROVIDERS[1:]:command(['start',ids[name]])
                record('private_providers_started')
                # No worker or backend starts until accepted authority, protocols
                # and the singleton generation were independently rechecked.
                grant(m['admission'])
                for role in ('redis','parser-worker','remote-ingestion-worker','backend','frontend'):
                    command(['start',ids['madar-'+slot+'-'+role]])
                record('known_good_core_started')
                load_environment_file(Path('/etc/madar/production.env'))
                # Recovery uses only the measured installed driver. Operator
                # configuration is pinned but cannot select another executable.
                os.environ['MADAR_TRAFFIC_SWITCH_COMMAND']=str(system.control_root/'bin/madar-switch-traffic')
                class RecoveryOperations(base_operations):
                    def run(self,args,**kwargs):
                        if args and args[0]==os.getenv('MADAR_TRAFFIC_SWITCH_COMMAND'):
                            args=['/usr/sbin/runuser','-u','madar','--',*args]
                        return super().run(args,**kwargs)
                from .release_deployer import Compatibility
                accepted=m['admission']['candidate'];compat=Compatibility(accepted['compatible_min'],accepted['compatible_max'],m['history']['schema'],'none',accepted['compatible_min'],accepted['compatible_max'])
                ops=RecoveryOperations(system.repo,STATE,Path('/etc/madar/production.env'),compat)
                ops.release_root=STATE/'releases'/m['source_sha']
                while True:
                    try:ops.validate_candidate_core(m['source_sha'],slot);break
                    except (RuntimeError,OSError,ValueError):
                        if time.monotonic()>=deadline:raise RuntimeError('automatic_recovery_core_unready')
                        time.sleep(1)
                ops._require_worker_authority(m['source_sha'],slot);ops._require_other_worker_slot_inactive(slot)
                for role in CONSUMERS:command(['start',ids['madar-'+slot+'-'+role]])
                record('accepted_workers_started')
            ops.validate_candidate(m['source_sha'],slot)
            native(system,m);grant(m['admission']);ops._require_other_worker_slot_inactive(slot)
            command(['start',ids['madar-release-proxy']])
            ops.switch_traffic(slot);ops.validate_stable_candidate(m['source_sha'])
            record('healthy',active_slot=slot,database=observation,worker_generation=m['worker_ownership']['generation'])
            return read(journal)
    except BaseException as error:
        if manifest is not None:
            # All starts are idempotent existing-container effects. On failure
            # leave only private providers available for authorized diagnosis.
            names=['madar-release-proxy']+['madar-'+manifest['admission']['candidate']['slot']+'-'+r for r in ('backend','parser-worker','remote-ingestion-worker',*CONSUMERS)]
            selected=[manifest['actors'][n] for n in names if n in manifest['actors']]
            if selected:
                try:run(['/usr/bin/docker','stop','--time','15',*selected])
                except Exception:pass
        if journal is not None:
            atomic_json(journal,{'operation':'known-good-boot-recovery','phase':'fenced','source_sha':manifest['source_sha'],'error_type':type(error).__name__,'error_code':str(error) if isinstance(error,RuntimeError) else 'bounded_effect_failed','migration_sql_executed':False,'deployment_authority_issued':False})
        raise
    finally:os.close(lock)


def unit_definitions():
    """Dormant source definitions; installation never enables a host timer."""
    entry='/opt/madar/control-plane/deployment/bin/madar-control-plane-upgrade'
    fence='''[Unit]
Description=Madar independently enrolled disposable guest network fence
DefaultDependencies=no
After=local-fs.target systemd-udev-settle.service
Before=network-pre.target network.target docker.service docker.socket
Wants=network-pre.target
RequiresMountsFor=/etc/madar /opt/madar /var/lib/madar-control-plane
[Service]
Type=oneshot
ExecStart='''+entry+''' --restore-isolated-fence
RemainAfterExit=yes
TimeoutStartSec=30
[Install]
WantedBy=multi-user.target
'''
    recover='''[Unit]
Description=Madar exact known-good application boot recovery
Requires=madar-isolated-fence.service docker.service
After=madar-isolated-fence.service docker.service network.target
RequiresMountsFor=/var/lib/madar /var/lib/madar-control-plane
[Service]
Type=oneshot
ExecStart='''+entry+''' --recover-known-good
TimeoutStartSec=360
[Install]
WantedBy=multi-user.target
'''
    dependency='[Unit]\nRequires=madar-isolated-fence.service\nAfter=madar-isolated-fence.service\n'
    return {'madar-isolated-fence.service':fence,'madar-known-good-recovery.service':recover,
        'docker.service.d/madar-isolated-fence.conf':dependency,'docker.socket.d/madar-isolated-fence.conf':dependency}


def install(system):
    """Explicit install ONLY inside the enrolled KVM; no host or staging path."""
    p,host=policy(system)
    verify_fence(p['control_interface'])
    # No changes before positive host, filesystem, fixed controller and fence.
    root=Path('/etc/systemd/system');files=unit_definitions()
    for name,body in files.items():
        path=root/name
        if path.exists() or path.is_symlink():
            if protected(path).read_text()!=body:raise RuntimeError('automatic_recovery_existing_unit_conflict')
    for name,body in files.items():
        path=root/name;path.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
        if not path.exists():
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
            with os.fdopen(fd,'w') as f:f.write(body);f.flush();os.fsync(f.fileno())
        protected(path)
    run(['/usr/bin/systemctl','daemon-reload'])
    run(['/usr/bin/systemctl','enable','madar-isolated-fence.service','madar-known-good-recovery.service'])
    return {'operation':'install-isolated-known-good-recovery','guest_uuid':host['guest_uuid'],
        'unit_sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in files.items()},'production_activation':False}
