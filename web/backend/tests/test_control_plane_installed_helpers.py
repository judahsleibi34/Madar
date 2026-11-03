"""Real helper bytes/modes with explicitly modeled root ownership."""
import os
from pathlib import Path
import re
import shlex
import tempfile
import unittest
from unittest.mock import patch
from deployment.lib import control_plane_upgrade as upgrade


class InstalledHelperTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.installed=self.root/'installed';self.control=self.root/'control'
        self.installed.mkdir();(self.control/'scripts').mkdir(parents=True)
        self.operations=upgrade.SystemOperations.__new__(upgrade.SystemOperations)
        self.operations.control_root=self.control
        self.original_stat=Path.stat
        self.wrong_owner=None
        def owned(path,*args,**kwargs):
            result=self.original_stat(path,*args,**kwargs)
            if path.is_relative_to(self.root):
                values=list(result);values[4]=12345 if path==self.wrong_owner else 0
                return os.stat_result(values)
            return result
        self.enterContext(patch.object(Path,'stat',owned))
        for name in upgrade.OPERATIONAL_SCRIPTS:
            for parent in (self.installed,self.control/'scripts'):
                p=parent/name;p.write_text('exact synthetic helper '+name);p.chmod(0o755)

    def verify(self):
        self.operations.verify_installed_operational_helpers(helper_root=self.installed)

    def refuses(self):
        return self.assertRaisesRegex(upgrade.UpgradeError,'installed_backup_helper_integrity_invalid')

    def test_protected_package_scripts_are_not_installed_backup_aliases(self):
        for name in ('prepare_completed_normal_package.py','continue_completed_normal_upgrade.py'):
            self.assertIn('web/scripts/'+name,upgrade.PROTECTED_PATHS)
            self.assertNotIn(name,upgrade.OPERATIONAL_SCRIPTS)
            self.assertFalse((self.installed/name).exists())
        self.verify()

    def test_exact_installer_and_filesystem_contract_agree(self):
        # Backend CI copies tests to /app/tests and mounts the authenticated
        # deployment source separately. Follow the imported module's layout.
        web=Path(upgrade.__file__).resolve().parents[2]
        installer=(web/'deployment/bin/madar-install-control-plane').read_text()
        body=re.search(r'declare -a operational_scripts=\((.*?)\)',installer,re.S).group(1)
        self.assertEqual(tuple(shlex.split(body)),upgrade.OPERATIONAL_SCRIPTS)
        from deployment.lib.control_plane_filesystem import InstallFilesystemLayout
        layout=InstallFilesystemLayout(source_root=self.root,backup_root=self.root/'backup')
        for name in upgrade.OPERATIONAL_SCRIPTS:
            self.assertIn(layout.alert_parent/name,layout.privileged_files)

    def test_changed_bytes_in_either_copy_refuse(self):
        for parent in (self.installed,self.control/'scripts'):
            p=parent/upgrade.OPERATIONAL_SCRIPTS[0];before=p.read_bytes();p.write_bytes(before+b' altered')
            with self.subTest(parent=parent),self.refuses():self.verify()
            p.write_bytes(before)
        self.verify()

    def test_missing_copies_refuse(self):
        for parent in (self.installed,self.control/'scripts'):
            p=parent/upgrade.OPERATIONAL_SCRIPTS[-1];before=p.read_bytes();p.unlink()
            with self.subTest(parent=parent),self.refuses():self.verify()
            p.write_bytes(before);p.chmod(0o755)

    def test_symlink_copies_refuse(self):
        for parent in (self.installed,self.control/'scripts'):
            p=parent/upgrade.OPERATIONAL_SCRIPTS[0];before=p.read_bytes();p.unlink();p.symlink_to(self.root/'unknown')
            with self.subTest(parent=parent),self.refuses():self.verify()
            p.unlink();p.write_bytes(before);p.chmod(0o755)

    def test_wrong_owner_or_mode_in_either_copy_refuse(self):
        for parent in (self.installed,self.control/'scripts'):
            p=parent/upgrade.OPERATIONAL_SCRIPTS[0]
            self.wrong_owner=p
            with self.subTest(parent=parent,kind='owner'),self.refuses():self.verify()
            self.wrong_owner=None;p.chmod(0o775)
            with self.subTest(parent=parent,kind='mode'),self.refuses():self.verify()
            p.chmod(0o755)
        self.verify()


if __name__=='__main__':unittest.main()
