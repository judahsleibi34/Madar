"""Read-only, fixed-path observations for fresh active-rollback authorization.

No configuration values are returned; only file/tree hashes. No historical PASS
or volatile credential is read. This observation cannot authorize a mutation.
"""
import hashlib
import json
from pathlib import Path

from deployment.lib.provider_recovery_runtime import protected,readonly_configuration,file_digest

CONTROL=Path('/opt/madar/control-plane/deployment')
LOCAL=Path('/var/lib/madar-control-plane/local-provider-transition')
RECOVERY=Path('/var/lib/madar-control-plane/provider402')
STATE=Path('/var/lib/madar/releases')
NATIVE=Path('/opt/madar/local-supabase')
INPUTS={
    'recovery_transaction':STATE/'provider-recovery.json','local_transaction':LOCAL/'transaction.json',
    'recovery_contract':RECOVERY/'contract.json','schema_contract':RECOVERY/'schema-contract.json',
    'local_contract':LOCAL/'contract.json','write_authority':LOCAL/'write-authority/authority.json',
    'fallback':STATE/'provider-recovery-fallback.json','controller':CONTROL/'CONTROL_PLANE_SOURCE_SHA',
    'traffic':STATE/'provider-recovery-traffic.json','worker_authority':STATE/'worker-ownership.json',
    'release_state':STATE/'state.json','upstream':Path('/var/lib/madar/proxy/active-upstreams.conf'),
    'local_configuration':LOCAL/'configuration.env','native_configuration':NATIVE/'.env',
    'native_compose':NATIVE/'docker-compose.yml','native_override':NATIVE/'docker-compose.madar-local.yml',
    'production_configuration':Path('/etc/madar/production.env'),'backup_configuration':Path('/etc/madar/backup.env'),
    'proxy_configuration':CONTROL/'proxy/nginx.conf','proxy_compose':CONTROL/'proxy/docker-compose.yml',
    'gateway_bootstrap':NATIVE/'volumes/api/envoy/envoy.yaml','gateway_cds':NATIVE/'volumes/api/envoy/cds.yaml',
    'gateway_lds':NATIVE/'volumes/api/envoy/lds.template.yaml',
}
KEYS=frozenset(INPUTS)|{'controller_tree','runtime_dependencies'}
OPERATOR_CONFIGURATION=frozenset({'native_configuration','native_compose','native_override','production_configuration','backup_configuration',
    'release_state','gateway_bootstrap','gateway_cds','gateway_lds',
    'recovery_transaction','fallback','traffic','worker_authority','upstream'})
PRIVATE_CONFIGURATION=frozenset({'native_configuration','production_configuration','backup_configuration','local_configuration','release_state','recovery_transaction','fallback','traffic','worker_authority'})


def controller_tree_digest():
    """Pin all existing installed bytes, including retained bytecode, as data.

    No installed code is imported or executed. Future installation attestation
    separately requires source-only imports; this cannot legitimize old pyc.
    """
    entries=[]
    for path in sorted(CONTROL.rglob('*')):
        if path.is_symlink():raise RuntimeError('resumption_controller_tree_untrusted')
        st=path.lstat()
        if st.st_uid != 0 or st.st_mode&0o022 or not (path.is_file() or path.is_dir()):
            raise RuntimeError('resumption_controller_tree_untrusted')
        entries.append({'path':path.relative_to(CONTROL).as_posix(),'mode':st.st_mode&0o7777,
            'sha256':file_digest(protected(path)) if path.is_file() else None})
    # Include the fixed hierarchy even for an unexpectedly empty tree.
    protected(CONTROL/'CONTROL_PLANE_SOURCE_SHA')
    return hashlib.sha256(json.dumps(entries,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def observe_retained_inputs():
    result={}
    for key,path in INPUTS.items():
        # Canonical runtime state and native gateway data belong to the madar
        # runtime operator. Their hashes are inputs to a separately root-approved
        # plan, never authorization evidence. Contracts, journals, credentials
        # and positive business-write authorities retain strict root-only protection.
        # Existing runtime ownership/traffic/rollback files are observed data,
        # not independent protected execution or authorization evidence.
        reader=readonly_configuration if key in OPERATOR_CONFIGURATION else protected
        result[key]=file_digest(reader(path,private=key in PRIVATE_CONFIGURATION))
    result['controller_tree']=controller_tree_digest()
    result['runtime_dependencies']=observe_runtime_dependencies()[1]
    return result


def observe_runtime_dependencies(runtime=None):
    """Pin retained native, Redis and canonical slot resources without IPs.

    These are measured inputs, not permission to consume historical acceptance.
    The service set is fixed; the Redis namespace derives only from the already
    registered fallback. Public routing stays untouched throughout observation.
    """
    from deployment.lib.emergency_routing_repair import Runtime,identities,spec
    from deployment.lib.provider_recovery_runtime import SERVICES,digest
    runtime=runtime or Runtime()
    _,_,fallback,_=identities(runtime.input_bytes())
    suffix='-local-fallback-backend'
    if not fallback['backend'].endswith(suffix):raise RuntimeError('resumption_dependency_namespace_invalid')
    prefix=fallback['backend'][:-len(suffix)]
    canonical=tuple(f'madar-{slot}-{role}' for slot in ('blue','green')
        for role in ('backend','frontend','notification-worker','calendar-sync-worker','data-deletion-worker'))
    names=(*SERVICES,prefix+'-redis',*canonical)
    rows=runtime.inspect(list(names))
    if set(rows)!=set(names):raise RuntimeError('resumption_dependency_inventory_invalid')
    result={};network_names=set()
    for name in names:
        row=rows[name];running=row['State']['Running'];health=row['State'].get('Health',{}).get('Status')
        if name in SERVICES and (running is not True or health!='healthy'):
            raise RuntimeError('resumption_dependency_unhealthy')
        if name.endswith(('-notification-worker','-calendar-sync-worker','-data-deletion-worker')) and running is not False:
            raise RuntimeError('resumption_existing_consumer_running')
        if name==prefix+'-redis':
            if running is not True or health not in {None,'healthy'} or runtime.command(['docker','exec',name,'redis-cli','PING'])!='PONG':
                raise RuntimeError('resumption_dependency_redis_unhealthy')
        network_map={key:value['NetworkID'] for key,value in row['NetworkSettings']['Networks'].items()}
        network_names.update(network_map)
        result[name]={'container_id':row['Id'],'image_id':row['Image'],'spec_sha256':spec(row),
            'running':running,'networks':network_map}
    networks=json.loads(runtime.command(['docker','network','inspect',*sorted(network_names)])) if network_names else []
    network_records={row['Name']:{key:row[key] for key in ('Id','Driver','Internal','IPAM','Options')} for row in networks}
    if set(network_records)!=network_names:raise RuntimeError('resumption_dependency_network_invalid')
    payload={'runtimes':result,'networks':network_records}
    return payload,digest(payload)


def verify_native_continuation_dependencies(plan,root,runtime=None):
    """Live native identity gate, with bounded boot availability classification.

    Only running/health transitions of unchanged approved native IDs are pending.
    Changed images/specifications/networks/configuration/schema always abort.
    """
    import json
    from deployment.lib.emergency_routing_repair import Runtime,AvailabilityFailure,spec
    from deployment.lib.provider_recovery_runtime import SERVICES,digest
    runtime=runtime or Runtime()
    for key in ('native_configuration','native_compose','native_override','gateway_bootstrap','gateway_cds','gateway_lds'):
        if file_digest(readonly_configuration(INPUTS[key],private=key in PRIVATE_CONFIGURATION))!=plan.retained_inputs[key]:
            raise RuntimeError('continuation_native_configuration_changed')
    packet=json.loads(protected(Path(root)/'runtime-dependencies.json',private=True).read_text())
    if digest(packet)!=plan.retained_inputs['runtime_dependencies']:
        raise RuntimeError('continuation_native_dependency_record_changed')
    rows=runtime.inspect(list(SERVICES));pending=False
    for name in SERVICES:
        row=rows[name];expected=packet['runtimes'][name]
        if (row['Id']!=expected['container_id'] or row['Image']!=expected['image_id']
                or spec(row)!=expected['spec_sha256']
                or {key:value['NetworkID'] for key,value in row['NetworkSettings']['Networks'].items()}!=expected['networks']):
            raise RuntimeError('continuation_native_runtime_identity_changed')
        if row['State']['Running'] is not True or row['State'].get('Health',{}).get('Status')!='healthy':pending=True
    if pending:raise AvailabilityFailure('continuation_native_activation_pending')
    runtime.schema()
    return {'schema':115,'native_services':len(SERVICES),'database_authority':'local'}
