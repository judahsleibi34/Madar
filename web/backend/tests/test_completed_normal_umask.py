"""Actual filesystem creation remains private under a hostile caller umask."""
import os
from pathlib import Path
import tempfile
import unittest

from test_completed_normal_execution import m


class PrivateCreationTests(unittest.TestCase):
    def test_hostile_umask_cannot_publish_writable_staging_files_or_directories(self):
        previous=os.umask(0)
        try:
            with tempfile.TemporaryDirectory() as directory:
                with m.protected_creation_mode():
                    root=Path(directory)/'stage';root.mkdir()
                    contract=root/'production-paths.conf';contract.write_text('NONSECRET=fixture\n')
                    self.assertEqual(root.stat().st_mode&0o777,0o700)
                    self.assertEqual(contract.stat().st_mode&0o777,0o600)
                    self.assertEqual(contract.stat().st_uid,os.getuid())
                self.assertEqual(os.umask(0),0)
        finally:os.umask(previous)

    def test_exception_restores_the_callers_mask(self):
        previous=os.umask(0o027)
        try:
            with self.assertRaisesRegex(RuntimeError,'fixture_failure'):
                with m.protected_creation_mode():raise RuntimeError('fixture_failure')
            self.assertEqual(os.umask(0o027),0o027)
        finally:os.umask(previous)

if __name__=='__main__':unittest.main()
