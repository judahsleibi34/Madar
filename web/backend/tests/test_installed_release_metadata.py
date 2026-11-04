"""Installation contract tests; ownership modeled here, native UID tested separately."""
import ast
import inspect
import os
from pathlib import Path
import re
import shlex
import tempfile
import unittest
from unittest.mock import patch
from deployment.lib import completed_normal_profile as profiles
from deployment.lib.completed_normal_execution import CompletedNormalUpgrade


class InstalledMetadataTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = Path(profiles.__file__).resolve().parents[1]
        self.path = self.root / profiles.RECONCILED.metadata
        self.path.write_bytes((self.source/'releases'/self.path.name).read_bytes())
        self.path.chmod(0o644)
        original = Path.lstat
        self.owner = 0
        def observed(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if path == self.path:
                fields = list(result); fields[4] = self.owner
                return os.stat_result(fields)
            return result
        self.enterContext(patch.object(Path, 'lstat', observed))

    def verify(self):
        return profiles.verify_installed_metadata(profiles.RECONCILED, releases=self.root)

    def test_exact_metadata_loads(self):
        self.assertEqual(self.verify(), self.path)

    def test_missing_private_writable_foreign_malformed_and_linked_refuse(self):
        original = self.path.read_bytes()
        cases = ('missing', 'private', 'writable', 'foreign', 'malformed', 'symlink', 'hardlink')
        for case in cases:
            with self.subTest(case=case):
                if case == 'missing': self.path.unlink()
                elif case == 'private': self.path.chmod(0o600)
                elif case == 'writable': self.path.chmod(0o664)
                elif case == 'foreign': self.owner = 1000
                elif case == 'malformed': self.path.write_text('{}')
                elif case == 'symlink':
                    self.path.unlink(); self.path.symlink_to(self.root/'absent')
                elif case == 'hardlink': os.link(self.path, self.root/'alias')
                with self.assertRaisesRegex(RuntimeError, 'completed_upgrade_installed_metadata_invalid'):
                    self.verify()
                self.owner = 0
                self.path.unlink(missing_ok=True)
                (self.root/'alias').unlink(missing_ok=True)
                self.path.write_bytes(original); self.path.chmod(0o644)

    def test_every_coordinator_profile_descriptor_is_installed(self):
        installer = (self.source/'bin/madar-install-control-plane').read_text()
        entries = shlex.split(re.search(r'declare -a tracked_files=\((.*?)\)', installer, re.S).group(1))
        selected = [v for v in vars(profiles).values() if isinstance(v, profiles.UpgradeProfile)]
        self.assertEqual(len(selected), 8)
        for profile in selected:
            with self.subTest(operation=profile.operation):
                self.assertIn('releases/'+profile.metadata, entries)
                self.assertTrue((self.source/'releases'/profile.metadata).is_file())

    def test_installed_python_direct_dependencies_are_in_installer(self):
        installer = (self.source/'bin/madar-install-control-plane').read_text()
        entries = shlex.split(re.search(r'declare -a tracked_files=\((.*?)\)', installer, re.S).group(1))
        for name in entries:
            path = self.source/name
            if not path.is_file(): continue
            try: tree = ast.parse(path.read_text())
            except (SyntaxError, UnicodeError): continue
            for node in ast.walk(tree):
                modules = ([node.module] if isinstance(node, ast.ImportFrom) else
                           [x.name for x in node.names] if isinstance(node, ast.Import) else [])
                for module in modules:
                    if module and module.startswith('deployment.lib.'):
                        with self.subTest(consumer=name, dependency=module):
                            self.assertIn('lib/'+module.split('.')[2]+'.py', entries)

    def test_default_targets_installed_tree_even_from_sealed_package(self):
        expected = Path('/opt/madar/control-plane/deployment/releases') / profiles.RECONCILED.metadata
        observed = []
        real_lstat = Path.lstat
        def inspect_path(path, *args, **kwargs):
            observed.append(path)
            if path == expected: return real_lstat(self.path, *args, **kwargs)
            return real_lstat(path, *args, **kwargs)
        with patch.object(profiles, '__file__', str(self.root/'private-package/web/deployment/lib/completed_normal_profile.py')), \
                patch.object(Path, 'lstat', inspect_path), \
                patch('deployment.lib.release_deployer.Compatibility.load') as loader:
            self.assertEqual(profiles.verify_installed_metadata(profiles.RECONCILED), expected)
            loader.assert_called_once_with(expected)
        self.assertEqual(observed, [expected])

    def test_preflight_checks_before_origin_and_effects(self):
        source = inspect.getsource(CompletedNormalUpgrade.preflight)
        self.assertLess(source.index('verify_installed_metadata(self.profile)'), source.index('current_preflight('))
        self.assertNotIn('write_authorization(', source)


if __name__ == '__main__': unittest.main()
