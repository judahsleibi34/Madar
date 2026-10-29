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
ROLES=('backend','frontend','redis','parser-worker','remote-ingestion-worker',
       'notification-worker','calendar-sync-worker','data-deletion-worker')


def preservation_roots(db):
    """Bounded native READ ONLY snapshot; customer values never leave as text.

    Auth challenge/access timestamps legitimately change during these probes;
    identities, password/MFA material, memberships and all public business rows
    remain fingerprinted. This is not a claim to freeze changing live sessions.
    """
    from psycopg import sql
    roots={};deadline=time.monotonic()+45
    if not db.autocommit:raise RuntimeError('historical_origin_readonly_connection_required')
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
    bootstrap=strict_json(protected(system.state_root/'origin-bootstrap-adopted.json',private=True).read_bytes())
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
        preserved=preservation_roots(db)
    for r in rows:
        name=r['Name'].lstrip('/')
        if (r['State']['Running'] and name.startswith('madar-') and name not in
                {'madar-'+known['slot']+'-'+role for role in ROLES}|{'madar-release-proxy'}):
            raise RuntimeError('historical_origin_unexpected_writer')
    return {'version':1,'kind':KIND,'environment_id':p['environment_id'],
        'host':{k:environment[k] for k in ('guest_uuid','machine_id','root_filesystem_uuid','realm_id')},
        'controller_sha':system.installed_sha(),'source_sha':p['source_sha'],'source_tree_sha':tree,
        'bootstrap_sha256':digest(bootstrap),'known_good':known,'worker_authority':owner,
        'runtime':{r['Name']:{'id':r['Id'],'image':r['Image'],'spec_sha256':measured_spec(r)} for r in rows},
        'runtime_scope_sha256':digest(environment['runtime_scope']),
        'configuration_sha256':{
            'application':hashlib.sha256(readonly_configuration(Path('/etc/madar/production.env'),private=True).read_bytes()).hexdigest(),
            'backup':hashlib.sha256(protected(Path('/etc/madar/backup.env'),private=True).read_bytes()).hexdigest(),
            'database_transport':hashlib.sha256(protected(Path('/etc/madar/automatic-database.dsn'),private=True).read_bytes()).hexdigest()},
        'database':catalog.document(),'history_sha256':history_digest(inventory,146),
        'original_data':preserved,
        'original_account_observations':accounts,'probe_configuration_sha256':hashlib.sha256(raw).hexdigest(),
        'protected_completion_claimed':False,'migration_authority_issued':False}


@contextmanager
def operation_locks(system):
    """Same upgrade/deployment lock inodes as the existing execution issuer."""
    from .control_plane_upgrade import acquire_lock
    from .automatic_release_admission import require_no_pending_operation
    upgrade=acquire_lock(system.upgrade_root/'upgrade.lock',create=False)
    try:
        deploy=acquire_lock(system.state_root/'deploy.lock',create=False)
        try:
            require_no_pending_operation()
            if system.interlock_file.exists() or system.interlock_file.is_symlink():
                raise RuntimeError('historical_origin_conflicting_operation')
            yield
        finally:os.close(deploy)
    finally:os.close(upgrade)


def prepare(system):
    with operation_locks(system):return _prepare(system)


def _prepare(system):
    p,key,environment=policy(system);value=observe(system,p,environment)
    if digest(value)!=p['observation_sha256']:raise RuntimeError('historical_origin_observation_not_independently_pinned')
    request_id=str(uuid.uuid4());now=int(time.time())
    request={'version':1,'kind':KIND,'request_id':request_id,'policy_sha256':digest(p),
        'observation':value,'created_at':now,'expires_at':min(p['expires_at'],now+p['max_request_seconds']),
        'successor_intent_sha256':p['successor_intent_sha256']}
    with journal_lock(request_id,namespace='historical-origins') as path:atomic_json(path/'bootstrap-origin-request.json',sign(request,key),exclusive=True)
    return {'request_id':request_id,'request_sha256':digest(request),'kind':KIND,
            'protected_completion_claimed':False,'migration_authority_issued':False}


def enroll(system,request_id,token,confirmation):
    with operation_locks(system):return _enroll(system,request_id,token,confirmation)


def _enroll(system,request_id,token,confirmation):
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
        if int(time.time())>=request['expires_at']:raise RuntimeError('historical_origin_request_expired')
        receipt={'version':1,'kind':KIND,'request_id':request_id,'request_sha256':digest(request),
            'policy_sha256':digest(p),'operator':operator,'enrolled_at':int(time.time()),
            'expires_at':p['expires_at'],'observation_sha256':digest(observed),
            'successor_intent_sha256':p['successor_intent_sha256'],
            'protected_completion_claimed':False,'migration_authority_issued':False}
        # Atomic no-replace consumption precedes mutable linkage; an interrupted
        # issuer cannot silently reuse a request or fabricate a release completion.
        atomic_json(path/'bootstrap-origin-consumed.json',sign(receipt,key),exclusive=True)
        state_path=system.state_root/'state.json';state=strict_json(readonly_configuration(state_path,private=True).read_bytes())
        known=state.get('known_good_release') or {}
        if (known!=observed['known_good'] or state.get('in_progress_release') or state.get('rollback_failure')):
            raise RuntimeError('historical_origin_state_changed_during_enrollment')
        if 'historical_origin' in known:raise RuntimeError('historical_origin_already_enrolled')
        known['historical_origin']={'request_id':request_id,'enrollment_sha256':digest(receipt)}
        metadata=state_path.stat()
        from .control_plane_upgrade import atomic_json as write_state
        write_state(state_path,state,owner=(metadata.st_uid,metadata.st_gid))
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


def bind_successor(system,state,intent,context_sha256):
    """Consume enrollment for one separately approved release context, not SQL.

    Intent is pinned before enrollment. Binding the later full context here
    avoids a circular hash between the enrollment and the release contract.
    Calling this does not replace the release's own technical admission or
    administrator authorization.
    """
    if not re.fullmatch('[a-f0-9]{64}',str(context_sha256)):
        raise RuntimeError('historical_origin_successor_context_invalid')
    with operation_locks(system):
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
            atomic_json(path/'bootstrap-origin-release-use.json',sign(receipt,key),exclusive=True)
        return receipt
