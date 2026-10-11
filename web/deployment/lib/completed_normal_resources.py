"""Non-destructive allocation shared by read-only preflight and staging.

Retained containers are never renamed, removed or reused by Compose. Their
stopped port declarations must match the fresh contract byte-for-byte.
"""
from __future__ import annotations
import ipaddress
import json
from deployment.lib.active_recovery_candidate import require_unreserved_ports
from deployment.lib.completed_normal_admission import digest

ROLES = ('backend','frontend','redis','parser-worker','remote-ingestion-worker',
         'notification-worker','calendar-sync-worker','data-deletion-worker')
NETWORK_KEYS = ('default','parser','remote_internal','remote_egress')
PORTS = {'blue': {'backend':'8101','frontend':'3100','redis':'6383'},
         'green': {'backend':'8201','frontend':'3200','redis':'6382'}}

def measured_spec(row):
    """New admission hashes bind mount objects independently of Docker order.

    Docker's Mounts response is an unordered inventory. Every complete mount
    object remains hashed, including source, destination and write permission;
    historical raw specification hashes are neither edited nor reinterpreted.
    """
    from deployment.lib.emergency_routing_repair import spec
    mounts=row.get('Mounts')
    if (not isinstance(mounts,list) or any(not isinstance(m,dict)
            or not isinstance(m.get('Destination'),str) or not m['Destination'] for m in mounts)
            or len({m['Destination'] for m in mounts})!=len(mounts)):
        raise RuntimeError('completed_normal_mount_inventory_invalid')
    host=dict(row['HostConfig'])
    if 'Dns' in host and host['Dns'] in (None,[]):host['Dns']=None
    return spec(dict(row,Mounts=sorted(mounts,key=lambda m:m['Destination']),HostConfig=host))


def measured_spec_matches(row, expected, *, started_worker=False):
    if measured_spec(row)==expected:return True
    if not started_worker or row['HostConfig'].get('OomKillDisable',False) is not None:return False
    return measured_spec(dict(row,HostConfig=dict(row['HostConfig'],OomKillDisable=False)))==expected


def origin_spec_matches(row, expected, *, started_worker=False):
    """Preserve the old digest while comparing only mount inventory ordering.

    The origin has five mounts. Bound the legacy search to six, reject duplicate
    destinations, and continue hashing ALL fields. This is used only for the
    independently attested six original services at their write-fence boundary.
    New native/candidate records always use measured_spec instead.
    """
    from deployment.lib.active_recovery_candidate import worker_spec_matches
    from itertools import permutations
    if worker_spec_matches(row,expected,started_worker=started_worker):return True
    measured_spec(row) # reject ambiguous mount inventories before comparison
    mounts=row['Mounts']
    if len(mounts)>6:return False
    return any(worker_spec_matches(dict(row,Mounts=list(order)),expected,started_worker=started_worker)
               for order in permutations(mounts))

def allocation(contract,slot):
    if slot not in PORTS: raise RuntimeError('completed_normal_allocation_slot_invalid')
    prefix='madar-schema136-'+digest(contract)[:16]
    resource=contract['resources'][slot]
    return {'prefix':prefix,'project':prefix+'-'+slot,
            'containers':{r:prefix+'-'+slot+'-'+r for r in ROLES},
            'networks':{k:prefix+'-'+slot+'-'+k.replace('_','-') for k in NETWORK_KEYS},
            'ports':dict(PORTS[slot]),'subnets':dict(resource['subnets']),
            'retired_port_declarations':resource['retired_port_declarations']}

def verify_allocation(contract,slot,runtime):
    result=allocation(contract,slot)
    ids=runtime.command(['docker','ps','-aq']).splitlines()
    rows=json.loads(runtime.command(['docker','inspect',*ids])) if ids else []
    if any(r['Name'].lstrip('/') in result['containers'].values() for r in rows):
        raise RuntimeError('completed_normal_allocation_container_occupied')
    nets=runtime.command(['docker','network','ls','-q']).splitlines()
    existing=json.loads(runtime.command(['docker','network','inspect',*nets])) if nets else []
    intended=[ipaddress.ip_network(cidr) for cidr in result['subnets'].values()]
    for net in existing:
        if net['Name'] in result['networks'].values():
            raise RuntimeError('completed_normal_allocation_network_occupied')
        for entry in (net.get('IPAM',{}).get('Config') or []):
            if entry.get('Subnet'):
                other=ipaddress.ip_network(entry['Subnet'])
                if any(n.version==other.version and n.overlaps(other) for n in intended):
                    raise RuntimeError('completed_normal_allocation_subnet_occupied')
    require_unreserved_ports(runtime,tuple(int(p) for p in result['ports'].values()),
                             retired=result['retired_port_declarations'])
    return result


def verify_runtime_binding(contract,publication,runtime,state_root):
    """Shared exact-runtime check for root boot and credential-bound routing."""
    from deployment.lib.completed_normal_admission import OPERATION
    from deployment.lib.runtime_authority import load_worker_authority
    if (set(publication)!={'operation','context_sha256','source_sha','images','runtimes','networks','worker_generation','origin_workers'}
            or publication['operation']!=OPERATION or publication['context_sha256']!=digest(contract)
            or publication['source_sha']!=contract['candidate']['source_sha']
            or publication['images']!=contract['candidate']['images']
            or set(publication['runtimes'])!=set(ROLES) or len(publication['origin_workers'])!=3):
        raise RuntimeError('compatible_boot_publication_changed')
    authority=load_worker_authority(state_root)
    if (authority is None or authority['owner']!='CANDIDATE'
            or authority['old']!={'sha':contract['source_roles']['application_sha'],'slot':contract['origin']['slot']}
            or authority['candidate']!={'sha':publication['source_sha'],'slot':contract['candidate']['slot']}
            or authority['generation']!=publication['worker_generation']):
        raise RuntimeError('compatible_boot_worker_owner_changed')
    old=runtime.inspect(publication['origin_workers'])
    if len(old)!=3 or any(r['State']['Running'] or r['HostConfig']['RestartPolicy']['Name']!='no' for r in old.values()):
        raise RuntimeError('compatible_boot_old_workers_not_inhibited')
    return verify_runtime_resources(contract,publication,runtime)


def verify_runtime_resources(contract,publication,runtime):
    """Identity-only part shared with the pre-handoff CREATED validation.

    This cannot authorize starts or traffic. Those callers additionally require
    their phase-specific, positive singleton worker ownership.
    """
    if (publication.get('context_sha256')!=digest(contract)
            or publication.get('source_sha')!=contract['candidate']['source_sha']
            or publication.get('images')!=contract['candidate']['images']
            or set(publication.get('runtimes',{}))!=set(ROLES)):
        raise RuntimeError('compatible_boot_publication_changed')
    rows=runtime.inspect([p['id'] for p in publication['runtimes'].values()])
    if len(rows)!=len(ROLES):raise RuntimeError('compatible_boot_inventory_changed')
    selected={}
    for kind,expected in publication['runtimes'].items():
        row=next((r for r in rows.values() if r['Id']==expected['id']),None)
        if (row is None or row['Image']!=expected['image'] or not measured_spec_matches(row,expected['spec_sha256'],
                started_worker=kind in {'notification-worker','calendar-sync-worker','data-deletion-worker'}
                    and row['State'].get('Status') in {'running','exited'})
                or row['HostConfig']['RestartPolicy']['Name']!='no'):
            raise RuntimeError('compatible_boot_runtime_identity_changed')
        image=contract['candidate']['redis_image'] if kind=='redis' else publication['images']['frontend' if kind=='frontend' else 'backend']
        if row['Image']!=image:raise RuntimeError('compatible_boot_runtime_image_changed')
        attached=row['NetworkSettings']['Networks']
        if set(attached)!=set(expected['networks']):raise RuntimeError('compatible_boot_network_changed')
        if not isinstance(expected.get('network_aliases'),dict) or set(expected['network_aliases'])!=set(attached):
            raise RuntimeError('compatible_boot_network_declarations_missing')
        for name,endpoint in attached.items():
            if sorted(endpoint.get('Aliases') or [])!=sorted(expected['network_aliases'][name]):
                raise RuntimeError('compatible_boot_network_alias_changed')
            if endpoint.get('NetworkID')!=expected['networks'][name]:
                if (row['State']['Running'] or endpoint.get('NetworkID')!='' or endpoint.get('EndpointID')
                        or endpoint.get('IPAddress') or row['State'].get('Status') not in {'created','exited'}):
                    raise RuntimeError('compatible_boot_network_changed')
        selected[kind]=row
    for name,identity in publication['networks'].items():
        objects=json.loads(runtime.command(['docker','network','inspect',name]))
        if len(objects)!=1 or objects[0]['Id']!=identity:raise RuntimeError('compatible_boot_network_object_changed')
    return selected
