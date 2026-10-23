"""Real disposable Git history: deletion does not remove prior exposure."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

WEB = Path(os.environ.get('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
spec = importlib.util.spec_from_file_location('historical_audit', WEB / 'scripts/audit_historical_exposure.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class HistoricalExposureAuditTests(unittest.TestCase):
    def test_deleted_secret_remains_detectable_without_value_disclosure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL)
            git('init', '-q')
            git('config', 'user.name', 'Synthetic Fixture')
            git('config', 'user.email', 'fixture@example.invalid')
            value = 'ghp_' + 'Z' * 36
            (root / 'removed.md').write_text(value + '\n')
            git('add', '.'); git('commit', '-qm', 'synthetic exposed fixture')
            git('rm', '-q', 'removed.md'); git('commit', '-qm', 'remove fixture')
            result = audit.scan(root, ['HEAD'])
            self.assertTrue(result['coverage_complete'])
            self.assertEqual(result['findings'][0]['kind'], 'github_token')
            self.assertNotIn(value, json.dumps(result))
            self.assertEqual(git('ls-tree', '--name-only', 'HEAD'), b'')
            limited = audit.scan(root, ['HEAD'], byte_limit=0)
            self.assertFalse(limited['coverage_complete'])
            self.assertEqual(limited['scanned_bytes'], 0)

    def test_private_report_never_replaces_existing_or_follows_symlink(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(audit, 'EVIDENCE_ROOTS', (Path(temporary),)):
            path = Path(temporary) / 'new-audit'
            audit.write_private(path, {'findings': []})
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)
            self.assertEqual((path / 'report.json').stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError): audit.write_private(path, {})
            linked = Path(temporary) / 'linked'
            linked.symlink_to(path, target_is_directory=True)
            with self.assertRaises(ValueError): audit.write_private(linked, {})
            with self.assertRaises(ValueError): audit.write_private(path / 'nested', {})
