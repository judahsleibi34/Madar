import importlib
import os
import unittest
from unittest.mock import patch


class PygwalkerPrivacyTests(unittest.TestCase):
    def test_server_side_pygwalker_telemetry_is_offline_by_default(self):
        with patch.dict(os.environ, {"PYGWALKER_TELEMETRY_ENABLED": "false"}):
            from data_analysis.visualization import _deps

            reloaded = importlib.reload(_deps)
            if reloaded.pyg is None:
                self.skipTest("pygwalker is not installed")

            from pygwalker.services.global_var import GlobalVarManager

            self.assertEqual(GlobalVarManager.privacy, "offline")


if __name__ == "__main__":
    unittest.main()
