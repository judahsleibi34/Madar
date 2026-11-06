"""Real process/boot observations with modeled root metadata; no deployment."""
import copy,os,time,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from deployment.lib import control_plane_upgrade_authorization as auth
from deployment.lib.completed_normal_admission import digest
from deployment.lib.completed_normal_profile import RECONCILED


class CanonicalOperationLeaseTests(unittest.TestCase):
    def setUp(self):
        self.process=Path('/proc')/str(os.getpid())
        self.lease={'version':1,'kind':'canonical-exceptional-operation-lease','request_id':str(uuid.uuid4()),
            'approval_sha256':'a'*64,'admission_sha256':'b'*64,'context_sha256':'c'*64,
            'operation_id':str(uuid.uuid4()),'attempt_id':str(uuid.uuid4()),'execution_expires_at':int(time.time())+120,
            'pid':os.getpid(),'process_start':Path('/proc/self/stat').read_text().split(') ',1)[1].split()[19],
            'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
        self.state={'operation':RECONCILED.operation,'context_sha256':'c'*64}
        self.authorization={'operation':RECONCILED.operation,'context_sha256':'c'*64,'canonical_exceptional_approval':self.lease}
        self.seal()
        original=Path.stat
        def stat(path,*a,**kw):
            if path==self.process:return SimpleNamespace(st_uid=0) # MODEL root parent only.
            return original(path,*a,**kw)
        self.enterContext(patch.object(Path,'stat',stat))

    def seal(self):self.state['canonical_exceptional_approval_sha256']=digest(self.lease)
    def check(self):return auth.require_canonical_operation_lease(self.state,self.authorization)

    def test_current_parent_and_exact_root_bound_lease_accept(self):self.assertIsNone(self.check())

    def test_missing_or_changed_lease_cannot_reuse_same_bearer_token(self):
        self.authorization.pop('canonical_exceptional_approval')
        with self.assertRaisesRegex(RuntimeError,'lease_invalid_or_expired'):self.check()
        self.authorization['canonical_exceptional_approval']=self.lease
        self.lease['approval_sha256']='f'*64
        with self.assertRaisesRegex(RuntimeError,'lease_invalid_or_expired'):self.check()

    def test_expiration_checked_even_when_root_hash_and_token_still_match(self):
        with patch.object(auth.time,'time',return_value=self.lease['execution_expires_at']):
            with self.assertRaisesRegex(RuntimeError,'lease_invalid_or_expired'):self.check()

    def test_parent_exit_process_reuse_and_reboot_refuse(self):
        for changed in ({'pid':2147483647},{'process_start':'0'},{'boot_id':str(uuid.uuid4())}):
            original=copy.deepcopy(self.lease);self.lease.update(changed);self.seal()
            with self.subTest(changed=changed),self.assertRaisesRegex(RuntimeError,'parent_not_current'):self.check()
            self.lease.clear();self.lease.update(original);self.seal()

    def test_ordinary_user_process_cannot_be_the_authorization_parent(self):
        with patch.object(Path,'stat',return_value=SimpleNamespace(st_uid=1000)):
            with self.assertRaisesRegex(RuntimeError,'parent_not_current'):self.check()

    def test_wrong_operation_or_context_does_not_inherit_canonical_permission(self):
        self.state['operation']='release'
        with self.assertRaisesRegex(RuntimeError,'lease_invalid_or_expired'):self.check()
        self.state['operation']=RECONCILED.operation;self.authorization['context_sha256']='d'*64
        with self.assertRaisesRegex(RuntimeError,'lease_invalid_or_expired'):self.check()
