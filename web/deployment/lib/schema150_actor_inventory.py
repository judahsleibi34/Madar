"""Pure source-bound schema150 actor inventory, not authority or discovery.

Callers must supply a root-protected independently measured inventory and ALL
actual Docker container rows. Exclusion proof hashes are references only: the
protected adapter must verify those proofs independently. This module neither
runs commands, opens supplied paths, changes roles nor attests systemd/sessions.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import PurePosixPath
import re

from deployment.lib.completed_normal_resources import measured_spec_matches
from deployment.lib.schema150_provider_lifecycle import digest, validate_binding

PHASES = ('prepared', 'fenced', 'private', 'active')
ATTEST_PHASES = PHASES + ('fencing-boundary', 'private-boundary', 'active-boundary')
PRIVATE_PROVIDER_ROLES = frozenset({'native:auth', 'native:rest', 'native:storage'})
# The private application is distinct from every queue/maintenance worker.
# Concrete effects additionally require the independently sealed candidate.
PRIVATE_CANDIDATE_ROLES = ('candidate:redis','candidate:backend','candidate:frontend')
PRIVATE_RUNTIME_ROLES = PRIVATE_PROVIDER_ROLES | frozenset(PRIVATE_CANDIDATE_ROLES)
NATIVE_NAMES = {
    'native:db': 'supabase-db', 'native:auth': 'supabase-auth', 'native:rest': 'supabase-rest',
    'native:storage': 'supabase-storage', 'native:realtime': 'realtime-dev.supabase-realtime',
    'native:pooler': 'supabase-pooler', 'native:meta': 'supabase-meta',
    'native:gateway': 'supabase-envoy', 'native:studio': 'supabase-studio',
    'native:functions': 'supabase-edge-functions', 'native:imgproxy': 'supabase-imgproxy',
}
SLOT_ROLES = ('backend', 'frontend', 'notification-worker', 'calendar-sync-worker', 'data-deletion-worker')
APP_ROLES = ('backend', 'frontend', 'redis', 'parser-worker', 'remote-ingestion-worker',
             'notification-worker', 'calendar-sync-worker', 'data-deletion-worker')
WORKER_ROLES = frozenset(role for role in APP_ROLES if role.endswith('-worker'))
CANONICAL_NAMES = {f'slot:{slot}:{role}': f'madar-{slot}-{role}'
                   for slot in ('blue', 'green') for role in SLOT_ROLES}
REQUIRED_ROLES = frozenset(NATIVE_NAMES) | frozenset(CANONICAL_NAMES) | {'proxy', 'fallback:backend', 'fallback:frontend'}
OPTIONAL_ROLES = frozenset(f'{generation}:{role}' for generation in ('origin', 'candidate') for role in APP_ROLES) | {'fallback:redis'}
SUPERVISOR_UNITS = frozenset({'madar-auto-deploy.service', 'madar-auto-deploy.timer',
    'madar-storage-reconcile.service', 'madar-storage-reconcile.timer', 'madar-release-proxy.service'})
OBJECT_ROOT_ROLES = frozenset({'database', 'provider_storage', 'builder_assets', 'private_uploads',
                              'generated_artifacts', 'avatars', 'datasets'})
REQUIRED_OBJECT_ROOTS = OBJECT_ROOT_ROLES - {'datasets'}
DEFAULT_NETWORK = 'madar-local-supabase_default'
CLIENT_NETWORK = 'madar-supabase-client'
REQUIRED_TARGET_NETWORKS = frozenset({DEFAULT_NETWORK, CLIENT_NETWORK})
CLIENT_APP_ROLES = frozenset({'backend', 'notification-worker', 'calendar-sync-worker', 'data-deletion-worker'})
MINIMUM_ROLES = frozenset({'postgres', 'authenticator', 'supabase_auth_admin', 'supabase_storage_admin'})
TOP_KEYS = {'version', 'binding_sha256', 'target_networks', 'target_credentials', 'containers',
            'roles', 'supervisors', 'object_roots', 'session_scope', 'exclusions'}
CONTAINER_KEYS = {'name', 'id', 'image', 'generation', 'source_sha', 'spec_sha256', 'mounts', 'networks', 'states'}


def _require(condition, code='schema150_actor_inventory_invalid'):
    if not condition: raise RuntimeError(code)


def _hex(value, length=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{'+str(length)+'}', value) is not None


def _image(value):
    return isinstance(value, str) and re.fullmatch('sha256:[0-9a-f]{64}', value) is not None


def _name(value):
    return isinstance(value, str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,159}', value) is not None


def _path(value):
    return (isinstance(value, str) and len(value) <= 4096 and value.startswith('/') and value != '/'
            and '\\' not in value and not any(ord(c) < 32 for c in value)
            and str(PurePosixPath(value)) == value and '..' not in PurePosixPath(value).parts)


def _detached(value):
    def primitive(item, depth=0):
        _require(depth <= 16)
        if item is None or type(item) in (bool, int): return
        if isinstance(item, str): _require(len(item) <= 16384); return
        if isinstance(item, list):
            _require(len(item) <= 2048)
            for child in item: primitive(child, depth+1)
            return
        if isinstance(item, dict):
            _require(len(item) <= 2048 and all(isinstance(key, str) for key in item))
            for key, child in item.items(): primitive(key, depth+1); primitive(child, depth+1)
            return
        raise RuntimeError('schema150_actor_inventory_primitive_invalid')
    primitive(value)
    body = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    _require(len(body.encode()) <= 4*1024*1024, 'schema150_actor_inventory_size_limit')
    return json.loads(body)


def binding_scope_digest(binding):
    """Noncircular scope: exclude context and inventory digests; final root binds both."""
    value = validate_binding(binding)
    return digest({key: item for key, item in value.items() if key not in {'context_sha256', 'inventory_sha256'}})


def inventory_digest(inventory):
    return digest(_detached(inventory))


def _mounts(rows):
    _require(isinstance(rows, list) and len(rows) <= 128)
    found = []
    for row in rows:
        _require(isinstance(row, dict) and set(row) == {'type', 'source', 'destination', 'read_only'})
        _require(isinstance(row['type'], str) and row['type'] in {'bind', 'volume'} and _path(row['source'])
                 and _path(row['destination']) and type(row['read_only']) is bool)
        found.append(row)
    _require(len({row['destination'] for row in found}) == len(found))
    return sorted(found, key=lambda row: row['destination'])


def _validate(inventory, binding=None):
    value = _detached(inventory)
    _require(isinstance(value, dict) and set(value) == TOP_KEYS and type(value['version']) is int and value['version'] == 1)
    _require(_hex(value['binding_sha256']))
    if binding is not None:
        binding = validate_binding(binding)
        _require(value['binding_sha256'] == binding_scope_digest(binding), 'schema150_actor_scope_changed')
        _require(inventory_digest(value) == binding['inventory_sha256'], 'schema150_actor_inventory_digest_changed')
    networks = value['target_networks']
    _require(isinstance(networks, dict) and REQUIRED_TARGET_NETWORKS <= set(networks) and len(networks) <= 32
             and all(_name(name) and _hex(identifier) for name, identifier in networks.items()))
    credentials = value['target_credentials']
    _require(isinstance(credentials, dict) and 1 <= len(credentials) <= 64
             and all(_name(name) and _hex(fingerprint) for name, fingerprint in credentials.items()))
    actors = value['containers']
    _require(isinstance(actors, dict) and REQUIRED_ROLES <= set(actors) <= REQUIRED_ROLES | OPTIONAL_ROLES)
    ids, names = [], []
    for logical, actor in actors.items():
        _require(isinstance(actor, dict) and set(actor) == CONTAINER_KEYS)
        _require(_name(actor['name']) and _hex(actor['id']) and _image(actor['image']) and _hex(actor['spec_sha256']))
        ids.append(actor['id']); names.append(actor['name'])
        if logical in NATIVE_NAMES:
            _require(actor['name'] == NATIVE_NAMES[logical] and actor['generation'] == 'native' and actor['source_sha'] is None)
        elif logical in CANONICAL_NAMES:
            _require(actor['name'] == CANONICAL_NAMES[logical] and actor['generation'] == 'canonical'
                     and (actor['source_sha'] is None or _hex(actor['source_sha'], 40)))
        elif logical == 'proxy':
            _require(actor['name'] == 'madar-release-proxy' and actor['generation'] == 'proxy' and actor['source_sha'] is None)
        else:
            generation, role = logical.split(':', 1)
            _require(actor['generation'] == generation and actor['name'].startswith('madar-') and _hex(actor['source_sha'], 40))
            if generation == 'candidate' and binding is not None:
                _require(actor['source_sha'] == binding['source_sha'], 'schema150_candidate_source_changed')
        actor['mounts'] = _mounts(actor['mounts'])
        _require(isinstance(actor['networks'], dict) and len(actor['networks']) <= 16
                 and all(_name(name) and _hex(identifier) for name, identifier in actor['networks'].items()))
        if logical in NATIVE_NAMES:
            _require(actor['networks'].get(DEFAULT_NETWORK) == networks[DEFAULT_NETWORK], 'schema150_native_network_scope_invalid')
        if logical == 'native:db':
            _require(set(actor['networks']) == {DEFAULT_NETWORK}, 'schema150_native_database_network_invalid')
        if (logical == 'native:gateway' or logical == 'fallback:backend'
                or logical.split(':')[0] in {'origin', 'candidate'} and logical.split(':')[-1] in CLIENT_APP_ROLES):
            _require(actor['networks'].get(CLIENT_NETWORK) == networks[CLIENT_NETWORK], 'schema150_client_network_scope_invalid')
        for name, identifier in actor['networks'].items():
            if name in networks:
                _require(identifier == networks[name], 'schema150_actor_network_scope_changed')
        _require(isinstance(actor['states'], dict) and set(actor['states']) == set(PHASES))
        for phase, state in actor['states'].items():
            _require(isinstance(state, dict) and set(state) == {'running', 'restarting', 'restart'}
                     and type(state['running']) is bool and state['restarting'] is False
                     and isinstance(state['restart'], str) and state['restart'] in {'no', 'always', 'unless-stopped', 'on-failure'})
            if logical == 'native:db': _require(state['running'])
            if phase in {'fenced', 'private'} and logical != 'native:db': _require(state['restart'] == 'no')
            if phase == 'fenced' and logical != 'native:db': _require(not state['running'])
            if phase == 'private' and logical in (set(NATIVE_NAMES) - {'native:db', *PRIVATE_PROVIDER_ROLES}) | {'proxy'}:
                _require(not state['running'])
            if phase in {'private', 'active'} and actor['generation'] in {'canonical', 'origin', 'fallback'}:
                _require(not state['running'] and state['restart'] == 'no')
            if phase == 'private' and logical.startswith('candidate:') and logical.split(':', 1)[1] in WORKER_ROLES:
                _require(not state['running'])
            if logical.startswith('candidate:') and phase != 'prepared': _require(state['restart'] == 'no')
        # Admit only states reachable by the fixed concrete adapter. It stops
        # all non-DB actors with restart=no, starts the private provider trio
        # and independently sealed private application, then accepted workers.
        prepared, fenced, private, active=(actor['states'][p] for p in PHASES)
        if logical == 'native:db':
            _require(all(state['restart']==prepared['restart'] for state in (fenced,private,active)),
                     'schema150_database_restart_preimage_changed')
        else:
            _require(active['restart']=='no','schema150_active_restart_not_reachable')
        if logical in PRIVATE_RUNTIME_ROLES:
            _require(private['running'] and active['running'],'schema150_private_provider_state_not_reachable')
        if logical=='proxy' or actor['generation']=='candidate':
            _require(active['running'],'schema150_normal_actor_not_active')
        if private['running']:
            _require(active['running'],'schema150_active_state_not_reachable')
    _require(len(ids) == len(set(ids)) and len(names) == len(set(names)))
    for generation in ('origin', 'candidate'):
        selected = {name for name in actors if name.startswith(generation+':')}
        _require(not selected or selected == {generation+':'+role for role in APP_ROLES})
    roles = value['roles']
    _require(isinstance(roles, dict) and MINIMUM_ROLES <= set(roles) and len(roles) <= 128)
    for name, role in roles.items():
        _require(_name(name) and isinstance(role, dict) and set(role) == {'login', 'attributes_sha256', 'memberships_sha256'}
                 and type(role['login']) is bool and _hex(role['attributes_sha256']) and _hex(role['memberships_sha256']))
    sessions = value['session_scope']
    _require(isinstance(sessions, dict) and set(sessions) == {'maintenance_role', 'writer_roles'}
             and sessions['maintenance_role'] == 'postgres' and roles['postgres']['login']
             and isinstance(sessions['writer_roles'], list) and all(_name(name) for name in sessions['writer_roles']) and len(sessions['writer_roles']) == len(set(sessions['writer_roles']))
             and set(sessions['writer_roles']) == {name for name, role in roles.items() if role['login'] and name != 'postgres'})
    supervisors = value['supervisors']
    _require(isinstance(supervisors, dict) and SUPERVISOR_UNITS <= set(supervisors) and len(supervisors) <= 32)
    for name, supervisor in supervisors.items():
        _require(isinstance(supervisor, dict) and set(supervisor) == {'fragment_sha256', 'dropins_sha256', 'container_ids', 'enabled', 'context_sha256'})
        _require(_hex(supervisor['fragment_sha256']) and _hex(supervisor['dropins_sha256'])
                 and isinstance(supervisor['enabled'], str) and supervisor['enabled'] in {'enabled', 'enabled-runtime', 'disabled', 'static', 'indirect', 'masked'}
                 and isinstance(supervisor['container_ids'], list) and all(_hex(item) for item in supervisor['container_ids']) and len(supervisor['container_ids']) == len(set(supervisor['container_ids']))
                 and set(supervisor['container_ids']) <= set(ids))
        if name in SUPERVISOR_UNITS: _require(supervisor['context_sha256'] is None)
        else:
            context = supervisor['context_sha256']
            _require(_hex(context) and name == 'madar-compatible-normal-boot-'+context[:12]+'.service', 'schema150_supervisor_namespace_invalid')
    roots = value['object_roots']
    _require(isinstance(roots, dict) and REQUIRED_OBJECT_ROOTS <= set(roots) <= OBJECT_ROOT_ROLES)
    for root in roots.values():
        _require(isinstance(root, dict) and set(root) == {'type', 'source', 'content_sha256'}
                 and isinstance(root['type'], str) and root['type'] in {'bind', 'volume'} and _path(root['source']) and _hex(root['content_sha256']))
    exclusions = value['exclusions']
    _require(isinstance(exclusions, dict) and len(exclusions) <= 1024 and not set(exclusions) & set(ids))
    for identifier, exclusion in exclusions.items():
        _require(_hex(identifier) and isinstance(exclusion, dict) and set(exclusion) == {'image', 'spec_sha256', 'proof_sha256'}
                 and _image(exclusion['image']) and _hex(exclusion['spec_sha256']) and _hex(exclusion['proof_sha256']))
    return value


def validate_inventory(inventory, binding):
    """Authenticate exact detached measurements; this issues no permission."""
    return _validate(inventory, binding)


def bind_staged_candidates(inventory, binding, stage, rows, *, phase):
    """Derive a measured view; never replace the admitted original inventory.

    The concrete caller must authenticate the root stage and its fresh issuer
    witness before calling. This pure function grants no authority. Its fixed
    lifecycle states cannot be supplied by the stage or discovered by name.
    """
    value=validate_inventory(inventory,binding)
    _require(phase in set(ATTEST_PHASES)-{'prepared'},'schema150_candidate_binding_boundary_invalid')
    _require(not any(k.startswith('candidate:') for k in value['containers']),
        'schema150_candidate_already_in_original_inventory')
    stage=_detached(stage)
    _require(stage.get('preparation_mode')=='created-fenced'
        and isinstance(stage.get('runtimes'),dict) and set(stage['runtimes'])==set(APP_ROLES),
        'schema150_candidate_fenced_preparation_required')
    _require(isinstance(rows,list) and len(rows)<=2048,'schema150_container_snapshot_invalid')
    observed={}
    for row in rows:
        _require(isinstance(row,dict) and _hex(row.get('Id')) and row['Id'] not in observed,
            'schema150_container_snapshot_invalid')
        observed[row['Id']]=row
    for role,sealed in stage['runtimes'].items():
        _require(isinstance(sealed,dict) and set(sealed)=={'id','image','spec_sha256','networks','network_aliases','name'},
            'schema150_private_candidate_identity_changed')
        actual=observed.get(sealed['id'])
        _require(actual is not None,'schema150_private_candidate_identity_changed')
        value['containers']['candidate:'+role]={
            'name':sealed['name'],'id':sealed['id'],'image':sealed['image'],
            'generation':'candidate','source_sha':binding['source_sha'],'spec_sha256':sealed['spec_sha256'],
            'mounts':_actual_mounts(actual),'networks':sealed['networks'],
            'states':{p:{'running':p=='active' or p=='private' and role not in WORKER_ROLES,
                         'restarting':False,'restart':'no'} for p in PHASES}}
    # Includes duplicate base/candidate IDs and names, mounts, source labels,
    # complete all-daemon snapshot, network IDs, and fixed phase restrictions.
    attest_containers(value,rows,phase=phase)
    return value


def _overlaps(left, right):
    a, b = PurePosixPath(left), PurePosixPath(right)
    return a == b or a in b.parents or b in a.parents


def _credential_hashes(row):
    env = row.get('Config', {}).get('Env') or []
    _require(isinstance(env, list) and len(env) <= 1024, 'schema150_container_environment_invalid')
    hashes = set()
    for entry in env:
        _require(isinstance(entry, str) and len(entry) <= 131072 and '=' in entry, 'schema150_container_environment_invalid')
        value = entry.split('=', 1)[1]
        if value: hashes.add(hashlib.sha256(value.encode()).hexdigest())
    return hashes


def _actual_mounts(row):
    mounts = row.get('Mounts')
    _require(isinstance(mounts, list) and len(mounts) <= 128, 'schema150_container_mounts_invalid')
    result = []
    for mount in mounts:
        _require(isinstance(mount, dict) and isinstance(mount.get('Type'), str) and mount.get('Type') in {'bind', 'volume'}
                 and _path(mount.get('Source')) and _path(mount.get('Destination')) and type(mount.get('RW')) is bool,
                 'schema150_container_mounts_invalid')
        result.append({'type': mount['Type'], 'source': mount['Source'], 'destination': mount['Destination'], 'read_only': not mount['RW']})
    _require(len({row['destination'] for row in result}) == len(result), 'schema150_container_mounts_invalid')
    return sorted(result, key=lambda item: item['destination'])


def _host_authority(row, mounts):
    host = row.get('HostConfig', {})
    _require(isinstance(host, dict), 'schema150_container_host_config_invalid')
    capabilities = host.get('CapAdd') or []
    _require(isinstance(capabilities, list) and all(isinstance(cap, str) for cap in capabilities),
             'schema150_container_capabilities_invalid')
    sensitive = ('/etc/madar', '/var/lib/madar-control-plane', '/opt/madar/control-plane',
                 '/var/run/docker.sock', '/run/docker.sock', '/var/lib/docker', '/var/lib/containerd')
    return (host.get('Privileged') is True or host.get('PidMode') == 'host'
            or host.get('NetworkMode') == 'host' or host.get('IpcMode') == 'host'
            or host.get('UTSMode') == 'host'
            or bool({cap.upper().removeprefix('CAP_') for cap in capabilities} & {'SYS_ADMIN', 'ALL'})
            or any(any(_overlaps(mount['source'], source) for source in sensitive) for mount in mounts))


def attest_containers(inventory, rows, *, phase):
    """Require a complete all-container snapshot, not filtered target discovery.

    The caller must prove snapshot completeness with the Docker daemon and
    independently verify exclusion proof references. Even a valid exclusion
    cannot authorize target-network, object-root or target-credential access.
    """
    _require(phase in ATTEST_PHASES, 'schema150_actor_phase_invalid')
    value = _validate(inventory)
    try:
        _require(len(json.dumps(rows, allow_nan=False).encode()) <= 64*1024*1024, 'schema150_container_snapshot_size_limit')
    except (TypeError, ValueError):
        raise RuntimeError('schema150_container_snapshot_invalid') from None
    _require(isinstance(rows, list) and 1 <= len(rows) <= 2048, 'schema150_container_snapshot_invalid')
    observed = {}
    for row in rows:
        _require(isinstance(row, dict) and _hex(row.get('Id')) and row['Id'] not in observed, 'schema150_container_snapshot_invalid')
        observed[row['Id']] = row
    actors = {actor['id']: (logical, actor) for logical, actor in value['containers'].items()}
    _require(set(observed) == set(actors) | set(value['exclusions']), 'schema150_container_snapshot_incomplete')
    for identifier, row in observed.items():
        networks = row.get('NetworkSettings', {}).get('Networks')
        _require(isinstance(networks, dict) and all(_name(name) and isinstance(endpoint, dict) for name, endpoint in networks.items()), 'schema150_container_networks_invalid')
        mounts = _actual_mounts(row)
        if identifier not in actors:
            exclusion = value['exclusions'][identifier]
            _require(row.get('Image') == exclusion['image'] and measured_spec_matches(row, exclusion['spec_sha256']), 'schema150_unrelated_identity_changed')
            _require(not _host_authority(row, mounts), 'schema150_unrelated_actor_has_host_authority')
            shared_network = any(name in value['target_networks'] or endpoint.get('NetworkID') in value['target_networks'].values()
                                 for name, endpoint in networks.items())
            shared_objects = any(_overlaps(mount['source'], root['source']) for mount in mounts for root in value['object_roots'].values())
            shared_credentials = bool(_credential_hashes(row) & set(value['target_credentials'].values()))
            _require(not (shared_network or shared_objects or shared_credentials), 'schema150_unrelated_actor_can_access_target')
            continue
        logical, actor = actors[identifier]
        state, host = row.get('State', {}), row.get('HostConfig', {})
        _require(isinstance(state, dict) and isinstance(host, dict), 'schema150_actor_state_changed')
        def matches(expected):
            return (state.get('Running') is expected['running'] and state.get('Restarting', False) is False
                    and host.get('RestartPolicy', {}).get('Name') == expected['restart'])
        if phase == 'fencing-boundary':
            expected = actor['states']['prepared'] if matches(actor['states']['prepared']) else actor['states']['fenced']
        elif phase == 'private-boundary':
            # This pure observation permits only the planned fixed private
            # roles. The concrete adapter separately verifies the root-sealed
            # stage and its credential witness before accepting candidates.
            expected = actor['states']['fenced']
            if logical in PRIVATE_RUNTIME_ROLES and matches(actor['states']['private']):
                expected = actor['states']['private']
        elif phase == 'active-boundary':
            expected = actor['states']['private'] if matches(actor['states']['private']) else actor['states']['active']
        else:
            expected = actor['states'][phase]
        _require(row.get('Name') == '/'+actor['name'] and row.get('Image') == actor['image'], 'schema150_actor_identity_changed')
        _require(state.get('Running') is expected['running'] and state.get('Restarting', False) is False
                 and host.get('RestartPolicy', {}).get('Name') == expected['restart'], 'schema150_actor_state_changed')
        normalized = copy.deepcopy(row)
        normalized['HostConfig']['RestartPolicy']['Name'] = actor['states']['prepared']['restart']
        _require(measured_spec_matches(normalized, actor['spec_sha256'], started_worker=logical.split(':')[-1] in WORKER_ROLES), 'schema150_actor_spec_changed')
        _require(mounts == actor['mounts'], 'schema150_actor_mounts_changed')
        _require(set(networks) == set(actor['networks']), 'schema150_actor_networks_changed')
        for name, endpoint in networks.items():
            network_id = endpoint.get('NetworkID')
            declared_only = not expected['running'] and network_id == ''
            _require(network_id == actor['networks'][name] or (declared_only and not endpoint.get('EndpointID') and not endpoint.get('IPAddress')),
                     'schema150_actor_network_identity_changed')
        # candidate:redis is an immutable third-party dependency, associated
        # with this source through the sealed runtime rather than a fabricated
        # Madar image label. ID/image/spec/mount/network checks above still
        # apply; the concrete adapter also requires the approved Redis digest.
        if actor['source_sha'] is not None and logical != 'candidate:redis':
            _require(row.get('Config', {}).get('Labels', {}).get('org.opencontainers.image.revision') == actor['source_sha'], 'schema150_actor_source_changed')
    return {'inventory_sha256': inventory_digest(value), 'phase': phase, 'containers': len(actors),
            'exclusion_proof_references': len(value['exclusions']), 'unknown_target_actors': 0,
            'supervisors_verified': False, 'database_roles_verified': False, 'sessions_verified': False,
            'production_authorization_issued': False}
