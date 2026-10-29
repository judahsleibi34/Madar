"""Immutable request producer for the existing protected entrypoint.

No issuer or executor. GitHub authenticates the commit/tree; actual original
runtime observations and source-owned validators bind the prepared request.
The candidate model is provisional. Actual candidate identities are sealed by
existing candidate-staged-runtime/issuer witnesses after private creation.
"""
import ctypes,hashlib,os,re,runpy,shutil,tempfile,uuid
from pathlib import Path
from deployment.lib.completed_normal_admission import encoded,digest,validate_provider_preparation
from deployment.lib.completed_normal_profile import RECONCILED,maintenance_role
from deployment.lib.migration_inventory import GitSource,strict_json
from deployment.lib.provider_recovery_runtime import protected

BASE=Path('/var/lib/madar-control-plane/normal-local-preparation')
MAX_SOURCE=128*1024**2
MAX_FILE=32*1024**2


def snapshot(repository,sha):
    git=GitSource(repository);git.commit(sha)
    tree=git.command('rev-parse',sha+'^{tree}').decode().strip()
    def object_bytes(kind,oid):
        if not re.fullmatch('[0-9a-f]{40}',oid):raise RuntimeError('completed_package_source_object_changed')
        body=git.command('cat-file',kind,oid)
        if hashlib.sha1(kind.encode()+b' '+str(len(body)).encode()+b'\0'+body).hexdigest()!=oid:
            raise RuntimeError('completed_package_source_object_changed')
        return body
    commit=object_bytes('commit',sha)
    if not commit.startswith(b'tree '+tree.encode()+b'\n'):
        raise RuntimeError('completed_package_source_object_changed')
    # Git reads a loose object's contents without necessarily checking that its
    # pathname equals the content hash. Authenticate intermediate trees too.
    trees={tree}
    for entry in git.command('ls-tree','-rtz',sha).split(b'\0'):
        if entry and entry.split(b'\t',1)[0].split()[1]==b'tree':
            trees.add(entry.split(b'\t',1)[0].split()[2].decode())
    if len(trees)>8192:raise RuntimeError('completed_package_source_limit')
    for oid in trees:object_bytes('tree',oid)
    entries=git.command('ls-tree','-rz',sha).split(b'\0');files={};size=0
    for raw in entries:
        if not raw:continue
        header,name=raw.split(b'\t',1);mode,kind,oid=header.decode().split();name=name.decode('utf-8');relative=Path(name)
        if (mode not in {'100644','100755'} or kind!='blob' or relative.is_absolute()
                or '..' in relative.parts or relative.as_posix()!=name or '.git' in relative.parts
                or relative.suffix in {'.pyc','.pyo'} or name in files or len(files)>=8192):
            raise RuntimeError('completed_package_source_inventory_invalid')
        length=int(git.command('cat-file','-s',oid))
        if not 0<=length<=MAX_FILE or size+length>MAX_SOURCE:raise RuntimeError('completed_package_source_limit')
        body=git.command('cat-file','blob',oid)
        if len(body)!=length or hashlib.sha1(b'blob '+str(length).encode()+b'\0'+body).hexdigest()!=oid:
            raise RuntimeError('completed_package_source_object_changed')
        files[name]=(mode,body);size+=length
    return tree,files


def validate_inputs(plan,inventory,probes,model):
    if not isinstance(plan,dict) or any(k in plan for k in ('source_bundle_sha256','operation_id','attempt_id')):
        raise RuntimeError('completed_package_fresh_plan_required')
    required={'controller_source_sha','admission_contract','application_artifacts','application_evidence',
        'live_configuration_sha256','installed_controller_tree_sha256','origin_routing_sha256','proxy_nginx_sha256',
        'boot_resources','backup_timer_states','node1_replica','original_provider_probe_sha256'}
    if not required<=set(plan):raise RuntimeError('completed_package_plan_incomplete')
    contract=plan['admission_contract']
    if not isinstance(contract,dict) or 'plan_sha256' in contract:raise RuntimeError('completed_package_circular_contract')
    contract=dict(contract,plan_sha256='0'*64)
    if validate_provider_preparation(contract) is not RECONCILED:
        raise RuntimeError('completed_package_canonical_operation_required')
    if plan['controller_source_sha']!=contract['candidate']['controller_sha']:
        raise RuntimeError('completed_package_controller_identity_changed')
    if plan.get('fixture_only') is not True or plan.get('production_authorization') is not False:
        raise RuntimeError('completed_package_test_request_only')
    from deployment.lib.completed_normal_boot_actor import CONFIGURATIONS
    if (set(plan['live_configuration_sha256'])!=set(CONFIGURATIONS)
            or any(not re.fullmatch('[0-9a-f]{64}',str(v)) for v in plan['live_configuration_sha256'].values())
            or any(not re.fullmatch('[0-9a-f]{64}',str(plan[k])) for k in
                ('installed_controller_tree_sha256','origin_routing_sha256','proxy_nginx_sha256'))):
        raise RuntimeError('completed_package_configuration_binding_invalid')
    from deployment.lib.schema150_actor_inventory import validate_inventory
    binding={'operation':RECONCILED.operation,'context_sha256':digest(contract),
        'source_sha':contract['candidate']['source_sha'],'controller_sha':plan['controller_source_sha'],
        'inventory_sha256':contract['writer_inventory_sha256'],'system_identifier':contract['database']['system_identifier'],
        'source_schema':146,'target_schema':160}
    validate_inventory(inventory,binding)
    if inventory['exclusions'] or any(k.startswith('candidate:') for k in inventory['containers']):
        raise RuntimeError('completed_package_original_inventory_required')
    from deployment.lib.completed_normal_private_acceptance import validate_subjects
    if (not isinstance(probes,dict) or set(probes)!={'version','system_identifier','subjects'}
            or type(probes['version']) is not int or probes['version']!=1
            or probes['system_identifier']!=binding['system_identifier']
            or digest(probes)!=plan['original_provider_probe_sha256']):
        raise RuntimeError('completed_package_original_probe_binding_invalid')
    validate_subjects(probes['subjects'])
    from deployment.lib.completed_normal_resources import candidate_roles
    if (not isinstance(model,dict) or set(model.get('services',{}))!=set(candidate_roles(contract))):
        raise RuntimeError('completed_package_candidate_model_incomplete')
    for role,row in model['services'].items():
        from deployment.lib.completed_normal_resources import candidate_image
        identity=candidate_image(contract,role)
        component='frontend' if role in {'frontend','provider-gateway'} else 'backend'
        reference=plan['application_artifacts'].get(component)
        permitted={identity}
        if role!='redis' and isinstance(reference,str) and reference.partition('@')[2]==identity:
            permitted.add(reference)
        if not isinstance(row,dict) or row.get('image') not in permitted:
            raise RuntimeError('completed_package_candidate_image_changed')
    return contract


def observe_origin(contract,runtime,state_root=Path('/var/lib/madar/releases')):
    """An initialized146 database is not a compatible running application."""
    from deployment.lib.completed_normal_resources import ROLES,measured_spec_matches
    from deployment.lib.runtime_authority import load_worker_authority
    roles=contract['source_roles'];origin=contract['origin']
    bootstrap=roles.get('origin_kind')=='independently-enrolled-historical-bootstrap-origin'
    if bootstrap:
        from deployment.lib.historical_origin import validate_source_binding,recorded_observation,attest
        from deployment.lib.control_plane_upgrade import SystemOperations
        from deployment.lib.provider_recovery_runtime import readonly_configuration
        root=validate_source_binding(roles)
        state=strict_json(readonly_configuration(state_root/'state.json',private=True).read_bytes())
        if attest(SystemOperations(),state)!=roles:raise RuntimeError('completed_package_historical_origin_changed')
        observed=recorded_observation(roles)
        record={'source_sha':roles['application_sha'],'images':{key:observed['runtime']['/madar-'+origin['slot']+'-'+key]['image'] for key in ('backend','frontend')},
            'worker_generation':observed['worker_authority']['generation'],
            'runtimes':{role:observed['runtime']['/madar-'+origin['slot']+'-'+role] for role in ROLES}}
    else:
        root=Path(roles['completion_root'])
    # Existing history is authenticated DATA, never reused execution authority.
    for name,expected in contract['historical_files'].items():
        if hashlib.sha256(protected(Path(name),private=Path(name).name!='admission.json').read_bytes()).hexdigest()!=expected:
            raise RuntimeError('completed_package_origin_history_changed')
    if not bootstrap:
        record=strict_json(protected(root/'candidate-runtime.json',private=True).read_bytes())
    if (record.get('source_sha')!=roles['application_sha'] or record.get('images')!=origin['images']
            or record.get('worker_generation')!=origin['worker_generation']
            or set(record.get('runtimes',{}))!=set(ROLES)):
        raise RuntimeError('completed_package_running_origin_required')
    rows=runtime.inspect([v['id'] for v in record['runtimes'].values()])
    actual={r['Id']:r for r in rows.values()}
    for role,expected in record['runtimes'].items():
        row=actual.get(expected['id'])
        if (row is None or row['Image']!=expected['image'] or not row['State']['Running']
                or row['State'].get('Restarting') or row['State'].get('Health',{}).get('Status')!='healthy'
                or not measured_spec_matches(row,expected['spec_sha256'],started_worker=role.endswith('-worker'))):
            raise RuntimeError('completed_package_origin_actor_changed')
    owner=load_worker_authority(state_root)
    if (owner is None or owner['owner']!='CANDIDATE' or owner['generation']!=origin['worker_generation']
            or owner['candidate']!={'sha':roles['application_sha'],'slot':origin['slot']}):
        raise RuntimeError('completed_package_origin_worker_owner_changed')
    if bootstrap:
        # Enrollment records actual pre-grant authority; it must never invent
        # a historical positive grant merely to satisfy the completed path.
        grant_path=root/'write-authority/authority.json'
        if (origin['write_contract_digest']!=roles['enrollment_sha256']
                or grant_path.exists() or grant_path.is_symlink()):
            raise RuntimeError('completed_package_bootstrap_grant_not_historical')
        for row in actual.values():
            config=dict(item.split('=',1) for item in row['Config'].get('Env',[]) if '=' in item)
            if (any(config.get(k) for k in ('MADAR_BUSINESS_WRITE_AUTHORITY','MADAR_BUSINESS_WRITE_CONTRACT'))
                    or any(m['Destination']=='/run/madar' or m['Destination'].startswith('/run/madar/business-write-authority')
                           for m in row.get('Mounts',[]))):
                raise RuntimeError('completed_package_bootstrap_authority_runtime_changed')
    else:
        grant=strict_json(protected(root/'write-authority/authority.json').read_bytes())
        if grant!={'version':2,'schema':146,'release_sha':roles['application_sha'],
                'contract_digest':origin['write_contract_digest'],'mode':'NORMAL','compatible_min':144,'compatible_max':146}:
            raise RuntimeError('completed_package_origin_authority_changed')
    observed=strict_json(runtime.command(['docker','exec',contract['database']['container_id'],
        'psql','-XqAt','-v','ON_ERROR_STOP=1','-U',maintenance_role(contract),'-d','postgres','-c',
        "BEGIN READ ONLY; SET LOCAL statement_timeout='3s'; SELECT json_build_array("
        "(SELECT system_identifier::text FROM pg_control_system()),schema_version) "
        "FROM public.application_schema_state WHERE contract_key='core'; COMMIT;"]))
    if observed!=[contract['database']['system_identifier'],146]:
        raise RuntimeError('completed_package_origin_database_changed')
    port=8101 if origin['slot']=='blue' else 8201;base='http://127.0.0.1:'+str(port)
    version=runtime.json_http(base+'/health/version')
    if (version.get('release_sha')!=roles['application_sha'] or version.get('release_slot')!=origin['slot']
            or (version.get('schema_compatible_min'),version.get('schema_compatible_max'))!=(144,146)
            or runtime.json_http(base+'/health/ready').get('ready') is not True
            or runtime.json_http(base+'/health/recovery')!={'restricted':False,'business_writes_enabled':True}):
        raise RuntimeError('completed_package_origin_application_incompatible')
    return {'source_sha':roles['application_sha'],'images':origin['images'],'worker_generation':origin['worker_generation']}


def freeze(base,source_sha,tree,files,plan,inventory,probes,model,authentication,*,nonce=None):
    """Filesystem publication only; caller must authenticate source/origin first.

    CLI supplies the real environment/origin/API observers. Constructor-supplied
    temporary bases in tests do not authorize a release or weaken entrypoint BASE.
    """
    nonce=nonce or str(uuid.uuid4());operation=str(uuid.uuid4())
    if str(uuid.UUID(nonce))!=nonce:raise RuntimeError('completed_package_attempt_invalid')
    contract=validate_inputs(plan,inventory,probes,model)
    if (source_sha!=plan['controller_source_sha'] or not re.fullmatch('[0-9a-f]{40}',str(tree))
            or authentication.get('sha')!=source_sha
            or authentication.get('commit',{}).get('tree',{}).get('sha')!=tree):
        raise RuntimeError('completed_package_remote_source_changed')
    size=0
    for name,(mode,body) in files.items():
        path=Path(name);size+=len(body)
        if (path.is_absolute() or '..' in path.parts or path.as_posix()!=name
                or '.git' in path.parts or mode not in {'100644','100755'}
                or path.suffix in {'.pyc','.pyo'} or len(body)>MAX_FILE or size>MAX_SOURCE):
            raise RuntimeError('completed_package_source_inventory_invalid')
    if not files or len(files)>8192:raise RuntimeError('completed_package_source_limit')
    from deployment.lib.control_plane_upgrade import require_root_directory
    require_root_directory(base,create=True)
    staging=Path(tempfile.mkdtemp(prefix='.package-',dir=base));published=False
    def write(path,body,mode=0o400):
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
        with os.fdopen(fd,'wb') as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
    try:
        for name,(mode,body) in files.items():write(staging/'source'/name,body,0o500 if mode=='100755' else 0o400)
        from deployment.lib.schema160_release import captured_source
        captured_source(staging/'source') # Captured immutable SQL + mirrors, never execution admission.
        manifest={'version':2,'source_sha':source_sha,'operation_id':operation,'attempt_id':nonce,
            'source_authentication_sha256':digest(authentication),
            'files':{name:hashlib.sha256(body).hexdigest() for name,(_,body) in files.items()}}
        document=dict(plan,source_bundle_sha256=digest(manifest),operation_id=operation,attempt_id=nonce,
            candidate_model_sha256=digest(model),provider_inventory_input_sha256=digest(inventory),
            source_authentication_sha256=digest(authentication))
        actual=dict(document['admission_contract'],plan_sha256=digest(document))
        validate_provider_preparation(actual)
        for name,value in {'source-bundle.json':manifest,'plan.json':document,'provider-inventory-input.json':inventory,
                'original-provider-probes.json':probes,'candidate-model.json':model,'source-authentication.json':authentication}.items():
            write(staging/name,encoded(value))
        entry=staging/'source/web/scripts/continue_completed_normal_upgrade.py'
        # Frozen authenticated stdlib-only measurement code, not another runner.
        measured=runpy.run_path(str(entry),run_name='completed_package_measurement')
        required=measured['REQUIRED_FILES']
        if not required<=set(files):raise RuntimeError('completed_package_required_source_missing')
        for path in sorted((p for p in staging.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):
            fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd);path.chmod(0o500)
        staging.chmod(0o500);destination=base/('normal-source-'+digest(manifest))
        libc=ctypes.CDLL(None,use_errno=True);rename=libc.renameat2
        rename.argtypes=(ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint)
        if rename(-100,os.fsencode(staging),-100,os.fsencode(destination),1):raise OSError(ctypes.get_errno(),'completed_package_publication_refused')
        published=True
        fd=os.open(base,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
        # Invoke the actual entrypoint's measurement after final rename. It
        # authenticates every exact source byte and the canonical plan encoding.
        measured['measure'](destination,digest(manifest),digest(document),base=base)
        return {'package':str(destination),'source_sha':source_sha,'source_bundle_sha256':digest(manifest),
            'plan_sha256':digest(document),'context_sha256':digest(actual),'operation_id':operation,'attempt_id':nonce,
            'candidate_runtime_status':'PROVISIONAL_MODEL; existing root stage seal required',
            'authority_issued':False,'operational_admission':False}
    finally:
        if not published and staging.exists():
            for path in staging.rglob('*'):
                if path.is_dir():path.chmod(0o700)
            staging.chmod(0o700);shutil.rmtree(staging)


def prepare(repository,plan,inventory,probes,model):
    """Actual guest-only producer. No effects on production or accepted staging."""
    from deployment.lib.isolated_release_environment import observe
    from deployment.lib.schema150_provider_adapter import capture_original_inventory
    from deployment.lib.emergency_routing_repair import Runtime
    environment=observe();contract=validate_inputs(plan,inventory,probes,model)
    if (contract['database']['container_id']!=environment['database_container_id']
            or contract['database']['system_identifier']!=environment['database_system_identifier']):
        raise RuntimeError('completed_package_guest_database_changed')
    runtime=Runtime();original=observe_origin(contract,runtime)
    import subprocess
    sha=plan['controller_source_sha']
    raw=subprocess.check_output(['/usr/sbin/runuser','-u','madar','--','/usr/bin/gh','api',
        'repos/judahsleibi34/Madar/commits/'+sha],timeout=30)
    authentication=strict_json(raw);tree,files=snapshot(repository,sha)
    result=freeze(BASE,sha,tree,files,plan,inventory,probes,model,authentication)
    package=Path(result['package'])
    def guard():
        if observe()!=environment:raise RuntimeError('completed_package_guest_changed')
        namespace=runpy.run_path(str(package/'source/web/scripts/continue_completed_normal_upgrade.py'),run_name='package_measurement')
        namespace['measure'](package,result['source_bundle_sha256'],result['plan_sha256'])
    final_contract=dict(plan['admission_contract'],plan_sha256=result['plan_sha256'])
    capture_original_inventory(package,final_contract,runtime,source_guard=guard)
    if observe_origin(contract,runtime)!=original:raise RuntimeError('completed_package_original_application_changed')
    return result
