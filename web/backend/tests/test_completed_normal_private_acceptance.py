"""Guard source/input contracts; actual Auth/MFA/storage probes run in the VM."""
import copy,hashlib,json,os
from pathlib import Path
from types import SimpleNamespace
import tempfile,unittest
from unittest.mock import Mock,patch

from deployment.lib import completed_normal_private_acceptance as acceptance
from deployment.lib.completed_normal_admission import encoded
from test_schema160_release import reconciled_contract


def subjects():
    return [{'auth_id':f'{n:08x}-1111-2222-3333-444444444444','factor_id':f'{n:08x}-5555-6666-7777-888888888888',
        'user_id':n,'tenant_id':n,'email':f'owner{n}@example.invalid','password':'synthetic-password',
        'totp_secret':'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ','bucket':'owned-private',
        'object':f'{n}/fixture.bin','object_sha256':'a'*64} for n in (1,2)]


class PrivateAcceptanceGuardTests(unittest.TestCase):
    def actor(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        root=Path(temp.name);contract=reconciled_contract()
        packet={'version':1,'system_identifier':contract['database']['system_identifier'],'subjects':subjects()}
        data=encoded(packet);(root/'original-provider-probes.json').write_bytes(data)
        actor=SimpleNamespace(package=root,root=root,contract=contract,
            document={'original_provider_probe_sha256':hashlib.sha256(data).hexdigest()})
        guard=patch.object(acceptance,'protected',lambda p,**kw:Path(p));guard.start();self.addCleanup(guard.stop)
        return actor,packet

    def test_original_packet_is_plan_bound_and_detached(self):
        actor,packet=self.actor();observer=acceptance.CompletedNormalMaintenanceGuards(actor)
        packet['subjects'][0]['password']='changed'
        self.assertEqual(observer.subjects[0]['password'],'synthetic-password')
        (actor.package/'original-provider-probes.json').write_bytes(b'{}')
        with self.assertRaisesRegex(RuntimeError,'bytes_changed'):acceptance.CompletedNormalMaintenanceGuards(actor)

    def test_missing_hash_wrong_cluster_or_packet_version_refuse(self):
        for fault in ('hash','cluster','version','bool_version','size'):
            actor,packet=self.actor()
            if fault=='hash':actor.document={}
            else:
                if fault=='cluster':packet['system_identifier']='123'
                elif fault=='version':packet['version']=2
                elif fault=='bool_version':packet['version']=True
                body=b'x'*65537 if fault=='size' else encoded(packet)
                (actor.package/'original-provider-probes.json').write_bytes(body)
                actor.document['original_provider_probe_sha256']=hashlib.sha256(body).hexdigest()
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):acceptance.CompletedNormalMaintenanceGuards(actor)

    def test_subjects_require_distinct_real_tenants_and_exact_inputs(self):
        changes=[('auth_id','foreign'),('user_id',True),('tenant_id',-1),('password','x'),
            ('totp_secret','INVALID!'),('bucket','https://evil'),('object','../secret'),
            ('object','x?query=secret'),('object','/absolute'),('object_sha256','a'*63),('PASS',True)]
        for key,value in changes:
            packet=subjects();packet[0][key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):acceptance.validate_subjects(packet)
        for packet in (subjects()[:1],subjects()*3):
            with self.assertRaises(RuntimeError):acceptance.validate_subjects(packet)
        packet=subjects();packet[1]['tenant_id']=packet[0]['tenant_id']
        with self.assertRaises(RuntimeError):acceptance.validate_subjects(packet)
        packet=subjects();packet[1]['auth_id']=packet[0]['auth_id']
        with self.assertRaises(RuntimeError):acceptance.validate_subjects(packet)

    def test_totp_uses_existing_factor_secret(self):
        self.assertEqual(acceptance.totp('GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ',59),'287082')

    def test_endpoint_urls_or_foreign_ports_refuse_before_network(self):
        endpoints={'auth':'http://172.20.0.2:9999','rest':'http://172.20.0.3:3000','storage':'http://172.20.0.4:5000'}
        for url in ('https://example.com:9999','http://172.20.0.2:9999/path',
                'http://user:password@172.20.0.2:9999','http://172.20.0.2:80',
                'http://172.20.0.2:9999?pass=true'):
            with patch.object(acceptance,'build_opener') as transport:
                with self.assertRaises(RuntimeError):acceptance.observe_subjects(subjects(),dict(endpoints,auth=url),'synthetic')
                transport.assert_not_called()

    def test_cannot_bind_an_unrelated_driver_or_use_a_callback_packet_as_provider(self):
        actor,_=self.actor();observer=acceptance.CompletedNormalMaintenanceGuards(actor)
        with self.assertRaisesRegex(RuntimeError,'driver_binding_invalid'):observer.bind(Mock())
        # No driver / real adapter means no probe, command or authority check.
        from test_schema150_actor_inventory import fixture,repin
        from deployment.lib.completed_normal_profile import RECONCILED
        (inventory,binding),_=fixture()
        binding.update(operation=RECONCILED.operation,target_schema=160)
        _,binding=repin(inventory,binding)
        with self.assertRaises(RuntimeError):observer.provider(binding,'prepare')

    def test_material_query_is_read_only_and_never_embeds_password_or_totp(self):
        actor,_=self.actor();observer=acceptance.CompletedNormalMaintenanceGuards(actor)
        provider=SimpleNamespace(_sql=Mock(return_value=json.dumps({'count':2,'sha256':'c'*64})))
        self.assertEqual(observer.material(provider),{'count':2,'sha256':'c'*64})
        query=provider._sql.call_args.args[0]
        self.assertTrue(query.startswith('BEGIN READ ONLY;'));self.assertTrue(query.endswith('COMMIT;'))
        for subject in subjects():
            self.assertNotIn(subject['password'],query);self.assertNotIn(subject['totp_secret'],query)
        provider._sql.return_value=json.dumps({'count':1,'sha256':'c'*64})
        with self.assertRaisesRegex(RuntimeError,'material_missing'):observer.material(provider)

    def test_operational_registration_and_manifest_admission_remain_closed(self):
        from deployment.lib.completed_normal_profile import profile
        from deployment.lib.schema160_release import admitted_manifest
        with self.assertRaisesRegex(RuntimeError,'operation_profile_invalid'):profile(reconciled_contract())
        with self.assertRaisesRegex(RuntimeError,'integration_incomplete'):admitted_manifest(Path('/unused'),reconciled_contract())


class BackupActivationEvidenceTests(unittest.TestCase):
    def fixture(self):
        from test_maintenance_backup import MaintenanceBackupTests
        from deployment.lib.completed_normal_admission import digest
        from deployment.lib.completed_normal_migration import intent_document
        from scripts import backup_support
        fixture=MaintenanceBackupTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        actor=SimpleNamespace(root=fixture.root,contract=reconciled_contract())
        contract=actor.contract;binding=fixture.binding
        binding.update(operation=contract['operation'],target_schema=160)
        contract['candidate'].update(source_sha=binding['source_sha'],controller_sha=binding['controller_sha'])
        contract['writer_inventory_sha256']=binding['inventory_sha256'];binding['context_sha256']=digest(contract)
        new_path=fixture.data.parent/fixture.manifest['backup_id'];fixture.data.rename(new_path);fixture.data=new_path
        checksum=fixture.seal();sums=backup_support.digest(fixture.data/'SHA256SUMS')
        scope=digest({'operation':binding['operation'],'context_sha256':binding['context_sha256'],'backup_stage':'pre-migration'})
        restore={'status':'logical_database_and_file_restore_passed','backup_schema':146,'maintenance_manifest_sha256':checksum,
            **{k:True for k in ('role_attributes_restored','ownership_and_acls_restored','database_fingerprint_verified','native_object_bytes_restored')}}
        receiver={'operation':'actual-append-only-normal-backup-replica','plan_sha256':scope,'schema':146,
            'backup_id':fixture.data.name,'checksum_exit_code':0,'sha256sums_sha256':sums,'maintenance_manifest_sha256':checksum}
        receipt={'operation':'actual-completed-normal-backup-restore-replica','context_sha256':binding['context_sha256'],
            'plan_sha256':scope,'stage':'pre-migration','authorizing_plan_sha256':contract['plan_sha256'],
            'source_sha':binding['source_sha'],'schema':146,'images':contract['candidate']['images'],'local_path':str(fixture.data),
            'sha256sums_sha256':sums,'restore':restore,'node1':receiver,'maintenance_manifest_sha256':checksum}
        inputs={'intent':intent_document(contract),'backup':str(fixture.data),
            'backup_manifest_sha256':backup_support.digest(fixture.data/'manifest.json'),
            'backup_checksums_sha256':sums,'restore_execution_sha256':digest(restore),'replica_execution_sha256':digest(receiver),
            'maintenance_manifest_sha256':checksum}
        def publish():
            (actor.root/'migration-inputs.json').write_bytes(encoded(inputs))
            (actor.root/'pre-migration-backup.json').write_bytes(encoded(receipt))
        publish()
        self.enterContext(patch.object(acceptance,'protected',lambda p,**kw:Path(p)))
        self.enterContext(patch.object(acceptance,'readonly_configuration',lambda p,**kw:Path(p)))
        self.enterContext(patch('deployment.lib.schema150_provider_adapter.protected',lambda p,**kw:Path(p)))
        observer=object.__new__(acceptance.CompletedNormalMaintenanceGuards);observer.actor=actor
        return observer,binding,inputs,receipt,fixture,publish

    def test_actual_archive_hashes_and_original_role_object_evidence_required(self):
        observer,binding,_,_,_,_=self.fixture();observer.verify_backup(binding)

    def test_changed_backup_bytes_are_rejected(self):
        observer,binding,_,_,fixture,_=self.fixture()
        (fixture.data/'maintenance/objects.tar.gz').write_bytes(b'truncated')
        with self.assertRaises(Exception):observer.verify_backup(binding)

    def test_root_receipt_cannot_substitute_a_different_restore_or_receiver(self):
        mutations=[lambda r:r.update(schema=160),lambda r:r.update(source_sha='f'*40),
            lambda r:r.update(stage='post-migration'),lambda r:r['restore'].update(backup_schema=160),
            lambda r:r['restore'].update(native_object_bytes_restored=False),
            lambda r:r['node1'].update(plan_sha256='e'*64),lambda r:r['node1'].update(checksum_exit_code=False),
            lambda r:r['node1'].update(maintenance_manifest_sha256='f'*64)]
        observer,binding,inputs,receipt,_,publish=self.fixture();original=copy.deepcopy(receipt)
        for mutate in mutations:
            receipt.clear();receipt.update(copy.deepcopy(original));mutate(receipt);publish()
            with self.subTest(mutation=mutate),self.assertRaises(RuntimeError):observer.verify_backup(binding)


class ActivationObservationTests(unittest.TestCase):
    actor=PrivateAcceptanceGuardTests.actor
    def activation_fixture(self):
        from deployment.lib.completed_normal_admission import digest
        from deployment.lib.completed_normal_profile import RECONCILED
        from deployment.lib.runtime_authority import write_worker_authority
        actor,_=self.actor();actor.ops=SimpleNamespace(state_root=actor.root/'state');actor.ops.state_root.mkdir()
        actor.installation=SimpleNamespace(installed=Mock())
        contract=actor.contract
        binding={'operation':RECONCILED.operation,'context_sha256':digest(contract),
            'source_sha':contract['candidate']['source_sha'],'controller_sha':contract['candidate']['controller_sha'],
            'inventory_sha256':contract['writer_inventory_sha256'],'system_identifier':contract['database']['system_identifier'],
            'source_schema':146,'target_schema':160}
        observer=acceptance.CompletedNormalMaintenanceGuards(actor)
        provider=SimpleNamespace(_database_identity=Mock(return_value=160),
            _sql=Mock(side_effect=lambda q:'[2,2,2]' if 'json_build_array' in q else '0'),
            verify_candidate_stage=Mock(return_value={'worker_generation':'c'*64}),_verify_barrier=Mock(),_attest=Mock(),
            _known_sessions=Mock(return_value=True),_sessions=Mock(return_value=[]))
        observer.provider=Mock(return_value=provider);observer.material=Mock(return_value={'count':2,'sha256':'a'*64})
        observer.verify_backup=Mock()
        documents={'pre-migration-customer-snapshot.json':{'snapshot':'original'},
            'post-migration-customer-snapshot.json':{'snapshot':'preserved'},
            'migration-customer-preservation.json':{'verified':'by actual comparison'},
            'original-private-acceptance.json':{'binding':binding,'probe_sha256':observer.probe_sha256,'material':observer.material.return_value}}
        for name,value in documents.items():(actor.root/name).write_bytes(encoded(value))
        self.enterContext(patch('deployment.lib.schema150_provider_adapter.protected',lambda p,**kw:Path(p)))
        self.enterContext(patch('deployment.lib.completed_normal_database.require_normal_migration_boundary'))
        self.enterContext(patch('deployment.lib.completed_normal_database.verify_migration_customer_preservation',
            return_value=documents['migration-customer-preservation.json']))
        artifacts=self.enterContext(patch('deployment.lib.completed_normal_evidence.verify_application_evidence'))
        grant={'mode':'READ_ONLY','schema':146,'binding':'synthetic-root-grant'}
        self.enterContext(patch.object(acceptance,'require_candidate_authority',side_effect=lambda *a,**k:dict(grant)))
        origin=contract['origin'];roles=contract['source_roles'];candidate=contract['candidate']
        def owner(target=False,generation=None):
            return write_worker_authority(actor.ops.state_root,generation=generation or (
                'c'*64 if target else origin['worker_generation']),owner='CANDIDATE',
                old={'sha':roles['application_sha'] if target else 'f'*40,
                     'slot':origin['slot'] if target else candidate['slot']},
                candidate={'sha':candidate['source_sha'] if target else roles['application_sha'],
                           'slot':candidate['slot'] if target else origin['slot']})
        owner()
        return observer,binding,provider,grant,owner,artifacts

    def test_observes_exact_origin_owner_before_target_handoff(self):
        observer,binding,provider,_,_,artifacts=self.activation_fixture()
        value=observer.activation(binding,private=True)
        from deployment.lib.schema150_provider_lifecycle import PRE_GRANT_GATES
        self.assertTrue(all(value[k] is True for k in PRE_GRANT_GATES))
        self.assertFalse(value['target_write_authority']);self.assertIsNone(value['write_authority_sha256'])
        self.assertNotIn('public_acceptance',value);self.assertNotIn('candidate_read_only',value)
        observer.verify_backup.assert_called_once_with(binding);artifacts.assert_called_once()
        provider._verify_barrier.assert_called_once();observer.actor.installation.installed.assert_called_once()

    def test_transferred_worker_owner_requires_exact_generation_and_target_grant(self):
        observer,binding,_,grant,owner,_=self.activation_fixture();owner(target=True)
        with self.assertRaisesRegex(RuntimeError,'requires_target_grant'):observer.activation(binding,private=False)
        grant.update(mode='NORMAL',schema=160)
        self.assertTrue(observer.activation(binding,private=False)['target_write_authority'])
        owner(target=True,generation='d'*64)
        with self.assertRaisesRegex(RuntimeError,'ownership_changed'):observer.activation(binding,private=False)

    def test_missing_backup_artifact_boot_or_barrier_cannot_be_replaced_by_flags(self):
        for name in ('backup','artifact','boot','barrier'):
            observer,binding,provider,_,_,artifacts=self.activation_fixture()
            chosen={'backup':observer.verify_backup,'artifact':artifacts,
                'boot':observer.actor.installation.installed,'barrier':provider._verify_barrier}[name]
            chosen.side_effect=RuntimeError('synthetic_missing_'+name)
            with self.subTest(name=name),self.assertRaisesRegex(RuntimeError,'synthetic_missing_'):
                observer.activation(binding,private=True)

    def test_foreign_session_or_prepared_transaction_blocks_activation(self):
        observer,binding,provider,_,_,_=self.activation_fixture()
        provider._known_sessions.return_value=False
        with self.assertRaisesRegex(RuntimeError,'unknown_writer'):observer.activation(binding,private=True)
        provider._known_sessions.return_value=True
        provider._sql.side_effect=lambda q:'[2,2,2]' if 'json_build_array' in q else '1'
        with self.assertRaisesRegex(RuntimeError,'unknown_writer'):observer.activation(binding,private=True)
