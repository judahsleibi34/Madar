"""Pure inventory: full synthetic Docker observations, no daemon or authority."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib import schema150_actor_inventory as inventory
from deployment.lib.completed_normal_resources import measured_spec


def binding():
    return {'operation': 'completed-normal-schema146-150-coordinated-release',
            'context_sha256': 'a'*64, 'source_sha': 'b'*40, 'controller_sha': 'c'*40,
            'inventory_sha256': 'd'*64, 'system_identifier': '123456789', 'source_schema': 146, 'target_schema': 150}


def row(identifier, name, *, running=False, restart='no', source=None):
    return {'Id': identifier, 'Name': '/'+name, 'Image': 'sha256:'+'e'*64,
            'Config': {'Env': ['FIXTURE=independent-synthetic-value'], 'Labels': {} if source is None else {'org.opencontainers.image.revision': source}},
            'HostConfig': {'RestartPolicy': {'Name': restart, 'MaximumRetryCount': 0}, 'Dns': None},
            'Mounts': [], 'State': {'Running': running, 'Restarting': False},
            'NetworkSettings': {'Networks': {}}}


def fixture(*, candidates=False):
    scope = binding()
    roles = dict(inventory.NATIVE_NAMES); roles.update(inventory.CANONICAL_NAMES)
    roles.update({'proxy': 'madar-release-proxy', 'fallback:backend': 'madar-provider402-local-fallback-backend',
                  'fallback:frontend': 'madar-provider402-local-fallback-frontend'})
    if candidates: roles.update({'candidate:'+role: 'madar-schema150-fixture-green-'+role for role in inventory.APP_ROLES})
    actors, rows = {}, []
    for index, (logical, name) in enumerate(sorted(roles.items()), 1):
        generation = ('native' if logical in inventory.NATIVE_NAMES else 'canonical' if logical in inventory.CANONICAL_NAMES
                      else 'proxy' if logical == 'proxy' else logical.split(':', 1)[0])
        source = None if generation in {'native', 'canonical', 'proxy'} else scope['source_sha']
        original = row(f'{index:064x}', name, running=generation in {'native', 'proxy'},
                       restart='unless-stopped' if generation in {'native', 'proxy'} else 'no', source=source)
        states = {}
        for phase in inventory.PHASES:
            running = (original['State']['Running'] if phase == 'prepared' else logical == 'native:db'
                       if phase == 'fenced' else (logical in {'native:db', *inventory.PRIVATE_PROVIDER_ROLES}
                           if phase == 'private' else generation in {'native', 'proxy'})
                       or (generation == 'candidate' and (phase == 'active' or logical.split(':', 1)[1] not in inventory.WORKER_ROLES)))
            restart = original['HostConfig']['RestartPolicy']['Name'] if phase == 'prepared' or logical == 'native:db' else 'no'
            states[phase] = {'running': running, 'restarting': False, 'restart': restart}
        networks = {}
        if generation == 'native': networks[inventory.DEFAULT_NETWORK] = '1'*64
        if logical in {'native:gateway', 'fallback:backend'} or generation == 'candidate' and logical.split(':')[-1] in inventory.CLIENT_APP_ROLES:
            networks[inventory.CLIENT_NETWORK] = '2'*64
        original['NetworkSettings']['Networks'] = {key: {'NetworkID': value, 'EndpointID': '', 'IPAddress': ''}
                                                   for key, value in networks.items()}
        actors[logical] = {'name': name, 'id': original['Id'], 'image': original['Image'], 'generation': generation,
                          'source_sha': source, 'spec_sha256': measured_spec(original), 'mounts': [], 'networks': networks, 'states': states}
        rows.append(original)
    data = {'version': 1, 'binding_sha256': inventory.binding_scope_digest(scope),
            'target_networks': {'madar-local-supabase_default': '1'*64, 'madar-supabase-client': '2'*64},
            'target_credentials': {'database_password': hashlib.sha256(b'synthetic-target-credential').hexdigest()},
            'containers': actors,
            'roles': {name: {'login': True, 'attributes_sha256': '3'*64, 'memberships_sha256': '4'*64}
                      for name in inventory.MINIMUM_ROLES},
            'supervisors': {name: {'fragment_sha256': '5'*64, 'dropins_sha256': '6'*64,
                                  'container_ids': [], 'enabled': 'enabled', 'context_sha256': None}
                            for name in inventory.SUPERVISOR_UNITS},
            'object_roots': {name: {'type': 'bind', 'source': '/synthetic-owned/'+name, 'content_sha256': '7'*64}
                             for name in inventory.REQUIRED_OBJECT_ROOTS},
            'session_scope': {'maintenance_role': 'postgres', 'writer_roles': sorted(inventory.MINIMUM_ROLES-{'postgres'})},
            'exclusions': {}}
    return repin(data, scope), rows


def repin(data, scope=None):
    scope = binding() if scope is None else copy.deepcopy(scope)
    data['binding_sha256'] = inventory.binding_scope_digest(scope)
    scope['inventory_sha256'] = inventory.inventory_digest(data)
    return data, scope


def phase_rows(data, rows, phase):
    result = copy.deepcopy(rows)
    by_id = {value['id']: value for value in data['containers'].values()}
    for actual in result:
        if actual['Id'] not in by_id: continue
        state = by_id[actual['Id']]['states'][phase]
        actual['State'].update(Running=state['running'], Restarting=state['restarting'])
        actual['HostConfig']['RestartPolicy']['Name'] = state['restart']
    return result


class ActorInventoryTests(unittest.TestCase):
    def test_exact_complete_inventory_detaches_and_authenticates_non_circular_binding(self):
        (data, scope), rows = fixture()
        validated = inventory.validate_inventory(data, scope)
        data['roles']['postgres']['login'] = False
        self.assertTrue(validated['roles']['postgres']['login'])
        # Final context can include the inventory hash without changing its scope.
        other = dict(scope, context_sha256='f'*64)
        inventory.validate_inventory(validated, other)
        for key in ('source_sha', 'controller_sha', 'system_identifier', 'operation', 'target_schema'):
            bad = dict(scope); bad[key] = '9'*40 if key.endswith('_sha') else '999' if key == 'system_identifier' else 'wrong'
            with self.subTest(key=key), self.assertRaises(RuntimeError): inventory.validate_inventory(validated, bad)
        bad = copy.deepcopy(validated); bad['roles']['authenticator']['login'] = False
        with self.assertRaisesRegex(RuntimeError, 'digest_changed'): inventory.validate_inventory(bad, scope)

    def test_all_phases_preserve_exact_image_spec_and_only_expected_restart_delta(self):
        (data, scope), rows = fixture(candidates=True)
        data = inventory.validate_inventory(data, scope)
        for phase in inventory.PHASES:
            result = inventory.attest_containers(data, phase_rows(data, rows, phase), phase=phase)
            self.assertEqual(result['unknown_target_actors'], 0)
            self.assertFalse(result['production_authorization_issued'])
            self.assertFalse(result['database_roles_verified'])
            self.assertFalse(result['supervisors_verified'])
            self.assertFalse(result['sessions_verified'])

    def test_missing_native_canonical_fallback_and_duplicate_identity_reject(self):
        (data, _), rows = fixture()
        for logical in ('native:pooler', 'slot:green:notification-worker', 'fallback:frontend', 'proxy'):
            bad = copy.deepcopy(data); bad['containers'].pop(logical); bad, scope = repin(bad)
            with self.subTest(logical=logical), self.assertRaises(RuntimeError): inventory.validate_inventory(bad, scope)
        bad = copy.deepcopy(data); bad['containers']['fallback:backend']['id'] = bad['containers']['proxy']['id']; bad, scope = repin(bad)
        with self.assertRaises(RuntimeError): inventory.validate_inventory(bad, scope)
        with self.assertRaisesRegex(RuntimeError, 'snapshot_incomplete'): inventory.attest_containers(data, rows[:-1], phase='prepared')
        with self.assertRaisesRegex(RuntimeError, 'snapshot_invalid'): inventory.attest_containers(data, rows+[rows[0]], phase='prepared')

    def test_native_names_and_reviewed_supervisor_namespace_are_finite(self):
        (data, _), rows = fixture()
        bad = copy.deepcopy(data); bad['containers']['native:auth']['name'] = 'unrelated-auth'; bad, scope = repin(bad)
        with self.assertRaises(RuntimeError): inventory.validate_inventory(bad, scope)
        for name in ('ssh.service', 'docker.service', 'madar-unknown.service'):
            bad = copy.deepcopy(data); bad['supervisors'][name] = copy.deepcopy(next(iter(data['supervisors'].values())))
            bad, scope = repin(bad)
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'supervisor_namespace'):
                inventory.validate_inventory(bad, scope)
        context = '8'*64; bad = copy.deepcopy(data)
        item = copy.deepcopy(next(iter(data['supervisors'].values()))); item['context_sha256'] = context
        bad['supervisors']['madar-compatible-normal-boot-'+context[:12]+'.service'] = item
        bad, scope = repin(bad); inventory.validate_inventory(bad, scope)

    def test_missing_login_role_scope_and_unknown_object_root_or_noncanonical_path_reject(self):
        (data, _), rows = fixture()
        mutations = [lambda value: value['session_scope']['writer_roles'].remove('authenticator'),
                     lambda value: value['roles'].pop('supabase_storage_admin'),
                     lambda value: value['object_roots'].update({'arbitrary': {'type': 'bind', 'source': '/tmp', 'content_sha256': '1'*64}}),
                     lambda value: value['object_roots']['provider_storage'].update(source='/'),
                     lambda value: value['object_roots']['provider_storage'].update(source='/synthetic-owned/../escape')]
        for mutate in mutations:
            bad = copy.deepcopy(data); mutate(bad); bad, scope = repin(bad)
            with self.assertRaises(RuntimeError): inventory.validate_inventory(bad, scope)

    def test_candidate_worker_or_old_actor_cannot_run_private_or_active(self):
        (data, _), rows = fixture(candidates=True)
        for logical, phase in (('candidate:notification-worker', 'private'), ('candidate:parser-worker', 'private'),
                               ('fallback:backend', 'active'), ('slot:blue:backend', 'private')):
            bad = copy.deepcopy(data); bad['containers'][logical]['states'][phase]['running'] = True; bad, scope = repin(bad)
            with self.subTest(logical=logical, phase=phase), self.assertRaises(RuntimeError): inventory.validate_inventory(bad, scope)
        bad = phase_rows(data, rows, 'private')
        selected = data['containers']['candidate:data-deletion-worker']['id']
        next(actual for actual in bad if actual['Id'] == selected)['State']['Running'] = True
        with self.assertRaisesRegex(RuntimeError, 'state_changed'): inventory.attest_containers(data, bad, phase='private')

    def test_same_names_wrong_image_environment_mount_network_or_source_reject(self):
        (data, _), rows = fixture(candidates=True)
        original = phase_rows(data, rows, 'private'); selected = data['containers']['candidate:backend']['id']
        for change in ('image', 'environment', 'mount', 'network', 'source'):
            bad = copy.deepcopy(original); actual = next(value for value in bad if value['Id'] == selected)
            if change == 'image': actual['Image'] = 'sha256:'+'0'*64
            elif change == 'environment': actual['Config']['Env'].append('EXTRA=source-substitution')
            elif change == 'mount': actual['Mounts'].append({'Type': 'bind', 'Source': '/unapproved', 'Destination': '/data', 'RW': True})
            elif change == 'network': actual['NetworkSettings']['Networks']['unapproved'] = {'NetworkID': '9'*64}
            else: actual['Config']['Labels']['org.opencontainers.image.revision'] = '0'*40
            with self.subTest(change=change), self.assertRaises(RuntimeError): inventory.attest_containers(data, bad, phase='private')

    def test_restart_policy_does_not_hide_other_host_configuration_substitution(self):
        (data, _), rows = fixture(); bad = phase_rows(data, rows, 'fenced')
        bad[0]['HostConfig']['Privileged'] = True
        with self.assertRaisesRegex(RuntimeError, 'spec_changed'): inventory.attest_containers(data, bad, phase='fenced')

    def excluded(self, *, network=False, objects=False, credential=False):
        (data, scope), rows = fixture()
        unrelated = row('f'*64, 'unrelated-owned-fixture')
        if network: unrelated['NetworkSettings']['Networks'] = {'alias': {'NetworkID': next(iter(data['target_networks'].values()))}}
        if objects: unrelated['Mounts'] = [{'Type': 'bind', 'Source': data['object_roots']['avatars']['source']+'/child', 'Destination': '/data', 'RW': False}]
        if credential: unrelated['Config']['Env'] = ['ANY_NAME=synthetic-target-credential']
        data['exclusions'][unrelated['Id']] = {'image': unrelated['Image'], 'spec_sha256': measured_spec(unrelated), 'proof_sha256': 'a'*64}
        data, scope = repin(data, scope)
        return data, rows+[unrelated]

    def test_unrelated_exclusion_requires_exact_identity_and_separate_proof_reference(self):
        data, rows = self.excluded()
        result = inventory.attest_containers(data, rows, phase='prepared')
        self.assertEqual(result['exclusion_proof_references'], 1)
        rows[-1]['Config']['Env'].append('MUTATION=unexpected')
        with self.assertRaisesRegex(RuntimeError, 'unrelated_identity_changed'): inventory.attest_containers(data, rows, phase='prepared')
        (plain, _), original = fixture(); original.append(row('f'*64, 'unlisted-fixture'))
        with self.assertRaisesRegex(RuntimeError, 'snapshot_incomplete'): inventory.attest_containers(plain, original, phase='prepared')

    def test_exclusion_proof_cannot_authorize_target_network_objects_or_credentials(self):
        for key in ('network', 'objects', 'credential'):
            data, rows = self.excluded(**{key: True})
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'can_access_target'):
                inventory.attest_containers(data, rows, phase='prepared')

    def test_strict_primitives_size_and_missing_measurements_fail_closed(self):
        (data, _), rows = fixture()
        for field, value in (('version', True), ('version', 1.0), ('version', float('nan'))):
            bad = copy.deepcopy(data); bad[field] = value
            with self.assertRaises(RuntimeError): inventory.validate_inventory(bad, binding())
        bad = copy.deepcopy(data); bad['exclusions'] = {'x': 'a'*16385}
        with self.assertRaises(RuntimeError): inventory.validate_inventory(bad, binding())
        bad = copy.deepcopy(data); bad['containers']['proxy']['states']['fenced']['restart'] = []
        bad, scope = repin(bad)
        with self.assertRaises(RuntimeError): inventory.validate_inventory(bad, scope)

    def test_private_boundary_accepts_only_exact_three_provider_state_alternatives(self):
        (data, _), rows = fixture(candidates=True)
        fenced = phase_rows(data, rows, 'fenced')
        inventory.attest_containers(data, fenced, phase='private-boundary')
        by_id = {actual['Id']: actual for actual in fenced}
        for logical in inventory.PRIVATE_PROVIDER_ROLES:
            by_id[data['containers'][logical]['id']]['State']['Running'] = data['containers'][logical]['states']['private']['running']
            inventory.attest_containers(data, fenced, phase='private-boundary')
        for logical in ('native:gateway', 'native:realtime', 'candidate:backend', 'candidate:data-deletion-worker'):
            bad = copy.deepcopy(fenced)
            next(actual for actual in bad if actual['Id'] == data['containers'][logical]['id'])['State']['Running'] = True
            with self.subTest(logical=logical), self.assertRaisesRegex(RuntimeError, 'state_changed'):
                inventory.attest_containers(data, bad, phase='private-boundary')
        bad = copy.deepcopy(fenced)
        next(actual for actual in bad if actual['Id'] == data['containers']['native:auth']['id'])['HostConfig']['RestartPolicy']['Name'] = 'always'
        with self.assertRaisesRegex(RuntimeError, 'state_changed'): inventory.attest_containers(data, bad, phase='private-boundary')

    def test_fencing_and_activation_boundaries_allow_only_exact_planned_pairs(self):
        (data, _), rows = fixture(candidates=True)
        prepared = phase_rows(data, rows, 'prepared')
        fenced = {actual['Id']: actual for actual in phase_rows(data, rows, 'fenced')}
        for index in range(len(prepared)):
            prepared[index] = copy.deepcopy(fenced[prepared[index]['Id']])
            inventory.attest_containers(data, prepared, phase='fencing-boundary')
        private = phase_rows(data, rows, 'private')
        active = {actual['Id']: actual for actual in phase_rows(data, rows, 'active')}
        for index in range(len(private)):
            private[index] = copy.deepcopy(active[private[index]['Id']])
            inventory.attest_containers(data, private, phase='active-boundary')
        bad = phase_rows(data, rows, 'prepared')
        actual = next(value for value in bad if value['Id'] == data['containers']['native:auth']['id'])
        actual['HostConfig']['RestartPolicy']['Name'] = 'no'  # Applied restart update, stop unproven.
        with self.assertRaisesRegex(RuntimeError, 'state_changed'): inventory.attest_containers(data, bad, phase='fencing-boundary')

    def test_private_inventory_never_broadens_unreviewed_native_or_proxy_startup(self):
        (data, _), rows = fixture()
        for logical in (set(inventory.NATIVE_NAMES)-{'native:db', *inventory.PRIVATE_PROVIDER_ROLES}) | {'proxy'}:
            bad = copy.deepcopy(data); bad['containers'][logical]['states']['private']['running'] = True
            bad, scope = repin(bad)
            with self.subTest(logical=logical), self.assertRaises(RuntimeError): inventory.validate_inventory(bad, scope)

    def test_exclusions_cannot_hide_privileged_host_namespace_or_credentials(self):
        for change in ('privileged', 'host-pid', 'host-network', 'sysadmin', 'docker-socket', 'credential-root'):
            data, rows = self.excluded(); actual = rows[-1]
            if change == 'privileged': actual['HostConfig']['Privileged'] = True
            elif change == 'host-pid': actual['HostConfig']['PidMode'] = 'host'
            elif change == 'host-network': actual['HostConfig']['NetworkMode'] = 'host'
            elif change == 'sysadmin': actual['HostConfig']['CapAdd'] = ['CAP_SYS_ADMIN']
            else:
                actual['Mounts'] = [{'Type': 'bind', 'Source': '/run/docker.sock' if change == 'docker-socket' else '/etc/madar/production.env', 'Destination': '/credentials', 'RW': False}]
            data['exclusions'][actual['Id']]['spec_sha256'] = measured_spec(actual)
            with self.subTest(change=change), self.assertRaisesRegex(RuntimeError, 'host_authority'):
                inventory.attest_containers(data, rows, phase='prepared')

    def test_native_and_client_networks_cannot_be_omitted_or_rebound(self):
        (data, _), rows = fixture(candidates=True)
        mutations = [lambda item: item['target_networks'].pop(inventory.DEFAULT_NETWORK),
                     lambda item: item['target_networks'].pop(inventory.CLIENT_NETWORK),
                     lambda item: item['containers']['native:db']['networks'].clear(),
                     lambda item: item['containers']['native:auth']['networks'].update({inventory.DEFAULT_NETWORK: 'f'*64}),
                     lambda item: item['containers']['native:gateway']['networks'].pop(inventory.CLIENT_NETWORK),
                     lambda item: item['containers']['fallback:backend']['networks'].pop(inventory.CLIENT_NETWORK),
                     lambda item: item['containers']['candidate:notification-worker']['networks'].pop(inventory.CLIENT_NETWORK)]
        for mutate in mutations:
            bad = copy.deepcopy(data); mutate(bad); bad, scope = repin(bad)
            with self.assertRaises(RuntimeError): inventory.validate_inventory(bad, scope)
