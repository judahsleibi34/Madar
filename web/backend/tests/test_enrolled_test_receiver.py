"""Cryptographic/enrollment refusals; physical-host proof is a separate run."""
import base64,copy,hashlib,importlib.util,io,json,os,sys,tarfile,tempfile,time,unittest,uuid
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from deployment.lib.migration_inventory import canonical,digest
WEB=Path(__file__).resolve().parents[2];sys.path.insert(0,str(WEB/'scripts'))
spec=importlib.util.spec_from_file_location('enrolled_replica',WEB/'scripts/normal_backup_replica.py');receiver=importlib.util.module_from_spec(spec);spec.loader.exec_module(receiver)


class EnrolledReceiverTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.run='codex-20261027T120000Z-automatic-execution-12345678';self.key=Ed25519PrivateKey.generate()
        self.data={name:b'synthetic' for name in ('postgres.tar.gz','objects.tar.gz','application.json')}
        self.value={'operation':'independent-synthetic-application-restoration','operation_id':str(uuid.uuid4()),'receiver_id':str(uuid.uuid4()),'source_sha':'c'*40,'source_guest_uuid':str(uuid.uuid4()),'source_database_system_identifier':'123456789',
            'backup_format':'postgres-physical-and-application-v1','expires_at':int(time.time())+900,'files':{name:{'size':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in self.data.items()}}
        self.enrollment={'version':1,'kind':'independent-physical-test-receiver','run_id':self.run,'receiver_id':self.value['receiver_id'],'machine_id':'a'*32,'product_uuid':str(uuid.uuid4()),'filesystem_uuid':str(uuid.uuid4()),'source_guest_uuid':self.value['source_guest_uuid'],'source_product_uuid':str(uuid.uuid4()),'source_database_system_identifier':'123456789','denied_database_identifiers':['987654321'],'source_sha':'c'*40,'backup_operation_id':self.value['operation_id'],'manifest_sha256':digest(self.value),'source_public_key':base64.b64encode(self.key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode(),'expires_at':self.value['expires_at'],'max_transfer_bytes':1024}
        realpath=Path
        self.enterContext(patch.object(receiver,'Path',side_effect=lambda p,*args:self.root if str(p)=='/opt/madar-recovery-tests' else realpath(p,*args)))
        # Receiver appends the authenticated run ID to its fixed parent.
        (self.root/self.run).mkdir()
        self.enterContext(patch.object(receiver.os,'geteuid',return_value=0))
        self.disk=SimpleNamespace(free=10*1024**3)
        self.enterContext(patch.object(receiver.shutil,'disk_usage',return_value=self.disk))
        self.enterContext(patch('deployment.lib.provider_recovery_runtime.protected',side_effect=lambda p,**kw:p))
        original=Path.read_text
        def read(p,*args,**kwargs):
            if str(p)=='/etc/machine-id':return self.enrollment['machine_id']
            if str(p)=='/sys/class/dmi/id/product_uuid':return self.enrollment['product_uuid']
            return original(p,*args,**kwargs)
        self.enterContext(patch.object(Path,'read_text',read))
        self.enterContext(patch.object(receiver.subprocess,'run',return_value=type('Result',(),{'stdout':'none\n'})()))
        self.enterContext(patch.object(receiver.subprocess,'check_output',side_effect=lambda *a,**k:'ext4 '+self.enrollment['filesystem_uuid']))

    def execute(self,*,signature=None):
        (self.root/self.run/'enrollment.json').write_bytes(canonical(self.enrollment))
        stream=io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as tar:
            for name,data in self.data.items():
                member=tarfile.TarInfo(name);member.size=len(data);tar.addfile(member,io.BytesIO(data))
        stream.seek(0)
        packet={'payload':self.value,'signature':signature or base64.b64encode(self.key.sign(canonical(self.value))).decode()}
        return receiver.receive_enrolled_test(self.run,packet,stream=stream)

    def test_authenticated_exact_bytes_receive_is_distinct_from_restoration_and_single_use(self):
        receipt=self.execute();self.assertFalse(receipt['database_restored']);self.assertFalse(receipt['application_restored']);self.assertEqual(receipt['manifest_sha256'],digest(self.value))
        with self.assertRaisesRegex(RuntimeError,'consumed'):self.execute()

    def test_signature_modified_manifest_expiration_and_production_identity_refuse(self):
        for change in ('signature','manifest','expired','production','wrong_receiver','wrong_operation'):
            before=copy.deepcopy((self.enrollment,self.value))
            if change=='manifest':self.value['source_sha']='b'*40
            elif change=='expired':self.enrollment['expires_at']=0
            elif change=='production':self.enrollment['denied_database_identifiers'].append('123456789')
            elif change=='wrong_receiver':self.value['receiver_id']=str(uuid.uuid4())
            elif change=='wrong_operation':self.value['operation_id']=str(uuid.uuid4())
            with self.subTest(change=change),self.assertRaises(RuntimeError):self.execute(signature=base64.b64encode(b'wrong').decode() if change=='signature' else None)
            self.assertFalse((self.root/self.run/'receive-consumed.json').exists())
            self.enrollment,self.value=before

    def test_changed_backup_bytes_consume_failed_attempt_but_never_publish_received(self):
        self.data['postgres.tar.gz']=b'changed__'
        with self.assertRaisesRegex(RuntimeError,'bytes_changed'):self.execute()
        self.assertTrue((self.root/self.run/'receive-consumed.json').exists());self.assertFalse((self.root/self.run/'received.json').exists())

    def test_insufficient_measured_headroom_refuses_before_consumption(self):
        self.disk.free=1024
        with self.assertRaisesRegex(RuntimeError,'headroom_invalid'):self.execute()
        self.assertFalse((self.root/self.run/'receive-consumed.json').exists())
