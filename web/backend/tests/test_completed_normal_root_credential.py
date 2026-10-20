"""Actual flock/descriptor windows; MODEL issuer, source and private path checks.

No real authority is issued and no systemd, provider or database is modified.
"""
import fcntl
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

sys.path.insert(0,os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib import completed_normal_execution as execution
from deployment.lib import schema150_provider_adapter as provider
from deployment.lib.control_plane_upgrade import acquire_lock

class RootCredentialLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        for name in ('upgrade','state','runtime'):(self.root/name).mkdir(mode=0o700)
        for name in ('upgrade/upgrade.lock','state/deploy.lock'):(self.root/name).touch(mode=0o600)
        self.driver=execution.CompletedNormalUpgrade.__new__(execution.CompletedNormalUpgrade)
        self.driver.contract={'synthetic':'MODEL ONLY'};self.driver.controller='a'*40
        self.driver.lock=acquire_lock(self.root/'upgrade/upgrade.lock',create=False)
        self.addCleanup(lambda:os.close(self.driver.lock) if self.driver.lock is not None else None)
        self.ops=SimpleNamespace(upgrade_root=self.root/'upgrade',state_root=self.root/'state',runtime_root=self.root/'runtime',
            authorization_file=self.root/'synthetic-authorization',deploy_lock_descriptor=None)
        self.driver.ops=self.ops
        def clear():self.ops.authorization_file.unlink(missing_ok=True)
        def issue(*args,**kw):self.ops.authorization_file.write_bytes(b'synthetic-test-only-token')
        def release():
            if self.ops.deploy_lock_descriptor is not None:
                os.close(self.ops.deploy_lock_descriptor);self.ops.deploy_lock_descriptor=None
        self.ops.write_authorization=Mock(side_effect=issue);self.ops.clear_authorization=Mock(side_effect=clear)
        self.ops.release_deployment_lock=Mock(side_effect=release);self.addCleanup(release)
        self.enterContext(patch.object(execution,'protected',lambda p,**kw:Path(p)))
        self.enterContext(patch.object(provider,'protected',lambda p,**kw:Path(p)))
        self.enterContext(patch.dict(os.environ,{},clear=False))

    def probe_lock(self,locked):
        descriptor=os.open(self.ops.state_root/'deploy.lock',os.O_RDWR)
        try:
            if locked:
                with self.assertRaises(BlockingIOError):fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
            else:fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        finally:os.close(descriptor)

    def test_root_stage_reacquires_released_deployment_lock_and_releases_only_its_window(self):
        previous=os.environ.get('CREDENTIALS_DIRECTORY')
        with self.driver.root_credential():
            provider.require_owned_lock(self.ops.deploy_lock_descriptor,self.ops.state_root/'deploy.lock')
            self.probe_lock(True)
            path=Path(os.environ['CREDENTIALS_DIRECTORY'])/'madar-control-plane-upgrade'
            self.assertEqual(path.read_bytes(),b'synthetic-test-only-token')
        self.assertIsNone(self.ops.deploy_lock_descriptor);self.probe_lock(False)
        self.assertFalse(path.exists());self.assertFalse(self.ops.authorization_file.exists())
        self.assertEqual(os.environ.get('CREDENTIALS_DIRECTORY'),previous)

    def test_existing_coordinator_lock_is_borrowed_without_release(self):
        self.ops.deploy_lock_descriptor=acquire_lock(self.ops.state_root/'deploy.lock',create=False)
        descriptor=self.ops.deploy_lock_descriptor
        with self.driver.root_credential():self.assertEqual(self.ops.deploy_lock_descriptor,descriptor)
        self.assertEqual(self.ops.deploy_lock_descriptor,descriptor);self.probe_lock(True)
        self.ops.release_deployment_lock.assert_not_called()

    def test_contention_refuses_before_issuance(self):
        descriptor=acquire_lock(self.ops.state_root/'deploy.lock',create=False)
        try:
            with self.assertRaises(RuntimeError):
                with self.driver.root_credential():self.fail('Must not enter an unlocked root stage')
            self.ops.write_authorization.assert_not_called()
        finally:os.close(descriptor)

    def test_issuer_failure_releases_new_lock_without_leaking_credential(self):
        previous=os.environ.get('CREDENTIALS_DIRECTORY')
        self.ops.write_authorization.side_effect=RuntimeError('synthetic issuer refusal')
        with self.assertRaisesRegex(RuntimeError,'issuer refusal'):
            with self.driver.root_credential():self.fail('Issuer failed')
        self.assertIsNone(self.ops.deploy_lock_descriptor);self.probe_lock(False)
        self.assertEqual(os.environ.get('CREDENTIALS_DIRECTORY'),previous)

    def test_effect_failure_revokes_temporary_credential_and_releases_lock(self):
        with self.assertRaisesRegex(RuntimeError,'synthetic effect failure'):
            with self.driver.root_credential():raise RuntimeError('synthetic effect failure')
        self.assertIsNone(self.ops.deploy_lock_descriptor);self.probe_lock(False)
        self.assertFalse(self.ops.authorization_file.exists())

    def test_collision_preserves_existing_credential_and_never_calls_issuer(self):
        directory=self.ops.runtime_root/('root-credentials-'+execution.digest(self.driver.contract)[:16])
        directory.mkdir(mode=0o700);path=directory/'madar-control-plane-upgrade';path.write_bytes(b'earlier-private-evidence')
        with self.assertRaisesRegex(RuntimeError,'credential_collision'):
            with self.driver.root_credential():self.fail('A prior credential must not be adopted')
        self.assertEqual(path.read_bytes(),b'earlier-private-evidence')
        self.ops.write_authorization.assert_not_called();self.probe_lock(False)

    def test_credential_unlink_failure_still_revokes_authorization_and_releases_lock(self):
        original=Path.unlink
        def remove(path,*args,**kwargs):
            if path.name=='madar-control-plane-upgrade':raise OSError('synthetic cleanup refusal')
            return original(path,*args,**kwargs)
        with patch.object(Path,'unlink',remove),self.assertRaisesRegex(OSError,'cleanup refusal'):
            with self.driver.root_credential():pass
        self.ops.clear_authorization.assert_called_once()
        self.assertFalse(self.ops.authorization_file.exists());self.probe_lock(False)

    def test_upgrade_lock_must_be_actually_owned_before_issuance(self):
        fcntl.flock(self.driver.lock,fcntl.LOCK_UN)
        with self.assertRaisesRegex(RuntimeError,'lock_not_held'):
            with self.driver.root_credential():self.fail('Unowned upgrade lock')
        self.ops.write_authorization.assert_not_called();self.probe_lock(False)

    def test_contended_lock_acquisition_does_not_leak_descriptors(self):
        descriptor=acquire_lock(self.ops.state_root/'deploy.lock',create=False)
        try:
            before=set(Path('/proc/self/fd').iterdir())
            for _ in range(4):
                with self.assertRaises(RuntimeError):acquire_lock(self.ops.state_root/'deploy.lock',create=False)
            after=set(Path('/proc/self/fd').iterdir())
            leaked=after-before
            try:self.assertFalse(leaked,'Failed coordinator lock attempts must close opened descriptors')
            finally:
                for path in leaked:
                    try:os.close(int(path.name))
                    except OSError:pass
        finally:os.close(descriptor)

if __name__=='__main__':unittest.main()
