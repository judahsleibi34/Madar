"""Real archives/signatures/journals; modeled physical identity, no off-host PASS."""
import base64,copy,hashlib,io,json,os,sys,tarfile,tempfile,time,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption
from deployment.lib import isolated_backup_replica as transport
from deployment.lib.migration_inventory import canonical,digest
from scripts import backup_support as backup
with patch.dict(sys.modules,{'backup_support':backup}):
    from scripts import normal_backup_replica as receiver
import test_schema160_backup_contract as checkpoint_fixture
import test_historical_origin as origin_fixture


def public(key):return base64.b64encode(key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode()


def policy_fixture():
    source=Ed25519PrivateKey.generate();target=Ed25519PrivateKey.generate()
    binding=origin_fixture.HistoricalPreparationBindingTests().contract()['source_roles']
    p={'version':1,'kind':'isolated-enrolled-maintenance-replica','environment_id':'isolated-'+str(uuid.uuid4()),
        'guest_uuid':str(uuid.uuid4()),'machine_id':'e'*32,'root_filesystem_uuid':str(uuid.uuid4()),
        'database_system_identifier':'731','controller_sha':binding['controller_sha'],'controller_tree_sha256':'7'*64,
        'historical_origin':binding,'source_origin_sha256':'8'*64,'source_physical_host_uuid':str(uuid.uuid4()),
        'receiver_physical_host_uuid':str(uuid.uuid4()),'receiver_filesystem_uuid':str(uuid.uuid4()),
        'receiver_run_id':'codex-20261102T200000Z-automatic-execution-abcdef01','receiver_id':str(uuid.uuid4()),
        'candidate_application_sha':'b'*40,'source_public_key':public(source),'receiver_public_key':public(target),
        'expires_at':int(time.time())+900,'max_archive_bytes':16*1024**2,'denied_database_identifiers':['987654321']}
    return p,source,target


def request_fixture(p):
    now=int(time.time())
    return {'version':1,'kind':'isolated-maintenance-replica-transfer','nonce':str(uuid.uuid4()),'policy_sha256':'1'*64,
        'context_sha256':'2'*64,'plan_sha256':'3'*64,'stage':'pre-migration','scope_sha256':'4'*64,'schema':146,
        'created_at':now,'expires_at':now+120,'backup_id':'madar-20261102T200000Z','sha256sums_sha256':'5'*64,
        'maintenance_manifest_sha256':'6'*64,'archive_sha256':'9'*64,'archive_bytes':10240}


def expectation(q):return {k:q[k] for k in ('policy_sha256','context_sha256','plan_sha256','stage','scope_sha256','schema')}


def received_packet(q,p,key):
    result={'operation':'actual-append-only-normal-backup-replica','plan_sha256':q['scope_sha256'],
        'backup_id':q['backup_id'],'sha256sums_sha256':q['sha256sums_sha256'],'schema':q['schema'],
        'namespace':transport.NAMESPACE,'maintenance_manifest_sha256':q['maintenance_manifest_sha256'],
        'checksum_exit_code':0,'historical_backups_modified':False,'latest_modified':False,'retention_performed':False,
        'destination':'/opt/madar-recovery-tests/'+p['receiver_run_id']+'/maintenance-replicas/'+q['scope_sha256']+'/'+q['backup_id']}
    value={'version':1,'kind':'independently-received-maintenance-replica','request_sha256':digest(q),
        'receiver_id':p['receiver_id'],'physical_host_uuid':p['receiver_physical_host_uuid'],'filesystem_uuid':p['receiver_filesystem_uuid'],
        'received_at':int(time.time()),'replica':result,'database_restored':False,'application_restored':False,
        'deployment_authority_issued':False,'migration_sql_executed':False}
    return {'payload':value,'signature':base64.b64encode(key.sign(canonical(value))).decode()}


class IndependentTransportTests(unittest.TestCase):
    def test_independent_signatures_and_exact_scope_are_required(self):
        p,source,target=policy_fixture();q=request_fixture(p)
        transport.validate_policy(p,now=int(time.time()))
        signed=transport.sign_parent_request(q,p,expectation(q),source)
        self.assertEqual(transport.verify_signature(signed,p['source_public_key']),q)
        receipt=received_packet(q,p,target)
        result=transport.verify_receipt(receipt,q,p,now=int(time.time()))
        self.assertEqual(result['namespace'],transport.NAMESPACE)
        self.assertIs(receipt['payload']['database_restored'],False)
        with self.assertRaisesRegex(RuntimeError,'signature_invalid'):transport.verify_signature(receipt,p['source_public_key'])

    def test_policy_cannot_target_production_same_host_or_unbounded_archive(self):
        p,source,target=policy_fixture()
        for changes in ({'denied_database_identifiers':['731']},{'receiver_physical_host_uuid':p['source_physical_host_uuid']},
                        {'expires_at':0},{'max_archive_bytes':2*1024**3},{'controller_sha':'f'*40},
                        {'receiver_run_id':'madar-staging'}):
            with self.subTest(changes=changes),self.assertRaises(RuntimeError):
                transport.validate_policy(dict(p,**changes),now=int(time.time()))

    def test_changed_operation_stale_request_wrong_key_refuse_parent_signature(self):
        p,source,target=policy_fixture();q=request_fixture(p);expected=expectation(q)
        for changes in ({'context_sha256':'f'*64},{'plan_sha256':'f'*64},{'stage':'post-migration'},
                        {'schema':164},{'schema':True},{'archive_bytes':p['max_archive_bytes']+1},
                        {'expires_at':0},{'created_at':int(time.time())+30},{'backup_id':'../production'}):
            with self.subTest(changes=changes),self.assertRaises(RuntimeError):
                transport.sign_parent_request(dict(q,**changes),p,expected,source)
        with self.assertRaisesRegex(RuntimeError,'parent_key_changed'):transport.sign_parent_request(q,p,expected,target)

    def test_authentic_receipt_cannot_claim_restore_or_substitute_its_scope(self):
        p,source,target=policy_fixture();q=request_fixture(p)
        for path,value in [('receiver_id',str(uuid.uuid4())),('physical_host_uuid',p['source_physical_host_uuid']),
                           ('request_sha256','f'*64),('application_restored',True),('database_restored',True),
                           ('migration_sql_executed',True),('deployment_authority_issued',True),('received_at',0),
                           ('replica.destination','/srv/data2/madar-backups/production'),('replica.schema',164),
                           ('replica.checksum_exit_code',False),('replica.maintenance_manifest_sha256','f'*64)]:
            packet=received_packet(q,p,target)
            if path.startswith('replica.'):packet['payload']['replica'][path.split('.')[1]]=value
            else:packet['payload'][path]=value
            packet['signature']=base64.b64encode(target.sign(canonical(packet['payload']))).decode()
            with self.subTest(field=path),self.assertRaises(RuntimeError):transport.verify_receipt(packet,q,p,now=int(time.time()))

    def test_bulk_copy_is_removed_after_exact_verified_receipt(self):
        p,source,target=policy_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'transfers';context=SimpleNamespace(context='2'*64,contract={'plan_sha256':'3'*64},
                stage='pre-migration',scope='4'*64,schema=146,authority=Mock())
            from deployment.lib.migration_executor import atomic_json
            def publish(path,value,**kw):
                atomic_json(path,value,**kw)
                if path.name=='request.json':atomic_json(path.parent/'response.json',received_packet(value,p,target),exclusive=True)
            with patch.object(transport,'ROOT',root),patch.object(transport,'policy',return_value=(p,'1'*64)),\
                 patch('deployment.lib.control_plane_upgrade.require_root_directory',lambda path,**kw:path.mkdir(mode=0o700)),\
                 patch.object(transport.shutil,'disk_usage',return_value=SimpleNamespace(free=20*1024**3)),\
                 patch.object(transport,'atomic_json',side_effect=publish),patch.object(transport,'protected',lambda path,**kw:path):
                result=transport.replicate(context,io.BytesIO(b'synthetic authenticated archive'),Path('madar-20261102T200000Z'),'5'*64,'6'*64)
            self.assertEqual(result['namespace'],transport.NAMESPACE)
            self.assertEqual(list(root.glob('*/archive.tar')),[])
            audit=json.loads(next(root.glob('*/audit.json')).read_bytes());self.assertEqual(audit['status'],'RECEIVED')
            self.assertEqual(context.authority.call_count,2)


class RealArchiveReceiverTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.workspace=Path(self.tmp.name)
        self.p,self.source,self.target=policy_fixture();self.run=self.p['receiver_run_id'];self.root=self.workspace/self.run;self.root.mkdir(mode=0o700)
        # Real canonical byte validators, with a synthetic dump. No pg_restore or application PASS is claimed.
        fixture=checkpoint_fixture.CanonicalCheckpointTests();self.addCleanup(fixture.doCleanups)
        f,maintenance,scope=fixture.fixture(146);self.fixture=f
        self.p['controller_sha']=f.binding['controller_sha'];self.p['historical_origin']['controller_sha']=f.binding['controller_sha']
        self.q=request_fixture(self.p);self.q.update(context_sha256=f.binding['context_sha256'],scope_sha256=scope,
            backup_id=f.manifest['backup_id'],sha256sums_sha256=backup.digest(f.data/'SHA256SUMS'),maintenance_manifest_sha256=maintenance)
        self.enrollment={'version':1,'kind':'independently-enrolled-maintenance-replica','policy':self.p,
            'policy_sha256':self.q['policy_sha256'],'machine_id':'a'*32,'context_sha256':self.q['context_sha256'],
            'plan_sha256':self.q['plan_sha256'],'stage_scopes':{'pre-migration':scope,'post-migration':'f'*64}}
        (self.root/'maintenance-enrollment.json').write_bytes(canonical(self.enrollment))
        (self.root/'receiver.key').write_bytes(self.target.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption()))
        realpath=Path;self.enterContext(patch.object(receiver,'Path',side_effect=lambda p,*a:self.workspace if str(p)=='/opt/madar-recovery-tests' else realpath(p,*a)))
        self.enterContext(patch.object(receiver.os,'geteuid',return_value=0))
        self.disk=SimpleNamespace(free=20*1024**3)
        self.enterContext(patch.object(receiver.shutil,'disk_usage',return_value=self.disk))
        self.enterContext(patch('deployment.lib.control_plane_upgrade.require_root_directory',lambda p,**kw:p.mkdir(mode=0o700,exist_ok=True) if kw.get('create') else None))
        self.enterContext(patch('deployment.lib.provider_recovery_runtime.protected',lambda p,**kw:p))
        actual=Path.read_text
        def read(path,*a,**kw):
            if str(path)=='/etc/machine-id':return self.enrollment['machine_id']
            if str(path)=='/sys/class/dmi/id/product_uuid':return self.p['receiver_physical_host_uuid']
            return actual(path,*a,**kw)
        self.enterContext(patch.object(Path,'read_text',read))
        self.enterContext(patch.object(receiver.subprocess,'run',return_value=SimpleNamespace(stdout='none\n',returncode=1)))
        self.enterContext(patch.object(receiver.subprocess,'check_output',return_value='ext4 '+self.p['receiver_filesystem_uuid']))

    def stream(self):
        stream=io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as tar:
            for child in sorted(self.fixture.data.iterdir()):tar.add(child,arcname=child.name,recursive=True)
        raw=stream.getvalue();self.q.update(archive_sha256=hashlib.sha256(raw).hexdigest(),archive_bytes=len(raw));return io.BytesIO(raw)

    def packet(self):return transport.sign_parent_request(self.q,self.p,expectation(self.q),self.source)

    def test_actual_canonical_archive_is_received_verified_signed_and_single_use(self):
        stream=self.stream();packet=self.packet()
        result=receiver.receive_enrolled_maintenance(self.run,packet,stream=stream)
        value=transport.verify_signature(result,self.p['receiver_public_key'])
        self.assertIs(value['application_restored'],False);self.assertEqual(value['replica']['schema'],146)
        final=self.root/'maintenance-replicas'/self.q['scope_sha256']/self.q['backup_id']
        backup.verify_reconciled_maintenance(final,expected_sha256=self.q['maintenance_manifest_sha256'],schema=146,scope=self.q['scope_sha256'])
        with self.assertRaisesRegex(RuntimeError,'consumed'):receiver.receive_enrolled_maintenance(self.run,packet,stream=self.stream())

    def test_changed_archive_consumes_attempt_without_signed_acceptance(self):
        raw=self.stream().getvalue();packet=self.packet();changed=bytearray(raw);changed[len(changed)//2]^=1
        with self.assertRaisesRegex(RuntimeError,'archive_bytes_changed'):
            receiver.receive_enrolled_maintenance(self.run,packet,stream=io.BytesIO(changed))
        attempts=self.root/'maintenance-attempts';self.assertTrue((attempts/(self.q['nonce']+'.json')).exists())
        self.assertEqual(list(attempts.glob('*.received.json')),[])

    def test_wrong_operation_or_signature_stops_before_scope_or_consumption(self):
        stream=self.stream();q=dict(self.q,context_sha256='f'*64)
        forged={'payload':q,'signature':base64.b64encode(self.source.sign(canonical(q))).decode()}
        with self.assertRaisesRegex(RuntimeError,'request_scope'):receiver.receive_enrolled_maintenance(self.run,forged,stream=stream)
        with self.assertRaisesRegex(RuntimeError,'signature_invalid'):
            receiver.receive_enrolled_maintenance(self.run,{'payload':self.q,'signature':base64.b64encode(b'f'*64).decode()},stream=stream)
        self.assertFalse((self.root/'maintenance-attempts').exists());self.assertFalse((self.root/'maintenance-replicas').exists())

    def test_measured_insufficient_space_refuses_before_consuming_receiver_attempt(self):
        stream=self.stream();self.disk.free=1024
        with self.assertRaisesRegex(RuntimeError,'receiver_headroom'):
            receiver.receive_enrolled_maintenance(self.run,self.packet(),stream=stream)
        self.assertFalse((self.root/'maintenance-attempts').exists());self.assertFalse((self.root/'maintenance-replicas').exists())
