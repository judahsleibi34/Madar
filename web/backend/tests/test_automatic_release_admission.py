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
