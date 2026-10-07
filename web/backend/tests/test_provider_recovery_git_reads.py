"""Actual Git provenance reads must preserve the operator's index."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from deployment.lib.provider_recovery_runtime import ProductionRecoveryOperations, RecoveryPaths


@unittest.skipUnless(shutil.which("git"), "Git is required by the locked CI image")
class RecoveryGitReadTests(unittest.TestCase):
    def test_status_does_not_refresh_or_replace_checkout_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            def git(*args):
                return subprocess.run(["git", "-C", temporary, *args], check=True,
                                      capture_output=True, text=True).stdout
            git("init")
            git("config", "user.name", "Fixture")
            git("config", "user.email", "fixture@example.invalid")
            tracked = repository / "tracked.txt"
            tracked.write_text("unchanged content\n")
            git("add", "tracked.txt")
            git("commit", "-m", "Fixture")
            index = repository / ".git/index"
            before = (index.stat().st_ino, index.stat().st_mtime_ns,
                      hashlib.sha256(index.read_bytes()).digest())
            os.utime(tracked, (tracked.stat().st_atime + 10, tracked.stat().st_mtime + 10))
            operations = ProductionRecoveryOperations.__new__(ProductionRecoveryOperations)
            operations.paths = replace(RecoveryPaths(), repository=repository)
            self.assertEqual(operations.command(["git", "-C", temporary, "status", "--porcelain"]), "")
            after = (index.stat().st_ino, index.stat().st_mtime_ns,
                     hashlib.sha256(index.read_bytes()).digest())
            self.assertEqual(before, after)
