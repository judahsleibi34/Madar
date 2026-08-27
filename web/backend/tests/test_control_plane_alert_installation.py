import os
from pathlib import Path
import unittest


WEB_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = WEB_ROOT / "deployment/bin/madar-install-control-plane"
ALERT_UNIT = WEB_ROOT / "deployment/systemd/madar-ops-alert@.service"
ALERT_HOOK = WEB_ROOT / "scripts/madar_alert_hook.sh"


class ControlPlaneAlertInstallationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.installer = INSTALLER.read_text(encoding="utf-8")
        cls.alert_unit = ALERT_UNIT.read_text(encoding="utf-8")
        cls.alert_hook = ALERT_HOOK.read_text(encoding="utf-8")

    def test_alert_template_is_installed_by_control_plane_installer(self):
        self.assertIn("madar-ops-alert@.service", self.installer)
        self.assertIn(
            '/etc/systemd/system/madar-ops-alert@.service',
            self.installer,
        )

    def test_alert_hook_is_installed_at_unit_execstart_path(self):
        self.assertIn(
            '/usr/local/lib/madar/madar_alert_hook.sh',
            self.installer,
        )
        self.assertIn(
            'ExecStart=/usr/local/lib/madar/madar_alert_hook.sh systemd_failure %i',
            self.alert_unit,
        )
        self.assertNotIn(
            'systemd_failure %I',
            self.alert_unit,
        )

    def test_installer_backs_up_alert_operational_files(self):
        self.assertIn(
            '/etc/systemd/system/madar-ops-alert@.service',
            self.installer,
        )
        self.assertIn(
            '/usr/local/lib/madar/madar_alert_hook.sh',
            self.installer,
        )

    def test_installer_fails_closed_for_missing_hook_source(self):
        self.assertIn(
            'missing or non-executable alert hook source',
            self.installer,
        )
        self.assertIn(
            'missing operations alert systemd template',
            self.installer,
        )

    def test_repository_alert_hook_is_executable_and_provider_neutral(self):
        self.assertTrue(ALERT_HOOK.is_file())
        self.assertTrue(os.access(ALERT_HOOK, os.X_OK))
        self.assertIn("MADAR_ALERT_PROVIDER_HOOK", self.alert_hook)
        self.assertIn("logger --tag madar-operations", self.alert_hook)


if __name__ == "__main__":
    unittest.main()
