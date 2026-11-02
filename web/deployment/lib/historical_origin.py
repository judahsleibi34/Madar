"""Truthful bootstrap-origin enrollment by the existing independent issuer.

An enrollment is NOT a protected-release completion or migration approval. It
records an observed historical application under separately pinned test policy.
Ordinary completed-release admission is deliberately unchanged.
"""
from __future__ import annotations
import hashlib, os, re, time, uuid
from contextlib import contextmanager
from pathlib import Path
from .migration_inventory import digest, strict_json
from .provider_recovery_runtime import protected, readonly_configuration
from .migration_executor import atomic_json
from .exceptional_release_approval import journal_lock, sign, verified, identifier

POLICY=Path('/etc/madar/historical-origin-policy.json')
KIND='independently-enrolled-historical-bootstrap-origin'
SOURCE_FIELDS={'origin_kind','enrollment_root','enrollment_sha256','application_sha',
               'controller_sha','schema','successor_intent_sha256'}
ROLES=('backend','frontend','redis','parser-worker','remote-ingestion-worker',
       'notification-worker','calendar-sync-worker','data-deletion-worker')


def bootstrap_record(path):
    """Read original operator lifecycle DATA, never a trusted issuer receipt.

    Historical bootstrap was written by the application operator. Its bytes
    become useful only after live verification and independent root digest
    pinning. Do not relax protected() for signed enrollments or completions.
    """
    import pwd, stat
    path=Path(path);operator=pwd.getpwnam('madar').pw_uid
    if not path.is_absolute():raise RuntimeError('historical_origin_bootstrap_path_invalid')
    for item in path.parents:
        metadata=item.lstat()
        if (not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid not in {0,operator}
                or metadata.st_mode&0o002 or metadata.st_mode&0o020 and metadata.st_uid!=operator):
            raise RuntimeError('historical_origin_bootstrap_parent_untrusted')
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        metadata=os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid not in {0,operator}
                or metadata.st_mode&0o077 or not 0<metadata.st_size<=65536):
            raise RuntimeError('historical_origin_bootstrap_data_untrusted')
        with os.fdopen(descriptor,'rb',closefd=False) as stream:body=stream.read(65537)
        if len(body)!=metadata.st_size:raise RuntimeError('historical_origin_bootstrap_data_changed')
        return strict_json(body)
    finally:os.close(descriptor)


def preservation_roots(db):
    """Bounded native READ ONLY snapshot; customer values never leave as text.

    Auth challenge/access timestamps legitimately change during these probes;
    identities, password/MFA material, memberships and all public business rows
    remain fingerprinted. This is not a claim to freeze changing live sessions.
    """
    from psycopg import sql
    from psycopg.pq import TransactionStatus
    roots={};deadline=time.monotonic()+45
    if not db.autocommit or db.info.transaction_status!=TransactionStatus.IDLE:
        raise RuntimeError('historical_origin_readonly_connection_required')
    db.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
    try:
        db.execute("SET LOCAL statement_timeout='5s'")
        db.execute("SET LOCAL lock_timeout='1s'")
        tables=db.execute("""SELECT n.nspname,c.relname FROM pg_catalog.pg_class c
          JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
          WHERE c.relkind IN ('r','p') AND (n.nspname='public' OR
          (n.nspname='auth' AND c.relname IN ('users','identities','mfa_factors')) OR
          (n.nspname='storage' AND c.relname IN ('objects','buckets')))
          ORDER BY n.nspname,c.relname""").fetchall()
        if not 1<=len(tables)<=512:raise RuntimeError('historical_origin_table_budget')
        for schema,table in tables:
            if time.monotonic()>deadline:raise RuntimeError('historical_origin_snapshot_deadline')
            relation=sql.SQL('{}.{}').format(sql.Identifier(schema),sql.Identifier(table))
            count=db.execute(sql.SQL('SELECT count(*) FROM {}').format(relation)).fetchone()[0]
            if not 0<=count<=100000:raise RuntimeError('historical_origin_row_budget')
            ignored=(['last_sign_in_at','updated_at'] if (schema,table)==('auth','users') else
                ['last_challenged_at','updated_at'] if (schema,table)==('auth','mfa_factors') else
                ['last_accessed_at','updated_at'] if (schema,table)==('storage','objects') else [])
            value=sql.SQL('to_jsonb(t) - {}::text[]').format(sql.Literal(ignored))
            checksum=db.execute(sql.SQL("""SELECT encode(sha256(convert_to(
              coalesce(string_agg(h,'' ORDER BY h COLLATE "C"),''),'UTF8')),'hex')
              FROM (SELECT encode(sha256(convert_to(({})::text,'UTF8')),'hex') AS h
                    FROM {} AS t) AS rows""").format(value,relation)).fetchone()[0]
            roots[schema+'.'+table]={'rows':count,'sha256':checksum,'ignored_probe_timestamps':ignored}
        sequences=db.execute("""SELECT schemaname,sequencename,last_value,start_value,
            increment_by,min_value,max_value,cache_size,cycle FROM pg_catalog.pg_sequences
            WHERE schemaname='public' ORDER BY sequencename""").fetchall()
        return {'tables':roots,'public_sequences_sha256':digest(sequences)}
    finally:db.execute('ROLLBACK')


def independent_operator_scope(rows,environment):
    """Prove the two enrolled test-identity actors cannot write the origin DB."""
    from .control_plane_upgrade_authorization import RELEASE_OPERATOR_POLICY,RELEASE_OPERATOR_KEY
    from .completed_normal_resources import measured_spec
    from .isolated_release_environment import run
    from urllib.parse import urlsplit
    facts=strict_json(protected(Path('/opt/madar-test/operator-fixture/facts.json'),private=True).read_bytes())
    operator=strict_json(protected(RELEASE_OPERATOR_POLICY,private=True).read_bytes())
    ids=facts.get('created_container_ids',[]);selected={r['Id']:r for r in rows if r['Id'] in ids}
    if (len(ids)!=2 or len(set(ids))!=2 or set(selected)!=set(ids) or facts.get('realm_id')!=environment['realm_id']
            or operator.get('environment_id')!='isolated-'+environment['realm_id']
            or operator.get('database_system_identifier')!=environment['database_system_identifier']
            or operator.get('auth_service')!=facts.get('auth_service')):
        raise RuntimeError('historical_origin_operator_scope_invalid')
    for row in selected.values():
        if (row['Config'].get('Labels',{}).get('com.madar.operator-fixture')!=environment['realm_id']
                or row['HostConfig'].get('Privileged') or row['HostConfig'].get('CapAdd')
                or row['HostConfig'].get('PortBindings')
                or {n['NetworkID'] for n in row['NetworkSettings']['Networks'].values()}!={facts['network_id']}):
            raise RuntimeError('historical_origin_operator_network_or_privilege_invalid')
    auth=selected.get(operator['auth_service']['id'])
    if not auth or auth['Image']!=operator['auth_service']['image'] or measured_spec(auth)!=operator['auth_service']['spec_sha256']:
        raise RuntimeError('historical_origin_operator_runtime_changed')
    database=next(r for r in selected.values() if r['Id']!=auth['Id'])
    database_endpoint=next(iter(database['NetworkSettings']['Networks'].values()))
    auth_endpoint=next(iter(auth['NetworkSettings']['Networks'].values()))
    database_names={database['Name'].lstrip('/'),*(database_endpoint.get('Aliases') or [])}
    config=dict(entry.split('=',1) for entry in auth['Config'].get('Env',[]) if '=' in entry)
    uri=urlsplit(config.get('GOTRUE_DB_DATABASE_URL',''))
    if (uri.scheme not in {'postgres','postgresql'} or uri.hostname not in database_names
            or uri.hostname in (auth_endpoint.get('Aliases') or [])
            or uri.port!=5432 or uri.path!='/operators' or uri.username!='supabase_auth_admin' or uri.query or uri.fragment):
        raise RuntimeError('historical_origin_operator_database_transport_changed')
    key=protected(RELEASE_OPERATOR_KEY,private=True).read_bytes()
    if hashlib.sha256(config.get('GOTRUE_JWT_SECRET','').encode()).hexdigest()!=hashlib.sha256(key).hexdigest():
        raise RuntimeError('historical_origin_operator_authentication_key_changed')
    observed=strict_json(run(['/usr/bin/docker','exec',database['Id'],'psql','-XqAt','-U','postgres','-d','operators','-c',
        """SELECT json_build_array(current_database(),system_identifier::text,
          EXISTS(SELECT 1 FROM pg_roles WHERE rolname='supabase_auth_admin'
            AND NOT rolsuper AND NOT rolbypassrls AND rolconnlimit=8)
          AND current_setting('max_connections')='16') FROM pg_control_system()"""] ))
    if (not isinstance(observed,list) or len(observed)!=3 or observed[0]!='operators' or observed[2] is not True
            or not re.fullmatch('[1-9][0-9]{0,31}',str(observed[1]))
            or observed[1] in {environment['database_system_identifier'],*environment['denied_database_identifiers']}):
        raise RuntimeError('historical_origin_operator_database_not_independent')
    return {'actor_ids':sorted(ids),'database_system_identifier':observed[1],
            'authentication_key_sha256':hashlib.sha256(key).hexdigest(),'network_id':facts['network_id']}


def boot_controls(system):
    """Measure original supervisors as DATA before any successor is admitted."""
    names=[]
    raw=system.command('historical_boot_units',['systemctl','list-unit-files','--no-legend','--no-pager',
        'madar-*.service','madar-*.timer']).stdout
    for line in raw.splitlines():
        fields=line.split()
        if not fields:continue
        if (not re.fullmatch(r'madar-[A-Za-z0-9-]+\.(service|timer)',fields[0])
                and fields[0]!='madar-ops-alert@.service'):
            raise RuntimeError('historical_origin_boot_unit_inventory_invalid')
        names.append(fields[0])
    if not 1<=len(names)<=64 or len(names)!=len(set(names)):
        raise RuntimeError('historical_origin_boot_unit_budget')
    files={};units={};templates={}
    for name in sorted(names):
        raw=system.command('historical_boot_unit',['systemctl','show',name,
            '--property=FragmentPath,DropInPaths,LoadState,ActiveState,UnitFileState']).stdout
        fields=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
        if (set(fields)!={'FragmentPath','DropInPaths','LoadState','ActiveState','UnitFileState'}
                or fields['LoadState']!='loaded' or not fields['FragmentPath']):
            raise RuntimeError('historical_origin_boot_unit_not_loaded')
        paths=[fields['FragmentPath'],*fields['DropInPaths'].split()]
        for raw_path in paths:
            path=Path(raw_path)
            if not path.is_relative_to('/etc/systemd/system') and not path.is_relative_to('/opt/madar/control-plane'):
                raise RuntimeError('historical_origin_boot_fragment_scope_invalid')
            metadata=protected(path).stat()
            files[raw_path]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'uid':metadata.st_uid,'mode':metadata.st_mode&0o7777}
        control={'fragment':fields['FragmentPath'],'dropins':fields['DropInPaths'].split(),
            'state':{'enabled':fields['UnitFileState'],'active':fields['ActiveState']}}
        if name=='madar-ops-alert@.service':
            # An uninstantiated alert template is authenticated configuration,
            # not a running supervisor that systemctl stop can address. Never
            # omit its bytes or treat arbitrary templates as reviewed actors.
            if fields['UnitFileState']!='static' or fields['ActiveState']!='inactive':
                raise RuntimeError('historical_origin_alert_template_state_invalid')
            templates[name]=control
        else:units[name]=control
    if 'madar-release-proxy.service' not in units:raise RuntimeError('historical_origin_proxy_boot_missing')
    return {'files':files,'units':units,**({'templates':templates} if templates else {})}


def policy(system):
    """Independent root inputs only; a candidate cannot select the trust root."""
    from .automatic_release_admission import execution_policy_configuration
    from .isolated_release_environment import observe
    from .exceptional_release_approval import KEY
    from .control_plane_upgrade_authorization import RELEASE_OPERATOR_KEY
    execution=execution_policy_configuration(system);environment=observe()
    p=strict_json(protected(POLICY,private=True).read_bytes())
    fields={'version','kind','environment_id','database_system_identifier','controller_sha',
            'source_sha','source_tree_sha','images','observation_sha256','approval_key_sha256',
            'successor_intent_sha256','expires_at','max_request_seconds'}
    if (not isinstance(p,dict) or set(p)!=fields or type(p['version']) is not int or p['version']!=1
            or p['kind']!=KIND or execution['environment']!='isolated-test'
            or p['environment_id']!=execution['environment_id']
            or p['environment_id']!='isolated-'+environment['realm_id']
            or environment['version']!=2
            or p['database_system_identifier']!=environment['database_system_identifier']
            or p['database_system_identifier'] in execution['denied_database_identifiers']
            or p['controller_sha']!=system.installed_sha()
            or any(not re.fullmatch('[a-f0-9]{40}',str(p[k])) for k in ('source_sha','source_tree_sha','controller_sha'))
            or any(not re.fullmatch('[a-f0-9]{64}',str(p[k])) for k in
                ('observation_sha256','approval_key_sha256','successor_intent_sha256'))
            or not isinstance(p['images'],dict) or set(p['images'])!={'backend','frontend'}
            or any(not re.fullmatch('sha256:[a-f0-9]{64}',str(v)) for v in p['images'].values())
            or type(p['expires_at']) is not int or not int(time.time())<p['expires_at']<=int(time.time())+14400
            or type(p['max_request_seconds']) is not int or not 1<=p['max_request_seconds']<=600):
        raise RuntimeError('historical_origin_independent_policy_invalid')
    key=protected(KEY,private=True).read_bytes()
    if (not 32<=len(key)<=4096 or hashlib.sha256(key).hexdigest()!=p['approval_key_sha256']
            or key==protected(RELEASE_OPERATOR_KEY,private=True).read_bytes()):
        raise RuntimeError('historical_origin_issuer_key_invalid')
    return p,key,environment


def observe(system,p,environment):
    """Measure actual original state, never accept caller-provided PASS fields.

    No SQL or application write authority is issued. The explicitly enrolled
    account probes create Auth sessions while verifying real password/MFA and
    private objects; their credentials cannot select foreign provider endpoints.
    """
    from .automatic_release_recovery import inspect_all
    from .completed_normal_resources import measured_spec
    from .completed_normal_package import snapshot
    from .automatic_release_admission import connect_database
    from .migration_inventory import discover
    from .migration_drift import observe as observe_database, history_digest
    from .runtime_authority import load_worker_authority
    from .completed_normal_private_acceptance import observe_subjects
    state=strict_json(readonly_configuration(system.state_root/'state.json',private=True).read_bytes())
    known=dict(state.get('known_good_release') or {});known.pop('historical_origin',None)
    if (state.get('in_progress_release') or state.get('rollback_failure') or known.get('schema')!=146
            or type(known.get('schema')) is not int or known.get('sha')!=p['source_sha']
            or known.get('slot') not in {'blue','green'} or state.get('active_slot')!=known['slot']
            or known.get('schema_compatible_min')!=144 or known.get('schema_compatible_max')!=146
            or 'completed_normal_upgrade' in known):
        raise RuntimeError('historical_origin_running146_required')
    bootstrap=bootstrap_record(system.state_root/'origin-bootstrap-adopted.json')
    if (bootstrap not in state.get('history',[]) or bootstrap.get('phase')!='bootstrap_adopted'
            or bootstrap.get('status')!='known_good' or bootstrap.get('release_sha')!=p['source_sha']
            or bootstrap.get('candidate_slot')!=known['slot'] or bootstrap.get('traffic_target')!=known['slot']
            or bootstrap.get('schema')!={'observed':146} or bootstrap.get('images')!=known.get('images')):
        raise RuntimeError('historical_origin_truthful_bootstrap_required')
    tree,_=snapshot(system.repo,p['source_sha'])
    if tree!=p['source_tree_sha']:raise RuntimeError('historical_origin_source_tree_changed')
    inventory=discover(system.repo,source_sha=p['source_sha'],history_base_sha=p['source_sha'])
    rows=inspect_all();by_name={r['Name'].lstrip('/'):r for r in rows}
    if len(by_name)!=len(rows):raise RuntimeError('historical_origin_actor_identity_ambiguous')
    operator_scope=independent_operator_scope(rows,environment)
    # Naming is the existing deployment contract, not an arbitrary caller list.
    for role in ROLES:
        r=by_name.get('madar-'+known['slot']+'-'+role)
        if (not r or not r['State']['Running'] or r['State'].get('Health',{}).get('Status')!='healthy'
                or (role not in {'redis'} and r['Image']!=p['images']['frontend' if role=='frontend' else 'backend'])):
            raise RuntimeError('historical_origin_eight_roles_required')
    for name in ('supabase-db','supabase-auth','supabase-rest','supabase-storage','supabase-envoy'):
        if name not in by_name or not by_name[name]['State']['Running']:
            raise RuntimeError('historical_origin_provider_missing')
    owner=load_worker_authority(system.state_root)
    if (not owner or owner.get('owner')!='CANDIDATE' or owner.get('candidate')!={'sha':p['source_sha'],'slot':known['slot']}
            or owner.get('generation')!=known.get('worker_generation') or system.current_traffic_slot()!=known['slot']):
        raise RuntimeError('historical_origin_worker_or_route_changed')
    # Existing private credentials and object probes, fixed root-owned path.
    probes=Path('/etc/madar/historical-origin-probes.json')
    raw=protected(probes,private=True).read_bytes()
    if len(raw)>65536:raise RuntimeError('historical_origin_probe_budget')
    material=strict_json(raw)
    if set(material)!={'subjects','endpoints','anon_key'}:raise RuntimeError('historical_origin_probe_shape')
    endpoints={}
    for component,port in (('auth',9999),('rest',3000),('storage',5000)):
        network=by_name['supabase-'+component]['NetworkSettings']['Networks'].get('madar-local-supabase_default')
        if not network or not network.get('IPAddress'):raise RuntimeError('historical_origin_provider_network_changed')
        endpoints[component]='http://'+network['IPAddress']+':'+str(port)
    if material['endpoints']!=endpoints:raise RuntimeError('historical_origin_probe_provider_substitution')
    accounts=observe_subjects(material['subjects'],material['endpoints'],material['anon_key'])
    with connect_database() as db:
        catalog=observe_database(db,required_protocols={})
        if catalog.schema!=146 or catalog.system_identifier!=p['database_system_identifier']:
            raise RuntimeError('historical_origin_database_changed')
        marker=db.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]
        if marker!='madar-isolated-'+environment['realm_id']:raise RuntimeError('historical_origin_database_realm_changed')
        absent=db.execute("""SELECT to_regprocedure('public.notification_delivery_protocol()') IS NULL,
            to_regprocedure('public.notification_outbox_protocol()') IS NULL,
            to_regprocedure('public.data_deletion_ownership_protocol()') IS NULL""").fetchone()
        if tuple(absent)!=(True,True,True):raise RuntimeError('historical_origin_protocol_history_changed')
        preserved=preservation_roots(db)
    for r in rows:
        name=r['Name'].lstrip('/')
        if (r['State']['Running'] and r['Id'] not in operator_scope['actor_ids'] and name.startswith('madar-') and name not in
                {'madar-'+known['slot']+'-'+role for role in ROLES}|{'madar-release-proxy'}):
            raise RuntimeError('historical_origin_unexpected_writer')
    return {'version':1,'kind':KIND,'environment_id':p['environment_id'],
        'host':{k:environment[k] for k in ('guest_uuid','machine_id','root_filesystem_uuid','realm_id')},
        'controller_sha':system.installed_sha(),'source_sha':p['source_sha'],'source_tree_sha':tree,
        'bootstrap_sha256':digest(bootstrap),'known_good':known,'worker_authority':owner,
        'runtime':{r['Name']:{'id':r['Id'],'image':r['Image'],'spec_sha256':measured_spec(r)} for r in rows},
        'runtime_scope_sha256':digest(environment['runtime_scope']),
        'boot_controls':boot_controls(system),
        'independent_operator_scope':operator_scope,
        'configuration_sha256':{
            'application':hashlib.sha256(readonly_configuration(Path('/etc/madar/production.env'),private=True).read_bytes()).hexdigest(),
            'backup':hashlib.sha256(protected(Path('/etc/madar/backup.env'),private=True).read_bytes()).hexdigest(),
            'database_transport':hashlib.sha256(protected(Path('/etc/madar/automatic-database.dsn'),private=True).read_bytes()).hexdigest()},
        'database':catalog.document(),'history_sha256':history_digest(inventory,146),
        'legacy_protocols':{'delivery':1,'outbox':1,'deletion':0,'native_successor_function_absence_verified':True},
        'original_data':preserved,
        'original_account_observations':accounts,'probe_configuration_sha256':hashlib.sha256(raw).hexdigest(),
        'protected_completion_claimed':False,'migration_authority_issued':False}


@contextmanager
def operation_locks(system):
    """Same upgrade/deployment lock inodes as the existing execution issuer."""
    from .control_plane_upgrade import acquire_lock
    from .automatic_release_admission import require_no_pending_operation
    from .schema150_provider_adapter import require_owned_lock
    upgrade=acquire_lock(system.upgrade_root/'upgrade.lock',create=False)
    try:
        deploy=acquire_lock(system.state_root/'deploy.lock',create=False)
        try:
            def guard():
                require_owned_lock(upgrade,system.upgrade_root/'upgrade.lock')
                require_owned_lock(deploy,system.state_root/'deploy.lock')
                require_no_pending_operation()
                if system.interlock_file.exists() or system.interlock_file.is_symlink():
                    raise RuntimeError('historical_origin_conflicting_operation')
            guard();yield guard
        finally:os.close(deploy)
    finally:os.close(upgrade)


def prepare(system):
    with operation_locks(system) as guard:return _prepare(system,guard)


def _prepare(system,guard):
    p,key,environment=policy(system);value=observe(system,p,environment)
    if digest(value)!=p['observation_sha256']:raise RuntimeError('historical_origin_observation_not_independently_pinned')
    request_id=str(uuid.uuid4());now=int(time.time())
    guard()
    if now>=p['expires_at']:raise RuntimeError('historical_origin_policy_expired_during_observation')
    request={'version':1,'kind':KIND,'request_id':request_id,'policy_sha256':digest(p),
        'observation':value,'created_at':now,'expires_at':min(p['expires_at'],now+p['max_request_seconds']),
        'successor_intent_sha256':p['successor_intent_sha256']}
    with journal_lock(request_id,namespace='historical-origins') as path:atomic_json(path/'bootstrap-origin-request.json',sign(request,key),exclusive=True)
    return {'request_id':request_id,'request_sha256':digest(request),'kind':KIND,
            'protected_completion_claimed':False,'migration_authority_issued':False}


def enroll(system,request_id,token,confirmation):
    with operation_locks(system) as guard:return _enroll(system,request_id,token,confirmation,guard)


def _enroll(system,request_id,token,confirmation,guard):
    p,key,environment=policy(system)
    with journal_lock(identifier(request_id),namespace='historical-origins') as path:
        request=verified(path/'bootstrap-origin-request.json',key)
        if (request.get('kind')!=KIND or request.get('request_id')!=request_id or confirmation!=digest(request)
                or request['policy_sha256']!=digest(p) or not int(time.time())<request['expires_at']
                or (path/'bootstrap-origin-consumed.json').exists()):
            raise RuntimeError('historical_origin_request_expired_changed_or_consumed')
        operator=system.authenticate_operator(token)
        observed=observe(system,p,environment)
        if observed!=request['observation'] or digest(observed)!=p['observation_sha256']:
            raise RuntimeError('historical_origin_changed_before_enrollment')
        current=system.authenticate_operator(token)
        if any(current.get(k)!=operator.get(k) for k in
                ('aal','operator_auth_id','policy_sha256','session_id_sha256','verification_key_sha256')):
            raise RuntimeError('historical_origin_operator_changed_during_observation')
        operator=current
        if int(time.time())>=request['expires_at']:raise RuntimeError('historical_origin_request_expired')
        receipt={'version':1,'kind':KIND,'request_id':request_id,'request_sha256':digest(request),
            'policy_sha256':digest(p),'operator':operator,'enrolled_at':int(time.time()),
            'expires_at':p['expires_at'],'observation_sha256':digest(observed),
            'successor_intent_sha256':p['successor_intent_sha256'],
            'protected_completion_claimed':False,'migration_authority_issued':False}
        # Atomic no-replace consumption precedes mutable linkage; an interrupted
        # issuer cannot silently reuse a request or fabricate a release completion.
        guard();atomic_json(path/'bootstrap-origin-consumed.json',sign(receipt,key),exclusive=True)
        state_path=system.state_root/'state.json';state=strict_json(readonly_configuration(state_path,private=True).read_bytes())
        known=state.get('known_good_release') or {}
        if (known!=observed['known_good'] or state.get('in_progress_release') or state.get('rollback_failure')):
            raise RuntimeError('historical_origin_state_changed_during_enrollment')
        if 'historical_origin' in known:raise RuntimeError('historical_origin_already_enrolled')
        known['historical_origin']={'request_id':request_id,'enrollment_sha256':digest(receipt)}
        metadata=state_path.stat()
        from .control_plane_upgrade import atomic_json as write_state
        guard();write_state(state_path,state,owner=(metadata.st_uid,metadata.st_gid))
        return receipt


def attest(system,state):
    """Read-only distinct origin binding; never impersonate completed evidence."""
    p,key,environment=policy(system)
    marker=(state.get('known_good_release') or {}).get('historical_origin')
    if not isinstance(marker,dict) or set(marker)!={'request_id','enrollment_sha256'}:
        raise RuntimeError('historical_origin_marker_missing')
    from .automatic_release_admission import ROOT
    path=ROOT/'historical-origins'/identifier(marker['request_id']);receipt=verified(path/'bootstrap-origin-consumed.json',key)
    request=verified(path/'bootstrap-origin-request.json',key)
    if (receipt.get('kind')!=KIND or receipt.get('request_id')!=marker['request_id']
            or digest(receipt)!=marker['enrollment_sha256'] or receipt['request_sha256']!=digest(request)
            or receipt['policy_sha256']!=digest(p) or int(time.time())>=receipt['expires_at']
            or receipt.get('protected_completion_claimed') is not False or receipt.get('migration_authority_issued') is not False
            or request['observation']!=observe(system,p,environment)):
        raise RuntimeError('historical_origin_enrollment_or_runtime_changed')
    return {'origin_kind':KIND,'enrollment_root':str(path),'enrollment_sha256':digest(receipt),
        'application_sha':p['source_sha'],'controller_sha':p['controller_sha'],'schema':146,
        'successor_intent_sha256':p['successor_intent_sha256']}


def inspect(system,request_id):
    """Display authenticated enrollment records; no token input or effects."""
    from .automatic_release_admission import ROOT
    p,key,_=policy(system)
    path=ROOT/'historical-origins'/identifier(request_id)
    request=verified(path/'bootstrap-origin-request.json',key)
    if request.get('kind')!=KIND or request.get('request_id')!=request_id or request.get('policy_sha256')!=digest(p):
        raise RuntimeError('historical_origin_request_binding_changed')
    receipt=verified(path/'bootstrap-origin-consumed.json',key) if (path/'bootstrap-origin-consumed.json').exists() else None
    return {'request':request,'request_sha256':digest(request),'enrollment':receipt,
            'state':'ENROLLED' if receipt else 'EXPIRED' if int(time.time())>=request['expires_at'] else 'AWAITING_ENROLLMENT',
            'migration_authority_issued':False}


def validate_source_binding(value):
    """Typed historical evidence reference, never a completed origin alias."""
    from .automatic_release_admission import ROOT
    if (not isinstance(value,dict) or set(value)!=SOURCE_FIELDS or value.get('origin_kind')!=KIND
            or type(value.get('schema')) is not int or value['schema']!=146
            or any(not re.fullmatch('[a-f0-9]{40}',str(value[k])) for k in ('application_sha','controller_sha'))
            or any(not re.fullmatch('[a-f0-9]{64}',str(value[k])) for k in ('enrollment_sha256','successor_intent_sha256'))):
        raise RuntimeError('historical_origin_source_binding_invalid')
    path=Path(value['enrollment_root'])
    if path.parent!=ROOT/'historical-origins' or str(path)!=value['enrollment_root']:
        raise RuntimeError('historical_origin_evidence_path_invalid')
    identifier(path.name)
    return path


def successor_intent(contract):
    """Non-circular exact C1 scope; receipt IDs are bound by the later context."""
    from .completed_normal_profile import RECONCILED
    if contract.get('operation')!=RECONCILED.operation or contract.get('version')!=RECONCILED.version:
        raise RuntimeError('historical_origin_successor_operation_invalid')
    return {'kind':'canonical146-160-successor-intent','repository':'judahsleibi34/Madar',
        'origin_source_sha':contract['source_roles']['application_sha'],
        'origin_database_system_identifier':contract['database']['system_identifier'],
        'origin_schema':146,'target_schema':160,'candidate_source_sha':contract['candidate']['source_sha'],
        'controller_sha':contract['candidate']['controller_sha'],'candidate_images':contract['candidate']['images'],
        'candidate_redis_image':contract['candidate']['redis_image'],
        'migration_manifest_sha256':contract['migration_manifest_sha256']}


def recorded_observation(binding):
    """Authenticate original DATA after writers stop; issue no live authority.

    attest() remains mandatory before using a live origin. Execution separately
    requires its own independently issued credential and technical acceptance.
    """
    from .exceptional_release_approval import KEY
    path=validate_source_binding(binding)
    p=strict_json(protected(POLICY,private=True).read_bytes());key=protected(KEY,private=True).read_bytes()
    if (p.get('kind')!=KIND or hashlib.sha256(key).hexdigest()!=p.get('approval_key_sha256')):
        raise RuntimeError('historical_origin_record_trust_changed')
    request=verified(path/'bootstrap-origin-request.json',key);receipt=verified(path/'bootstrap-origin-consumed.json',key)
    observation=request.get('observation')
    if (not isinstance(observation,dict) or observation.get('kind')!=KIND
            or request.get('kind')!=KIND or receipt.get('kind')!=KIND
            or request.get('request_id')!=path.name or receipt.get('request_id')!=path.name
            or receipt.get('request_sha256')!=digest(request) or digest(receipt)!=binding['enrollment_sha256']
            or receipt.get('policy_sha256')!=digest(p) or request.get('policy_sha256')!=digest(p)
            or receipt.get('observation_sha256')!=digest(observation) or p.get('observation_sha256')!=digest(observation)
            or p.get('source_sha')!=binding['application_sha'] or observation.get('source_sha')!=binding['application_sha']
            or p.get('controller_sha')!=binding['controller_sha'] or observation.get('controller_sha')!=binding['controller_sha']
            or p.get('successor_intent_sha256')!=binding['successor_intent_sha256']
            or receipt.get('successor_intent_sha256')!=binding['successor_intent_sha256']
            or receipt.get('protected_completion_claimed') is not False or receipt.get('migration_authority_issued') is not False):
        raise RuntimeError('historical_origin_recorded_evidence_changed')
    return observation


def bind_successor(system,state,intent,context_sha256):
    """Consume enrollment for one separately approved release context, not SQL.

    Intent is pinned before enrollment. Binding the later full context here
    avoids a circular hash between the enrollment and the release contract.
    Calling this does not replace the release's own technical admission or
    administrator authorization.
    """
    if not re.fullmatch('[a-f0-9]{64}',str(context_sha256)):
        raise RuntimeError('historical_origin_successor_context_invalid')
    with operation_locks(system) as guard:
        origin=attest(system,state);p,key,_=policy(system)
        if digest(intent)!=origin['successor_intent_sha256']:
            raise RuntimeError('historical_origin_successor_intent_changed')
        request_id=(state['known_good_release']['historical_origin'])['request_id']
        with journal_lock(request_id,namespace='historical-origins') as path:
            if (path/'bootstrap-origin-release-use.json').exists():
                raise RuntimeError('historical_origin_successor_already_bound')
            receipt={'kind':'historical-origin-single-successor-binding','origin':origin,
                'context_sha256':context_sha256,'intent_sha256':digest(intent),'bound_at':int(time.time()),
                'migration_authority_issued':False}
            guard();atomic_json(path/'bootstrap-origin-release-use.json',sign(receipt,key),exclusive=True)
        return receipt


def original_runtime(contract):
    """Authenticated historical actors, without a completed-runtime alias."""
    from .completed_normal_admission import validate_provider_preparation
    validate_provider_preparation(contract)
    binding=contract['source_roles'];validate_source_binding(binding)
    observed=recorded_observation(binding);origin=contract['origin']
    if (digest(successor_intent(contract))!=binding['successor_intent_sha256']
            or observed['database']['system_identifier']!=contract['database']['system_identifier']
            or observed['database']['schema']!=146 or observed['known_good']['slot']!=origin['slot']
            or observed['worker_authority']['generation']!=origin['worker_generation']
            or origin['write_contract_digest']!=binding['enrollment_sha256']):
        raise RuntimeError('historical_origin_operation_scope_changed')
    runtimes={role:observed['runtime']['/madar-'+origin['slot']+'-'+role] for role in ROLES}
    images={role:runtimes[role]['image'] for role in ('backend','frontend')}
    if images!=origin['images']:raise RuntimeError('historical_origin_images_changed')
    return {'origin_kind':KIND,'source_sha':binding['application_sha'],'images':images,
            'worker_generation':origin['worker_generation'],'runtimes':runtimes}


def history_witness(contract):
    """Nonsecret projection issued only by the existing root credential path."""
    return {'source_roles':contract['source_roles'],'origin':contract['origin'],
            'database':contract['database'],'historical_files':contract['historical_files'],
            'original_runtime':original_runtime(contract)}


def validate_history_witness(contract,value):
    from .completed_normal_admission import validate_provider_preparation
    validate_provider_preparation(contract)
    if (not isinstance(value,dict) or set(value)!={'source_roles','origin','database','historical_files','original_runtime'}
            or any(value[k]!=contract[k] for k in ('source_roles','origin','database','historical_files'))):
        raise RuntimeError('historical_origin_child_history_changed')
    runtime=value['original_runtime']
    if (not isinstance(runtime,dict) or set(runtime)!={'origin_kind','source_sha','images','worker_generation','runtimes'}
            or runtime['origin_kind']!=KIND or runtime['source_sha']!=contract['source_roles']['application_sha']
            or runtime['images']!=contract['origin']['images'] or runtime['worker_generation']!=contract['origin']['worker_generation']
            or set(runtime.get('runtimes',{}))!=set(ROLES)):
        raise RuntimeError('historical_origin_child_runtime_changed')
    for row in runtime['runtimes'].values():
        if (not isinstance(row,dict) or set(row)!={'id','image','spec_sha256'}
                or not re.fullmatch('[a-f0-9]{64}',str(row['id']))
                or not re.fullmatch('sha256:[a-f0-9]{64}',str(row['image']))
                or not re.fullmatch('[a-f0-9]{64}',str(row['spec_sha256']))):
            raise RuntimeError('historical_origin_child_actor_invalid')
    if len({r['id'] for r in runtime['runtimes'].values()})!=len(ROLES):
        raise RuntimeError('historical_origin_child_actor_ambiguous')
    return runtime


def stopped_originals(contract,runtime,original):
    """Native evidence that legacy writers cannot use their old credentials."""
    from .completed_normal_resources import measured_spec_matches
    rows=runtime.inspect([r['id'] for r in original['runtimes'].values()])
    actual={r['Id']:r for r in rows.values()}
    if set(actual)!={r['id'] for r in original['runtimes'].values()}:
        raise RuntimeError('historical_origin_fence_actor_missing')
    for role,identity in original['runtimes'].items():
        row=actual[identity['id']]
        environment=dict(e.split('=',1) for e in row['Config'].get('Env',[]) if '=' in e)
        if (row['Image']!=identity['image'] or row['State']['Running'] or row['State'].get('Restarting')
                or row['HostConfig']['RestartPolicy']['Name']!='no'
                or not measured_spec_matches(row,identity['spec_sha256'],started_worker=role.endswith('-worker'))
                or any(environment.get(k) for k in ('MADAR_BUSINESS_WRITE_AUTHORITY','MADAR_BUSINESS_WRITE_CONTRACT'))
                or any(m['Destination']=='/run/madar' or m['Destination'].startswith('/run/madar/business-write-authority')
                       for m in row.get('Mounts',[]))):
            raise RuntimeError('historical_origin_writer_not_fenced')


def validate_fence(contract,original,record):
    from .completed_normal_admission import digest as context_digest
    fields={'version','kind','operation','context_sha256','enrollment_sha256','original_runtime_sha256',
            'original_actor_ids','database_system_identifier','source_schema','provider_journal_count',
            'provider_journal_sha256','legacy_write_grant_existed'}
    if (not isinstance(record,dict) or set(record)!=fields or type(record['version']) is not int or record['version']!=1
            or record['kind']!='historical-origin-provider-fence' or record['operation']!=contract['operation']
            or record['context_sha256']!=context_digest(contract)
            or record['enrollment_sha256']!=contract['source_roles']['enrollment_sha256']
            or record['original_runtime_sha256']!=context_digest(original)
            or record['original_actor_ids']!={k:r['id'] for k,r in original['runtimes'].items()}
            or record['database_system_identifier']!=contract['database']['system_identifier']
            or type(record['source_schema']) is not int or record['source_schema']!=146
            or record['legacy_write_grant_existed'] is not False
            or type(record['provider_journal_count']) is not int or not 1<=record['provider_journal_count']<=4096
            or not re.fullmatch('[a-f0-9]{64}',str(record['provider_journal_sha256']))):
        raise RuntimeError('historical_origin_fence_record_changed')
    return record


def seal_fence(contract,provider):
    """Record the EXISTING provider lifecycle's completed native fence.

    No grant is created or downgraded. The coordinator must first fence ingress,
    actors, roles and sessions through the concrete provider adapter.
    """
    from .completed_normal_admission import digest as context_digest,encoded
    from .schema150_provider_adapter import Schema150ProviderAdapter
    from .schema150_provider_lifecycle import ProviderMaintenance150,ProtectedProviderJournal,FENCE_STEPS
    from .emergency_routing_repair import exclusive
    if type(provider) is not Schema150ProviderAdapter or provider.contract!=contract:
        raise RuntimeError('historical_origin_concrete_provider_required')
    provider.require_authority(provider.binding,purpose='observe_quiescence')
    lifecycle=ProviderMaintenance150(provider.binding,ProtectedProviderJournal(provider.root/'provider-journal'),provider)
    with lifecycle._locked():
        rows,completed,pending,ready=lifecycle._state()
        if pending or ready or completed!=list(FENCE_STEPS):raise RuntimeError('historical_origin_provider_fence_incomplete')
        quiescence=provider.observe_quiescence(provider.binding)
        if quiescence['schema']!=146:raise RuntimeError('historical_origin_fence_source_changed')
        original=original_runtime(contract);stopped_originals(contract,provider.runtime,original)
        value={'version':1,'kind':'historical-origin-provider-fence','operation':contract['operation'],
            'context_sha256':context_digest(contract),'enrollment_sha256':contract['source_roles']['enrollment_sha256'],
            'original_runtime_sha256':context_digest(original),
            'original_actor_ids':{k:r['id'] for k,r in original['runtimes'].items()},
            'database_system_identifier':contract['database']['system_identifier'],'source_schema':146,
            'provider_journal_count':len(rows),'provider_journal_sha256':context_digest(rows),
            'legacy_write_grant_existed':False}
        validate_fence(contract,original,value)
        exclusive(provider.root/'historical-origin-fence.json',encoded(value))
        return value


def require_fence(contract,runtime,root):
    from .completed_normal_admission import digest as context_digest
    from .schema150_provider_lifecycle import ProtectedProviderJournal
    original=original_runtime(contract)
    value=validate_fence(contract,original,strict_json(protected(Path(root)/'historical-origin-fence.json',private=True).read_bytes()))
    rows=ProtectedProviderJournal(Path(root)/'provider-journal').read()
    if len(rows)<value['provider_journal_count'] or context_digest(rows[:value['provider_journal_count']])!=value['provider_journal_sha256']:
        raise RuntimeError('historical_origin_fence_journal_changed')
    stopped_originals(contract,runtime,original)
    return value


def verify_actor_inventory(contract,inventory,rows):
    """Authenticate v2 historical topology against the enrolled ALL-daemon view.

    Absent modern slots are not invented. The only exclusions are the separately
    authenticated operator provider/database pair; ordinary unrelated-container
    exclusion machinery is deliberately not enabled by this adapter.
    """
    from .schema150_provider_lifecycle import digest as inventory_digest
    source=contract['source_roles'];observed=recorded_observation(source)
    if inventory.get('version')!=2 or inventory.get('historical_origin')!=source:
        raise RuntimeError('historical_origin_inventory_enrollment_changed')
    actors=inventory['containers'];excluded=inventory['exclusions']
    all_original=observed['runtime'];by_id={v['id']:(name,v) for name,v in all_original.items()}
    if len(by_id)!=len(all_original) or {a['id'] for a in actors.values()}|set(excluded)!=set(by_id):
        raise RuntimeError('historical_origin_inventory_actor_universe_changed')
    expected=original_runtime(contract)
    for role,value in expected['runtimes'].items():
        if any(actors.get('origin:'+role,{}).get(k)!=v for k,v in value.items()):
            raise RuntimeError('historical_origin_inventory_original_changed')
    for actor in actors.values():
        name,pinned=by_id[actor['id']]
        if (name!='/'+actor['name'] or any(actor.get(k)!=v for k,v in pinned.items())):
            raise RuntimeError('historical_origin_inventory_actor_changed')
    scope=observed['independent_operator_scope']
    from .isolated_release_environment import observe_host,observe_effect_fence
    environment=observe_host()
    observe_effect_fence(execution=True)
    if (environment['version']!=2 or observed['environment_id']!='isolated-'+environment['realm_id']
            or observed['database']['system_identifier']!=environment['database_system_identifier']
            or observed['host']!={k:environment[k] for k in ('guest_uuid','machine_id','root_filesystem_uuid','realm_id')}):
        raise RuntimeError('historical_origin_inventory_host_changed')
    if (set(excluded)!=set(scope['actor_ids']) or independent_operator_scope(rows,environment)!=scope):
        raise RuntimeError('historical_origin_inventory_operator_changed')
    for identifier,exclusion in excluded.items():
        pinned=by_id[identifier][1]
        if exclusion!={'image':pinned['image'],'spec_sha256':pinned['spec_sha256'],'proof_sha256':inventory_digest(scope)}:
            raise RuntimeError('historical_origin_inventory_exclusion_changed')
    controls=observed['boot_controls']
    for name,template in controls.get('templates',{}).items():
        if name!='madar-ops-alert@.service' or template['state']!={'enabled':'static','active':'inactive'}:
            raise RuntimeError('historical_origin_alert_template_changed')
        for path in (template['fragment'],*template['dropins']):
            record=controls['files'][path];actual=protected(Path(path));metadata=actual.stat()
            if (metadata.st_uid!=record['uid'] or metadata.st_mode&0o7777!=record['mode']
                    or hashlib.sha256(actual.read_bytes()).hexdigest()!=record['sha256']):
                raise RuntimeError('historical_origin_alert_template_changed')
    if set(inventory['supervisors'])!=set(controls['units']):
        raise RuntimeError('historical_origin_inventory_supervisor_universe_changed')
    for name,unit in controls['units'].items():
        actor=inventory['supervisors'][name]
        if (actor['fragment_sha256']!=controls['files'][unit['fragment']]['sha256']
                or actor['dropins_sha256']!=inventory_digest({p:controls['files'][p]['sha256'] for p in unit['dropins']})
                or actor['enabled']!=unit['state']['enabled'] or actor['context_sha256'] is not None):
            raise RuntimeError('historical_origin_inventory_supervisor_preimage_changed')
    return scope


def supervisor_controls(contract,name,root):
    """Expected boot supersession DATA after the existing installer completes.

    The adapter's mandatory source_guard first verifies the installed resources
    against the immutable package. This projection additionally preserves the
    signed origin preimage; it cannot excuse arbitrary or missing drop-ins.
    """
    from .completed_normal_admission import digest as context_digest
    from .completed_normal_boot_installation import UNITS,PROXY
    controls=recorded_observation(contract['source_roles'])['boot_controls']
    if name not in controls['units']:raise RuntimeError('historical_origin_supervisor_not_enrolled')
    unit=controls['units'][name]
    original={p:controls['files'][p]['sha256'] for p in unit['dropins']}
    installation=strict_json(protected(Path(root)/'boot-installation.json',private=True).read_bytes())
    if (installation.get('operation')!=contract['operation']
            or installation.get('context_sha256')!=context_digest(contract)
            or installation.get('historical_units_deleted') is not False):
        raise RuntimeError('historical_origin_boot_installation_changed')
    original_paths=set(original)
    for path,checksum in installation['superseded_proxy_dropins'].items():
        if name==PROXY:
            if path not in original_paths:raise RuntimeError('historical_origin_boot_replacement_not_enrolled')
            preimage=Path(root)/'proxy-originals'/Path(path).name
            if hashlib.sha256(protected(preimage,private=True).read_bytes()).hexdigest()!=original[path]:
                raise RuntimeError('historical_origin_boot_replacement_preimage_changed')
            original[path]=checksum
    for path,checksum in installation['resources'].items():
        destination=Path(path)
        if destination.parent==UNITS/(name+'.d'):
            if path in original:raise RuntimeError('historical_origin_boot_addition_overwrites_original')
            original[path]=checksum
    for path,checksum in original.items():
        if hashlib.sha256(protected(Path(path)).read_bytes()).hexdigest()!=checksum:
            raise RuntimeError('historical_origin_supervisor_controls_changed')
    return original,'disabled' if name in installation['superseded_units'] else unit['state']['enabled']


def native_database_endpoint(contract,row):
    """Resolve the enrolled native bridge, never the loopback control bridge.

    A root SQL lease uses this observer only after ordinary identity/credential
    checks. It neither opens a connection nor issues migration permission.
    """
    from .completed_normal_resources import measured_spec_matches
    from .schema150_actor_inventory import DEFAULT_NETWORK
    from .isolated_release_environment import observe_host,observe_effect_fence
    observed=recorded_observation(contract['source_roles']);environment=observe_host()
    observe_effect_fence(execution=True)
    expected=observed['runtime'].get('/supabase-db',{})
    if (observed['host']!={k:environment[k] for k in ('guest_uuid','machine_id','root_filesystem_uuid','realm_id')}
            or environment['database_container_id']!=contract['database']['container_id']
            or environment['database_system_identifier']!=contract['database']['system_identifier']
            or observed['database']['system_identifier']!=environment['database_system_identifier']
            or row.get('Id')!=expected.get('id') or row.get('Id')!=contract['database']['container_id']
            or row.get('Name')!='/supabase-db' or row.get('Image')!=expected.get('image')
            or row.get('Image')!=contract['database']['image'] or not row.get('State',{}).get('Running')
            or row['State'].get('Restarting') or not measured_spec_matches(row,expected.get('spec_sha256'))):
        raise RuntimeError('historical_origin_database_transport_changed')
    host=row['HostConfig'];networks=row['NetworkSettings']['Networks']
    enrolled=environment['runtime_scope'].get(row['Id'],{})
    from .completed_normal_admission import ADMISSIONS,digest as context_digest
    from .schema150_actor_inventory import validate_inventory
    from .completed_normal_profile import RECONCILED
    binding={'operation':RECONCILED.operation,'context_sha256':context_digest(contract),
        'source_sha':contract['candidate']['source_sha'],'controller_sha':contract['candidate']['controller_sha'],
        'inventory_sha256':contract['writer_inventory_sha256'],'system_identifier':contract['database']['system_identifier'],
        'source_schema':146,'target_schema':160}
    inventory=validate_inventory(strict_json(protected(ADMISSIONS/context_digest(contract)/'provider-inventory.json',private=True).read_bytes()),binding)
    native=inventory['containers']['native:db']
    if (inventory.get('historical_origin')!=contract['source_roles'] or native['id']!=row['Id']
            or set(networks)!=set(native['networks'])
            or any(v.get('NetworkID')!=native['networks'][k] for k,v in networks.items())):
        raise RuntimeError('historical_origin_database_transport_changed')
    # The full original row was independently enrolled; do not let a new port,
    # host network, or Docker DNS override become an alternate maintenance path.
    if (enrolled.get('spec_sha256')!=expected['spec_sha256']
            or host.get('NetworkMode') in ('host','none') or host.get('ExtraHosts') or host.get('Dns')
            or host.get('DnsSearch') or host.get('DnsOptions') or host.get('PublishAllPorts')
            or any(b.get('HostIp')!='127.0.0.1' for ports in (host.get('PortBindings') or {}).values() for b in ports)
            or DEFAULT_NETWORK not in networks or not networks[DEFAULT_NETWORK].get('NetworkID')):
        raise RuntimeError('historical_origin_database_transport_changed')
    return networks[DEFAULT_NETWORK]
