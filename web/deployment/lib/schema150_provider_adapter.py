"""Concrete fixed-effect provider maintenance, subordinate to the root coordinator.

No CLI, approval issuer, SQL input, command input, or operational registration.
The inventory is protected measured data under the exact operation admission.
Every effect needs the existing fresh credential AND the coordinator's held locks.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit, unquote, parse_qs
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from deployment.lib.completed_normal_admission import (ADMISSIONS, digest as contract_digest,
    validate_provider_preparation150)
from deployment.lib.completed_normal_profile import DELETION
from deployment.lib.control_plane_upgrade_authorization import require_upgrade_authorization, UPGRADE_INTERLOCK
from deployment.lib.emergency_routing_repair import exclusive
from deployment.lib.provider_recovery_runtime import protected
from deployment.lib.schema150_provider_lifecycle import (validate_binding, digest, encoded, STEPS,
    FENCE_STEPS, PRIVATE_STEPS, ACTIVATE_STEPS)
from deployment.lib.schema150_release import QUIESCENCE_SQL, BACKGROUND_WRITER_SQL, require_target_protocols

LOCKS = (Path('/var/lib/madar-control-plane/upgrades/upgrade.lock'),
         Path('/var/lib/madar/releases/deploy.lock'))
UNITS = Path('/etc/systemd/system')
PROVIDER_NAMES = ('supabase-auth', 'supabase-rest', 'supabase-storage')
ROLE_SQL = """SELECT json_build_object(
 'roles',(SELECT coalesce(json_object_agg(rolname,to_jsonb(r)-'oid'),'{}'::json) FROM pg_authid r),
 'memberships',(SELECT coalesce(json_agg(json_build_object('role',roleid::regrole::text,
 'member',member::regrole::text,'grantor',grantor::regrole::text,'admin_option',admin_option,
 'inherit_option',inherit_option,'set_option',set_option) ORDER BY roleid::regrole::text,member::regrole::text),'[]'::json)
 FROM pg_auth_members));"""
SESSION_SQL = """SELECT coalesce(json_agg(json_build_object('pid',pid,'start',backend_start::text,
 'role',usename,'address',host(client_addr),'database',datname) ORDER BY pid),'[]'::json)
 FROM pg_stat_activity WHERE backend_type='client backend' AND pid<>pg_backend_pid();"""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def private_json(path):
    source = protected(path, private=True)
    if source.stat().st_size > 2 * 1024 * 1024:
        raise RuntimeError('schema150_provider_private_input_limit')
    return json.loads(source.read_bytes())


def require_owned_lock(descriptor, path):
    """Observe an already owned flock; never acquire a missing coordinator lock."""
    if type(descriptor) is not int or descriptor < 0:
        raise RuntimeError('schema150_provider_coordinator_lock_required')
    source = protected(path, private=True)
    current, expected = os.fstat(descriptor), source.stat()
    if (current.st_dev, current.st_ino) != (expected.st_dev, expected.st_ino):
        raise RuntimeError('schema150_provider_coordinator_lock_changed')
    records = Path('/proc/self/fdinfo/' + str(descriptor)).read_text().splitlines()
    if not any(re.search(r'\bFLOCK\s+ADVISORY\s+WRITE\s+' + str(os.getpid()) + r'\s+', row)
               for row in records if row.startswith('lock:')):
        raise RuntimeError('schema150_provider_coordinator_lock_not_held')


def _env(row):
    values = {}
    for raw in row['Config'].get('Env', []) or []:
        name, sep, value = raw.partition('=')
        if not sep or name in values: raise RuntimeError('schema150_provider_environment_ambiguous')
        values[name] = value
    return values


def require_provider_database_bindings(rows, database_id):
    """Bind each measured native provider URI to the measured database network.

    URI text never becomes a SQL/command argument. Provider HTTP success at the
    same schema version is insufficient proof of the intended database cluster.
    """
    databases = [r for r in rows if r.get('Id') == database_id]
    if len(databases) != 1:
        raise RuntimeError('schema150_provider_database_binding_missing')
    database = databases[0]
    if len(database.get('NetworkSettings',{}).get('Networks',{}))!=1:
        raise RuntimeError('schema150_provider_database_uri_scope_invalid')
    expected = {'supabase-rest': ('PGRST_DB_URI','authenticator'),
        'supabase-auth': ('GOTRUE_DB_DATABASE_URL','supabase_auth_admin'),
        'supabase-storage': ('DATABASE_URL','supabase_storage_admin')}
    for name, (key, role) in expected.items():
        services = [r for r in rows if r.get('Name','').lstrip('/') == name]
        if len(services) != 1:
            raise RuntimeError('schema150_provider_database_binding_missing')
        service = services[0]
        if set(service.get('NetworkSettings',{}).get('Networks',{}))!=set(database['NetworkSettings']['Networks']):
            raise RuntimeError('schema150_provider_database_uri_scope_invalid')
        host = service.get('HostConfig',{})
        if (host.get('ExtraHosts') or host.get('Dns') or host.get('DnsSearch')
                or host.get('NetworkMode') in ('host','none')
                or any(m.get('Destination') in ('/etc','/etc/hosts','/etc/resolv.conf','/etc/nsswitch.conf')
                       for m in service.get('Mounts',[]))):
            raise RuntimeError('schema150_provider_database_uri_scope_invalid')
        environment = _env(service)
        # libpq fills distinct omitted URI parameters from PG* environment (for
        # example PGHOSTADDR overrides DNS without changing the URI hostname).
        # PGRST_* is the reviewed PostgREST namespace, not ambient libpq input.
        if any(name.startswith('PG') and not name.startswith('PGRST_') for name in environment):
            raise RuntimeError('schema150_provider_database_uri_scope_invalid')
        raw = environment.get(key)
        try:
            uri = urlsplit(raw or '')
            options = parse_qs(uri.query, strict_parsing=True, keep_blank_values=True)
            if (uri.scheme not in ('postgres','postgresql') or uri.fragment
                    or uri.path != '/postgres' or unquote(uri.username or '') != role
                    or not uri.password or uri.port not in (None,5432)
                    or set(options)-{'sslmode'}
                    or any(v not in (['disable'],['require'],['verify-ca'],['verify-full']) for v in options.values())):
                raise ValueError('unexpected native database URI')
            targets = []
            for network, db in database['NetworkSettings']['Networks'].items():
                provider = service['NetworkSettings']['Networks'].get(network)
                if not provider or provider['NetworkID'] != db['NetworkID']:
                    continue
                aliases = set((db.get('Aliases') or []) + (db.get('DNSNames') or []))
                aliases.update({database['Name'].lstrip('/'),db.get('IPAddress')})
                if uri.hostname in aliases:
                    owners = set()
                    for other in rows:
                        peer = other['NetworkSettings']['Networks'].get(network)
                        if not peer or peer['NetworkID'] != db['NetworkID']: continue
                        names = set((peer.get('Aliases') or []) + (peer.get('DNSNames') or []))
                        names.update({other['Name'].lstrip('/'),peer.get('IPAddress')})
                        if uri.hostname in names: owners.add(other['Id'])
                    if owners != {database_id}:
                        raise ValueError('ambiguous measured database alias')
                    targets.append(db['NetworkID'])
            if len(set(targets)) != 1:
                raise ValueError('URI target not the measured database')
        except (ValueError,TypeError,KeyError):
            # Never expose URI credentials or private endpoint text in errors.
            raise RuntimeError('schema150_provider_database_uri_scope_invalid') from None
    return True


def role_measurements(snapshot):
    """Canonical private measurement, shared by preparation and native capture."""
    if not isinstance(snapshot, dict) or set(snapshot) != {'roles','memberships'}:
        raise RuntimeError('schema150_provider_role_snapshot_invalid')
    result={}
    for name, value in snapshot['roles'].items():
        if (not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,159}',name)
                or not isinstance(value,dict) or type(value.get('rolcanlogin')) is not bool):
            raise RuntimeError('schema150_provider_role_snapshot_invalid')
        memberships=sorted((r for r in snapshot['memberships'] if name in (r.get('role'),r.get('member'),r.get('grantor'))),key=encoded)
        result[name]={'login':value['rolcanlogin'],
            'attributes_sha256':digest({k:v for k,v in value.items() if k!='rolcanlogin'}),
            'memberships_sha256':digest(memberships)}
    return result


class Schema150ProviderAdapter:
    """Actual Docker/systemd/PostgreSQL effects using immutable accepted identities.

    source_guard is the existing frozen coordinator measurement; lock descriptors
    are borrowed, never created here. Verification/acceptance delegates are code
    owned existing coordinator boundaries, not operator PASS packets. Their final
    production wiring remains an independent registration prerequisite.
    """
    def __init__(self, contract, binding, runtime, *, source_guard, lock_descriptors,
                 acceptance_guard, activation_guard):
        validate_provider_preparation150(contract)
        self.contract = json.loads(json.dumps(contract))
        self.binding = validate_binding(binding)
        if (self.binding['context_sha256'] != contract_digest(contract)
                or self.binding['source_sha'] != contract['candidate']['source_sha']
                or self.binding['controller_sha'] != contract['candidate']['controller_sha']
                or self.binding['inventory_sha256'] != contract['writer_inventory_sha256']
                or self.binding['system_identifier'] != contract['database']['system_identifier']
                or not all(callable(f) for f in (source_guard, acceptance_guard, activation_guard))
                or not isinstance(lock_descriptors, tuple) or len(lock_descriptors) != 2):
            raise RuntimeError('schema150_provider_adapter_binding_invalid')
        self.runtime, self.source_guard = runtime, source_guard
        self.acceptance_guard, self.activation_guard = acceptance_guard, activation_guard
        self.lock_descriptors = lock_descriptors
        self.root = ADMISSIONS / self.binding['context_sha256']
        from deployment.lib.schema150_actor_inventory import validate_inventory
        self.inventory = validate_inventory(private_json(self.root / 'provider-inventory.json'), self.binding)
        if self.inventory['exclusions']:
            raise RuntimeError('schema150_provider_live_exclusion_proofs_required')
        self.barrier = self.root / 'provider-barrier.json'
        self.dropin_name = '99zzzzzz-schema150-' + self.binding['context_sha256'][:12] + '.conf'

    def require_authority(self, binding, *, purpose):
        if (binding != self.binding or purpose not in {*STEPS, 'prepare', 'fence', 'observe_quiescence',
                'prepare_private_activation', 'seal_private_acceptance', 'activate_after_grant', 'reconcile', 'backup', 'observe_activation'}
                or os.geteuid() != 0):
            raise RuntimeError('schema150_provider_effect_scope_invalid')
        self.source_guard()
        require_upgrade_authorization(self.binding['controller_sha'], required_operation=DELETION.operation,
            required_schema=146, required_context_digest=self.binding['context_sha256'], require_rehearsal=True)
        authority = private_json(UPGRADE_INTERLOCK)
        if (authority.get('status') != 'authorized_cycle'
                or authority.get('rehearsal_sha256') != self.contract['rehearsal_sha256']):
            raise RuntimeError('schema150_provider_fresh_authority_required')
        for descriptor, path in zip(self.lock_descriptors, LOCKS): require_owned_lock(descriptor, path)
        from deployment.lib.schema150_actor_inventory import validate_inventory
        if validate_inventory(private_json(self.root / 'provider-inventory.json'), binding) != self.inventory:
            raise RuntimeError('schema150_provider_inventory_changed')
        self._database_identity()
        from deployment.lib.schema150_provider_lifecycle import ProtectedProviderJournal
        records = ProtectedProviderJournal(self.root/'provider-journal').read()
        initial_fence = (purpose == 'fence' and len(records)==1
            and records[0]['event']=='prepared' and records[0]['payload'].get('binding')==binding
            and not self.barrier.exists())
        if purpose == 'prepare' or initial_fence: phase = 'prepared'
        elif purpose == 'observe_activation':
            activating = any(r['event'] in ('effect_intent','effect_complete')
                and r['payload'].get('step') in ACTIVATE_STEPS for r in records)
            phase = 'active-boundary' if activating else 'private-boundary'
        elif purpose in PRIVATE_STEPS or purpose in {'prepare_private_activation', 'seal_private_acceptance'}:
            phase = 'private-boundary'
        elif purpose in ACTIVATE_STEPS or purpose == 'activate_after_grant': phase = 'active-boundary'
        elif purpose == 'reconcile':
            pending = self._pending_step()
            phase = ('active-boundary' if pending in ACTIVATE_STEPS else
                     'private-boundary' if pending in PRIVATE_STEPS else 'fencing-boundary')
        else: phase = 'fencing-boundary'
        self._attest(phase)
        if purpose not in {'prepare', 'arm_boot_interlock'} and not initial_fence:
            if (purpose == 'clear_boot_interlock' or self._pending_step() == 'clear_boot_interlock') and not self.barrier.exists(): return
            self._verify_barrier()

    def _pending_step(self):
        from deployment.lib.schema150_provider_lifecycle import ProtectedProviderJournal
        records = ProtectedProviderJournal(self.root/'provider-journal').read()
        return records[-1]['payload'].get('step') if records and records[-1]['event']=='effect_intent' else None

    def _verify_barrier(self):
        record = private_json(self.root/'provider-journal'/'0000.json')
        preimage = record['payload']['preimage']
        if private_json(self.barrier) != {'binding':self.binding, 'preimage_sha256':digest(preimage)}:
            raise RuntimeError('schema150_provider_persistent_barrier_changed')
        expected = ('[Unit]\nConditionPathExists=!'+str(self.barrier)+'\n').encode()
        for name in self.inventory['supervisors']:
            path = UNITS/(name+'.d')/self.dropin_name
            if protected(path).read_bytes() != expected or str(path) not in self._unit(name)['DropInPaths'].split():
                raise RuntimeError('schema150_provider_effective_boot_barrier_missing')
            unit = json.loads(self.runtime.command(['busctl','--json=short','call',
                'org.freedesktop.systemd1','/org/freedesktop/systemd1',
                'org.freedesktop.systemd1.Manager','GetUnit','s',name]))
            if (not isinstance(unit,dict) or unit.get('type') != 'o'
                    or not isinstance(unit.get('data'),list) or len(unit['data']) != 1
                    or not isinstance(unit['data'][0],str)
                    or not re.fullmatch(r'/org/freedesktop/systemd1/unit/[A-Za-z0-9_]+',unit['data'][0])):
                raise RuntimeError('schema150_provider_effective_boot_unit_invalid')
            conditions = json.loads(self.runtime.command(['busctl','--json=short','get-property',
                'org.freedesktop.systemd1',unit['data'][0],'org.freedesktop.systemd1.Unit','Conditions']))
            # D-Bus a(sbbsi): type, trigger, negate, parameter, last result.
            # A substring, positive condition, or trigger cannot fence startup.
            if (not isinstance(conditions,dict) or conditions.get('type') != 'a(sbbsi)'
                    or not isinstance(conditions.get('data'),list)
                    or not any(isinstance(c,list) and len(c)==5 and c[0]=='ConditionPathExists'
                        and c[1] is False and c[2] is True and c[3]==str(self.barrier)
                        and type(c[4]) is int for c in conditions['data'])):
                raise RuntimeError('schema150_provider_effective_boot_condition_missing')

    def _rows(self):
        identifiers = self.runtime.command(['docker', 'ps', '-aq', '--no-trunc']).split()
        if not identifiers or len(identifiers) > 1024 or any(not re.fullmatch('[0-9a-f]{64}', x) for x in identifiers):
            raise RuntimeError('schema150_provider_container_inventory_unbounded')
        return json.loads(self.runtime.command(['docker', 'inspect', *identifiers]))

    def _row(self, name):
        rows = [r for r in self._rows() if r['Name'].lstrip('/') == name]
        expected = [r for r in self.inventory['containers'].values() if r['name'] == name]
        if len(rows) != 1 or len(expected) != 1 or rows[0]['Id'] != expected[0]['id'] or rows[0]['Image'] != expected[0]['image']:
            raise RuntimeError('schema150_provider_actor_substitution')
        return rows[0]

    def _sql(self, body):
        # Only internal constants and validated original preimages reach this method.
        identifier = self.contract['database']['container_id']
        return self.runtime.command(['docker', 'exec', '-i', identifier, 'psql', '-XqAt',
            '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', 'postgres'],
            input="SET search_path=pg_catalog,public,extensions; SET statement_timeout='10s'; SET lock_timeout='2s';\n" + body)

    def _database_identity(self):
        row = self._row('supabase-db')
        if row['Id'] != self.contract['database']['container_id'] or row['Image'] != self.contract['database']['image']:
            raise RuntimeError('schema150_provider_database_substitution')
        raw = json.loads(self._sql("BEGIN READ ONLY; SELECT json_build_array((SELECT system_identifier::text FROM pg_control_system()),"
            "(SELECT schema_version FROM public.application_schema_state WHERE contract_key='core')); COMMIT;"))
        if raw[0] != self.binding['system_identifier'] or type(raw[1]) is not int or raw[1] not in (146,147,148,149,150):
            raise RuntimeError('schema150_provider_database_identity_changed')
        return raw[1]

    def _attest(self, phase):
        from deployment.lib.schema150_actor_inventory import attest_containers
        rows=self._rows()
        proof=attest_containers(self.inventory, rows, phase=phase)
        if phase in ('private','private-boundary'):
            for row in rows:
                if row.get('Name','').lstrip('/') in PROVIDER_NAMES:self._private_ports(row)
        return proof

    @staticmethod
    def _private_ports(row):
        if (row.get('HostConfig',{}).get('PublishAllPorts')
                or row.get('HostConfig',{}).get('PortBindings')
                or any(row.get('NetworkSettings',{}).get('Ports',{}).values())):
            raise RuntimeError('schema150_provider_private_port_exposed')

    def _roles(self): return json.loads(self._sql('BEGIN READ ONLY;' + ROLE_SQL + 'COMMIT;'))
    def _sessions(self): return json.loads(self._sql('BEGIN READ ONLY;' + SESSION_SQL + 'COMMIT;'))

    def _known_sessions(self, sessions):
        roles = self.inventory['session_scope']['writer_roles']
        addresses = {v.get('IPAddress') for r in self._rows() for v in r['NetworkSettings']['Networks'].values()
                     if r['Id'] in {c['id'] for c in self.inventory['containers'].values()}}
        return all(r['role'] in roles and r['address'] in addresses and r['address'] is not None for r in sessions)

    def _unit(self, name):
        value = self.runtime.command(['systemctl', 'show', name, '--property=FragmentPath,DropInPaths,UnitFileState,ActiveState,SubState,Job,ExecMainPID,ControlPID', '--no-pager'])
        fields = dict(row.split('=',1) for row in value.splitlines() if '=' in row)
        fragment = Path(fields.get('FragmentPath',''))
        expected = self.inventory['supervisors'][name]
        if not fragment.is_absolute() or hashlib.sha256(protected(fragment).read_bytes()).hexdigest() != expected['fragment_sha256']:
            raise RuntimeError('schema150_provider_supervisor_fragment_changed')
        paths = fields.get('DropInPaths','').split()
        original = [p for p in paths if Path(p).name != self.dropin_name]
        actual = {p: hashlib.sha256(protected(Path(p)).read_bytes()).hexdigest() for p in original}
        if fields.get('UnitFileState') != expected['enabled']:
            raise RuntimeError('schema150_provider_supervisor_enablement_changed')
        if digest(actual) != expected['dropins_sha256']:
            raise RuntimeError('schema150_provider_supervisor_dropins_changed')
        return fields

    def _supervisors_stopped(self):
        for name in self.inventory['supervisors']:
            state=self._unit(name)
            if (state.get('ActiveState')!='inactive' or state.get('SubState')!='dead'
                    or state.get('Job')!='' or state.get('ExecMainPID')!='0' or state.get('ControlPID')!='0'):
                raise RuntimeError('schema150_provider_supervisor_not_quiescent')
        return True

    def _http(self, name, port, path, token):
        row = self._row(name)
        addresses = {n['IPAddress'] for n in row['NetworkSettings']['Networks'].values()
                     if n['NetworkID'] in self.inventory['target_networks'].values()}
        if len(addresses) != 1: raise RuntimeError('schema150_provider_endpoint_ambiguous')
        import ipaddress
        address = addresses.pop()
        if not ipaddress.ip_address(address).is_private: raise RuntimeError('schema150_provider_endpoint_not_private')
        opener = build_opener(ProxyHandler({}), NoRedirect())
        try:
            response = opener.open(Request('http://' + address + ':' + str(port) + path,
                headers={'Authorization':'Bearer ' + token, 'apikey':token}), timeout=5)
        except HTTPError as error: response = error
        with response:
            body = response.read(65537)
            if len(body)>65536: raise RuntimeError('schema150_provider_probe_response_limit')
            return response.status, json.loads(body) if body else None

    def positive_identity_probes(self, binding):
        self.require_authority(binding, purpose='prepare'); self._attest('prepared')
        require_provider_database_bindings(self._rows(),self.contract['database']['container_id'])
        rest = _env(self._row('supabase-rest'))
        auth = _env(self._row('supabase-auth'))
        storage = _env(self._row('supabase-storage'))
        token = storage.get('SERVICE_KEY') or storage.get('SUPABASE_SERVICE_KEY')
        anon = storage.get('ANON_KEY') or storage.get('SUPABASE_ANON_KEY')
        if not token or not anon or token == anon: raise RuntimeError('schema150_provider_scope_credentials_missing')
        from deployment.lib.schema148_consumers import foreign_service_credential
        if foreign_service_credential(token, rest.get('PGRST_JWT_SECRET')):
            raise RuntimeError('schema150_provider_scope_credential_mismatch')
        status, rows = self._http('supabase-rest',3000,
            '/application_schema_state?select=schema_version&contract_key=eq.core&limit=1',token)
        if status != 200 or rows != [{'schema_version':146}]: raise RuntimeError('schema150_provider_rest_positive_failed')
        denied,_=self._http('supabase-rest',3000,'/application_schema_state?select=schema_version&limit=1','invalid')
        if denied not in (401,403): raise RuntimeError('schema150_provider_rest_negative_failed')
        status, body = self._http('supabase-auth',9999,'/admin/users?page=1&per_page=1',token)
        if status != 200 or not isinstance(body,dict) or not isinstance(body.get('users'),list):
            raise RuntimeError('schema150_provider_auth_positive_failed')
        denied,_ = self._http('supabase-auth',9999,'/admin/users?page=1&per_page=1',anon)
        if denied not in (401,403): raise RuntimeError('schema150_provider_auth_scope_failed')
        status, body = self._http('supabase-storage',5000,'/bucket',token)
        denied,_ = self._http('supabase-storage',5000,'/bucket','invalid')
        if status != 200 or not isinstance(body,list) or denied not in (400,401,403):
            raise RuntimeError('schema150_provider_storage_scope_failed')
        return dict(binding_sha256=digest(binding),postgrest=True,auth_scope=True,storage_scope=True,database_scope=True)

    def capture_preimage(self, binding):
        self.require_authority(binding,purpose='prepare'); self._attest('prepared')
        roles, sessions = self._roles(), self._sessions()
        if role_measurements(roles) != self.inventory['roles']:
            raise RuntimeError('schema150_provider_measured_role_scope_changed')
        if not self._known_sessions(sessions): raise RuntimeError('schema150_provider_unknown_session')
        allowed = set(self.inventory['session_scope']['writer_roles']) | {'postgres'}
        if any(r['rolcanlogin'] and name not in allowed and not name.startswith('pg_') for name,r in roles['roles'].items()):
            raise RuntimeError('schema150_provider_unknown_login_role')
        if int(self._sql('BEGIN READ ONLY;'+BACKGROUND_WRITER_SQL+';COMMIT;'))!=0:
            raise RuntimeError('schema150_provider_unknown_background_writer')
        units = {name:self._unit(name) for name in self.inventory['supervisors']}
        rows = self._rows();known={r['id'] for r in self.inventory['containers'].values()}
        states={r['Id']:{'running':r['State']['Running'],'restart':r['HostConfig']['RestartPolicy']['Name']}
                for r in rows if r['Id'] in known}
        archive = self.runtime.command(['docker','exec',self.contract['database']['container_id'],
            'pg_dumpall','-U','postgres','--roles-only'])
        if not archive.startswith('--') or len(archive.encode())>1024*1024:
            raise RuntimeError('schema150_provider_role_archive_invalid')
        return {'ingress':{'containers':states},'supervisors':{'units':units,'sessions':sessions},
            'objects':self._object_measurement(phase='identity'),
            'roles':{'original':roles,'archive':archive,'sha256':hashlib.sha256(archive.encode()).hexdigest()}}

    def _object_measurement(self, *, phase, previous=None):
        from deployment.lib.schema150_object_inventory import measure_roots
        return measure_roots(self.inventory['object_roots'],phase=phase,previous=previous)

    def _object_preservation(self, binding, preimage, *, capture=False):
        path=self.root/'provider-object-preservation.json'
        if path.exists() or path.is_symlink():
            record=private_json(path)
            if not isinstance(record,dict) or set(record)!={'binding','measurement'} or record['binding']!=binding:
                raise RuntimeError('schema150_provider_object_preimage_changed')
            previous=record['measurement']
            if (not isinstance(previous,dict) or type(previous.get('version')) is not int
                    or previous.get('version')!=1 or previous.get('phase')!='fenced'):
                raise RuntimeError('schema150_provider_object_preimage_changed')
        else:
            # Only the first fully fenced146 boundary may capture object bytes.
            # A lost/missing preimage after migration can never be reconstructed.
            from deployment.lib.schema150_provider_lifecycle import ProtectedProviderJournal
            records=ProtectedProviderJournal(self.root/'provider-journal').read()
            if not capture or self._database_identity()!=146 or any(r['event']=='quiescence' for r in records):
                raise RuntimeError('schema150_provider_object_preimage_required')
            previous=preimage['objects']
        actual=self._object_measurement(phase='fenced',previous=previous)
        if not path.exists(): exclusive(path,encoded({'binding':binding,'measurement':actual}))
        return actual

    def arm_boot_interlock(self, binding, preimage):
        self.require_authority(binding,purpose='arm_boot_interlock')
        # Publish persistent barrier BEFORE the first unit rewrite or Docker effect.
        exclusive(self.barrier, encoded({'binding':binding,'preimage_sha256':digest(preimage)}))
        for name in self.inventory['supervisors']:
            self._unit(name)
            directory=UNITS/(name+'.d')
            if not directory.exists(): directory.mkdir(mode=0o755)
            from deployment.lib.control_plane_upgrade import require_root_directory
            require_root_directory(directory)
            exclusive(directory/self.dropin_name, ('[Unit]\nConditionPathExists=!'+str(self.barrier)+'\n').encode())
        self.runtime.command(['systemctl','daemon-reload'])

    def _stop(self, predicate):
        # Verify the immutable source spec, including the preimage restart policy,
        # before normalizing only the separately controlled restart field.
        rows=self._rows();by_id={r['Id']:r for r in rows}
        from deployment.lib.completed_normal_resources import measured_spec_matches
        for record in self.inventory['containers'].values():
            if not predicate(record): continue
            row=by_id.get(record['id'])
            if row is None or row['Image']!=record['image']: raise RuntimeError('schema150_provider_stop_identity_changed')
            import copy
            normalized=copy.deepcopy(row)
            normalized['HostConfig']['RestartPolicy']['Name']=record['states']['prepared']['restart']
            if not measured_spec_matches(normalized,record['spec_sha256']):
                raise RuntimeError('schema150_provider_stop_spec_changed')
            self._attest('fencing-boundary')
            self.runtime.command(['docker','update','--restart=no',record['id']])
            if row['State']['Running']: self.runtime.command(['docker','stop','--time','15',record['id']])

    def fence_ingress(self,binding,preimage):
        self.require_authority(binding,purpose='fence_ingress')
        self._stop(lambda r:r['name']=='supabase-envoy' or r['name'].endswith('-frontend') or r['name']=='madar-release-proxy')

    def fence_supervisors(self,binding,preimage):
        self.require_authority(binding,purpose='fence_supervisors')
        for name in self.inventory['supervisors']:
            self._unit(name); self.runtime.command(['systemctl','stop',name])
        self._stop(lambda r:r['generation']!='native')

    def fence_objects(self,binding,preimage):
        self.require_authority(binding,purpose='fence_objects')
        self._stop(lambda r:r['generation']=='native' and r['name']!='supabase-db')

    def _expected_roles(self,preimage,*,fenced):
        import copy
        value=copy.deepcopy(preimage['roles']['original'])
        if fenced:
            for name in self.inventory['session_scope']['writer_roles']: value['roles'][name]['rolcanlogin']=False
        return value

    def fence_roles(self,binding,preimage):
        self.require_authority(binding,purpose='fence_roles')
        if self._roles()!=self._expected_roles(preimage,fenced=False):
            raise RuntimeError('schema150_provider_role_preimage_changed')
        names=self.inventory['session_scope']['writer_roles']
        self._sql('BEGIN;'+''.join('ALTER ROLE "'+name+'" NOLOGIN;' for name in names)+'COMMIT;')

    def drain_sessions(self,binding,preimage):
        self.require_authority(binding,purpose='drain_sessions')
        original=preimage['supervisors']['sessions']; deadline=time.monotonic()+10
        while True:
            sessions=self._sessions()
            if not sessions: return
            if any(s not in original for s in sessions): raise RuntimeError('schema150_provider_new_or_unknown_session')
            # Known service shutdown should close its sockets. A surviving client
            # is NOT silently killed with a PID-only primitive (PID reuse race).
            if time.monotonic()>=deadline: raise RuntimeError('schema150_provider_session_drain_incomplete')
            time.sleep(.2)

    def verify_effect(self,step,binding,preimage):
        self.require_authority(binding,purpose='reconcile')
        if step not in STEPS: raise RuntimeError('schema150_provider_unknown_effect')
        if step=='arm_boot_interlock':
            if private_json(self.barrier)!={'binding':binding,'preimage_sha256':digest(preimage)}: return False
            body=('[Unit]\nConditionPathExists=!'+str(self.barrier)+'\n').encode()
            for name in self.inventory['supervisors']:
                if protected(UNITS/(name+'.d')/self.dropin_name).read_bytes()!=body:return False
                fields=self._unit(name)
                if str(UNITS/(name+'.d')/self.dropin_name) not in fields['DropInPaths'].split():return False
            return True
        if step=='fence_roles':return self._roles()==self._expected_roles(preimage,fenced=True)
        if step=='drain_sessions':return not self._sessions()
        if step=='restore_roles_private':return self._roles()==self._expected_roles(preimage,fenced=False)
        if step in ('fence_ingress','fence_supervisors','fence_objects'):
            if step=='fence_supervisors':self._supervisors_stopped()
            rows={r['Id']:r for r in self._rows()}
            names=(lambda r:r['name']=='supabase-envoy' or r['name'].endswith('-frontend') or r['name']=='madar-release-proxy') if step=='fence_ingress' else (
                (lambda r:r['generation']!='native') if step=='fence_supervisors' else
                (lambda r:r['generation']=='native' and r['name']!='supabase-db'))
            return all(not rows[r['id']]['State']['Running'] and not rows[r['id']]['State'].get('Restarting')
                and rows[r['id']]['HostConfig']['RestartPolicy']['Name']=='no' for r in self.inventory['containers'].values() if names(r))
        if step=='resume_providers_private':
            self._attest('private');return True
        if step=='verify_native_acceptance':return self.acceptance_guard(binding,private=True) is True
        if step=='resume_accepted_workers':
            self._attest('active-boundary')
            rows={r['Id']:r for r in self._rows()}
            return all(rows[r['id']]['State']['Running'] is r['states']['active']['running']
                for r in self.inventory['containers'].values() if r['generation']=='candidate')
        if step=='restore_ingress':
            self._attest('active')
            return self.activation_guard(binding,private=False).get('public_acceptance') is True
        if step=='clear_boot_interlock':return not self.barrier.exists()
        return False

    def observe_quiescence(self,binding):
        self.require_authority(binding,purpose='observe_quiescence');self._attest('fenced')
        self._supervisors_stopped()
        # Native /proc visibility with a positive live PostgreSQL container PID.
        # This catches manual/docker-exec queue consumers absent from Config.Cmd;
        # broader dormant host writers remain a separate registration gate.
        from deployment.lib.schema149_consumers import verify_host_processes
        verify_host_processes(self.runtime,{r['id'] for r in self.inventory['containers'].values()},
            positive_pid=self._row('supabase-db')['State'].get('Pid'))
        value=json.loads(self._sql('BEGIN READ ONLY;'+QUIESCENCE_SQL+';COMMIT;'))
        records=private_json(self.root/'provider-journal'/'0000.json')
        preimage=records['payload']['preimage']
        if self._roles()!=self._expected_roles(preimage,fenced=True):raise RuntimeError('schema150_provider_roles_not_fenced')
        from deployment.lib.schema150_release import COUNTERS as DATABASE_COUNTERS
        if (not isinstance(value,dict) or value.get('system_identifier')!=binding['system_identifier']
                or any(type(value.get(k)) is not int or value[k]!=0 for k in DATABASE_COUNTERS)):
            raise RuntimeError('schema150_provider_database_not_quiescent')
        self._object_preservation(binding,preimage,capture=True)
        value.update(ingress_fenced=True,supervisors_fenced=True,objects_fenced=True,
            roles_fenced=True,boot_interlock_armed=self.barrier.exists(),candidate_read_only=self.activation_guard(binding,private=True).get('candidate_read_only') is True)
        return value

    def backup_role_archive(self, binding):
        """Return original full role bytes only under proven maintenance fencing.

        The ordinary backup coordinator must store this private archive, rather
        than mistake current NOLOGIN state for recoverable original role state.
        This does not create/publish a production backup or replica receipt.
        """
        observed=self.observe_quiescence(binding)
        from deployment.lib.schema150_provider_lifecycle import COUNTERS
        if any(type(observed.get(k)) is not int or observed[k] != 0 for k in COUNTERS):
            raise RuntimeError('schema150_provider_backup_not_quiescent')
        record=private_json(self.root/'provider-journal'/'0000.json')
        original=record['payload']['preimage']['roles']
        archive=original['archive'].encode()
        if hashlib.sha256(archive).hexdigest()!=original['sha256']:
            raise RuntimeError('schema150_provider_original_role_archive_changed')
        if role_measurements(original['original'])!=self.inventory['roles']:
            raise RuntimeError('schema150_provider_original_role_archive_scope_changed')
        return archive

    def activation_evidence(self,binding,preimage):
        self.require_authority(binding,purpose='observe_activation')
        # This boundary must independently validate receipts/backup/replica and
        # the existing issuer. A returned flag alone is never an issuer here.
        return self.activation_guard(binding,private=True)

    def observe_private_boundary(self,binding):
        self.require_authority(binding,purpose='prepare_private_activation')
        self._attest('private-boundary')
        self._supervisors_stopped()
        sessions=self._sessions()
        return {'binding_sha256':digest(binding),'ingress_fenced':True,'workers_fenced':True,
            'boot_interlock_armed':self.barrier.exists(),'candidate_read_only':self.activation_guard(binding,private=True).get('target_write_authority') is False,
            'unknown_writers':int(self._sql('BEGIN READ ONLY;'+BACKGROUND_WRITER_SQL+';COMMIT;')),
            'unknown_client_sessions':0 if self._known_sessions(sessions) else len(sessions),
            'prepared_transactions':int(self._sql('SELECT count(*) FROM pg_prepared_xacts;'))}

    def restore_roles_private(self,binding,preimage):
        self.require_authority(binding,purpose='restore_roles_private');self._attest('fenced')
        if self._database_identity()!=150 or self._sessions() or self._roles()!=self._expected_roles(preimage,fenced=True):
            raise RuntimeError('schema150_provider_private_restore_boundary_changed')
        self._object_preservation(binding,preimage)
        roles=preimage['roles']['original']['roles']
        self._sql('BEGIN;'+''.join('ALTER ROLE "'+n+'" '+('LOGIN' if roles[n]['rolcanlogin'] else 'NOLOGIN')+';'
            for n in self.inventory['session_scope']['writer_roles'])+'COMMIT;')

    def resume_providers_private(self,binding,preimage):
        self.require_authority(binding,purpose='resume_providers_private')
        if self._roles()!=self._expected_roles(preimage,fenced=False):raise RuntimeError('schema150_provider_original_roles_required')
        for name in PROVIDER_NAMES:
            row=self._row(name)
            self._private_ports(row)
            self.runtime.command(['docker','start',row['Id']])

    def verify_native_acceptance(self,binding,preimage):
        self.require_authority(binding,purpose='verify_native_acceptance')
        require_target_protocols(150,*json.loads(self._sql('SELECT json_build_array(public.notification_delivery_protocol(),'
            'public.notification_outbox_protocol(),public.data_deletion_ownership_protocol());')))
        if self.acceptance_guard(binding,private=True) is not True:raise RuntimeError('schema150_provider_native_acceptance_failed')

    def resume_accepted_workers(self,binding,preimage):
        self.require_authority(binding,purpose='resume_accepted_workers')
        # Existing accepted authority is verified, not created/replayed here.
        evidence=self.activation_guard(binding,private=False)
        if evidence.get('target_write_authority') is not True:raise RuntimeError('schema150_provider_target_authority_required')
        for record in self.inventory['containers'].values():
            if record['states']['active']['running'] and record['generation']=='candidate':
                self.runtime.command(['docker','start',record['id']])

    def restore_ingress(self,binding,preimage):
        self.require_authority(binding,purpose='restore_ingress')
        if self.activation_guard(binding,private=False).get('target_write_authority') is not True:
            raise RuntimeError('schema150_provider_target_authority_required')
        for record in self.inventory['containers'].values():
            if record['states']['active']['running'] and record['generation'] not in ('origin','fallback','canonical'):
                self.runtime.command(['docker','start',record['id']])

    def clear_boot_interlock(self,binding,preimage):
        self.require_authority(binding,purpose='clear_boot_interlock');self._attest('active')
        if self.activation_guard(binding,private=False).get('public_acceptance') is not True:
            raise RuntimeError('schema150_provider_public_acceptance_required')
        if private_json(self.barrier)!={'binding':binding,'preimage_sha256':digest(preimage)}:
            raise RuntimeError('schema150_provider_barrier_identity_changed')
        self.barrier.unlink()
        descriptor=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
