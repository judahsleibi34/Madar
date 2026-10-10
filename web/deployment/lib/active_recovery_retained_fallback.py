"""Explicit reuse of a compensated local release; historical R0 stays intact.

The retained release reads the ordinary backup directory. Its revoked authority
and stopped workers, not a historical backup marker or PASS summary, fence it.
No effect is performed by these independent observations.
"""
import json
from pathlib import Path
from deployment.lib.provider_recovery_runtime import protected, readonly_configuration, file_digest
from deployment.lib.emergency_routing_repair import spec, require

OPERATION='reuse-verified-compensated-local-release'

def declaration(plan):
    return ((getattr(plan,'candidate_destination',None) or {}).get('post_compensation') or {}).get('retained_fallback')

def verify_backup(plan):
    binding=declaration(plan)
    require(isinstance(binding,dict),'retained_fallback_contract_required')
    from deployment.lib.active_recovery_backup_freshness import BASE,require_publication
    from deployment.lib.active_recovery_resumption import ResumptionPlan
    producer=binding['backup_plan_sha256']
    base=Path('/var/lib/madar-control-plane/normal-local-preparation')
    auth=json.loads(protected(BASE/producer/'authorization.json',private=True).read_text())
    package=base/('normal-source-'+auth['source_bundle_sha256'])
    path=protected(package/'plan.json',private=True)
    prior=ResumptionPlan(**json.loads(path.read_text()));prior.validate()
    require(prior.digest==producer and file_digest(path)==producer,'retained_fallback_backup_plan_changed')
    require(file_digest(protected(BASE/producer/'verified-recovery-backup.json',private=True))==binding['backup_receipt_sha256']
        and file_digest(protected(BASE/producer/'publication.json',private=True))==binding['backup_publication_sha256'],
        'retained_fallback_backup_evidence_changed')
    # Independent current checksums, native restore and actual replica checks.
    # The producer's consumed permission is historical DATA, never execution.
    result=require_publication(prior,package,verify_availability=False)
    previous=plan.candidate_destination['post_compensation']['baseline']['previous_plan_sha256']
    from deployment.lib.active_recovery_compensated import inspect_history
    old,_,_,_=inspect_history(previous)
    require(result['captured_release_sha']==old.source_sha,'retained_fallback_backup_release_changed')
    return result

def verify_runtime(plan,runtime):
    binding=declaration(plan)
    require(binding and binding.get('operation')==OPERATION,'retained_fallback_contract_required')
    from deployment.lib.active_recovery_compensated import inspect_history
    baseline=plan.candidate_destination['post_compensation']['baseline']
    old,root,records,_=inspect_history(baseline['previous_plan_sha256'])
    require(file_digest(protected(root/'write-authority/authority.json'))==baseline['routing_restoration']['green_authority_sha256'],
        'retained_fallback_authority_bytes_changed')
    return verify_release(old,root,records,baseline['resources'],runtime)

def verify_release(old,root,records,resources,runtime):
    """Observe the exact already-revoked release; never infer a write grant."""
    authority=json.loads(protected(root/'write-authority/authority.json').read_text())
    require(authority.get('mode')=='READ_ONLY' and authority.get('schema')==115
        and authority.get('release_sha')==old.source_sha,'retained_fallback_write_authority_changed')
    owner=records['worker-owner.json'];slot=owner['authority']['candidate']['slot']
    names={role:'madar-'+slot+'-'+role for role in ('backend','frontend')}
    endpoints={};rows=runtime.inspect(list(names.values()))
    for role,name in names.items():
        row=rows[name];expected=resources[name]
        require(row['Id']==expected['container_id'] and row['Image']==expected['image_id']
            and row['Image']==old.candidate_images[role] and spec(row)==expected['spec_sha256']
            and row['State']['Running'] and row['HostConfig']['RestartPolicy']['Name']=='no'
            and row['Config'].get('Labels',{}).get('org.opencontainers.image.revision')==old.source_sha,
            'retained_fallback_runtime_changed')
        mappings=row['HostConfig'].get('PortBindings')
        port={'green':{'backend':8201,'frontend':3200},'blue':{'backend':8101,'frontend':3100}}[slot][role]
        require(mappings=={('8000' if role=='backend' else '8080')+'/tcp':[{'HostIp':'127.0.0.1','HostPort':str(port)}]},
            'retained_fallback_public_binding_changed')
        require({k:v['NetworkID'] for k,v in row['NetworkSettings']['Networks'].items()}==expected['networks'],
            'retained_fallback_network_changed')
        for name,attachment in row['NetworkSettings']['Networks'].items():
            network=runtime.network(name)
            require(network['Id']==attachment['NetworkID'] and network['Driver']=='bridge','retained_fallback_network_changed')
        endpoints[role]=('127.0.0.1',port)
    # Exactly the original three stopped workers. New workers may be validated
    # standbys during pre-grant observation; full forwarding checks ALL workers.
    workers=runtime.inspect([owner['active'][kind] for kind in ('notification','calendar-sync','data-deletion')])
    by_id={row['Id']:row for row in workers.values()}
    for kind in ('notification','calendar-sync','data-deletion'):
        row=by_id[owner['active'][kind]];expected=resources[f'madar-{slot}-{kind}-worker']
        require(row['Id']==expected['container_id'] and row['Image']==expected['image_id']
            and spec(row)==expected['spec_sha256'] and not row['State']['Running']
            and row['HostConfig']['RestartPolicy']['Name']=='no',
            'retained_fallback_old_consumer_running')
    runtime.schema();backend='http://%s:%d'%endpoints['backend']
    status,body=runtime.fetch(backend+'/health/ready');ready=json.loads(body);components=ready.get('components',{})
    worker_components={'notification_worker','calendar_sync_worker','data_deletion_worker'}
    require(status in (200,503) and all(components.get(key)=='ok' for key in (
        'environment','database','redis','auth','storage','schema','admin_mfa_policy','parser_isolation','backup_freshness'))
        and all(value in ('ok','disabled','configured','not_required','development')
            or (key in worker_components and value=='unavailable') for key,value in components.items()),
        'retained_fallback_core_unready')
    # A read-only fallback intentionally has no business consumers. Never report
    # this as NORMAL readiness or turn unavailable worker checks into PASS.
    for role in ('backend','frontend'):
        base='http://%s:%d'%endpoints[role]+('/api' if role=='frontend' else '')
        version=runtime.json_http(base+'/health/version')
        require(version.get('release_sha')==old.source_sha and version.get('release_slot')==slot
            and version.get('schema_compatible_min')==version.get('schema_compatible_max')==115,'retained_fallback_version_changed')
        require(runtime.json_http(base+'/health/recovery')=={'restricted':True,'business_writes_enabled':False},
            'retained_fallback_business_fence_failed')
        runtime.denied(base)
    runtime.http_status('http://%s:%d/'%endpoints['frontend'])
    latest=runtime.inspect([row['Id'] for row in rows.values()]);by_id={row['Id']:row for row in latest.values()}
    for row in rows.values():
        current=by_id[row['Id']]
        require(spec(current)==spec(row) and current['State']['Running']
            and current['NetworkSettings']['Networks']==row['NetworkSettings']['Networks'],'retained_fallback_changed_during_verification')
    return endpoints


def measure_routing_restoration(old,root,records,runtime):
    """Bind the consumed routing-only operation as data plus live observations.

    The immutable routing package supplies the previously verified resource
    inventory. Neither its approval nor its result grants this continuation.
    """
    import hashlib
    route_plan='ee19ed2d94d75cffa29cb9d30c80040b3a30a0ce1a5b0f4027dc51d2bae08430'
    driver_hash='134b39ab56eaaf65ace6e81fa821d068207f1318e9897ea3f35746f772d97555'
    producer='0c73460b3ca9a7fb98a711b3ae46143ca0f15813a700b7ba3adc3c6a3af15395'
    base=Path('/var/lib/madar-control-plane/normal-local-preparation')
    route_package=base/('existing-green-route-source-'+driver_hash)
    plan_path=protected(route_package/'plan.json',private=True)
    require(file_digest(plan_path)==route_plan and file_digest(protected(route_package/'driver.py',private=True))==driver_hash,
        'retained_routing_source_changed')
    binding=json.loads(plan_path.read_text())
    package=base/('normal-source-'+binding['source_package_sha256'])
    source_path=protected(package/'source-bundle.json',private=True)
    previous_path=protected(package/'plan.json',private=True)
    require(file_digest(source_path)==binding['source_package_sha256'] and file_digest(previous_path)==producer,
        'retained_routing_baseline_source_changed')
    prior=json.loads(previous_path.read_text())['candidate_destination']['post_compensation']
    from deployment.lib.provider_recovery_runtime import digest
    require(digest(prior['baseline'])==binding['baseline_sha256']
        and prior['baseline']['previous_plan_sha256']==old.digest
        and binding['application_sha']==old.source_sha and binding['images']==old.candidate_images,
        'retained_routing_release_changed')
    attempt=Path('/var/lib/madar-control-plane/emergency-existing-green-routing')/route_plan
    auth_path=protected(attempt/'authorization.json',private=True)
    result_path=protected(attempt/'result.json',private=True)
    auth=json.loads(auth_path.read_text());result=json.loads(result_path.read_text())
    require(auth.get('operation')=='emergency-existing-green-read-only-routing'
        and auth.get('plan_sha256')==route_plan and auth.get('source_sha256')==driver_hash
        and result.get('status')=='RECOVERY_ONLY' and result.get('normal_claimed') is False
        and result.get('business_writes_enabled') is False and result.get('all_six_workers_stopped') is True
        and result.get('application_sha')==old.source_sha and result.get('images')==old.candidate_images
        and result.get('schema')==115,'retained_routing_history_changed')
    require(file_digest(protected(root/'write-authority/authority.json'))==binding['green_authority_sha256'],
        'retained_routing_authority_changed')
    endpoints=verify_release(old,root,records,prior['baseline']['resources'],runtime)
    route=(f'upstream madar_backend_active {{ server {endpoints["backend"][0]}:{endpoints["backend"][1]}; }}\n'
        f'upstream madar_frontend_active {{ server {endpoints["frontend"][0]}:{endpoints["frontend"][1]}; }}\n').encode()
    require(hashlib.sha256(route).hexdigest()==binding['route_sha256'],'retained_routing_destination_changed')
    for url in ('https://madarportal.com/','https://api.madarportal.com/'):runtime.http_status(url)
    slot=records['worker-owner.json']['authority']['candidate']['slot']
    for base in ('http://127.0.0.1:8001','http://127.0.0.1:3000/api',
            'https://api.madarportal.com','https://madarportal.com/api'):
        version=runtime.json_http(base+'/health/version')
        require(version.get('release_sha')==old.source_sha and version.get('release_slot')==slot
            and version.get('schema_compatible_min')==version.get('schema_compatible_max')==115,
            'retained_public_release_changed')
        require(runtime.json_http(base+'/health/recovery')=={'restricted':True,'business_writes_enabled':False},
            'retained_public_fence_changed')
        runtime.denied(base)
    require(runtime.inspect(['madar-release-proxy'])['madar-release-proxy']['State'].get('Health',{}).get('Status')=='healthy',
        'retained_public_proxy_unhealthy')
    return route,{'plan_sha256':route_plan,'driver_sha256':driver_hash,
        'authorization_sha256':file_digest(auth_path),'execution_sha256':file_digest(result_path),
        'green_authority_sha256':binding['green_authority_sha256'],
        'route_sha256':hashlib.sha256(route).hexdigest()}
