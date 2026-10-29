"""Independent Compose-to-runtime validation before sealing the bridge.

An observed Docker spec hash alone proves continuity, not that the initial
container was authorized. This verifier compares immutable images, image
defaults and the freshly rendered frozen deployment specification first.
No configuration or environment values are written to its public results.
"""
import json
import os
from pathlib import Path
import re
import hashlib
import time

from deployment.lib.completed_normal_admission import ADMISSIONS,OPERATION,digest,encoded,require_fresh_authorization,validate_contract
from deployment.lib.completed_normal_resources import ROLES,candidate_roles,candidate_image,allocation,verify_runtime_binding,measured_spec
from deployment.lib.emergency_routing_repair import exclusive,spec,AvailabilityFailure,verification_window
from deployment.lib.provider_recovery_runtime import protected
from deployment.lib.runtime_authority import load_worker_authority,runtime_mutation_lock
from deployment.lib.completed_normal_profile import profile, LEGACY

BUSINESS=('notification-worker','calendar-sync-worker','data-deletion-worker')

def _environment(items):
    result={}
    for raw in items or []:
        key,separator,value=raw.partition('=')
        if not separator or key in result:raise RuntimeError('completed_runtime_environment_invalid')
        result[key]=value
    return result


def verify_private_parser(row, *, source_sha, image, network_name, uploads_root):
    """Measure the bounded HTTP compute sidecar, never a queue/DB consumer.

    The existing full rendered-model seal remains required. This independent
    semantic check prevents a source-bound model from giving the pre-handoff
    parser credentials, writable data, host access or an egress network.
    No Docker effect, health claim or authority follows from this function.
    """
    config=row.get('Config',{});host=row.get('HostConfig',{})
    env=_environment(config.get('Env'))
    required={'APP_ENV':'production','MADAR_RELEASE_SHA':source_sha,
        'DATA_UPLOAD_DIR':'/app/private_uploads','MADAR_UPLOAD_WORKSPACE_DIR':'/tmp/madar_parser',
        'PARSER_WORKER_PROCESS':'true','PARSER_WORKER_HEALTH_HOST':'0.0.0.0','PARSER_WORKER_PORT':'8092',
        'ALLOW_REMOTE_DATASET_URLS':'false'}
    allowed=set(required)|{'MADAR_BUILD_TIMESTAMP','PARSER_JOB_TIMEOUT_SECONDS','STRUCTURED_LOGS',
        'PATH','LANG','GPG_KEY','PYTHON_VERSION','PYTHON_SHA256','PYTHONUNBUFFERED','PYTHONDONTWRITEBYTECODE'}
    timeout=env.get('PARSER_JOB_TIMEOUT_SECONDS','')
    if (not set(env)<=allowed or any(env.get(k)!=v for k,v in required.items())
            or not timeout.isdecimal() or not 1<=int(timeout)<=295
            or env.get('STRUCTURED_LOGS') not in {'true','false'}
            or row.get('Image')!=image or config.get('User')!='65534:65534'
            or config.get('Cmd')!=['python','-m','workers.parser_worker']
            or config.get('Entrypoint') not in (None,[]) or config.get('WorkingDir')!='/app'
            or config.get('Labels',{}).get('org.opencontainers.image.revision')!=source_sha):
        raise RuntimeError('completed_private_parser_configuration_invalid')
    if (host.get('Privileged') is not False or host.get('ReadonlyRootfs') is not True
            or sorted(host.get('CapDrop') or [])!=['ALL'] or host.get('CapAdd')
            or sorted(host.get('SecurityOpt') or [])!=['no-new-privileges:true']
            or host.get('Devices') or host.get('DeviceRequests') or host.get('PidMode')
            or host.get('IpcMode') not in {None,'','private','none'} or host.get('UTSMode')
            or host.get('Init') is not True or host.get('Memory')!=768*1024*1024
            or host.get('NanoCpus')!=750_000_000 or host.get('PidsLimit')!=64
            or host.get('RestartPolicy',{}).get('Name')!='no'
            or host.get('PublishAllPorts') or host.get('PortBindings')
            or any(row.get('NetworkSettings',{}).get('Ports',{}).values())
            or host.get('NetworkMode')!=network_name
            or set(row.get('NetworkSettings',{}).get('Networks',{}))!={network_name}
            or host.get('Tmpfs')!={'/tmp':'rw,noexec,nosuid,size=256m,uid=65534,gid=65534'}):
        raise RuntimeError('completed_private_parser_isolation_invalid')
    mounts=row.get('Mounts')
    if (not isinstance(mounts,list) or len(mounts)!=1 or mounts[0].get('Type')!='bind'
            or mounts[0].get('Source')!=uploads_root or mounts[0].get('Destination')!='/app/private_uploads'
            or mounts[0].get('RW') is not False):
        raise RuntimeError('completed_private_parser_mount_invalid')


def _image_default(service, key, base, image_key):
    # Compose's explicit null means inherit the image configuration, exactly
    # like an omitted field. An explicit empty value still overrides it.
    value = service.get(key)
    return base.get(image_key) if value is None else value

def _duration(value):
    units={'ns':1,'us':1000,'ms':1_000_000,'s':1_000_000_000,'m':60_000_000_000,'h':3_600_000_000_000}
    if type(value) is int:return value
    parts=re.findall(r'([0-9]+(?:\.[0-9]+)?)(ns|us|ms|s|m|h)',str(value))
    if not parts or ''.join(n+u for n,u in parts)!=str(value):
        raise RuntimeError('completed_runtime_health_declaration_invalid')
    return round(sum(float(n)*units[u] for n,u in parts))

def validate_model(contract,model,runtime, *, phase='running'):
    if phase not in {'staged','running','fenced','provisional'}:
        raise RuntimeError('completed_runtime_lifecycle_invalid')
    from deployment.lib.completed_normal_profile import DELETION, RECONCILED
    preparation150=phase=='provisional' and contract.get('operation') in {DELETION.operation, RECONCILED.operation}
    if preparation150:
        from deployment.lib.completed_normal_admission import validate_provider_preparation
        release=validate_provider_preparation(contract)
    else:
        validate_contract(contract)
        release=profile(contract)
    selected=allocation(contract,contract['candidate']['slot'],preparation150=preparation150)
    services=model.get('services',{})
    if set(services)!=set(candidate_roles(contract)):raise RuntimeError('completed_runtime_service_inventory_changed')
    images={};rows=runtime.inspect(list(selected['containers'].values()))
    if len(rows)!=len(candidate_roles(contract)):raise RuntimeError('completed_runtime_container_inventory_changed')
    for image in {*contract['candidate']['images'].values(),contract['candidate']['redis_image']}:
        result=json.loads(runtime.command(['docker','image','inspect',image]))
        if len(result)!=1 or result[0]['Id']!=image:raise RuntimeError('completed_runtime_image_changed')
        images[image]=result[0]['Config']
        if image in contract['candidate']['images'].values() and (
                images[image].get('Labels',{}).get('org.opencontainers.image.revision')!=contract['candidate']['source_sha']):
            raise RuntimeError('completed_runtime_image_source_changed')
    network_ids={}
    for declaration in model.get('networks',{}).values():
        name=declaration.get('name')
        native=release is RECONCILED and name=='madar-local-supabase_default'
        if name not in {*selected['networks'].values(),'madar-supabase-client'} and not native:
            raise RuntimeError('completed_runtime_network_declaration_changed')
        observed=json.loads(runtime.command(['docker','network','inspect',name]))
        if len(observed)!=1 or observed[0]['Name']!=name or observed[0]['Driver']!='bridge':
            raise RuntimeError('completed_runtime_network_object_changed')
        net=observed[0]
        if bool(net.get('Internal'))!= (False if native else bool(declaration.get('internal',declaration.get('external',False)))):
            raise RuntimeError('completed_runtime_network_isolation_changed')
        if not declaration.get('external') and (net.get('IPAM',{}).get('Config') or [])!=declaration.get('ipam',{}).get('config',[]):
            # Docker adds the gateway to IPAM serialization. Compare subnets
            # exactly; an additional range is never treated as a default.
            expected=[n.get('subnet') for n in declaration.get('ipam',{}).get('config',[])]
            actual=[n.get('Subnet') for n in net.get('IPAM',{}).get('Config',[])]
            if actual!=expected:raise RuntimeError('completed_runtime_network_subnet_changed')
        network_ids[name]=net['Id']
        if release is RECONCILED and name==selected['networks']['parser'] and net.get('Internal') is not True:
            raise RuntimeError('completed_private_parser_network_invalid')
    bindings={};health_pending=False
    for role,service in services.items():
        name=selected['containers'][role]
        if service.get('container_name')!=name or service.get('restart')!='no':
            raise RuntimeError('completed_runtime_role_declaration_changed')
        row=rows.get(name)
        image=candidate_image(contract,role)
        if row is not None:
            state=row['State']
            if phase in {'fenced','provisional'}:
                if (state.get('Running') is not False or state.get('Restarting') is not False
                        or state.get('Status') not in ({'created'} if phase=='provisional' else {'created','exited'})):
                    raise RuntimeError('completed_runtime_fenced_candidate_started')
            elif phase=='staged' and role in BUSINESS:
                if state.get('Running') or state.get('Status')!='created':
                    raise RuntimeError('completed_runtime_standby_started')
            elif not state.get('Running'):
                raise RuntimeError('completed_runtime_service_not_running')
        if row is None or row['Image']!=image:
            raise RuntimeError('completed_runtime_running_identity_changed')
        if phase not in {'fenced','provisional'} and not (phase=='staged' and role in BUSINESS):
            health=row['State'].get('Health',{}).get('Status')
            if health not in {'healthy','starting'}:
                raise RuntimeError('completed_runtime_running_identity_changed')
            health_pending=health_pending or health=='starting'
        base=images[image];config=row['Config'];host=row['HostConfig']
        labels=config.get('Labels',{})
        if labels.get('com.docker.compose.service')!=role or labels.get('com.docker.compose.project')!=selected['project']:
            raise RuntimeError('completed_runtime_role_identity_changed')
        expected_env=_environment(base.get('Env'))
        expected_env.update({k:str(v) for k,v in service.get('environment',{}).items() if v is not None})
        if (_environment(config.get('Env'))!=expected_env or config.get('User','')!=_image_default(service,'user',base,'User')
                or config.get('Cmd')!=_image_default(service,'command',base,'Cmd')
                or config.get('Entrypoint')!=_image_default(service,'entrypoint',base,'Entrypoint')
                or config.get('WorkingDir','')!=_image_default(service,'working_dir',base,'WorkingDir')):
            raise RuntimeError('completed_runtime_configuration_changed')
        if (host.get('RestartPolicy',{}).get('Name')!='no' or host.get('Privileged') is not False
                or host.get('ReadonlyRootfs') is not True or sorted(host.get('CapDrop') or [])!=['ALL']
                or host.get('CapAdd') or host.get('Devices') or host.get('DeviceRequests')
                or host.get('PidMode') or host.get('IpcMode') in {'host'} or host.get('UTSMode')
                or sorted(host.get('SecurityOpt') or [])!=['no-new-privileges:true']
                or host.get('Dns') not in (None,[]) or host.get('Init')!=service.get('init',False)
                or host.get('Memory')!=int(service.get('mem_limit',0))
                or host.get('NanoCpus')!=round(float(service.get('cpus',0))*1_000_000_000)
                or ('pids_limit' in service and host.get('PidsLimit')!=service['pids_limit'])):
            raise RuntimeError('completed_runtime_security_changed')
        expected_tmpfs={}
        for entry in service.get('tmpfs',[]):
            target,separator,options=entry.partition(':')
            if not separator or target in expected_tmpfs:raise RuntimeError('completed_runtime_tmpfs_declaration_invalid')
            expected_tmpfs[target]=options
        if (host.get('Tmpfs') or {})!=expected_tmpfs:
            raise RuntimeError('completed_runtime_tmpfs_changed')
        health=dict(base.get('Healthcheck') or {})
        for key,value in service.get('healthcheck',{}).items():
            if key in {'interval','timeout','start_period','start_interval'}:
                health[{'interval':'Interval','timeout':'Timeout','start_period':'StartPeriod','start_interval':'StartInterval'}[key]]=_duration(value)
            elif key=='test':health['Test']=value
            elif key=='retries':health['Retries']=value
            elif key=='disable':
                if value:raise RuntimeError('completed_runtime_healthcheck_disabled')
            else:raise RuntimeError('completed_runtime_health_declaration_invalid')
        actual_health=config.get('Healthcheck') or {}
        if any(actual_health.get(key,0)!=health.get(key,0) for key in set(health)|set(actual_health)):
            raise RuntimeError('completed_runtime_healthcheck_changed')
        expected_ports={}
        for port in service.get('ports',[]):
            if port.get('host_ip')!='127.0.0.1':raise RuntimeError('completed_runtime_port_declaration_changed')
            expected_ports.setdefault(str(port['target'])+'/'+port.get('protocol','tcp'),[]).append(
                {'HostIp':'127.0.0.1','HostPort':str(port['published'])})
        if (host.get('PortBindings') or {})!=expected_ports:
            raise RuntimeError('completed_runtime_listener_changed')
        mounts={}
        for mount in row.get('Mounts',[]):
            if mount['Destination'] in mounts:raise RuntimeError('completed_runtime_mount_changed')
            mounts[mount['Destination']]=mount
        declared={volume['target']:volume for volume in service.get('volumes',[])}
        if set(mounts)!=set(declared):raise RuntimeError('completed_runtime_mount_inventory_changed')
        for target,expected in declared.items():
            actual=mounts[target]
            if (expected['type']!='bind' or actual['Type']!='bind' or actual['Source']!=expected['source']
                    or actual['RW']!=(not bool(expected.get('read_only',False)))):
                raise RuntimeError('completed_runtime_mount_changed')
        if release is RECONCILED and role=='parser-worker':
            uploads=declared.get('/app/private_uploads',{})
            verify_private_parser(row,source_sha=contract['candidate']['source_sha'],image=image,
                network_name=selected['networks']['parser'],uploads_root=uploads.get('source'))
        if release is RECONCILED and role=='provider-gateway':
            from deployment.lib.completed_normal_private_provider import verify_gateway
            verify_gateway(row,source_sha=contract['candidate']['source_sha'],image=image)
        if release is RECONCILED and role=='backend':
            from deployment.lib.completed_normal_private_provider import require_calendar_environment
            require_calendar_environment(expected_env,gateway_name=selected['containers']['provider-gateway'],
                system_identifier=contract['database']['system_identifier'])
        if role in {'backend',*BUSINESS}:
            from deployment.lib.completed_normal_profile import RECONCILED
            if release is RECONCILED and (
                    expected_env.get('MADAR_RELEASE_CONTROLLER_SHA')!=contract['candidate']['controller_sha']
                    or expected_env.get('MADAR_RELEASE_MIGRATION_MANIFEST_SHA256')!=contract['migration_manifest_sha256']):
                raise RuntimeError('completed_runtime_exact_maintenance_authority_changed')
            authority=declared.get('/run/madar/business-write-authority')
            if (authority is None or authority['source']!=str(ADMISSIONS/digest(contract)/'write-authority')
                    or not authority.get('read_only') or authority.get('bind',{}).get('create_host_path') is not False
                    or expected_env.get('MADAR_BUSINESS_WRITE_CONTRACT')!=digest(contract)
                    or expected_env.get('MADAR_BUSINESS_WRITE_AUTHORITY')!='/run/madar/business-write-authority/authority.json'
                    or expected_env.get('SCHEMA_COMPATIBLE_MIN')!=str(release.minimum)
                    or expected_env.get('SCHEMA_COMPATIBLE_MAX')!=str(release.target)
                    or expected_env.get('SCHEMA_EXCLUDED_VERSIONS','')!=','.join(map(str,release.excluded))):
                raise RuntimeError('completed_runtime_authority_mount_changed')
        expected_networks={model['networks'][key]['name'] for key in service.get('networks',{})}
        if release is RECONCILED and role=='backend' and 'madar-supabase-client' not in expected_networks:
            raise RuntimeError('completed_private_calendar_network_missing')
        attached=row['NetworkSettings']['Networks']
        if set(attached)!=expected_networks or host.get('NetworkMode') not in expected_networks:
            raise RuntimeError('completed_runtime_network_attachment_changed')
        for key,definition in service.get('networks',{}).items():
            net=model['networks'][key]['name'];definition=definition or {}
            aliases=sorted({name,role,*definition.get('aliases',[])})
            endpoint=attached[net]
            declared_only=phase in {'fenced','provisional'} or (phase=='staged' and role in BUSINESS)
            attachment_ok=(endpoint.get('NetworkID')==network_ids[net] and bool(endpoint.get('IPAddress')))
            if declared_only:
                attachment_ok=(endpoint.get('NetworkID') in {'',network_ids[net]}
                    and not endpoint.get('IPAddress') and not endpoint.get('EndpointID'))
            if (not attachment_ok or sorted(endpoint.get('Aliases') or [])!=aliases):
                raise RuntimeError('completed_runtime_network_role_changed')
        bindings[role]={'id':row['Id'],'image':image,'spec_sha256':measured_spec(row),
            'networks':{net:network_ids[net] for net in attached},
            'network_aliases':{net:attached[net].get('Aliases') or [] for net in attached}}
    # Complete every specification/security check before treating startup as
    # transient. Docker HTTP health may succeed before its first healthcheck
    # records healthy; that state cannot hide a changed image or attachment.
    if health_pending:raise AvailabilityFailure('completed_runtime_health_activation_pending')
    return bindings,network_ids


def converge_running_model(contract,model_loader,runtime,source_guard,*,admissions=ADMISSIONS,mode='READ_ONLY'):
    """One bounded deadline; unchanged starting health alone may converge."""
    with verification_window(runtime,180):
        while True:
            runtime.budget(1)
            source_guard();require_fresh_authorization(contract)
            from deployment.lib.completed_normal_admission import require_candidate_authority
            require_candidate_authority(contract,mode=mode,admissions=admissions)
            try:return validate_model(contract,model_loader(),runtime)
            except AvailabilityFailure:time.sleep(runtime.budget(1))

def seal_candidate_runtime(contract, *, source_guard,model_loader,runtime,state_root,admissions=ADMISSIONS,mode='READ_ONLY'):
    """The model loader must render frozen source against measured private env.

    The final frozen coordinator, not a child-written summary, supplies it.
    Historical workers run READ_ONLY. Exact160 maintenance seals only after its
    independently witnessed private NORMAL handoff and consumer-owner transfer.
    """
    if os.geteuid()!=0:raise RuntimeError('completed_runtime_root_required')
    if not callable(source_guard) or not callable(model_loader):raise RuntimeError('completed_runtime_independent_guards_required')
    from deployment.lib.completed_normal_admission import require_candidate_authority,require_maintenance_handoff
    from deployment.lib.completed_normal_profile import RECONCILED
    if mode not in {'READ_ONLY','NORMAL'} or mode=='NORMAL' and profile(contract) is not RECONCILED:
        raise RuntimeError('completed_runtime_sealing_mode_invalid')
    if mode=='NORMAL':require_maintenance_handoff(contract,admissions=admissions)
    source_guard();require_fresh_authorization(contract)
    require_candidate_authority(contract,mode=mode,admissions=admissions)
    root=Path(admissions)/digest(contract)
    with runtime_mutation_lock(Path(state_root)):
        source_guard();require_fresh_authorization(contract)
        runtimes,networks=converge_running_model(contract,model_loader,runtime,source_guard,admissions=admissions,mode=mode)
        if mode=='NORMAL':
            # A fresh container with identical image/configuration is still not
            # the candidate whose original application was privately accepted.
            stage=json.loads(protected(root/'candidate-staged-runtime.json',private=True).read_bytes())
            if any(runtimes[k]['id']!=stage['runtimes'][k]['id'] or runtimes[k]['image']!=stage['runtimes'][k]['image']
                    or runtimes[k]['networks']!=stage['runtimes'][k]['networks']
                    or runtimes[k]['network_aliases']!=stage['runtimes'][k]['network_aliases'] for k in candidate_roles(contract)):
                raise RuntimeError('completed_runtime_private_candidate_substituted')
        owner=load_worker_authority(Path(state_root))
        legacy=profile(contract) is LEGACY
        original=json.loads(protected(Path(contract['source_roles']['completion_root'])/
            ('candidate-identities.json' if legacy else 'candidate-runtime.json'),private=True).read_text())
        origin_workers=[original['runtimes'][role]['id'] for role in
            (('notification','calendar-sync','data-deletion') if legacy else BUSINESS)]
        publication={'operation':profile(contract).operation,'context_sha256':digest(contract),'source_sha':contract['candidate']['source_sha'],
            'images':contract['candidate']['images'],'runtimes':runtimes,'networks':networks,
            'worker_generation':owner['generation'] if owner else '', 'origin_workers':origin_workers}
        verify_runtime_binding(contract,publication,runtime,Path(state_root))
        require_candidate_authority(contract,mode=mode,admissions=admissions)
        source_guard()
        exclusive(root/'candidate-runtime.json',encoded(publication))
    return publication


def seal_candidate_stage(contract, *, source_guard,model_loader,runtime,state_root,admissions=ADMISSIONS):
    """Seal independently modeled resources BEFORE retiring the old workers.

    All three accepted business workers must be CREATED. The exact record also
    provides a durable recovery target if interruption follows owner transfer
    but precedes worker startup. It does not grant writes or transfer ownership.
    """
    from deployment.lib.completed_normal_admission import require_candidate_authority
    from deployment.lib.provider_recovery_runtime import readonly_configuration
    from deployment.lib.completed_normal_profile import DELETION, RECONCILED
    maintenance=contract.get('operation') in {DELETION.operation, RECONCILED.operation}
    if maintenance:
        from deployment.lib.completed_normal_admission import validate_provider_preparation
        maintenance_profile=validate_provider_preparation(contract)
    if os.geteuid()!=0:raise RuntimeError('completed_runtime_root_required')
    if not callable(source_guard) or not callable(model_loader):raise RuntimeError('completed_runtime_independent_guards_required')
    root=Path(admissions)/digest(contract)
    source_guard();require_fresh_authorization(contract)
    require_candidate_authority(contract,mode='READ_ONLY',admissions=admissions)
    with runtime_mutation_lock(Path(state_root)):
        source_guard();require_fresh_authorization(contract)
        runtimes,networks=validate_model(contract,model_loader(),runtime,phase='provisional' if maintenance else 'staged')
        from deployment.lib.completed_normal_admission import prepared_path
        prepared=json.loads(readonly_configuration(prepared_path(contract,state_root,preparation150=maintenance),private=True).read_text())
        if (prepared.get('release_sha')!=contract['candidate']['source_sha']
                or prepared.get('candidate_slot')!=contract['candidate']['slot']
                or prepared.get('status')!=('candidate_created_fenced' if maintenance else 'candidate_validated_workers_inactive')
                or not isinstance(prepared.get('prepared_at'),str) or not prepared['prepared_at']):
            raise RuntimeError('completed_runtime_stage_record_changed')
        owner=load_worker_authority(Path(state_root))
        if (owner is None or owner['owner']!='CANDIDATE' or owner['generation']!=contract['origin']['worker_generation']
                or owner['candidate']!={'sha':contract['source_roles']['application_sha'],'slot':contract['origin']['slot']}):
            raise RuntimeError('completed_runtime_origin_owner_changed')
        selected=maintenance_profile if maintenance else profile(contract)
        legacy=selected is LEGACY
        original=json.loads(protected(Path(contract['source_roles']['completion_root'])/
            ('candidate-identities.json' if legacy else 'candidate-runtime.json'),private=True).read_text())
        origin_workers=[original['runtimes'][role]['id'] for role in
            (('notification','calendar-sync','data-deletion') if legacy else BUSINESS)]
        publication={'operation':selected.operation,'context_sha256':digest(contract),'source_sha':contract['candidate']['source_sha'],
            'images':contract['candidate']['images'],'runtimes':runtimes,'networks':networks,
            'worker_generation':hashlib.sha256(f"bootstrap:{prepared['release_sha']}:{prepared['candidate_slot']}:{prepared['prepared_at']}".encode()).hexdigest(),
            'origin_workers':origin_workers}
        if maintenance:
            publication['preparation_mode']='created-fenced'
            selected_names=allocation(contract,contract['candidate']['slot'],preparation150=True)['containers']
            for role,record in publication['runtimes'].items():record['name']=selected_names[role]
        source_guard()
        exclusive(root/'candidate-staged-runtime.json',encoded(publication))
    return publication
