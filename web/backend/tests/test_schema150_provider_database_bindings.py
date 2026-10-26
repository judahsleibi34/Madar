"""Synthetic provider URI/cluster boundaries; no Docker, SQL or HTTP effects."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib import schema150_provider_adapter as adapter


DATABASE_ID = 'd' * 64
NETWORK_ID = 'a' * 64
PASSWORD = 'synthetic-private-password-do-not-report'
PROVIDERS = {
    'supabase-rest': ('PGRST_DB_URI', 'authenticator'),
    'supabase-auth': ('GOTRUE_DB_DATABASE_URL', 'supabase_auth_admin'),
    'supabase-storage': ('DATABASE_URL', 'supabase_storage_admin'),
}


def fixture():
    def row(identifier, name, address, aliases):
        return {'Id': identifier, 'Name': '/' + name, 'Image': 'sha256:' + 'e' * 64,
            'Config': {'Env': []}, 'NetworkSettings': {'Networks': {
                'native': {'NetworkID': NETWORK_ID, 'IPAddress': address,
                           'Aliases': aliases, 'DNSNames': [name]}}}}
    rows = [row(DATABASE_ID, 'supabase-db', '172.25.0.2', ['supabase-db', 'db'])]
    for index, (name, (key, role)) in enumerate(PROVIDERS.items(), 3):
        value = row(str(index) * 64, name, '172.25.0.' + str(index), [name])
        value['Config']['Env'] = [key + '=postgresql://' + role + ':' + PASSWORD + '@db:5432/postgres']
        rows.append(value)
    return rows


def provider(rows, name):
    return next(row for row in rows if row['Name'] == '/' + name)


def set_uri(rows, name, uri):
    provider(rows, name)['Config']['Env'] = [PROVIDERS[name][0] + '=' + uri]


class ProviderDatabaseBindingTests(unittest.TestCase):
    def rejected(self, rows, database_id=DATABASE_ID):
        with self.assertRaises(RuntimeError) as error:
            adapter.require_provider_database_bindings(rows, database_id)
        self.assertNotIn(PASSWORD, str(error.exception))
        self.assertNotIn('postgresql://', str(error.exception))
        self.assertNotIn('foreign-sensitive-host', str(error.exception))

    def test_ambient_libpq_overrides_cannot_escape_approved_database_uri(self):
        for key in ('PGHOSTADDR','PGHOST','PGSERVICE','PGSERVICEFILE','PGPASSFILE',
                    'PGOPTIONS','PGPORT','PGUSER','PGDATABASE','PGSSLMODE'):
            for name in PROVIDERS:
                with self.subTest(key=key,provider=name):
                    rows=fixture()
                    provider(rows,name)['Config']['Env'].append(key+'=synthetic-override')
                    self.rejected(rows)

    def test_secondary_network_alias_cannot_select_a_different_database(self):
        rows=fixture()
        provider(rows,'supabase-rest')['NetworkSettings']['Networks']['other']={
            'NetworkID':'b'*64,'IPAddress':'172.26.0.3','Aliases':['rest']}
        foreign=copy.deepcopy(rows[0]);foreign['Id']='f'*64;foreign['Name']='/foreign'
        foreign['NetworkSettings']['Networks']={'other':{
            'NetworkID':'b'*64,'IPAddress':'172.26.0.2','Aliases':['db']}}
        rows.append(foreign)
        self.rejected(rows)

    def test_all_three_native_provider_roles_bind_to_exact_measured_container(self):
        rows = fixture(); before = copy.deepcopy(rows)
        self.assertIs(adapter.require_provider_database_bindings(rows, DATABASE_ID), True)
        self.assertEqual(rows, before)

    def test_exact_container_name_alias_dns_name_and_ip_are_supported(self):
        for host in ('supabase-db', 'db', '172.25.0.2'):
            with self.subTest(host=host):
                rows = fixture()
                set_uri(rows, 'supabase-rest', f'postgres://authenticator:{PASSWORD}@{host}/postgres?sslmode=require')
                self.assertTrue(adapter.require_provider_database_bindings(rows, DATABASE_ID))

    def test_missing_or_duplicated_measured_database_and_provider_reject(self):
        for selection in ('missing-db', 'duplicate-db', 'missing-provider', 'duplicate-provider'):
            with self.subTest(selection=selection):
                rows = fixture()
                if selection == 'missing-db': rows.pop(0)
                elif selection == 'duplicate-db': rows.append(copy.deepcopy(rows[0]))
                elif selection == 'missing-provider': rows.pop()
                else: rows.append(copy.deepcopy(rows[-1]))
                self.rejected(rows)

    def test_foreign_cluster_at_same_schema_cannot_substitute_uri_target(self):
        # Schema is deliberately the same: URI identity must still fail.
        for name, (_, role) in PROVIDERS.items():
            with self.subTest(name=name):
                rows = fixture(); rows[0]['synthetic_schema_version'] = 146
                other = copy.deepcopy(rows[0]); other.update(Id='f'*64, Name='/foreign-sensitive-host')
                endpoint = other['NetworkSettings']['Networks']['native']
                endpoint.update(IPAddress='172.25.0.99', Aliases=['foreign-sensitive-host'], DNSNames=['foreign-sensitive-host'])
                rows.append(other)
                set_uri(rows, name, f'postgresql://{role}:{PASSWORD}@foreign-sensitive-host:5432/postgres')
                self.rejected(rows)

    def test_wrong_roles_ports_databases_and_missing_password_reject_for_each_provider(self):
        for name, (_, role) in PROVIDERS.items():
            for uri in (f'postgresql://postgres:{PASSWORD}@db:5432/postgres',
                        f'postgresql://{role}:{PASSWORD}@db:6543/postgres',
                        f'postgresql://{role}:{PASSWORD}@db:5432/another',
                        f'postgresql://{role}@db:5432/postgres',
                        f'postgresql://{role}:@db:5432/postgres'):
                with self.subTest(name=name, uri_kind=uri.split('@')[-1]):
                    rows = fixture(); set_uri(rows, name, uri); self.rejected(rows)

    def test_provider_must_share_exact_docker_network_identity(self):
        for missing in (False, True):
            rows = fixture(); networks = provider(rows, 'supabase-auth')['NetworkSettings']['Networks']
            if missing: networks.clear()
            else: networks['native']['NetworkID'] = 'b'*64
            self.rejected(rows)

    def test_provider_extra_hosts_cannot_override_the_attested_database_alias(self):
        for name in PROVIDERS:
            with self.subTest(name=name):
                rows = fixture()
                provider(rows, name)['HostConfig'] = {'ExtraHosts': ['db:172.25.0.99']}
                self.rejected(rows)

    def test_provider_mounted_name_resolution_files_do_not_prove_database_scope(self):
        for target in ('/etc', '/etc/hosts', '/etc/resolv.conf', '/etc/nsswitch.conf'):
            with self.subTest(target=target):
                rows = fixture()
                provider(rows, 'supabase-auth')['Mounts'] = [{'Type':'bind',
                    'Source':'/synthetic-untrusted-resolution', 'Destination':target, 'RW':False}]
                self.rejected(rows)

    def test_custom_dns_search_or_host_network_is_not_native_database_binding(self):
        for host in ({'Dns':['172.25.0.99']}, {'DnsSearch':['synthetic.invalid']},
                     {'NetworkMode':'host'}, {'NetworkMode':'none'}):
            with self.subTest(host=host):
                rows = fixture(); provider(rows, 'supabase-rest')['HostConfig'] = host
                self.rejected(rows)

    def test_uri_alias_matching_multiple_database_networks_is_ambiguous(self):
        rows = fixture()
        for value in rows:
            value['NetworkSettings']['Networks']['second'] = dict(
                value['NetworkSettings']['Networks']['native'], NetworkID='b'*64)
        self.rejected(rows)

    def test_database_alias_owned_by_foreign_container_on_same_network_rejects(self):
        for field in ('Aliases', 'DNSNames'):
            with self.subTest(field=field):
                rows = fixture(); other = copy.deepcopy(rows[0])
                other.update(Id='f'*64, Name='/foreign-sensitive-host')
                other['NetworkSettings']['Networks']['native'].update(
                    IPAddress='172.25.0.99', Aliases=['foreign-sensitive-host'], DNSNames=['foreign-sensitive-host'])
                other['NetworkSettings']['Networks']['native'][field].append('db')
                rows.append(other); self.rejected(rows)

    def test_nonblank_unsupported_or_repeated_query_parameters_reject(self):
        for suffix in ('?host=foreign-sensitive-host', '?port=6543', '?user=postgres',
                       '?sslmode=disable&sslmode=require', '?sslmode=prefer', '?options=-csearch_path=public'):
            with self.subTest(suffix=suffix):
                rows = fixture(); set_uri(rows, 'supabase-rest', f'postgresql://authenticator:{PASSWORD}@db:5432/postgres{suffix}')
                self.rejected(rows)

    def test_blank_unsupported_query_parameters_do_not_disappear_before_validation(self):
        for suffix in ('?host=', '?port=', '?user=', '?service=', '?options=', '?host=&sslmode=require'):
            with self.subTest(suffix=suffix):
                rows = fixture(); set_uri(rows, 'supabase-rest', f'postgresql://authenticator:{PASSWORD}@db:5432/postgres{suffix}')
                self.rejected(rows)

    def test_malformed_or_non_postgres_uri_and_environment_reject_without_secrets(self):
        for uri in ('not-a-uri', f'https://authenticator:{PASSWORD}@db/postgres',
                    f'postgresql://authenticator:{PASSWORD}@db:invalid/postgres',
                    f'postgresql://authenticator:{PASSWORD}@db/postgres#secret',
                    f'postgresql://authenticator:{PASSWORD}@db/postgres?invalid'):
            with self.subTest(uri_kind=uri.split('@')[-1]):
                rows = fixture(); set_uri(rows, 'supabase-rest', uri); self.rejected(rows)
        rows = fixture(); provider(rows, 'supabase-auth')['Config']['Env'] *= 2; self.rejected(rows)

    def test_positive_http_results_cannot_replace_measured_system_identifier(self):
        actor = adapter.Schema150ProviderAdapter.__new__(adapter.Schema150ProviderAdapter)
        rows = fixture()
        actor.contract = {'database': {'container_id': DATABASE_ID, 'image': rows[0]['Image']}}
        actor.binding = {'system_identifier': '123456789'}
        actor._row = lambda name: provider(rows, name)
        actor._rows = Mock(return_value=rows)
        actor._attest = Mock()
        actor._sql = Mock(return_value=json.dumps(['different-actual-cluster', 146]))
        actor._http = Mock(return_value=(200, [{'schema_version': 146}]))
        # Isolate authority issuance while preserving its actual database
        # identity measurement; no fake HTTP PASS may bypass that measurement.
        actor.require_authority = Mock(side_effect=lambda *_args, **_kwargs: actor._database_identity())
        with self.assertRaisesRegex(RuntimeError, 'database_identity_changed'):
            actor.positive_identity_probes(actor.binding)
        actor._http.assert_not_called()


if __name__ == '__main__':
    unittest.main()
