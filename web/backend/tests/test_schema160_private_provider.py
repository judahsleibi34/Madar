"""The private provider is immutable, portless and has no write credential.

These pure and actual Compose-render tests grant no execution admission.
Native network/provider acceptance is executed separately on owned resources.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import shutil
import unittest
from unittest.mock import patch

from deployment.lib import completed_normal_private_provider as provider
from deployment.lib.completed_normal_resources import candidate_roles,allocation
from deployment.lib.completed_normal_profile import profile
from test_schema160_release import reconciled_contract
from test_schema160_private_parser import gateway_row,canonical_parser
from test_schema150_actor_inventory import fixture,phase_rows
from test_completed_normal_compose import cli,WEB


class PrivateProviderTests(unittest.TestCase):
    def test_gateway_is_a_canonical_only_candidate_not_an_admitted_profile(self):
        value=reconciled_contract()
        self.assertEqual(len(candidate_roles(value)),9)
        self.assertIn('provider-gateway',allocation(value,'green',preparation150=True)['containers'])
        with self.assertRaises(RuntimeError):profile(value)
        from test_schema150_admission import deletion_contract
        self.assertEqual(len(candidate_roles(deletion_contract())),8)

    def test_configuration_cannot_supply_authority_credentials_ports_mounts_or_an_extra_network(self):
        scope={'context_sha256':'a'*64,'source_sha':'b'*40};row=gateway_row(scope)
        def verify(value):provider.verify_gateway(value,source_sha=scope['source_sha'],image=row['Image'])
        verify(row)
        faults=[lambda r:r['Config']['Env'].append('SUPABASE_SERVICE_KEY=synthetic-forbidden'),
            lambda r:r['Config'].update(User='root'),lambda r:r['Config'].update(Cmd=['-g','daemon off;']),
            lambda r:r['HostConfig'].update(PortBindings={'8000/tcp':[{'HostIp':'0.0.0.0','HostPort':'18000'}]}),
            lambda r:r['Mounts'].append({'Type':'bind','Source':'/private','Destination':'/private','RW':False}),
            lambda r:r['HostConfig'].update(ExtraHosts=['supabase-db:192.0.2.1']),
            lambda r:r['HostConfig'].update(Privileged=True),lambda r:r['HostConfig'].update(Memory=0),
            lambda r:r['NetworkSettings']['Networks'].update({'foreign':{}})]
        for mutate in faults:
            bad=copy.deepcopy(row);mutate(bad)
            with self.assertRaises(RuntimeError):verify(bad)

    def test_calendar_is_exactly_cluster_and_gateway_bound_and_errors_do_not_expose_credentials(self):
        name='madar-schema160-'+'a'*16+'-green-provider-gateway'
        env={'SUPABASE_URL':'http://'+name+':8000',
            'MADAR_CALENDAR_DATABASE_DSN':'postgresql://authenticator:synthetic-private@'+name+':5432/postgres?sslmode=disable',
            'MADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER':'731'}
        provider.require_calendar_environment(env,gateway_name=name,system_identifier='731')
        for old,new in (('authenticator:','postgres:'),(name,'foreign-db'),('5432','6432'),
                ('/postgres?','/other?'),('sslmode=disable','sslmode=disable&hostaddr=192.0.2.1')):
            bad=dict(env,MADAR_CALENDAR_DATABASE_DSN=env['MADAR_CALENDAR_DATABASE_DSN'].replace(old,new))
            with self.assertRaisesRegex(RuntimeError,'calendar_transport_invalid') as error:
                provider.require_calendar_environment(bad,gateway_name=name,system_identifier='731')
            self.assertNotIn('synthetic-private',str(error.exception))
        with self.assertRaises(RuntimeError):provider.require_calendar_environment(env,gateway_name=name,system_identifier='732')

    def test_changed_dns_owner_or_calendar_target_blocks_the_actual_inventory_observer(self):
        from deployment.lib.schema150_actor_inventory import attest_containers
        (data,scope),rows=fixture(candidates=True);data,scope=canonical_parser(data,scope,rows)
        rows=phase_rows(data,rows,'private')
        attest_containers(data,rows,phase='private',binding=scope)
        other=next(r for r in rows if r['Id']==data['containers']['native:gateway']['id'])
        other['NetworkSettings']['Networks'][provider.CLIENT_NETWORK]['Aliases']=[data['containers']['candidate:provider-gateway']['name']]
        with self.assertRaisesRegex(RuntimeError,'dns_ambiguous'):
            attest_containers(data,rows,phase='private',binding=scope)

    def test_real_preauthorization_compose_contains_the_gateway_and_private_calendar_without_a_grant(self):
        import tempfile
        if not shutil.which('docker'):self.skipTest('actual Compose render runs separately on the Docker host')
        if subprocess.run(['docker','compose','version'],capture_output=True,timeout=10).returncode:
            self.skipTest('Compose plugin unavailable; separate host render required')
        with tempfile.TemporaryDirectory() as directory:
            contract=reconciled_contract();selected=allocation(contract,'green',preparation150=True)
            images={'backend':'backend@'+contract['candidate']['images']['backend'],
                'frontend':'frontend@'+contract['candidate']['images']['frontend'],
                'worker':'backend@'+contract['candidate']['images']['backend'],'build_timestamp':'2026-10-25T00:00:00Z'}
            config=Path(directory)/'synthetic.env';config.write_text('SUPABASE_URL=http://madar-supabase:8000\n')
            ops=cli.DockerGitOperations(WEB.parent,Path(directory),config,cli.Compatibility(146,160,160,'coordinated',160,160))
            ops.release_root=WEB.parent;ops.read_only_model_contract=contract;ops.completed_normal_admission=contract
            ops.schema_version=lambda:146;models=[]
            def render(args,**kwargs):
                self.assertEqual(args[-3:],['config','--format','json'])
                result=subprocess.run(args,capture_output=True,text=True,timeout=30,**kwargs)
                self.assertEqual(result.returncode,0,'synthetic Compose rendering failed')
                models.append(json.loads(result.stdout));return result.stdout
            ops.run=render;name=selected['containers']['provider-gateway']
            env={'MADAR_STORAGE_ROOT':str(Path(directory)/'storage'),
                'MADAR_CALENDAR_DATABASE_DSN':'postgresql://authenticator:synthetic@'+name+':5432/postgres?sslmode=disable',
                'MADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER':contract['database']['system_identifier']}
            with patch.dict(os.environ,env),patch('deployment.lib.completed_normal_admission.require_candidate_authority',side_effect=AssertionError('preauthorization must issue/read no grant')):
                ops._compose(contract['candidate']['source_sha'],'green',images,'config','--format','json',workers_active=True)
            services=models[0]['services'];self.assertEqual(set(services),set(candidate_roles(contract)))
            gateway=services['provider-gateway'];self.assertEqual(gateway['image'],images['frontend'])
            self.assertFalse(gateway.get('ports'));self.assertFalse(gateway.get('volumes'));self.assertFalse(gateway.get('environment'))
            self.assertEqual(set(gateway['networks']),{'supabase_client','provider_native'})
            self.assertEqual(services['backend']['environment']['SUPABASE_URL'],'http://'+name+':8000')
            for role in ('notification-worker','calendar-sync-worker','data-deletion-worker'):
                self.assertEqual(services[role]['environment']['MADAR_CALENDAR_DATABASE_DSN'],'')
            with self.assertRaises(RuntimeError):profile(contract)
