"""Real signatures/files/journals; modeled Docker and host identity, not Node1 acceptance."""
import base64,copy,json,os,tempfile,time,unittest,uuid
import io
from pathlib import Path
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption
from deployment.lib import automatic_release_recovery as recovery
from deployment.lib.migration_inventory import canonical,digest
from test_offhost_application_restoration import receiver
import test_historical_boot_recovery as historical_fixture


def modeled_root_lstat(root):
    original=Path.lstat
    def observed(path,*args,**kw):
        result=original(path,*args,**kw)
        if path!=root:return result
        fields=list(result);fields[4]=0
        return os.stat_result(fields)
    return patch.object(Path,'lstat',observed)


def fixture():
    now=int(time.time());key=Ed25519PrivateKey.generate();public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    enrollment={'version':2,'run_id':'codex-20261102T200000Z-automatic-execution-abcdef01',
        'receiver_id':str(uuid.uuid4()),'backup_operation_id':str(uuid.uuid4()),'manifest_sha256':'1'*64,
        'source_guest_uuid':str(uuid.uuid4()),'source_sha':'a'*40,'source_database_system_identifier':'123456789',
        'source_product_uuid':str(uuid.uuid4()),'product_uuid':str(uuid.uuid4()),'filesystem_uuid':str(uuid.uuid4()),
        'source_origin_sha256':'2'*64}
    result={'directory_removed':True,'containers_removed':['f'*64]}
    packet=receiver.retirement_receipt(enrollment,result,(key,public))
    hold={'version':1,'kind':'isolated-independent-restoration-source-hold','hold_id':str(uuid.uuid4()),
        'environment_id':'isolated-fixture','guest_uuid':enrollment['source_guest_uuid'],'machine_id':'d'*32,
        'root_filesystem_uuid':str(uuid.uuid4()),'controller_sha':'b'*40,'controller_tree_sha256':'3'*64,
        'historical_origin':{'unit_fixture':True},'known_good_sha256':'4'*64,
        'receiver_public_key':base64.b64encode(public).decode(),'created_at':now-10,'expires_at':now+100,
        **{k:v for k,v in packet['payload'].items() if k in {
            'run_id','receiver_id','operation_id','manifest_sha256','source_guest_uuid','source_sha',
            'source_database_system_identifier','source_physical_host_uuid','receiver_physical_host_uuid',
            'receiver_filesystem_uuid','receiver_enrollment_sha256','source_origin_sha256'}}}
    return enrollment,result,key,public,hold,packet


class RetirementSignatures(unittest.TestCase):
    def test_exact_receiver_signature_is_separate_from_restore_or_deployment(self):
        e,result,key,public,hold,packet=fixture()
        self.assertEqual(recovery.verify_receiver_retirement(hold,packet),packet['payload'])
        self.assertEqual(packet['payload']['cleanup_sha256'],digest(result))
        self.assertNotIn('application_restored',packet['payload'])
        self.assertIs(packet['payload']['deployment_authority_issued'],False)

    def test_substituted_signature_or_public_key_refuses(self):
        e,result,key,public,hold,packet=fixture()
        for field,value in [('signature',base64.b64encode(b'0'*64).decode()),
                            ('receiver_public_key',base64.b64encode(b'0'*32).decode())]:
            with self.subTest(field=field),self.assertRaisesRegex(RuntimeError,'signature_invalid'):
                recovery.verify_receiver_retirement(hold,dict(packet,**{field:value}))
        altered=copy.deepcopy(packet);altered['payload']['receiver_id']=str(uuid.uuid4())
        with self.assertRaisesRegex(RuntimeError,'signature_invalid'):recovery.verify_receiver_retirement(hold,altered)

    def test_signed_wrong_scope_stale_cleanup_or_authority_claim_refuses(self):
        e,result,key,public,hold,packet=fixture()
        changes={'receiver_id':str(uuid.uuid4()),'operation_id':str(uuid.uuid4()),'manifest_sha256':'5'*64,
            'source_guest_uuid':str(uuid.uuid4()),'source_database_system_identifier':'999999999',
            'source_origin_sha256':'6'*64,'receiver_enrollment_sha256':'7'*64,'receiver_filesystem_uuid':str(uuid.uuid4()),
            'directory_removed':False,'no_owned_containers':False,'no_owned_networks':False,'no_owned_volumes':False,
            'deployment_authority_issued':True,'migration_sql_executed':True,'retired_at':int(time.time())-301}
        for field,value in changes.items():
            changed=copy.deepcopy(packet);changed['payload'][field]=value
            changed['signature']=base64.b64encode(key.sign(canonical(changed['payload']))).decode()
            with self.subTest(field=field),self.assertRaisesRegex(RuntimeError,'scope_invalid'):
                recovery.verify_receiver_retirement(hold,changed)
        with self.assertRaisesRegex(RuntimeError,'hold_invalid'):
            recovery.verify_receiver_retirement(dict(hold,expires_at=0),packet)
        with self.assertRaisesRegex(RuntimeError,'scope_invalid'):
            recovery.verify_receiver_retirement(hold,packet,now=packet['payload']['retired_at']-1)

    def test_real_owned_directory_is_removed_before_signature(self):
        e,result,key,public,hold,packet=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'receiver';root.mkdir();st=root.stat()
            (root/'baseline.json').write_bytes(canonical({'directory_device':st.st_dev,'directory_inode':st.st_ino,'start_time':time.time(),'images':[]}))
            (root/'receiver.key').write_bytes(key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption()))
            (root/'receiver.pub').write_bytes(public)
            def command(args,**kw):return b''
            real=receiver.retirement_receipt
            def sign(enrollment,result,signer):
                self.assertFalse(root.exists());return real(enrollment,result,signer)
            with modeled_root_lstat(root),patch.object(receiver,'root_for',return_value=(root,e)),patch.object(receiver,'protected',lambda p,**kw:p),\
                 patch.object(receiver,'cleanup',return_value={'containers_removed':[],'networks_removed':[],'volumes_removed':[]}),\
                 patch.object(receiver,'command',side_effect=command),patch.object(receiver,'retirement_receipt',side_effect=sign):
                observed=receiver.retire_scope(e['run_id'],attest=True)
            self.assertFalse(root.exists());recovery.verify_receiver_retirement(hold,observed['retirement_receipt'])

    def test_live_resource_after_cleanup_prevents_signature(self):
        e,result,key,public,hold,packet=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'receiver';root.mkdir();st=root.stat()
            (root/'baseline.json').write_bytes(canonical({'directory_device':st.st_dev,'directory_inode':st.st_ino,'start_time':time.time(),'images':[]}))
            def command(args,**kw):return b'foreign-id' if '--filter' in args and 'events' not in args else b''
            with modeled_root_lstat(root),patch.object(receiver,'root_for',return_value=(root,e)),patch.object(receiver,'protected',lambda p,**kw:p),\
                 patch.object(receiver,'cleanup',return_value={}),patch.object(receiver,'retirement_signer',return_value=(key,public)),\
                 patch.object(receiver,'command',side_effect=command),patch.object(receiver,'retirement_receipt') as sign:
                with self.assertRaisesRegex(RuntimeError,'owned_resource_survived'):receiver.retire_scope(e['run_id'],attest=True)
            sign.assert_not_called()


class SourceHoldConsumption(unittest.TestCase):
    def setUp(self):
        # Reuse the existing modeled historical-origin fixture, not its tests.
        self.model=historical_fixture.HistoricalBootRecoveryTests();self.model.setUp();self.addCleanup(self.model.doCleanups)
        m=self.model;m.host['machine_id']='d'*32
        m.p.update({k:m.host[k] for k in ('guest_uuid','machine_id','root_filesystem_uuid')})
        m.p.update(environment_id='isolated-fixture',controller_tree_sha256='3'*64,control_interface='ens3')
        m.original['host']={'guest_uuid':m.host['guest_uuid']}
        manifest=m.seal()
        e,result,key,public,hold,packet=fixture()
        e.update(source_guest_uuid=m.host['guest_uuid'],source_sha=m.source,source_origin_sha256=digest(m.context))
        packet=receiver.retirement_receipt(e,result,(key,public))
        hold.update({k:packet['payload'][k] for k in packet['payload'] if k in hold and k not in {'version','kind'}})
        hold.update({k:m.p[k] for k in ('environment_id','guest_uuid','machine_id','root_filesystem_uuid','controller_sha','controller_tree_sha256','historical_origin')})
        hold['known_good_sha256']=digest(manifest)
        self.hold=hold;self.packet=packet;self.path=m.journal/'independent-restore-in-progress.json'
        self.path.write_bytes(canonical(hold))
        for row in m.rows:row['State']['Running']=False
        self.enterContext(patch.object(recovery.os,'geteuid',return_value=0))
        self.enterContext(patch.object(recovery,'verify_fence'))

    def release(self):return recovery.release_independent_restoration_hold(self.model.system,self.packet)

    def test_durable_consumption_does_not_start_application_and_cannot_replay(self):
        with patch.object(recovery,'run') as effect:
            result=self.release();self.assertFalse(self.path.exists());effect.assert_not_called()
        record=self.model.journal/'restoration-retirements'/(self.hold['hold_id']+'.json')
        self.assertEqual(json.loads(record.read_bytes()),result)
        self.assertIs(result['application_started'],False)
        with self.assertRaises(FileNotFoundError):self.release()

    def test_crash_after_consumption_can_finish_only_exact_same_hold(self):
        original=Path.unlink
        def interrupt(path,*args,**kw):
            if path==self.path:raise OSError('unit-fixture interruption after durable consumption')
            return original(path,*args,**kw)
        with patch.object(Path,'unlink',interrupt),self.assertRaises(OSError):self.release()
        self.assertTrue(self.path.exists());self.release();self.assertFalse(self.path.exists())

    def test_source_actor_policy_origin_and_manifest_substitution_refuse(self):
        m=self.model
        m.rows[0]['State']['Running']=True
        with self.assertRaisesRegex(RuntimeError,'source_not_stopped'):self.release()
        m.rows[0]['State']['Running']=False
        m.p['controller_tree_sha256']='f'*64
        with self.assertRaisesRegex(RuntimeError,'policy_changed'):self.release()
        m.p['controller_tree_sha256']='3'*64
        changed=dict(self.hold,known_good_sha256='f'*64);self.path.write_bytes(canonical(changed))
        with self.assertRaisesRegex(RuntimeError,'origin_changed'):self.release()
        self.assertTrue(self.path.exists());self.assertFalse((m.journal/'restoration-retirements').exists())


class RetirementCli(unittest.TestCase):
    def test_stdin_receipt_uses_existing_root_entrypoint_without_starting_services(self):
        from deployment.lib import control_plane_upgrade as controller
        from types import SimpleNamespace
        e,result,key,public,hold,packet=fixture();system=object()
        with patch.object(controller.os,'geteuid',return_value=0),patch.object(controller,'SystemOperations',return_value=system),\
             patch.object(controller.sys,'stdin',SimpleNamespace(buffer=io.BytesIO(canonical(packet)))),\
             patch.object(controller.sys,'stdout',io.StringIO()),\
             patch.object(recovery,'release_independent_restoration_hold',return_value={'application_started':False}) as release:
            self.assertEqual(controller.main(['--release-independent-restore-hold']),0)
        release.assert_called_once_with(system,packet)

    def test_mixed_deploy_or_recovery_flags_cannot_clear_hold(self):
        from deployment.lib import control_plane_upgrade as controller
        for flags in (['--recover-known-good'],['--automatic-poll'],['--authenticate-operator'],
                      ['--historical-origin','prepare'],['--exceptional','list']):
            with self.subTest(flags=flags),patch.object(controller.os,'geteuid',return_value=0),\
                 patch.object(controller.sys,'stderr',io.StringIO()),patch.object(controller,'SystemOperations') as create,\
                 self.assertRaises(SystemExit) as error:
                controller.main(['--release-independent-restore-hold',*flags])
            self.assertEqual(error.exception.code,2);create.assert_not_called()
