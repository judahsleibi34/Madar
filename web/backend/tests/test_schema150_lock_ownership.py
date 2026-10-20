"""Real operator-owned lock metadata/flock; synthetic operator name mapping.

No operational credential, service or production lock path is accessed. The test
patches the fixed approved lock locations into an owned temporary home directory.
"""
import fcntl
import os
from pathlib import Path
import pwd
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib import schema150_provider_adapter as adapter

class LockOwnershipTests(unittest.TestCase):
    def setUp(self):
        home=Path.home()
        if (not home.is_dir() or home.stat().st_uid!=os.getuid() or os.getuid()==0
                or any(parent.lstat().st_uid not in {0,os.getuid()} for parent in home.parents)):
            self.skipTest('Requires an actual unprivileged owner/home filesystem')
        self.tmp=tempfile.TemporaryDirectory(prefix='madar-lock-metadata-',dir=home);self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.root.chmod(0o700)
        self.deploy=self.root/'deploy.lock';self.upgrade=self.root/'upgrade.lock'
        for path in (self.deploy,self.upgrade):path.touch(mode=0o600)
        self.descriptor=os.open(self.deploy,os.O_RDWR);self.addCleanup(os.close,self.descriptor)
        fcntl.flock(self.descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        original=pwd.getpwnam
        def identity(name):return pwd.getpwuid(os.getuid()) if name=='madar' else original(name)
        self.enterContext(patch.object(pwd,'getpwnam',side_effect=identity))
        self.enterContext(patch.object(adapter,'LOCKS',(self.upgrade,self.deploy)))

    def test_only_fixed_runtime_lock_accepts_real_operator_owned_metadata(self):
        adapter.require_owned_lock(self.descriptor,self.deploy)
        with self.assertRaisesRegex(RuntimeError,'untrusted'):
            adapter.require_owned_lock(self.descriptor,self.upgrade)

    def test_replaced_runtime_inode_cannot_reuse_a_held_descriptor(self):
        self.deploy.rename(self.root/'retained-lock');self.deploy.touch(mode=0o600)
        with self.assertRaisesRegex(RuntimeError,'lock_changed'):adapter.require_owned_lock(self.descriptor,self.deploy)

    def test_group_world_writable_or_symlinked_runtime_lock_is_rejected(self):
        for mode in (0o620,0o602,0o644):
            self.deploy.chmod(mode)
            with self.subTest(mode=mode),self.assertRaises(RuntimeError):adapter.require_owned_lock(self.descriptor,self.deploy)
        self.deploy.chmod(0o600);self.deploy.rename(self.root/'retained-lock');self.deploy.symlink_to(self.root/'retained-lock')
        with self.assertRaises(RuntimeError):adapter.require_owned_lock(self.descriptor,self.deploy)

    def test_real_lock_ownership_is_still_mandatory(self):
        fcntl.flock(self.descriptor,fcntl.LOCK_UN)
        with self.assertRaisesRegex(RuntimeError,'lock_not_held'):adapter.require_owned_lock(self.descriptor,self.deploy)

if __name__=='__main__':unittest.main()
