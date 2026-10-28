"""MODEL admission and real crypto tests; not a deployment acceptance claim."""
import base64,copy,hashlib,json,os,tempfile,time,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from deployment.lib import automatic_release_admission as admission
from deployment.lib.migration_inventory import canonical,digest


def sample():
    now=int(time.time());images={'backend':'fixture-backend:a@sha256:'+'a'*64,
        'frontend':'fixture-frontend:a@sha256:'+'b'*64,'worker':'fixture-backend:a@sha256:'+'a'*64,
        'build_timestamp':'2026-10-26T00:00:00Z'}
    plan={'source_sha':'a'*40,'repository':'judahsleibi34/Madar','operation_id':'migration-plan-'+'d'*64,
        'risk_class':'A','execution_class':'transactional','compatibility_covers_path':True,
        'protected_control_plane_changed':False,'origin_schema':160,'target_schema':160,'migrations':[]}
    origin={'source_sha':'b'*40,'slot':'blue','images':images,'compatible_min':160,'compatible_max':162,'configuration_sha256':'c'*64}
    return {'version':1,'operation':admission.OPERATION,'operation_id':plan['operation_id'],'attempt_id':str(uuid.uuid4()),
        'environment':'isolated-test','source_sha':'a'*40,'controller_sha':'f'*40,'plan':plan,'policy_sha256':'e'*64,
        'database':{'system_identifier':'123456789','origin_schema':160,'target_schema':160,'structure_sha256':'1'*64},
        'origin':origin,'candidate':dict(origin,source_sha='a'*40,slot='green'),
        'evidence':{k:'2'*64 for k in admission.GATES},'created_at':now,'expires_at':now+300}


class AutomaticAdmissionTests(unittest.TestCase):
    def test_native_reused_artifact_receipt_projects_only_exact_identity(self):
        images=sample()['origin']['images']
        self.assertEqual(admission.image_identities(dict(images,artifact_reused=True)),images)
        for fields in ({'artifact_reused':'true'},{'authority':'PASS'},{'image_override':'foreign'}):
            with self.subTest(fields=fields),self.assertRaises(RuntimeError):
                admission.image_identities(dict(images,**fields))

    def test_exact_application_only_scope_is_data_not_authority(self):
        value=sample();self.assertEqual(admission.validate(value),value)
        self.assertNotIn('token',value);self.assertNotIn('PASS',canonical(value).decode())

    def test_scope_substitution_unknown_risk_and_wrong_range_refuse(self):
        mutations=[lambda v:v.update(source_sha='not-a-sha'),lambda v:v['plan'].update(risk_class='D'),
            lambda v:v['plan'].update(risk_class='C'),lambda v:v['plan'].update(execution_class='unsupported'),
            lambda v:v['plan'].update(compatibility_covers_path=False),lambda v:v['plan'].update(protected_control_plane_changed=True),
            lambda v:v['database'].update(system_identifier='production'),lambda v:v['database'].update(origin_schema=True),
            lambda v:v['candidate'].update(slot='blue'),lambda v:v['candidate'].update(compatible_max=159),
            lambda v:v.update(attempt_id='../foreign'),lambda v:v['evidence'].update(ci=True),
            lambda v:v.update(authority_issued=True),lambda v:v.update(expires_at=int(time.time())-1)]
        for mutation in mutations:
            value=sample();mutation(value)
            with self.subTest(mutation=mutation),self.assertRaises(RuntimeError):admission.validate(value)

    def test_environment_marker_does_not_authorize_without_real_root_reader(self):
        with patch.object(admission.os,'geteuid',return_value=1000):
            with self.assertRaisesRegex(RuntimeError,'root_issuer'):admission.require_issue(sample(),None)

    def test_root_issue_requires_both_owned_locks_and_current_observations(self):
        value=sample();ops=SimpleNamespace(automatic_upgrade_lock=11,upgrade_root=Path('/fixture/upgrades'),
            deploy_lock_descriptor=12,state_root=Path('/fixture/releases'),reobserve_automatic_admission=lambda _:dict(value,controller_sha='e'*40))
        with patch.object(admission.os,'geteuid',return_value=0),patch.object(admission,'sealed'),\
             patch('deployment.lib.schema150_provider_adapter.require_owned_lock') as lock:
            with self.assertRaisesRegex(RuntimeError,'observations_changed'):admission.require_issue(value,ops)
            self.assertEqual(lock.call_count,2)

    def test_test_credential_cannot_authorize_foreign_source(self):
        value=sample()
        with patch('deployment.lib.completed_normal_admission.credential_witness',return_value=value):
            with self.assertRaisesRegex(RuntimeError,'source_substitution'):admission.credential('c'*40)


class IndependentEvidenceTests(unittest.TestCase):
    def setUp(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.private=Ed25519PrivateKey.generate();key=self.private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        (self.root/'key').write_bytes(key)
        self.enterContext(patch.object(admission,'TEST_PUBLIC_KEY',self.root/'key'))
        self.enterContext(patch.object(admission,'EVIDENCE',self.root))
        self.enterContext(patch.object(admission,'protected',lambda path,**kw:path)) # MODEL filesystem; native suite separately.
        self.policy={'environment':'isolated-test','environment_id':'isolated-fixture','denied_database_identifiers':['777777777'],'test_public_key_sha256':hashlib.sha256(key).hexdigest(),
            'evidence_max_age_seconds':300,'recovery_max_age_seconds':3600,'test_runner_sha256':'a'*64,'test_commands_sha256':'b'*64}
        value=sample();now=int(time.time())
        self.payload={'version':1,'kind':'isolated-parent-executed-acceptance','environment_id':'isolated-fixture',
            'source_sha':value['source_sha'],'history_base_sha':value['origin']['source_sha'],'tree_sha':'c'*40,
            'images':value['candidate']['images'],'candidate_configuration_sha256':'d'*64,'origin_configuration_sha256':'e'*64,
            'attempt_id':value['attempt_id'],'observed_at':now,'expires_at':now+240,
            'gates':{
                'source':{'repository':'judahsleibi34/Madar','branch':'refs/heads/main','source_sha':value['source_sha'],'history_base_sha':value['origin']['source_sha'],'tree_sha':'c'*40},
                'ci':{'runner_sha256':'a'*64,'commands_sha256':'b'*64,'exit_codes':[0,0]},
                'artifacts':{'source_sha':value['source_sha'],'images':value['candidate']['images'],'build_inputs_sha256':'f'*64},
                'staging':{'source_sha':value['source_sha'],'images':value['candidate']['images'],'schema':160,'database_system_identifier':'987654321','checks_sha256':'1'*64},
                'compatibility':{'origin_source_sha':value['origin']['source_sha'],'candidate_source_sha':value['source_sha'],'origin_range':[160,162],'candidate_range':[160,162],'protocols':{'delivery':2,'outbox':2,'deletion':2}},
                'recovery':{'source_system_identifier':'123456789','backup_sha256':'2'*64,'restore_system_identifier':'987654321','restored_schema':160,'rows_sha256':'3'*64,'roles_sha256':'4'*64,'objects_sha256':'5'*64,'backup_created_at':now-600,'restored_at':now-500,'verified_at':now},
                'resources':{'disk_free_bytes':100,'memory_available_bytes':100,'required_disk_bytes':50,'required_memory_bytes':50,'max_candidate_memory_bytes':30,'max_candidate_cpu_millis':100}}}

    def publish(self):
        body={'payload':self.payload,'signature':base64.b64encode(self.private.sign(canonical(self.payload))).decode()}
        path=self.root/(self.payload['source_sha']+'.json');path.write_bytes(canonical(body));return path

    def test_real_signature_binds_independent_test_execution_to_source_and_realm(self):
        self.publish();self.assertEqual(admission.independent_evidence('a'*40,self.policy),self.payload)

    def test_tampered_packet_wrong_key_runner_or_production_environment_refuse(self):
        path=self.publish();body=json.loads(path.read_bytes());body['payload']['gates']['ci']['exit_codes']=[1];path.write_bytes(canonical(body))
        with self.assertRaisesRegex(RuntimeError,'signature_invalid'):admission.independent_evidence('a'*40,self.policy)
        self.publish()
        for updates in ({'environment':'production'},{'environment_id':'production'},{'test_runner_sha256':'f'*64},{'test_public_key_sha256':'0'*64}):
            with self.subTest(updates=updates),self.assertRaises(RuntimeError):admission.independent_evidence('a'*40,dict(self.policy,**updates))

    def test_failed_ci_stale_evidence_or_same_cluster_restore_cannot_be_approved(self):
        original=copy.deepcopy(self.payload)
        for mutation in (lambda p:p['gates']['ci'].update(exit_codes=[0,1]),
                lambda p:p.update(expires_at=0),lambda p:p['gates']['recovery'].update(restore_system_identifier='123456789')):
            mutation(self.payload);self.publish()
            with self.assertRaises(RuntimeError):admission.independent_evidence('a'*40,self.policy)
            self.payload=copy.deepcopy(original)


    def test_reverification_does_not_redate_backup_or_restore(self):
        self.publish();verified=admission.independent_evidence('a'*40,self.policy)
        self.assertLess(verified['gates']['recovery']['restored_at'],verified['gates']['recovery']['verified_at'])
        for mutation in (lambda r:r.update(backup_created_at=int(time.time())-4000),
                         lambda r:r.update(verified_at=int(time.time())-301),
                         lambda r:r.update(restored_at=int(time.time())+5)):
            original=copy.deepcopy(self.payload);mutation(self.payload['gates']['recovery']);self.publish()
            with self.assertRaises(RuntimeError):admission.independent_evidence('a'*40,self.policy)
            self.payload=original


if __name__=='__main__':unittest.main()


class DurableAutomaticOperationTests(unittest.TestCase):
    def test_pending_scope_survives_runtime_interlock_loss_and_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(admission,'ROOT',Path(directory)),patch.object(admission,'require_reserved'),patch.object(admission,'protected',side_effect=lambda p,**_:p):
            value=sample();admission.arm_operation(value)
            pointer=Path(directory)/'in-progress.json';original=pointer.read_bytes()
            self.assertEqual(pointer.stat().st_mode&0o777,0o600)
            self.assertEqual(json.loads(original)['database_system_identifier'],value['database']['system_identifier'])
            # No volatile /run file exists in this fixture; persistent state is decisive.
            with self.assertRaisesRegex(RuntimeError,'durable_operation_requires_recovery'):
                admission.require_no_pending_operation()
            with self.assertRaisesRegex(RuntimeError,'durable_operation_requires_recovery'):
                admission.arm_operation(sample())
            self.assertEqual(pointer.read_bytes(),original)

    def test_only_exact_genuine_completion_can_retire_pending_scope(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(admission,'ROOT',Path(directory)),patch.object(admission,'require_reserved'),patch.object(admission,'protected',side_effect=lambda p,**_:p):
            value=sample();admission.arm_operation(value);root=Path(directory)
            completion=root/'attempts'/value['attempt_id']/'completion.json';completion.parent.mkdir(parents=True)
            record={'admission_sha256':digest(value),'attempt_id':value['attempt_id'],'source_sha':value['source_sha'],'release':{'status':'failed'}}
            completion.write_bytes(canonical(record))
            with self.assertRaisesRegex(RuntimeError,'completion_binding_invalid'):admission.finish_operation(value)
            self.assertTrue((root/'in-progress.json').exists())
            record['release']['status']='known_good';record['source_sha']='e'*40;completion.write_bytes(canonical(record))
            with self.assertRaisesRegex(RuntimeError,'completion_binding_invalid'):admission.finish_operation(value)
            self.assertTrue((root/'in-progress.json').exists())
            record['source_sha']=value['source_sha'];completion.write_bytes(canonical(record));admission.finish_operation(value)
            self.assertFalse((root/'in-progress.json').exists());admission.require_no_pending_operation()

class PhysicalRecoveryAdmissionTests(IndependentEvidenceTests):
    """Separate receiver signature and root pin; the logical policy stays strict."""
    def setUp(self):
        super().setUp()
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
        self.receiver_key=Ed25519PrivateKey.generate()
        public=base64.b64encode(self.receiver_key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode()
        now=int(time.time());receiver_id=str(uuid.uuid4())
        observed={'system_identifier':'123456789','schema':160,'protocols':[2,2,2],'read_only':True,'fingerprints':218}
        self.receipt={'version':1,'kind':'independently-restored-synthetic-application',
            'source_physical_host_uuid':str(uuid.uuid4()),'receiver_physical_host_uuid':str(uuid.uuid4()),
            'receiver_filesystem_uuid':str(uuid.uuid4()),'source_guest_uuid':str(uuid.uuid4()),
            'source_sha':'b'*40,'manifest_sha256':'1'*64,'received_sha256':'2'*64,'receiver_id':receiver_id,
            'operation_id':str(uuid.uuid4()),'attempt_id':str(uuid.uuid4()),'receiver_implementation_sha256':'3'*64,
            'receiver_source_sha':'c'*40,'backup_format':'postgres-physical-and-application-v1',
            'source_and_restored_database_system_identifier':'123456789','database_observation':observed,
            'release_context':{'completion_sha256':'4'*64,'history':{'history_sha256':'5'*64}},
            'production_modified':False,'new_deployment_authority_issued':False,'release_migration_sql_executed':False,
            'received_at':now-100,'accepted_at':now-1,
            'runtime':{'/madar-recovery-'+receiver_id[:12]+'-'+str(n):{'id':f'{n:064x}','image':'sha256:'+'a'*64,'spec_sha256':'b'*64} for n in range(14)}}
        required=('ready','original_password_login','original_auth_identity','original_mfa_totp','admin_AAL2',
            'refresh_rotation','anonymous_storage_denied','original_forms_and_reservations_read',
            'reservation_transaction_api','tenant_isolation','notification_delivery','private_frontend_backend_routing',
            'network_external_access_refused','external_dns_refused')
        self.receipt['functional_acceptance']={k:True for k in required}|{'source_sha':'b'*40,'schema':160,
            'database_system_identifier':'123456789','original_private_object_sha256':'6'*64,
            'calendar':{'status':'PASS'},'external_notifications_sent':False}
        names=('source_physical_host_uuid','receiver_physical_host_uuid','receiver_filesystem_uuid','source_guest_uuid',
            'source_sha','manifest_sha256','received_sha256','receiver_id','operation_id','attempt_id',
            'receiver_implementation_sha256','receiver_source_sha')
        self.trust={k:self.receipt[k] for k in names}|{'version':1,'kind':'independently-enrolled-physical-test-restoration',
            'environment_id':self.policy['environment_id'],'receiver_public_key':public,'database_system_identifier':'123456789',
            'schema':160,'backup_earliest_at':now-200,'expires_at':now+200,'completion_sha256':'4'*64,'history_sha256':'5'*64}
        self.enterContext(patch.object(admission,'PHYSICAL_RECOVERY',self.root))
        self.seal_receiver()

    def seal_receiver(self):
        packet={'payload':self.receipt,'receiver_public_key':self.trust['receiver_public_key'],
            'signature':base64.b64encode(self.receiver_key.sign(canonical(self.receipt))).decode()}
        sha=digest(packet);self.trust.update(receipt=packet,receipt_sha256=sha)
        (self.root/(sha+'.json')).write_bytes(canonical(self.trust))
        self.payload['gates']['recovery']={'kind':'independent-physical-application-v1','source_system_identifier':'123456789',
            'restore_system_identifier':'123456789','restored_schema':160,'receipt_sha256':sha}
        self.publish()

    def test_same_identifier_is_accepted_only_for_independently_pinned_physical_restoration(self):
        self.assertEqual(admission.independent_evidence('a'*40,self.policy),self.payload)
        p=self.root/(self.trust['receipt_sha256']+'.json');p.unlink()
        with self.assertRaises(Exception):admission.independent_evidence('a'*40,self.policy)

    def test_receipt_signature_cannot_be_replaced_by_the_outer_runner(self):
        packet=self.trust['receipt'];packet['signature']=base64.b64encode(b'forged').decode()
        sha=digest(packet);self.trust.update(receipt_sha256=sha)
        (self.root/(sha+'.json')).write_bytes(canonical(self.trust))
        self.payload['gates']['recovery']['receipt_sha256']=sha;self.publish()
        with self.assertRaisesRegex(RuntimeError,'receiver_signature_invalid'):admission.independent_evidence('a'*40,self.policy)

    def test_even_a_signed_receiver_cannot_change_independently_pinned_identity_or_acceptance(self):
        original=copy.deepcopy(self.receipt)
        changes=(lambda r:r.update(source_physical_host_uuid=r['receiver_physical_host_uuid']),
            lambda r:r.update(source_sha='e'*40),lambda r:r['database_observation'].update(protocols=[1,2,2]),
            lambda r:r['functional_acceptance'].update(tenant_isolation=False),
            lambda r:r['functional_acceptance'].update(original_mfa_totp=False),
            lambda r:r.update(accepted_at=int(time.time())-400),lambda r:r.update(production_modified=True),
            lambda r:r['release_context'].update(completion_sha256='f'*64),lambda r:r.update(runtime={}))
        for change in changes:
            self.receipt=copy.deepcopy(original);change(self.receipt);self.seal_receiver()
            with self.subTest(change=change),self.assertRaises(RuntimeError):admission.independent_evidence('a'*40,self.policy)

    # Inherited logical-only mutations do not describe this physical envelope.
    def test_reverification_does_not_redate_backup_or_restore(self):
        self.trust['backup_earliest_at']=int(time.time())-4000;self.seal_receiver()
        with self.assertRaisesRegex(RuntimeError,'stale'):admission.independent_evidence('a'*40,self.policy)

    def test_failed_ci_stale_evidence_or_same_cluster_restore_cannot_be_approved(self):
        self.payload['gates']['ci']['exit_codes']=[1];self.publish()
        with self.assertRaises(RuntimeError):admission.independent_evidence('a'*40,self.policy)
