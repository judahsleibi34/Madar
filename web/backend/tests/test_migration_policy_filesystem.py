"""Opt-in actual root/private filesystem enforcement in a disposable container.

No authority,DB,systemd or production target. This is native file/UID behavior,
not privileged protected-controller installation or release acceptance.
"""
import errno
import json
import os
from pathlib import Path
import socket
import sys
import unittest
sys.path.insert(0,os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib.migration_policy import load_policy

ENABLED=os.getenv('MIGRATION_POLICY_NATIVE_FILESYSTEM')=='1'
ROOT=Path('/etc/madar')
POLICY=ROOT/'migration-policy.json'


@unittest.skipUnless(ENABLED,'Requires a fresh owned read-only container and /etc/madar tmpfs')
class NativePolicyFilesystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.geteuid()!=0 or socket.gethostname()!='madar-policy-native':
            raise RuntimeError('isolated_root_policy_fixture_required')
        mounts=Path('/proc/self/mountinfo').read_text().splitlines()
        if not any(row.split()[4]=='/etc/madar' and ' - tmpfs ' in row for row in mounts):
            raise RuntimeError('isolated_policy_tmpfs_required')
        if not os.statvfs('/').f_flag & os.ST_RDONLY or any(ROOT.iterdir()):
            raise RuntimeError('fresh_read_only_policy_fixture_required')

    def setUp(self):
        self.value={'version':1,'policy_id':'native-file-fixture','environment_id':'isolated-fixture',
            'database_system_identifier':'0','controller_sha':'c'*40,'repository':'judahsleibi34/Madar',
            'branch':'refs/heads/main','enabled':False,'expires_at':0,'max_migrations':3,
            'risk_classes':['A'],'automation_inputs_sha256':'0'*64}
        self.write(self.value)

    def write(self,value):
        POLICY.write_text(json.dumps(value)); POLICY.chmod(0o600)

    def tearDown(self):
        os.seteuid(0)
        ROOT.chmod(0o700)
        for name in ('migration-policy.json','reference.json'):
            (ROOT/name).unlink(missing_ok=True)

    def test_root_can_inspect_disabled_policy_without_issuing_authority(self):
        self.assertEqual(load_policy(),self.value)
        self.assertIs(load_policy()['enabled'],False)

    def test_nonroot_cannot_read_or_evaluate_protected_file(self):
        os.seteuid(65534)
        try:
            with self.assertRaisesRegex(RuntimeError,'root_reader_required'): load_policy()
        finally: os.seteuid(0)

    def test_world_readable_policy_rejects(self):
        POLICY.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError,'file_unprotected'): load_policy()

    def test_wrong_owner_rejects(self):
        os.chown(POLICY,65534,65534)
        with self.assertRaisesRegex(RuntimeError,'file_unprotected'): load_policy()

    def test_writable_parent_rejects(self):
        ROOT.chmod(0o777)
        with self.assertRaisesRegex(RuntimeError,'parent_unprotected'): load_policy()

    def test_symlink_leaf_rejects_before_read(self):
        POLICY.rename(ROOT/'reference.json'); POLICY.symlink_to('reference.json')
        with self.assertRaises(OSError) as caught: load_policy()
        self.assertEqual(caught.exception.errno,errno.ELOOP)

    def test_missing_policy_rejects(self):
        POLICY.unlink()
        with self.assertRaises(FileNotFoundError): load_policy()

    def test_duplicate_keys_reject(self):
        POLICY.write_text('{"version":1,"version":1}')
        with self.assertRaisesRegex(RuntimeError,'duplicate_key'): load_policy()

    def test_broader_class_scope_rejects(self):
        self.value['risk_classes']=['A','C']; self.write(self.value)
        with self.assertRaisesRegex(RuntimeError,'policy_invalid'): load_policy()

    def test_caller_authority_field_rejects(self):
        self.value['authority_issued']=True; self.write(self.value)
        with self.assertRaisesRegex(RuntimeError,'policy_invalid'): load_policy()


if __name__=='__main__': unittest.main()
