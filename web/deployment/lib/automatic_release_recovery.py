"""Known-good restart effects inside the EXISTING installed release controller.

Recovery consumes independently protected restart policy and actual completed
release evidence. It never calls the migration engine or publishes write grants.
Production installation/activation is deliberately not enabled by test enrollment.
"""
import hashlib,json,os,re,subprocess,time,uuid
from pathlib import Path
from .migration_inventory import canonical,digest,strict_json
from .provider_recovery_runtime import protected,readonly_configuration
from .migration_executor import atomic_json,_sync_directory
from . import automatic_release_admission as admission
from .isolated_release_environment import observe_host,observe_effect_fence,required_rules,TABLE,run,verify_runtime_scope

POLICY=Path('/etc/madar/automatic-recovery-policy.json')
ROOT=Path('/var/lib/madar-control-plane/upgrades/automatic-recovery')
STATE=Path('/var/lib/madar/releases')
ROUTE=Path('/var/lib/madar/proxy/active-upstreams.conf')
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
    historical=type(p.get('version')) is int and p['version']==2
    if historical:fields|={'historical_origin'}
    if (set(p)!=fields or type(p['version']) is not int or p['version'] not in {1,2}
            or p['kind']!=('isolated-historical-recovery-policy' if historical else 'isolated-known-good-recovery-policy')
            or p['environment_id']!='isolated-'+host['realm_id']
            or any(p[k]!=host[k] for k in ('guest_uuid','machine_id','root_filesystem_uuid'))
            or p['controller_sha']!=system.installed_sha()
            or type(p['expires_at']) is not int or not int(time.time())<p['expires_at']<=int(time.time())+14400
            or type(p['max_recovery_seconds']) is not int or not 30<=p['max_recovery_seconds']<=300
            or p['control_interface']!='ens3' or not re.fullmatch('[0-9a-f]{2}(:[0-9a-f]{2}){5}',str(p['control_mac']))
            or p['control_address']!='10.0.2.15/24' or p['control_gateway']!='10.0.2.2'):
        raise RuntimeError('automatic_recovery_independent_policy_invalid')
    if historical:
        from .historical_origin import validate_source_binding
        validate_source_binding(p['historical_origin'])
        if p['historical_origin']['controller_sha']!=p['controller_sha']:
            raise RuntimeError('automatic_recovery_historical_controller_changed')
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

def grant(value,*,mode='NORMAL'):
    if mode not in {'NORMAL','READ_ONLY'}:raise RuntimeError('automatic_recovery_grant_mode_invalid')
    from .automatic_release_execution import grant_directory,runtime_context
    p=grant_directory(value)/'authority.json';body=protected(p).read_bytes();v=strict_json(body)
    expected={'version':4,'operation':admission.OPERATION,'operation_id':value['operation_id'],
        'attempt_id':value['attempt_id'],'schema':value['database']['target_schema'],
        'target_schema':value['database']['target_schema'],'release_sha':value['source_sha'],
        'contract_digest':runtime_context(value),'mode':mode,'controller_sha':value['controller_sha'],
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
    p,host=policy(system)
    if p.get('version')!=1:raise RuntimeError('automatic_recovery_completed_policy_required')
    receipt,completion_sha=completed(value)
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
        'route_sha256':hashlib.sha256(ROUTE.read_bytes()).hexdigest()}
    atomic_json(ROOT/'known-good.json',manifest)
    return {'operation':'seal-known-good-recovery','source_sha':value['source_sha'],'manifest_sha256':digest(manifest),'deployment_authority_issued':False}

def same_known_good(left,right):
    # A live rollback-target observation refreshes this audit timestamp before
    # candidate effects. It cannot change release, schema, images or ownership.
    return (isinstance(left,dict) and isinstance(right,dict)
        and {k:v for k,v in left.items() if k!='schema_attested_at'}=={k:v for k,v in right.items() if k!='schema_attested_at'})


def historical_context(binding):
    from .historical_origin import KIND,validate_source_binding,recorded_observation
    path=validate_source_binding(binding);observed=recorded_observation(binding)
    return {'kind':KIND,'source_binding':binding,'request_record':read(path/'bootstrap-origin-request.json'),
        'enrollment_record':read(path/'bootstrap-origin-consumed.json'),'history':observed['database']}


def require_historical_boot_controls(system,original):
    from .historical_origin import network_barrier_control,BOOT_UNIT_ROOT
    controls=original.get('boot_controls',{});barriers=controls.get('network_barriers',{})
    if (set(barriers)!={'madar-isolated-fence.service'}
            or network_barrier_control(system)!=barriers['madar-isolated-fence.service']):
        raise RuntimeError('automatic_recovery_historical_network_barrier_required')
    name='madar-known-good-recovery.service';fragment=BOOT_UNIT_ROOT/name
    expected=unit_definitions()[name].encode();metadata={'uid':0,'mode':0o644,'sha256':hashlib.sha256(expected).hexdigest()}
    unit=controls.get('units',{}).get(name)
    if (unit!={'fragment':str(fragment),'dropins':[],'state':{'enabled':'enabled','active':'inactive'}}
            or controls.get('files',{}).get(str(fragment))!=metadata):
        raise RuntimeError('automatic_recovery_historical_restart_unit_required')
    raw=system.command('historical_restart_unit',['systemctl','show',name,
        '--property=FragmentPath,DropInPaths,UnitFileState,NeedDaemonReload']).stdout
    observed=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
    file=protected(fragment);info=file.stat()
    if (observed!={'FragmentPath':str(fragment),'DropInPaths':'','UnitFileState':'enabled','NeedDaemonReload':'no'}
            or info.st_uid!=0 or info.st_mode&0o7777!=0o644 or file.read_bytes()!=expected):
        raise RuntimeError('automatic_recovery_historical_restart_unit_changed')


def require_historical_boundary(binding,system):
    """No restart through consumed/ambiguous deployment or active restoration.

    An off-host source hold is root controlled and never expires itself. The
    independent recovery operator retires its receiver before releasing it.
    This path never consumes or reuses deployment approval.
    """
    from .historical_origin import validate_source_binding
    from .exceptional_release_approval import KEY,verified,CANONICAL_KIND,root as approval_root
    path=validate_source_binding(binding)
    forbidden=(ROOT/'independent-restore-in-progress.json',path/'bootstrap-origin-release-use.json',
        system.interlock_file,admission.ROOT/'in-progress.json')
    if any(p.exists() or p.is_symlink() for p in forbidden):
        raise RuntimeError('automatic_recovery_historical_operation_or_restore_pending')
    # Consumption precedes successor binding. A crash in that narrow interval
    # cannot hide the already consumed approval from boot recovery.
    requests=list(approval_root().glob('*/approval-consumed.json'))
    if len(requests)>256:raise RuntimeError('automatic_recovery_historical_journal_budget')
    if requests:
        key=protected(KEY,private=True).read_bytes()
        for consumed in requests:
            verified(consumed,key);request=verified(consumed.parent/'request.json',key)
            value=request.get('admission',{})
            if value.get('kind')==CANONICAL_KIND and value.get('contract',{}).get('source_roles')==binding:
                raise RuntimeError('automatic_recovery_historical_consumed_operation_requires_recovery')


def validate_restoration_hold(hold,*,now=None):
    """Verify the independently pinned receiver, not a caller's cleanup flag.

    The source hold is root-private and pinned before source poweroff. Neither
    this receipt nor its key can issue deployment, migration or write authority.
    Expired holds remain blocking until independently resolved; they never clear
    themselves. A retirement receipt does not certify application restoration.
    """
    now=int(time.time()) if now is None else now
    local={'version','kind','hold_id','environment_id','guest_uuid','machine_id','root_filesystem_uuid',
        'controller_sha','controller_tree_sha256','historical_origin','known_good_sha256',
        'receiver_public_key','created_at','expires_at'}
    bound={'run_id','receiver_id','operation_id','manifest_sha256','source_guest_uuid','source_sha',
        'source_database_system_identifier','source_physical_host_uuid','receiver_physical_host_uuid',
        'receiver_filesystem_uuid','receiver_enrollment_sha256','source_origin_sha256'}
    if (not isinstance(hold,dict) or set(hold)!=local|bound or type(hold['version']) is not int or hold['version']!=1
            or hold['kind']!='isolated-independent-restoration-source-hold'
            or type(hold['created_at']) is not int or type(hold['expires_at']) is not int
            or not hold['created_at']<=now<hold['expires_at']<=hold['created_at']+14400
            or not re.fullmatch(r'codex-[0-9]{8}T[0-9]{6}Z-automatic-execution-[a-f0-9]{8}',str(hold['run_id']))
            or hold['source_guest_uuid']!=hold['guest_uuid']
            or hold['receiver_physical_host_uuid'] in {hold['source_physical_host_uuid'],hold['source_guest_uuid']}
            or not re.fullmatch('[a-f0-9]{32}',str(hold['machine_id']))
            or not re.fullmatch('[1-9][0-9]{0,19}',str(hold['source_database_system_identifier']))):
        raise RuntimeError('automatic_recovery_restore_hold_invalid')
    for name in ('hold_id','guest_uuid','root_filesystem_uuid','source_physical_host_uuid',
                 'receiver_physical_host_uuid','receiver_filesystem_uuid','receiver_id','operation_id'):
        try:
            if str(uuid.UUID(hold[name]))!=hold[name]:raise ValueError()
        except (ValueError,TypeError,AttributeError):raise RuntimeError('automatic_recovery_restore_hold_identity_invalid') from None
    for name in ('manifest_sha256','receiver_enrollment_sha256','source_origin_sha256','known_good_sha256','controller_tree_sha256'):
        if not re.fullmatch('[a-f0-9]{64}',str(hold[name])):raise RuntimeError('automatic_recovery_restore_hold_digest_invalid')
    if any(not re.fullmatch('[a-f0-9]{40}',str(hold[n])) for n in ('source_sha','controller_sha')):
        raise RuntimeError('automatic_recovery_restore_hold_source_invalid')
    try:
        import base64
        if len(base64.b64decode(hold['receiver_public_key'],validate=True))!=32:raise ValueError()
    except (ValueError,TypeError):raise RuntimeError('automatic_recovery_restore_hold_key_invalid') from None
    return hold


def verify_receiver_retirement(hold,packet,*,now=None):
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    now=int(time.time()) if now is None else now
    validate_restoration_hold(hold,now=now)
    bound={'run_id','receiver_id','operation_id','manifest_sha256','source_guest_uuid','source_sha',
        'source_database_system_identifier','source_physical_host_uuid','receiver_physical_host_uuid',
        'receiver_filesystem_uuid','receiver_enrollment_sha256','source_origin_sha256'}
    if not isinstance(packet,dict) or set(packet)!={'payload','signature','receiver_public_key'}:
        raise RuntimeError('automatic_recovery_receiver_retirement_packet_invalid')
    try:
        if packet['receiver_public_key']!=hold['receiver_public_key']:raise ValueError()
        Ed25519PublicKey.from_public_bytes(base64.b64decode(hold['receiver_public_key'],validate=True)).verify(
            base64.b64decode(packet['signature'],validate=True),canonical(packet['payload']))
    except Exception:raise RuntimeError('automatic_recovery_receiver_retirement_signature_invalid') from None
    value=packet['payload']
    fields=bound|{'version','kind','cleanup_sha256','retired_at','directory_removed',
        'no_owned_containers','no_owned_networks','no_owned_volumes','deployment_authority_issued','migration_sql_executed'}
    if (not isinstance(value,dict) or set(value)!=fields or type(value['version']) is not int or value['version']!=1
            or value['kind']!='independently-retired-synthetic-receiver'
            or any(value[k]!=hold[k] for k in bound)
            or type(value['retired_at']) is not int or not hold['created_at']<=value['retired_at']<=now
            or now-value['retired_at']>300
            or not re.fullmatch('[a-f0-9]{64}',str(value['cleanup_sha256']))
            or any(value[k] is not True for k in ('directory_removed','no_owned_containers','no_owned_networks','no_owned_volumes'))
            or any(value[k] is not False for k in ('deployment_authority_issued','migration_sql_executed'))):
        raise RuntimeError('automatic_recovery_receiver_retirement_scope_invalid')
    return value


def observe_restoration_hold(system,hold):
    """Read-only source observation, shared by parent pinning and consumption."""
    if os.geteuid()!=0:raise RuntimeError('automatic_recovery_restore_hold_root_required')
    from .historical_origin import restored_context
    validate_restoration_hold(hold)
    p,host=policy(system)
    if (p.get('version')!=2 or any(hold[k]!=p[k] for k in
            ('environment_id','guest_uuid','machine_id','root_filesystem_uuid','controller_sha','controller_tree_sha256','historical_origin'))
            or hold['expires_at']>p['expires_at']):
        raise RuntimeError('automatic_recovery_restore_hold_policy_changed')
    source=historical_context(hold['historical_origin'])
    original=restored_context(hold['historical_origin'],source,now=int(time.time()))
    manifest=read(ROOT/'known-good.json')
    if (digest(manifest)!=hold['known_good_sha256'] or manifest.get('kind')!='historical-bootstrap-known-good-recovery'
            or manifest.get('historical_origin')!=hold['historical_origin']
            or original['source_sha']!=hold['source_sha'] or original['host']['guest_uuid']!=hold['guest_uuid']
            or original['database']['system_identifier']!=hold['source_database_system_identifier']
            or host['database_system_identifier']!=hold['source_database_system_identifier']
            or digest(source)!=hold['source_origin_sha256']):
        raise RuntimeError('automatic_recovery_restore_hold_origin_changed')
    rows=inspect_all();verify_runtime_scope(host['runtime_scope'],rows)
    if any(r['State'].get('Running') is not False for r in rows):
        raise RuntimeError('automatic_recovery_restore_hold_source_not_stopped')
    verify_fence(p['control_interface'])


def inspect_independent_restoration_hold(system):
    from .historical_origin import operation_locks
    with operation_locks(system) as guard:
        hold=read(ROOT/'independent-restore-in-progress.json')
        observe_restoration_hold(system,hold);guard()
        return hold


def release_independent_restoration_hold(system,packet):
    """Release only the exact source hold after verified off-host retirement.

    The normal known-good restart remains a separate operation. All actors are
    still stopped here, and the existing boot policy rechecks DB/protocol/state
    before starting any of them. Existing SQL/approval interlocks stay intact.
    """
    if os.geteuid()!=0:raise RuntimeError('automatic_recovery_restore_hold_root_required')
    from .historical_origin import operation_locks
    from .control_plane_upgrade import require_root_directory
    with operation_locks(system) as guard:
        path=ROOT/'independent-restore-in-progress.json';hold=read(path)
        value=verify_receiver_retirement(hold,packet)
        observe_restoration_hold(system,hold);guard()
        record={'operation':'release-independent-restoration-source-hold','hold_sha256':digest(hold),
            'retirement_receipt_sha256':digest(packet),'receiver_id':value['receiver_id'],
            'migration_sql_executed':False,'deployment_authority_issued':False,'application_started':False}
        parent=ROOT/'restoration-retirements';require_root_directory(parent,create=True)
        consumed=parent/(hold['hold_id']+'.json')
        if consumed.exists():
            if read(consumed)!=record:raise RuntimeError('automatic_recovery_restore_hold_consumption_conflict')
        else:atomic_json(consumed,record,exclusive=True)
        # A crash after durable consumption can finish this same unlink only
        # while the exact original hold still exists. No absent-hold replay.
        guard()
        if read(path)!=hold:raise RuntimeError('automatic_recovery_restore_hold_replaced')
        path.unlink()
        descriptor=os.open(ROOT,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
        return record


def seal_historical_known_good(system):
    """Seal an actual enrolled bootstrap origin, without a completion or grant."""
    from .historical_origin import operation_locks,attest,restored_context
    from .control_plane_upgrade import require_root_directory
    p,host=policy(system)
    if p.get('version')!=2:raise RuntimeError('automatic_recovery_historical_policy_required')
    require_historical_boot_prerequisites(system)
    with operation_locks(system) as guard:
        state=read(STATE/'state.json',private=False);binding=attest(system,state)
        if binding!=p['historical_origin']:raise RuntimeError('automatic_recovery_historical_enrollment_changed')
        require_historical_boundary(binding,system)
        context=historical_context(binding);original=restored_context(binding,context,now=int(time.time()))
        require_historical_boot_controls(system,original)
        if p['expires_at']>context['enrollment_record']['payload']['expires_at']:
            raise RuntimeError('automatic_recovery_historical_policy_outlives_enrollment')
        rows=inspect_all();verify_runtime_scope(host['runtime_scope'],rows)
        if (any(r['HostConfig']['RestartPolicy']['Name']!='no' for r in rows)
                or {r['Id'] for r in rows}!={r['id'] for r in original['runtime'].values()}):
            raise RuntimeError('automatic_recovery_historical_actor_scope_changed')
        byname={r['Name'].removeprefix('/'):r for r in rows};slot=state['known_good_release']['slot']
        names=list(PROVIDERS)+['madar-'+slot+'-'+r for r in ROLES]+['madar-release-proxy']
        operator=original['independent_operator_scope']
        from .control_plane_upgrade_authorization import RELEASE_OPERATOR_POLICY
        auth=read(RELEASE_OPERATOR_POLICY)['auth_service']['id']
        if auth not in operator['actor_ids'] or len(operator['actor_ids'])!=2:
            raise RuntimeError('automatic_recovery_historical_operator_scope_changed')
        database=next(i for i in operator['actor_ids'] if i!=auth)
        if (any(n not in byname for n in names)
                or set(byname)-set(names)!={r['Name'].removeprefix('/') for r in rows if r['Id'] in operator['actor_ids']}):
            raise RuntimeError('automatic_recovery_historical_runtime_incomplete')
        history={**original['database'],'history_sha256':original['history_sha256']}
        manifest={'version':2,'kind':'historical-bootstrap-known-good-recovery','policy_sha256':digest(p),
            'source_sha':binding['application_sha'],'recovery_controller_sha':system.installed_sha(),
            'historical_origin':binding,'historical_context':context,
            'operator_configuration_sha256':hashlib.sha256(readonly_configuration(Path('/etc/madar/production.env')).read_bytes()).hexdigest(),
            'configuration_sha256':original['configuration_sha256'],
            'environment':host,'history':history,'known_good_release':state['known_good_release'],
            'worker_ownership':read(STATE/'worker-ownership.json',private=False),
            'operator_actors':{'database':database,'auth':auth},
            'actors':{name:row['Id'] for name,row in byname.items()},
            'route_sha256':hashlib.sha256(ROUTE.read_bytes()).hexdigest()}
        require_root_directory(ROOT,create=True);guard()
        atomic_json(ROOT/'known-good.json',manifest,exclusive=True)
        return {'operation':'seal-historical-known-good-recovery','source_sha':binding['application_sha'],
            'manifest_sha256':digest(manifest),'deployment_authority_issued':False,'protected_completion_claimed':False}


def validate_historical_manifest(system,p,host,m):
    from .historical_origin import restored_context,bootstrap_record
    fields={'version','kind','policy_sha256','source_sha','recovery_controller_sha','historical_origin','historical_context',
        'operator_configuration_sha256','configuration_sha256','environment','history','known_good_release','worker_ownership',
        'operator_actors','actors','route_sha256'}
    if (set(m)!=fields or type(m.get('version')) is not int or m['version']!=2 or p.get('version')!=2
            or m.get('kind')!='historical-bootstrap-known-good-recovery' or m['policy_sha256']!=digest(p)
            or m['historical_origin']!=p['historical_origin'] or m['recovery_controller_sha']!=system.installed_sha()
            or any(m['environment'].get(k)!=host.get(k) for k in ('guest_uuid','machine_id','root_filesystem_uuid','realm_id'))):
        raise RuntimeError('automatic_recovery_historical_manifest_changed')
    require_historical_boundary(m['historical_origin'],system)
    original=restored_context(m['historical_origin'],m['historical_context'],now=int(time.time()))
    require_historical_boot_controls(system,original)
    if (m['source_sha']!=original['source_sha'] or m['history']!={**original['database'],'history_sha256':original['history_sha256']}
            or host['database_system_identifier']!=original['database']['system_identifier']
            or host['database_container_id']!=m['actors'].get('supabase-db')
            or digest(host['runtime_scope'])!=original['runtime_scope_sha256']
            or digest(bootstrap_record(STATE/'origin-bootstrap-adopted.json'))!=original['bootstrap_sha256']
            or hashlib.sha256(readonly_configuration(Path('/etc/madar/production.env')).read_bytes()).hexdigest()!=m['operator_configuration_sha256']
            or m['operator_configuration_sha256']!=original['configuration_sha256']['application']):
        raise RuntimeError('automatic_recovery_historical_original_data_changed')
    files={'application':Path('/etc/madar/production.env'),'backup':Path('/etc/madar/backup.env'),
        'database_transport':Path('/etc/madar/automatic-database.dsn')}
    if (m['configuration_sha256']!=original['configuration_sha256'] or set(m['configuration_sha256'])!=set(files)
            or any(hashlib.sha256(readonly_configuration(path,private=True).read_bytes()).hexdigest()!=m['configuration_sha256'][key]
                for key,path in files.items())):
        raise RuntimeError('automatic_recovery_historical_configuration_changed')
    state=read(STATE/'state.json',private=False);known=state.get('known_good_release') or {}
    owner=read(STATE/'worker-ownership.json',private=False)
    if (state.get('in_progress_release') or state.get('rollback_failure') or state.get('active_slot')!=known.get('slot')
            or not same_known_good(known,m['known_good_release'])
            or any(type(known.get(k)) is not int for k in ('schema','schema_compatible_min','schema_compatible_max'))
            or (known['schema'],known['schema_compatible_min'],known['schema_compatible_max'])!=(146,144,146)
            or known.get('sha')!=m['source_sha'] or 'completed_normal_upgrade' in known
            or owner!=m['worker_ownership'] or owner!=original['worker_authority']
            or owner.get('owner')!='CANDIDATE' or owner.get('candidate')!={'sha':m['source_sha'],'slot':known['slot']}
            or owner.get('generation')!=known.get('worker_generation')
            or hashlib.sha256(ROUTE.read_bytes()).hexdigest()!=m['route_sha256']):
        raise RuntimeError('automatic_recovery_historical_owner_or_route_changed')
    actual={name.removeprefix('/'):r['id'] for name,r in original['runtime'].items()}
    from .control_plane_upgrade_authorization import RELEASE_OPERATOR_POLICY
    if (m['actors']!=actual or set(m['operator_actors'])!={'database','auth'}
            or set(m['operator_actors'].values())!=set(original['independent_operator_scope']['actor_ids'])
            or m['operator_actors']['auth']!=read(RELEASE_OPERATOR_POLICY)['auth_service']['id']):
        raise RuntimeError('automatic_recovery_historical_actor_scope_changed')
    return p,m,state


def validate_manifest(system):
    p,host=policy(system);m=read(ROOT/'known-good.json')
    if m.get('kind')=='historical-bootstrap-known-good-recovery':
        return validate_historical_manifest(system,p,host,m)
    if (p.get('version')!=1 or m.get('version')!=1 or m.get('kind')!='completed-known-good-recovery'
            or m.get('policy_sha256')!=digest(p) or m.get('recovery_controller_sha')!=system.installed_sha()
            or any(m['environment'].get(k)!=host.get(k) for k in ('guest_uuid','machine_id','root_filesystem_uuid','realm_id'))):
        raise RuntimeError('automatic_recovery_manifest_policy_changed')
    if hashlib.sha256(readonly_configuration(Path('/etc/madar/production.env')).read_bytes()).hexdigest()!=m.get('operator_configuration_sha256'):
        raise RuntimeError('automatic_recovery_operator_configuration_changed')
    receipt,sha=completed(m['admission'])
    if sha!=m['completion_sha256'] or grant(m['admission'])!=m['authority_sha256']:
        raise RuntimeError('automatic_recovery_completed_authority_changed')
    state=read(STATE/'state.json',private=False)
    if not same_known_good(state.get('known_good_release'),m['known_good_release']) or state.get('active_slot')!=m['admission']['candidate']['slot']:
        raise RuntimeError('automatic_recovery_current_source_changed')
    if read(STATE/'worker-ownership.json',private=False)!=m['worker_ownership']:
        raise RuntimeError('automatic_recovery_worker_ownership_ambiguous')
    if read('/var/lib/madar-control-plane/automatic-history.json')!=m['history']:
        raise RuntimeError('automatic_recovery_applied_history_changed')
    if hashlib.sha256(ROUTE.read_bytes()).hexdigest()!=m['route_sha256']:
        raise RuntimeError('automatic_recovery_recorded_route_changed')
    return p,m,state

def native(system,m):
    from .migration_inventory import discover,GitSource
    from .migration_drift import observe,history_digest
    from .automatic_release_selection import fixture_inventory
    if m.get('kind')=='historical-bootstrap-known-good-recovery':
        inventory=discover(system.repo,source_sha=m['source_sha'],history_base_sha=m['source_sha'])
        with admission.connect_database() as db:
            observed=observe(db,required_protocols={},expected_structure_sha256=m['history']['structure_sha256'])
            try:
                db.execute('BEGIN READ ONLY')
                absent=db.execute("SELECT to_regprocedure('public.notification_delivery_protocol()') IS NULL AND to_regprocedure('public.notification_outbox_protocol()') IS NULL AND to_regprocedure('public.data_deletion_ownership_protocol()') IS NULL").fetchone()
            finally:db.rollback()
        if (observed.system_identifier!=m['history']['system_identifier'] or observed.schema!=146
                or history_digest(inventory,146)!=m['history']['history_sha256'] or absent!=(True,)):
            raise RuntimeError('automatic_recovery_historical_database_changed')
        return observed.document()
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


def accepted_runtime(m):
    if m.get('kind')=='historical-bootstrap-known-good-recovery':
        known=m['known_good_release']
        return {'slot':known['slot'],'compatible_min':known['schema_compatible_min'],
            'compatible_max':known['schema_compatible_max']}
    return m['admission']['candidate']


def historical_restart_authority(system,m):
    """Reverify the existing grantless owner; never create a modern grant."""
    p,host=policy(system);validate_historical_manifest(system,p,host,m)
    slot=m['known_good_release']['slot'];rows=inspect_all()
    from .completed_normal_resources import measured_spec
    original=m['historical_context']['request_record']['payload']['observation']['runtime']
    for row in rows:
        name=row['Name'];expected=original.get(name)
        if expected is None or (row['Id'],row['Image'],measured_spec(row))!=(expected['id'],expected['image'],expected['spec_sha256']):
            raise RuntimeError('automatic_recovery_historical_runtime_changed')
        if name in {'/madar-'+slot+'-'+role for role in ROLES}:
            env=dict(x.split('=',1) for x in row['Config'].get('Env',[]) if '=' in x)
            if (any(env.get(k) for k in ('MADAR_BUSINESS_WRITE_AUTHORITY','MADAR_BUSINESS_WRITE_CONTRACT'))
                    or any(x['Destination']=='/run/madar' or x['Destination'].startswith('/run/madar/business-write-authority') for x in row.get('Mounts',[]))):
                raise RuntimeError('automatic_recovery_historical_grant_was_not_original')
    if {r['Id'] for r in rows}!=set(m['actors'].values()):raise RuntimeError('automatic_recovery_historical_runtime_changed')


def recover_historical_operator(system,m,deadline):
    """Restart only the separately enrolled infrastructure identity pair."""
    historical_restart_authority(system,m)
    p,_=policy(system);verify_fence(p['control_interface'])
    ids=m['operator_actors'];run(['/usr/bin/docker','start',ids['database']])
    while True:
        ready=subprocess.run(['/usr/bin/docker','exec',ids['database'],'pg_isready','-h','127.0.0.1','-U','postgres','-d','operators'],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5,
            env={'PATH':os.defpath,'HOME':'/nonexistent','DOCKER_HOST':'unix:///var/run/docker.sock','DOCKER_CONFIG':'/nonexistent'})
        if ready.returncode==0:break
        if time.monotonic()>=deadline:raise RuntimeError('automatic_recovery_historical_operator_database_unavailable')
        time.sleep(1)
    run(['/usr/bin/docker','start',ids['auth']])
    from .historical_origin import independent_operator_scope
    original=m['historical_context']['request_record']['payload']['observation']
    current=inspect_all()
    if independent_operator_scope(current,observe_host())!=original['independent_operator_scope']:
        raise RuntimeError('automatic_recovery_historical_operator_scope_changed')
    auth=next(r for r in current if r['Id']==ids['auth'])
    endpoints=auth['NetworkSettings']['Networks']
    if len(endpoints)!=1:raise RuntimeError('automatic_recovery_historical_operator_network_changed')
    address=next(iter(endpoints.values())).get('IPAddress')
    from ipaddress import IPv4Address
    try:
        if not IPv4Address(address).is_private or str(IPv4Address(address))!=address:raise ValueError()
    except (ValueError,TypeError):raise RuntimeError('automatic_recovery_historical_operator_network_changed') from None
    from urllib.request import build_opener,ProxyHandler,HTTPRedirectHandler
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*a,**kw):return None
    opener=build_opener(ProxyHandler({}),NoRedirect())
    while True:
        try:
            with opener.open('http://'+address+':9999/health',timeout=5) as response:
                body=response.read(65537)
                if response.status!=200 or len(body)>65536 or not isinstance(strict_json(body),dict):raise ValueError()
            break
        except (OSError,ValueError):
            if time.monotonic()>=deadline:raise RuntimeError('automatic_recovery_historical_operator_auth_unavailable')
            time.sleep(1)

def observe_reserved_attempt(value):
    """Authenticate a historical consumption record without reusing its grant.

    Ordinary execution remains bound to its original live PID/start/boot. Boot
    recovery only observes that consumed attempt, and refuses a still-live owner.
    """
    record=read(admission.ROOT/'attempts'/value['attempt_id']/'consumed.json')
    fixed={'admission_sha256':digest(value),'source_sha':value['source_sha'],
        'operation_id':value['operation_id'],'attempt_id':value['attempt_id']}
    if (set(record)!=set(fixed)|{'pid','process_start','boot_id'}
            or any(record.get(k)!=v for k,v in fixed.items())
            or type(record.get('pid')) is not int or record['pid']<=1
            or not isinstance(record.get('process_start'),str) or not record['process_start'].isdigit()):
        raise RuntimeError('automatic_recovery_consumed_attempt_changed')
    try:
        if str(uuid.UUID(record['boot_id']))!=record['boot_id']:raise ValueError()
    except (ValueError,TypeError,AttributeError):raise RuntimeError('automatic_recovery_consumed_attempt_changed') from None
    if record['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        try:start=Path('/proc',str(record['pid']),'stat').read_text().split(') ',1)[1].split()[19]
        except FileNotFoundError:start=None
        except (OSError,IndexError):raise RuntimeError('automatic_recovery_pending_owner_unknown') from None
        if start==record['process_start']:raise RuntimeError('automatic_recovery_pending_owner_still_running')
    return record


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
    unsafe='automatic_recovery_committed_or_effectful_operation_requires_authorized_recovery'
    if any((root/name).exists() or (root/name).is_symlink() for name in
            ('migration-execution.json','migration-completion.json','migration-boundaries.json','locked-exceptional-impact.json','completion.json')):
        raise RuntimeError(unsafe)
    candidates=[read(f) for f in admission.ROOT.glob('*/admission.json')]
    values=[v for v in candidates if v['attempt_id']==attempt]
    if len(values)!=1:raise RuntimeError(unsafe)
    value=values[0]
    admission.sealed(value,allow_expired=True);observe_reserved_attempt(value)
    expected={'version':1,'operation':admission.OPERATION,'attempt_id':attempt,'admission_sha256':digest(value),
        'source_sha':value['source_sha'],'operation_id':value['operation_id'],'database_system_identifier':value['database']['system_identifier']}
    runtime=root/'candidate-runtime.json'
    interrupted=state.get('in_progress_release') or {}
    # The trusted SQL executor fsyncs migration-execution before SQL. Only the
    # earlier source/build/preflight boundary, with unchanged original worker
    # authority and no candidate runtime, can abandon a planned migration.
    planned_pre_effect=(bool(value['plan']['migrations'])
        and interrupted.get('release_sha')==value['source_sha']
        and interrupted.get('phase') in {'source_validation','immutable_build','preflight'}
        and not runtime.exists() and not runtime.is_symlink())
    if (scope!=expected or (value['plan']['migrations'] and not planned_pre_effect)
            or value['origin']['source_sha']!=m['source_sha'] or value['origin']['slot']!=m['admission']['candidate']['slot']
            or value['database']['system_identifier']!=m['history']['system_identifier']
            or value['database']['origin_schema']!=m['history']['schema'] or (not planned_pre_effect and value['database']['target_schema']!=m['history']['schema'])
            or read(STATE/'worker-ownership.json',private=False)!=m['worker_ownership']):raise RuntimeError(unsafe)
    from .automatic_release_execution import grant_directory
    authority=grant_directory(value)/'authority.json'
    has_runtime=runtime.exists() or runtime.is_symlink()
    if has_runtime or authority.exists() or authority.is_symlink():grant(value,mode='READ_ONLY')
    if has_runtime:
        candidate=read(runtime)
        if not isinstance(candidate,dict) or len(candidate)!=len(ROLES):raise RuntimeError(unsafe)
        # A finished failed-candidate cleanup is provable; an interrupted Docker
        # effect or still-present candidate remains fenced for authorized repair.
        present={r['Id'] for r in inspect_all()}
        if set(candidate)&present:raise RuntimeError(unsafe)

    return scope

def recover(system,base_operations):
    """Restart only exact accepted IDs; never compose/build/migrate/issue grants."""
    from .control_plane_upgrade import acquire_lock
    from .runtime_authority import open_deployment_lock,runtime_mutation_lock
    from .environment_file import load_environment_file
    # Authenticate the guest and code before any recovery journal/lock effect.
    initial_policy,_=policy(system)
    lock=acquire_lock(system.upgrade_root/'upgrade.lock',create=True)
    started=time.monotonic();journal=None;manifest=None
    try:
        with open_deployment_lock(STATE/'deploy.lock') as deploy:
            __import__('fcntl').flock(deploy.fileno(),__import__('fcntl').LOCK_EX)
            from .control_plane_upgrade import require_root_directory
            require_root_directory(ROOT,create=True)
            boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();uuid.UUID(boot)
            journal=ROOT/('boot-'+boot+'.json')
            atomic_json(journal,{'operation':'historical-known-good-boot-recovery' if initial_policy.get('version')==2 else 'known-good-boot-recovery',
                'boot_id':boot,'phase':'verifying_historical_enrollment' if initial_policy.get('version')==2 else 'verifying_completed_scope',
                'controller_sha':initial_policy['controller_sha'],'deployment_authority_issued':False,'migration_sql_executed':False})
            p,m,state=validate_manifest(system);manifest=m;verify_fence(p['control_interface'])
            historical=m.get('kind')=='historical-bootstrap-known-good-recovery'
            pending=None if historical else pending_scope(m,state);rows=inspect_all()
            # Current independently enrolled inventory can retire an obsolete
            # inactive slot. Every accepted provider/application identity still
            # has to match its original sealed preimage exactly.
            _,host=policy(system);verify_runtime_scope(host['runtime_scope'],rows)
            accepted=set(m['actors'].values())
            selected={identity:spec for identity,spec in m['environment']['runtime_scope'].items() if identity in accepted}
            if set(selected)!=accepted:raise RuntimeError('automatic_recovery_accepted_inventory_incomplete')
            verify_runtime_scope(selected,[r for r in rows if r['Id'] in accepted])
            if any(r['HostConfig']['RestartPolicy']['Name']!='no' for r in rows):raise RuntimeError('automatic_recovery_restart_policy_changed')
            slot=accepted_runtime(m)['slot'];ids=m['actors'];deadline=started+p['max_recovery_seconds']
            boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();uuid.UUID(boot)
            journal=ROOT/('boot-'+boot+'.json')
            def record(phase,**details):
                atomic_json(journal,{'operation':'historical-known-good-boot-recovery' if historical else 'known-good-boot-recovery','boot_id':boot,'source_sha':m['source_sha'],'manifest_sha256':digest(m),'phase':phase,'deployment_authority_issued':False,'migration_sql_executed':False,**({'protected_completion_claimed':False} if historical else {}),**details})
            record('verified_identity_and_historical_enrollment' if historical else 'verified_identity_and_completed_scope')
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
                    planned=read(admission.ROOT/pending['admission_sha256']/'admission.json')['plan']['migrations']
                    abort={'operation':'abort-verified-pre-effect-migration-attempt' if planned else 'abort-verified-application-only-attempt','scope':pending,'known_good_source':m['source_sha'],'boot_id':boot,'database':observation,'deployment_authority_issued':False,'migration_sql_executed':False}
                    abort_path=admission.ROOT/'attempts'/pending['attempt_id']/'recovery-aborted.json'
                    if abort_path.exists() or abort_path.is_symlink():
                        prior=read(abort_path)
                        if {k:v for k,v in prior.items() if k!='boot_id'}!={k:v for k,v in abort.items() if k!='boot_id'}:
                            raise RuntimeError('automatic_recovery_existing_abort_changed')
                    else:atomic_json(abort_path,abort,exclusive=True)
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
                if historical:
                    recover_historical_operator(system,m,deadline)
                    historical_restart_authority(system,m)
                else:grant(m['admission'])
                for role in ('redis','parser-worker','remote-ingestion-worker','backend','frontend'):
                    command(['start',ids['madar-'+slot+'-'+role]])
                record('known_good_core_started')
                load_environment_file(Path('/etc/madar/production.env'))
                from .release_deployer import Compatibility
                accepted=accepted_runtime(m);compat=Compatibility(accepted['compatible_min'],accepted['compatible_max'],m['history']['schema'],'none',accepted['compatible_min'],accepted['compatible_max'])
                ops=base_operations(system.repo,STATE,Path('/etc/madar/production.env'),compat)
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
            native(system,m)
            if historical:historical_restart_authority(system,m)
            else:grant(m['admission'])
            # Boot restores the already accepted route, not a new promotion.
            # The proxy was fenced/stopped above, so its new process loads the
            # exact sealed configuration. Rewriting it through the promotion
            # driver can change an original root-owned file to operator-owned
            # bytes and invalidate the immutable bind on the next reboot.
            with runtime_mutation_lock(STATE):
                ops._require_other_worker_slot_inactive(slot)
                if hashlib.sha256(ROUTE.read_bytes()).hexdigest()!=m['route_sha256']:
                    raise RuntimeError('automatic_recovery_recorded_route_changed')
                command(['start',ids['madar-release-proxy']])
                while True:
                    try:identity=system.http_json('http://127.0.0.1:8001/health/version');break
                    except RuntimeError as error:
                        if str(error)!='production_health_unavailable':raise
                        if time.monotonic()>=deadline:raise RuntimeError('automatic_recovery_proxy_unavailable') from None
                        time.sleep(.25)
                if identity.get('release_sha')!=m['source_sha'] or identity.get('release_slot')!=slot:
                    raise RuntimeError('automatic_recovery_loaded_route_changed')
                ops.validate_stable_candidate(m['source_sha'])
                verify_runtime_scope(host['runtime_scope'],inspect_all())
                if policy(system)!=(p,host):raise RuntimeError('automatic_recovery_policy_changed_during_restart')
            if pending:
                # Rebind the same genuine completion after proven pre-SQL
                # compensation. No new deployment receipt or authority exists.
                seal_known_good(system,m['admission']);m=read(ROOT/'known-good.json');manifest=m
            record('healthy',active_slot=slot,database=observation,worker_generation=m['worker_ownership']['generation'])
            return read(journal)
    except BaseException as error:
        if manifest is not None:
            # All starts are idempotent existing-container effects. On failure
            # leave only private providers available for authorized diagnosis.
            names=['madar-release-proxy']+['madar-'+accepted_runtime(manifest)['slot']+'-'+r for r in ('backend','parser-worker','remote-ingestion-worker',*CONSUMERS)]
            selected=[manifest['actors'][n] for n in names if n in manifest['actors']]
            if selected:
                try:run(['/usr/bin/docker','stop','--time','15',*selected])
                except Exception:pass
        if journal is not None:
            atomic_json(journal,{'operation':'historical-known-good-boot-recovery' if initial_policy.get('version')==2 else 'known-good-boot-recovery',
                'phase':'fenced','source_sha':manifest['source_sha'] if manifest is not None else None,'error_type':type(error).__name__,'error_code':str(error) if isinstance(error,RuntimeError) else 'bounded_effect_failed','migration_sql_executed':False,'deployment_authority_issued':False})
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


def _install_units(system,p,host):
    """Existing unit installer; callers already verified the independent policy."""
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
    result={'operation':'install-isolated-known-good-recovery','guest_uuid':host['guest_uuid'],
        'unit_sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in files.items()},'production_activation':False}
    return result


BOOT_PREREQUISITES=ROOT/'historical-boot-prerequisites'


def _historical_boot_scope(system,p,host,*,unsigned=False):
    from .historical_origin import bootstrap_record
    state=strict_json(readonly_configuration(system.state_root/'state.json',private=True).read_bytes())
    known=state.get('known_good_release') or {}
    if (known.get('schema')!=146 or type(known.get('schema')) is not int
            or known.get('slot') not in {'blue','green'} or state.get('active_slot')!=known['slot']
            or state.get('in_progress_release') or state.get('rollback_failure')
            or 'completed_normal_upgrade' in known):
        raise RuntimeError('historical_boot_original146_required')
    bootstrap=bootstrap_record(system.state_root/'origin-bootstrap-adopted.json')
    if (bootstrap not in state.get('history',[]) or bootstrap.get('phase')!='bootstrap_adopted'
            or bootstrap.get('status')!='known_good' or bootstrap.get('release_sha')!=known.get('sha')
            or bootstrap.get('candidate_slot')!=known['slot'] or bootstrap.get('traffic_target')!=known['slot']
            or bootstrap.get('schema')!={'observed':146} or bootstrap.get('images')!=known.get('images')):
        raise RuntimeError('historical_boot_truthful_bootstrap_required')
    if unsigned:
        requests=admission.ROOT/'historical-origins'
        if (p['version']!=1 or known.get('historical_origin')
                or any(requests.glob('*/bootstrap-origin-request.json'))):
            raise RuntimeError('historical_boot_installation_must_precede_signed_inventory')
    observed=strict_json(run(['/usr/bin/docker','exec',host['database_container_id'],'psql','-XqAt',
        '-v','ON_ERROR_STOP=1','-U','supabase_admin','-d','postgres','-c',
        "BEGIN READ ONLY; SET LOCAL statement_timeout='5s'; SELECT json_build_array("
        "(SELECT system_identifier::text FROM pg_control_system()),schema_version) "
        "FROM public.application_schema_state WHERE contract_key='core'; COMMIT;"]))
    if observed!=[host['database_system_identifier'],146]:
        raise RuntimeError('historical_boot_database_changed')
    return {'environment_id':p['environment_id'],**{k:p[k] for k in
        ('guest_uuid','machine_id','root_filesystem_uuid','controller_sha','controller_tree_sha256',
         'control_interface','control_mac','control_address','control_gateway')},
        'database_system_identifier':host['database_system_identifier'],'source_sha':known['sha'],
        'slot':known['slot'],'bootstrap_sha256':digest(bootstrap)}


def require_historical_boot_prerequisites(system):
    """A ready root journal and real units precede signed origin inventories."""
    p,host=policy(system);scope=_historical_boot_scope(system,p,host)
    try:original=read(BOOT_PREREQUISITES/'scope.json');ready=read(BOOT_PREREQUISITES/'ready.json')
    except (OSError,RuntimeError):
        raise RuntimeError('historical_boot_prerequisites_not_ready') from None
    if (set(original)!={'version','kind','scope','bootstrap_policy'} or original['version']!=1
            or original['kind']!='isolated-historical-boot-prerequisites' or original['scope']!=scope
            or original['bootstrap_policy'].get('version')!=1
            or any(original['bootstrap_policy'].get(k)!=p[k] for k in scope if k in p)
            or p['expires_at']>original['bootstrap_policy']['expires_at']):
        raise RuntimeError('historical_boot_prerequisite_scope_changed')
    fields={'operation','scope_sha256','attempt_id','unit_sha256','network_barrier',
        'deployment_authority_issued','migration_sql_executed','historical_inventory_signed'}
    try:
        if str(uuid.UUID(ready.get('attempt_id','')))!=ready['attempt_id']:raise ValueError()
    except (ValueError,TypeError,AttributeError):
        raise RuntimeError('historical_boot_prerequisite_receipt_changed') from None
    if (set(ready)!=fields or ready['operation']!='prepare-historical-boot-prerequisites'
            or ready['scope_sha256']!=digest(original)
            or any(ready[k] is not False for k in ('deployment_authority_issued','migration_sql_executed','historical_inventory_signed'))
            or ready['unit_sha256']!={k:hashlib.sha256(v.encode()).hexdigest() for k,v in unit_definitions().items()}):
        raise RuntimeError('historical_boot_prerequisite_receipt_changed')
    from .historical_origin import network_barrier_control
    verify_fence(p['control_interface'])
    if network_barrier_control(system)!=ready['network_barrier']:
        raise RuntimeError('historical_boot_prerequisite_barrier_changed')
    for name,body in unit_definitions().items():
        if protected(Path('/etc/systemd/system')/name).read_text()!=body:
            raise RuntimeError('historical_boot_prerequisite_unit_changed')
    state=system.systemctl_state('madar-known-good-recovery.service')
    if state!={'enabled':'enabled','active':'inactive'}:
        raise RuntimeError('historical_boot_prerequisite_recovery_unit_changed')
    completion=read(BOOT_PREREQUISITES/'attempts'/ready['attempt_id']/'completed.json')
    if completion!=ready:raise RuntimeError('historical_boot_prerequisite_attempt_changed')
    return ready


def prepare_historical_boot_prerequisites(system):
    """Install the existing boot controls before one historical enrollment.

    This is recovery infrastructure preparation, never migration/release authority.
    Interrupted intents and failed attempts remain in the existing recovery tree;
    a retry must have the same independent policy, source, database and controller.
    """
    from .historical_origin import operation_locks,network_barrier_control
    from .control_plane_upgrade import require_root_directory
    p,host=policy(system)
    with operation_locks(system):
        scope=_historical_boot_scope(system,p,host,unsigned=True)
        require_root_directory(ROOT,create=True)
        _sync_directory(ROOT.parent)
        require_root_directory(BOOT_PREREQUISITES,create=True)
        _sync_directory(BOOT_PREREQUISITES.parent)
        initial={'version':1,'kind':'isolated-historical-boot-prerequisites','scope':scope,'bootstrap_policy':p}
        location=BOOT_PREREQUISITES/'scope.json'
        if location.exists():
            if read(location)!=initial:raise RuntimeError('historical_boot_prerequisite_scope_changed')
        else:atomic_json(location,initial,exclusive=True)
        if (BOOT_PREREQUISITES/'ready.json').exists():return require_historical_boot_prerequisites(system)
        attempts=BOOT_PREREQUISITES/'attempts';require_root_directory(attempts,create=True)
        _sync_directory(BOOT_PREREQUISITES)
        if len(list(attempts.iterdir()))>=8:raise RuntimeError('historical_boot_prerequisite_attempt_budget')
        attempt_id=str(uuid.uuid4());attempt=attempts/attempt_id;attempt.mkdir(mode=0o700)
        _sync_directory(attempts)
        atomic_json(attempt/'intent.json',{'operation':'prepare-historical-boot-prerequisites',
            'scope_sha256':digest(initial),'attempt_id':attempt_id,'deployment_authority_issued':False,
            'migration_sql_executed':False},exclusive=True)
        try:
            installed=_install_units(system,p,host)
            run(['/usr/bin/systemctl','start','madar-isolated-fence.service'])
            ready={'operation':'prepare-historical-boot-prerequisites','scope_sha256':digest(initial),
                'attempt_id':attempt_id,'unit_sha256':installed['unit_sha256'],
                'network_barrier':network_barrier_control(system),'deployment_authority_issued':False,
                'migration_sql_executed':False,'historical_inventory_signed':False}
            # Confirm source/policy again before accepting an interrupted retry.
            current,current_host=policy(system)
            if current!=p or _historical_boot_scope(system,current,current_host,unsigned=True)!=scope:
                raise RuntimeError('historical_boot_prerequisite_scope_changed')
            atomic_json(attempt/'completed.json',ready,exclusive=True)
            atomic_json(BOOT_PREREQUISITES/'ready.json',ready,exclusive=True)
            return require_historical_boot_prerequisites(system)
        except Exception as error:
            atomic_json(attempt/'failed.json',{'attempt_id':attempt_id,'exception_type':type(error).__name__,
                'scope_sha256':digest(initial),'deployment_authority_issued':False,'migration_sql_executed':False},exclusive=True)
            raise


def install(system):
    """Explicit install ONLY inside the enrolled KVM; no host or staging path."""
    p,host=policy(system)
    state_file=getattr(system,'state_root',STATE)/'state.json'
    if p['version']==1 and state_file.exists():
        state=strict_json(readonly_configuration(state_file,private=True).read_bytes())
        if (state.get('known_good_release') or {}).get('schema')==146:
            return prepare_historical_boot_prerequisites(system)
    result=_install_units(system,p,host)
    if p['version']==2:result['historical_recovery']=seal_historical_known_good(system)
    return result
