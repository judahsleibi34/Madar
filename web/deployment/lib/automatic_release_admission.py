"""Exact routine-release admission for the existing root issuer and deployer.

An assessment is NOT authority. Only a root-sealed, reobserved admission can be
projected by SystemOperations.write_authorization through the existing credential
boundary. This module creates no SQL executor, service or authorization token.
"""
from __future__ import annotations
import hashlib,json,os,re,time,uuid
from pathlib import Path
from .migration_inventory import canonical,digest,strict_json
from .provider_recovery_runtime import protected

OPERATION='policy-governed-automatic-release'
ROOT=Path('/var/lib/madar-control-plane/upgrades/automatic-admissions')
FIELDS={'version','operation','operation_id','attempt_id','environment','source_sha','controller_sha',
        'plan','policy_sha256','database','origin','candidate','evidence','created_at','expires_at'}
GATES={'source','ci','artifacts','staging','compatibility','recovery','resources'}


def image_identities(images):
    """Separate existing build-reuse receipt metadata from immutable identity."""
    fields={'backend','frontend','worker','build_timestamp'}
    if (not isinstance(images,dict) or not fields<=set(images)
            or set(images)-fields-{'artifact_reused'}
            or 'artifact_reused' in images and type(images['artifact_reused']) is not bool):
        raise RuntimeError('automatic_origin_image_receipt_invalid')
    return {key:images[key] for key in fields}


def validate(value,*,now=None):
    now=int(time.time()) if now is None else now
    if (not isinstance(value,dict) or set(value)!=FIELDS or type(value['version']) is not int or value['version']!=1
            or value['operation']!=OPERATION or value['environment'] not in {'isolated-test','production'}
            or any(not re.fullmatch('[a-f0-9]{40}',str(value[k])) for k in ('source_sha','controller_sha'))
            or any(not re.fullmatch('[a-f0-9]{64}',str(value[k])) for k in ('policy_sha256',))
            or any(type(value[k]) is not int for k in ('created_at','expires_at'))
            or not value['created_at']<=now<value['expires_at']<=value['created_at']+900):
        raise RuntimeError('automatic_admission_binding_invalid_or_expired')
    try:
        if str(uuid.UUID(value['attempt_id']))!=value['attempt_id']:raise ValueError()
    except (ValueError,TypeError,AttributeError):raise RuntimeError('automatic_admission_attempt_invalid') from None
    plan=value['plan']
    if (not isinstance(plan,dict) or plan.get('source_sha')!=value['source_sha']
            or plan.get('repository')!='judahsleibi34/Madar' or plan.get('operation_id')!=value['operation_id']
            or plan.get('risk_class') not in {'A','B'} or plan.get('execution_class')!='transactional'
            or plan.get('compatibility_covers_path') is not True or plan.get('protected_control_plane_changed') is not False
            or not isinstance(value['database'],dict) or set(value['database'])!={'system_identifier','origin_schema','target_schema','structure_sha256'}
            or not re.fullmatch('[1-9][0-9]{0,31}',str(value['database']['system_identifier']))
            or not re.fullmatch('[a-f0-9]{64}',str(value['database']['structure_sha256']))
            or type(value['database']['origin_schema']) is not int or type(value['database']['target_schema']) is not int
            or (value['database']['origin_schema'],value['database']['target_schema'])!=(plan.get('origin_schema'),plan.get('target_schema'))):
        raise RuntimeError('automatic_admission_plan_or_database_invalid')
    for key in ('origin','candidate'):
        row=value[key]
        if (not isinstance(row,dict) or set(row)!={'source_sha','slot','images','compatible_min','compatible_max','configuration_sha256'}
                or not re.fullmatch('[a-f0-9]{40}',str(row['source_sha'])) or row['slot'] not in {'blue','green'}
                or any(type(row[k]) is not int for k in ('compatible_min','compatible_max'))
                or not row['compatible_min']<=plan['origin_schema']<=plan['target_schema']<=row['compatible_max']
                or not re.fullmatch('[a-f0-9]{64}',str(row['configuration_sha256']))
                or not isinstance(row['images'],dict) or set(row['images'])!={'backend','frontend','worker','build_timestamp'}
                or any(not re.fullmatch('.+@sha256:[a-f0-9]{64}',str(row['images'][role])) for role in ('backend','frontend','worker'))):
            raise RuntimeError('automatic_admission_runtime_invalid')
    if value['candidate']['slot']==value['origin']['slot'] or value['candidate']['source_sha']!=value['source_sha']:
        raise RuntimeError('automatic_admission_slot_or_source_invalid')
    evidence=value['evidence']
    if (not isinstance(evidence,dict) or set(evidence)!=(GATES|({'migration'} if plan.get('migrations') else set()))
            or any(not re.fullmatch('[a-f0-9]{64}',str(v)) for v in evidence.values())):
        raise RuntimeError('automatic_admission_independent_evidence_required')
    return value


def directory(value):
    validate(value,now=value.get('created_at'))
    return ROOT/digest(value)


def sealed(value,*,allow_expired=False):
    """Read only a fixed root-frozen admission; this is not a caller PASS gate."""
    validate(value,now=value.get('created_at') if allow_expired else None)
    path=protected(directory(value)/'admission.json',private=True)
    body=path.read_bytes()
    if path.stat().st_mode&0o200 or body!=canonical(value):
        raise RuntimeError('automatic_admission_sealed_bytes_changed')
    return value


def credential(sha):
    """The existing root issuer, interlock and private credential are mandatory."""
    from .completed_normal_admission import credential_witness
    from .control_plane_upgrade_authorization import require_upgrade_authorization
    value=credential_witness('automatic_release_admission','automatic_release_admission_sha256')
    validate(value)
    if value['source_sha']!=sha:raise RuntimeError('automatic_admission_source_substitution')
    require_upgrade_authorization(sha,required_operation=OPERATION,
        required_schema=value['database']['origin_schema'],required_context_digest=digest(value))
    return value


def require_issue(value,operations):
    """Revalidate independently under both existing locks before token issuance.

    The concrete SystemOperations observer owns artifact/CI/staging/live checks;
    callers cannot replace them with an admission document or PASS booleans.
    """
    from .schema150_provider_adapter import require_owned_lock
    if os.geteuid()!=0:raise RuntimeError('automatic_admission_root_issuer_required')
    sealed(value)
    require_owned_lock(operations.automatic_upgrade_lock,operations.upgrade_root/'upgrade.lock')
    require_owned_lock(operations.deploy_lock_descriptor,operations.state_root/'deploy.lock')
    observed=operations.reobserve_automatic_admission(value)
    if observed!=value:raise RuntimeError('automatic_admission_observations_changed')
    if value['plan'].get('migrations'):
        from .automatic_release_migration import prepared
        prepared(value,operations)
    # Production remains closed until the complete original cutover and its
    # resulting compatible origin can be independently attested. Test scope
    # cannot be promoted into production simply by changing its environment.
    if value['environment']=='isolated-test':
        from .isolated_release_environment import observe
        env=observe()
        if env['version']!=2 or env['database_system_identifier']!=value['database']['system_identifier']:
            raise RuntimeError('automatic_admission_test_environment_changed')
    else:
        from .completed_normal_baseline import attest_compatible_runtime
        state=strict_json(operations.state_root.joinpath('state.json').read_bytes())
        origin=attest_compatible_runtime(operations,state,operations.repository_head(),operations.installed_sha())
        if origin['application_sha']!=value['origin']['source_sha'] or origin['schema']!=value['database']['origin_schema']:
            raise RuntimeError('automatic_admission_production_origin_changed')
    return value

EXECUTION_POLICY=Path('/etc/madar/automatic-execution.json')
TEST_PUBLIC_KEY=Path('/etc/madar/automatic-test-evidence.pub')
EVIDENCE=Path('/var/lib/madar-control-plane/automatic-evidence')
DATABASE_DSN=Path('/etc/madar/automatic-database.dsn')


def execution_policy(operations):
    """Fixed independent operational input; no repo/CLI policy override."""
    if os.geteuid()!=0:raise RuntimeError('automatic_policy_root_reader_required')
    body=protected(EXECUTION_POLICY,private=True).read_bytes()
    if not 0<len(body)<=32768:raise RuntimeError('automatic_policy_size')
    p=strict_json(body)
    fields={'version','enabled','environment','environment_id','controller_sha','controller_tree_sha256',
        'test_public_key_sha256','test_runner_sha256','test_commands_sha256','evidence_max_age_seconds','operation_max_seconds','recovery_max_age_seconds','denied_database_identifiers'}
    if (not isinstance(p,dict) or set(p)!=fields or type(p['version']) is not int or p['version']!=1
            or p['enabled'] is not True or p['environment']!='isolated-test'
            or p['controller_sha']!=operations.installed_sha()
            or not re.fullmatch('[a-f0-9]{40}',str(p['controller_sha']))
            or not re.fullmatch('[a-f0-9]{64}',str(p['controller_tree_sha256']))
            or any(not re.fullmatch('[a-f0-9]{64}',str(p[k])) for k in ('test_public_key_sha256','test_runner_sha256','test_commands_sha256'))
            or any(type(p[k]) is not int or not 0<p[k]<=limit for k,limit in
                (('evidence_max_age_seconds',600),('operation_max_seconds',900),('recovery_max_age_seconds',86400)))
            or not isinstance(p['denied_database_identifiers'],list) or not 1<=len(p['denied_database_identifiers'])<=64
            or any(not isinstance(v,str) or not re.fullmatch('[1-9][0-9]{0,31}',v) for v in p['denied_database_identifiers'])):
        raise RuntimeError('automatic_policy_not_enabled_for_accepted_environment')
    from .active_recovery_inputs import controller_tree_digest
    if controller_tree_digest()!=p['controller_tree_sha256']:
        raise RuntimeError('automatic_installed_controller_bytes_changed')
    from .isolated_release_environment import observe
    environment=observe()
    if (environment['version']!=2 or p['environment_id']!='isolated-'+environment['realm_id']
            or environment['database_system_identifier'] in p['denied_database_identifiers']):
        raise RuntimeError('automatic_policy_environment_or_database_refused')
    return p,environment


def independent_evidence(source,policy,*,now=None):
    """Authenticate the independent TEST runner, never a candidate PASS file.

    Production does not accept this evidence kind/key. The private signing key
    stays outside the guest/application. Scope includes actual executed CI and
    staging observations, source tree, image IDs and recovery inputs. Execution
    also reobserves live state; signed stale receipts do not authorize drift.
    """
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    now=int(time.time()) if now is None else now
    if not re.fullmatch('[a-f0-9]{40}',str(source)):raise RuntimeError('automatic_evidence_source_invalid')
    raw=protected(EVIDENCE/(source+'.json'),private=True).read_bytes()
    key=protected(TEST_PUBLIC_KEY,private=True).read_bytes()
    if not 0<len(raw)<=2*1024**2 or len(key)!=32 or hashlib.sha256(key).hexdigest()!=policy['test_public_key_sha256']:
        raise RuntimeError('automatic_evidence_key_or_size_invalid')
    packet=strict_json(raw)
    if not isinstance(packet,dict) or set(packet)!={'payload','signature'}:raise RuntimeError('automatic_evidence_envelope_invalid')
    try:Ed25519PublicKey.from_public_bytes(key).verify(base64.b64decode(packet['signature'],validate=True),canonical(packet['payload']))
    except Exception:raise RuntimeError('automatic_independent_evidence_signature_invalid') from None
    value=packet['payload']
    fields={'version','kind','environment_id','source_sha','history_base_sha','tree_sha','images','candidate_configuration_sha256',
        'origin_configuration_sha256','attempt_id','observed_at','expires_at','gates'}
    if (not isinstance(value,dict) or type(value.get('version')) is not int or value['version'] not in {1,2}
            or set(value)!=fields|({'migration'} if value['version']==2 else set())
            or value['kind']!='isolated-parent-executed-acceptance'
            or policy['environment']!='isolated-test' or value['environment_id']!=policy['environment_id']
            or value['source_sha']!=source or any(not re.fullmatch('[a-f0-9]{40}',str(value[k])) for k in ('history_base_sha','tree_sha'))
            or any(type(value[k]) is not int for k in ('observed_at','expires_at'))
            or not 0<=now-value['observed_at']<=policy['evidence_max_age_seconds'] or value['expires_at']<=now
            or value['expires_at']-value['observed_at']>policy['evidence_max_age_seconds']
            or not isinstance(value['gates'],dict) or set(value['gates'])!=GATES):
        raise RuntimeError('automatic_independent_evidence_scope_or_freshness')
    # The independent runner records executed process outcomes and runtime
    # identity, rather than accepting assertions written by the candidate.
    ci=value['gates']['ci'];stage=value['gates']['staging'];compat=value['gates']['compatibility']
    if (not isinstance(ci,dict) or set(ci)!={'runner_sha256','commands_sha256','exit_codes'}
            or any(not re.fullmatch('[a-f0-9]{64}',str(ci[k])) for k in ('runner_sha256','commands_sha256'))
            or ci['runner_sha256']!=policy['test_runner_sha256'] or ci['commands_sha256']!=policy['test_commands_sha256']
            or not isinstance(ci['exit_codes'],list) or not ci['exit_codes'] or any(type(n) is not int or n!=0 for n in ci['exit_codes'])
            or not isinstance(stage,dict) or set(stage)!={'source_sha','images','schema','database_system_identifier','checks_sha256'}
            or stage['source_sha']!=source or stage['images']!=value['images']
            or not re.fullmatch('[a-f0-9]{64}',str(stage['checks_sha256']))
            or not re.fullmatch('[1-9][0-9]{0,31}',str(stage['database_system_identifier']))
            or stage['database_system_identifier'] in policy['denied_database_identifiers']
            or type(stage['schema']) is not int or not isinstance(compat,dict)
            or set(compat)!={'origin_source_sha','candidate_source_sha','origin_range','candidate_range','protocols'}
            or compat['origin_source_sha']!=value['history_base_sha'] or compat['candidate_source_sha']!=source):
        raise RuntimeError('automatic_independent_ci_or_staging_incomplete')
    source_record=value['gates']['source'];artifacts=value['gates']['artifacts']
    recovery=value['gates']['recovery'];resources=value['gates']['resources']
    if (source_record!={'repository':'judahsleibi34/Madar','branch':'refs/heads/main','source_sha':source,
                       'history_base_sha':value['history_base_sha'],'tree_sha':value['tree_sha']}
            or not isinstance(artifacts,dict) or set(artifacts)!={'source_sha','images','build_inputs_sha256'}
            or artifacts['source_sha']!=source or artifacts['images']!=value['images']
            or not re.fullmatch('[a-f0-9]{64}',str(artifacts['build_inputs_sha256']))
            or not isinstance(recovery,dict) or set(recovery)!={'source_system_identifier','backup_sha256',
                'restore_system_identifier','restored_schema','rows_sha256','roles_sha256','objects_sha256',
                'backup_created_at','restored_at','verified_at'}
            or any(not re.fullmatch('[a-f0-9]{64}',str(recovery[k])) for k in ('backup_sha256','rows_sha256','roles_sha256','objects_sha256'))
            or recovery['source_system_identifier']==recovery['restore_system_identifier']
            or any(not re.fullmatch('[1-9][0-9]{0,31}',str(recovery[k])) for k in ('source_system_identifier','restore_system_identifier'))
            or any(type(recovery[k]) is not int for k in ('backup_created_at','restored_at','verified_at'))
            or not recovery['backup_created_at']<=recovery['restored_at']<=recovery['verified_at']<=now
            or not 0<=now-recovery['backup_created_at']<=policy['recovery_max_age_seconds']
            or not 0<=now-recovery['verified_at']<=policy['evidence_max_age_seconds']
            or type(recovery['restored_schema']) is not int
            or not isinstance(resources,dict) or set(resources)!={'disk_free_bytes','memory_available_bytes',
                'required_disk_bytes','required_memory_bytes','max_candidate_memory_bytes','max_candidate_cpu_millis'}
            or any(type(v) is not int or v<=0 for v in resources.values())
            or resources['disk_free_bytes']<resources['required_disk_bytes']
            or resources['memory_available_bytes']<resources['required_memory_bytes']):
        raise RuntimeError('automatic_independent_source_recovery_or_resources_incomplete')
    return value


def connect_database():
    """Observation/executor transport from fixed root-private configuration."""
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    raw=protected(DATABASE_DSN,private=True).read_bytes()
    if not 0<len(raw)<=8192:raise RuntimeError('automatic_database_configuration_size')
    args=conninfo_to_dict(raw.decode().strip())
    if args.get('host')!='127.0.0.1' or args.get('hostaddr','127.0.0.1')!='127.0.0.1' or args.get('service'):
        raise RuntimeError('automatic_test_database_transport_refused')
    return psycopg.connect(raw.decode().strip(),hostaddr='127.0.0.1',connect_timeout=5,autocommit=True,
        options='-c search_path=pg_catalog,public,extensions -c statement_timeout=10000 -c lock_timeout=1500')


def observe_admission(operations,source,*,attempt_id=None,created_at=None,expires_at=None):
    """Concrete root observer used both for preparation AND locked issuance."""
    from .migration_policy import load_policy,assess
    from .migration_inventory import discover,GitSource
    from .migration_plan import generate
    from .migration_drift import observe,measure_class_b,history_digest
    from .provider_recovery_runtime import readonly_configuration
    from .completed_normal_resources import measured_spec
    policy,environment=execution_policy(operations);routine=load_policy();now=int(time.time())
    if (routine['environment_id']!=policy['environment_id'] or routine['controller_sha']!=policy['controller_sha']
            or routine['database_system_identifier']!=environment['database_system_identifier']):
        raise RuntimeError('automatic_independent_policies_disagree')
    proof=independent_evidence(source,policy,now=now)
    state=strict_json(readonly_configuration(operations.state_root/'state.json',private=True).read_bytes())
    origin=state.get('known_good_release')
    if (not isinstance(origin,dict) or state.get('in_progress_release') or state.get('rollback_failure')
            or origin.get('sha')!=proof['history_base_sha'] or state.get('active_slot')!=origin.get('slot')
            or origin.get('slot') not in {'blue','green'}):
        raise RuntimeError('automatic_origin_not_stable')
    git=GitSource(operations.repo);git.commit(source)
    # Reuse protected-package object authentication, including commits and all
    # intermediate trees. A loose object's filename alone proves no identity.
    from .completed_normal_package import snapshot
    authenticated_tree,_=snapshot(operations.repo,source)
    if authenticated_tree!=proof['tree_sha']:raise RuntimeError('automatic_source_object_identity_changed')
    if git.command('rev-parse','refs/remotes/origin/main').decode().strip()!=source:
        raise RuntimeError('automatic_source_not_current_main')
    if git.command('merge-base','--is-ancestor',origin['sha'],source)!=b'':
        raise RuntimeError('automatic_source_ancestry_invalid')
    if git.command('rev-parse',source+'^{tree}').decode().strip()!=proof['tree_sha']:
        raise RuntimeError('automatic_source_tree_changed')
    with connect_database() as db:
        catalog=observe(db,required_protocols={})
        marker=db.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]
        if catalog.system_identifier!=environment['database_system_identifier'] or marker!='madar-isolated-'+environment['realm_id']:
            raise RuntimeError('automatic_live_database_changed')
        from .automatic_release_selection import select
        inventory,target,selection=select(operations,source,proof,policy,routine,catalog.schema)
        history=strict_json(protected(Path('/var/lib/madar-control-plane/automatic-history.json'),private=True).read_bytes())
        if history!={'version':1,'system_identifier':catalog.system_identifier,'schema':catalog.schema,
                      'structure_sha256':catalog.structure_sha256,'history_sha256':history_digest(inventory,catalog.schema)}:
            raise RuntimeError('automatic_applied_history_or_catalog_drift')
        plan=generate(operations.repo,inventory,origin=catalog.schema,target=target)
        if selection is not None and selection['plan_sha256']!=plan.sha256:
            raise RuntimeError('automatic_selected_plan_changed')
        value=plan.document()
        measurements=measure_class_b(db,plan,expected_system_identifier=catalog.system_identifier,
            expected_structure_sha256=catalog.structure_sha256) if value['risk_class']=='B' else None
    if value['migrations']:
        from .automatic_release_migration import proof_scope
        proof_scope({'plan':value},proof)
    elif proof['version']!=1:
        raise RuntimeError('automatic_application_only_evidence_scope_changed')
    compat=proof['gates']['compatibility'];stage=proof['gates']['staging']
    expected_ranges=[value['origin_compatibility_intent'],value['compatibility_intent']]
    if any(not isinstance(intent,dict) for intent in expected_ranges):raise RuntimeError('automatic_compatibility_intent_missing')
    if (compat['origin_range']!=[expected_ranges[0]['compatible_min'],expected_ranges[0]['compatible_max']]
            or compat['candidate_range']!=[expected_ranges[1]['compatible_min'],expected_ranges[1]['compatible_max']]
            or compat['protocols']!=expected_ranges[1]['worker_protocols'] or stage['schema']!=value['target_schema']
            or stage['database_system_identifier']==catalog.system_identifier):
        raise RuntimeError('automatic_independent_runtime_compatibility_missing')
    # Root's pinned real Docker observation of the currently running application.
    slot=origin['slot'];port=8101 if slot=='blue' else 8201
    from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    opener=build_opener(ProxyHandler({}),NoRedirect())
    def http(path):
        with opener.open(Request('http://127.0.0.1:'+str(port)+path),timeout=5) as response:
            raw=response.read(65537)
            if response.status!=200 or len(raw)>65536:raise RuntimeError('automatic_origin_health_invalid')
            return strict_json(raw)
    if (proof['gates']['recovery']['source_system_identifier']!=catalog.system_identifier
            or proof['gates']['recovery']['restored_schema']!=catalog.schema):
        raise RuntimeError('automatic_recovery_origin_changed')
    import shutil
    available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))*1024
    budgets=proof['gates']['resources']
    if shutil.disk_usage(operations.state_root).free<budgets['required_disk_bytes'] or available<budgets['required_memory_bytes']:
        raise RuntimeError('automatic_current_resource_headroom_insufficient')
    identity=http('/health/version')
    if (identity.get('release_sha')!=origin['sha'] or identity.get('release_slot')!=slot
            or [identity.get('schema_compatible_min'),identity.get('schema_compatible_max')]!=compat['origin_range']
            or http('/health/ready').get('ready') is not True):
        raise RuntimeError('automatic_running_origin_incompatible')
    rows=json.loads(operations.command('automatic_origin_docker',['/usr/bin/docker','inspect',*[
        'madar-'+slot+'-'+role for role in ('backend','frontend','redis','parser-worker','remote-ingestion-worker',
        'notification-worker','calendar-sync-worker','data-deletion-worker')]]).stdout)
    actual=digest({r['Name']:{'id':r['Id'],'image':r['Image'],'spec_sha256':measured_spec(r)} for r in rows})
    if actual!=proof['origin_configuration_sha256'] or any(not r['State']['Running'] for r in rows):
        raise RuntimeError('automatic_origin_runtime_changed')
    images=proof['images']
    for role in ('backend','frontend','worker'):
        expected=images[role].split('@')[-1]
        image=json.loads(operations.command('automatic_artifact_docker',['/usr/bin/docker','image','inspect',expected]).stdout)[0]
        if (image['Id']!=expected or image['Config'].get('Labels',{}).get('com.madar.release.sha')!=source
                or image['Config']['Labels'].get('com.madar.release.built_at')!=images['build_timestamp']):
            raise RuntimeError('automatic_authenticated_image_substituted')
    observation={k:routine[k] for k in ('environment_id','database_system_identifier','controller_sha','repository','branch')}
    observation.update(source_sha=source,origin_schema=value['origin_schema'],target_schema=value['target_schema'],
        operation_id=value['operation_id'],plan_sha256=plan.sha256,operation_consumed=False,
        evidence_expires_at=proof['expires_at'],structure_sha256=catalog.structure_sha256,
        gates={gate:True for gate in value['required_gates'] if gate!='fresh_independent_authority'})
    # These booleans are produced ONLY after authenticated independent evidence
    # and direct live observations above; they are never CLI/candidate inputs.
    if measurements is not None:observation['class_b_measurements']=measurements
    result=assess(plan,routine,observation,now=now)
    if not result['policy_match']:raise RuntimeError('automatic_policy_refused:'+','.join(result['reasons']))
    start=now if created_at is None else created_at
    end=min(start+policy['operation_max_seconds'],proof['expires_at']) if expires_at is None else expires_at
    target_slot='green' if slot=='blue' else 'blue'
    output={'version':1,'operation':OPERATION,'operation_id':value['operation_id'],'attempt_id':attempt_id or proof['attempt_id'],
        'environment':policy['environment'],'source_sha':source,'controller_sha':policy['controller_sha'],'plan':value,
        'policy_sha256':digest({'routine':routine,'execution':policy}),
        'database':{'system_identifier':catalog.system_identifier,'origin_schema':catalog.schema,
            'target_schema':value['target_schema'],'structure_sha256':catalog.structure_sha256},
        'origin':{'source_sha':origin['sha'],'slot':slot,'images':image_identities(origin['images']),
            'compatible_min':compat['origin_range'][0],'compatible_max':compat['origin_range'][1],
            'configuration_sha256':actual},
        'candidate':{'source_sha':source,'slot':target_slot,'images':images,
            'compatible_min':compat['candidate_range'][0],'compatible_max':compat['candidate_range'][1],
            'configuration_sha256':proof['candidate_configuration_sha256']},
        'evidence':{gate:digest(proof['gates'][gate]) for gate in GATES},'created_at':start,'expires_at':end}
    if value['migrations']:output['evidence']['migration']=digest(proof['migration'])
    return validate(output,now=now)


def publish(value):
    """Freeze already independently observed DATA. Creates no authority."""
    from .control_plane_upgrade import require_root_directory
    from .migration_executor import atomic_json
    if os.geteuid()!=0:raise RuntimeError('automatic_publication_root_required')
    validate(value);require_root_directory(ROOT,create=True)
    path=directory(value)
    path.mkdir(mode=0o700)
    fd=os.open(path/'admission.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
    with os.fdopen(fd,'wb') as stream:stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
    for parent in (path,ROOT):
        fd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    return path


def reserve(value,operations):
    """Durably consume this exact attempt BEFORE any credentials/effects."""
    from .control_plane_upgrade import require_root_directory
    from .migration_executor import atomic_json
    require_issue(value,operations)
    parent=ROOT/'attempts';require_root_directory(parent,create=True)
    path=parent/value['attempt_id'];path.mkdir(mode=0o700) # no overwrite/retry
    record={'admission_sha256':digest(value),'source_sha':value['source_sha'],
        'operation_id':value['operation_id'],'attempt_id':value['attempt_id'],
        'pid':os.getpid(),'process_start':Path('/proc/self/stat').read_text().split(') ',1)[1].split()[19],
        'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    atomic_json(path/'consumed.json',record,exclusive=True)
    fd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    return record


def require_reserved(value,*,allow_completed=False):
    record=strict_json(protected(ROOT/'attempts'/value['attempt_id']/'consumed.json',private=True).read_bytes())
    expected={'admission_sha256':digest(value),'source_sha':value['source_sha'],
        'operation_id':value['operation_id'],'attempt_id':value['attempt_id'],
        'pid':os.getpid(),'process_start':Path('/proc/self/stat').read_text().split(') ',1)[1].split()[19],
        'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    if record!=expected or (not allow_completed and (ROOT/'attempts'/value['attempt_id']/'completion.json').exists()):
        raise RuntimeError('automatic_attempt_foreign_consumed_or_completed')
    return record


def require_no_pending_operation():
    """A lost /run interlock must never permit a second operation after boot."""
    path=ROOT/'in-progress.json'
    if path.exists() or path.is_symlink():
        # Even a corrupt/unreadable pointer blocks. Recovery must observe the
        # consumed journal and actual serving state; absence of /run proves none.
        protected(path,private=True)
        raise RuntimeError('automatic_durable_operation_requires_recovery')


def arm_operation(value):
    from .migration_executor import atomic_json
    require_reserved(value)
    require_no_pending_operation()
    record={'version':1,'operation':OPERATION,'attempt_id':value['attempt_id'],
        'admission_sha256':digest(value),'source_sha':value['source_sha'],
        'operation_id':value['operation_id'],'database_system_identifier':value['database']['system_identifier']}
    atomic_json(ROOT/'in-progress.json',record,exclusive=True)
    return record


def finish_operation(value):
    """Only this live consumed attempt and its genuine completion may retire it."""
    require_reserved(value,allow_completed=True)
    path=ROOT/'in-progress.json'
    record=strict_json(protected(path,private=True).read_bytes())
    expected={'version':1,'operation':OPERATION,'attempt_id':value['attempt_id'],
        'admission_sha256':digest(value),'source_sha':value['source_sha'],
        'operation_id':value['operation_id'],'database_system_identifier':value['database']['system_identifier']}
    completion=strict_json(protected(ROOT/'attempts'/value['attempt_id']/'completion.json',private=True).read_bytes())
    if (record!=expected or completion.get('admission_sha256')!=digest(value)
            or completion.get('attempt_id')!=value['attempt_id'] or completion.get('source_sha')!=value['source_sha']
            or completion.get('release',{}).get('status')!='known_good'):
        raise RuntimeError('automatic_durable_completion_binding_invalid')
    path.unlink()
    fd=os.open(ROOT,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
