"""Early fixture refusal checks; live provider proof is a separate KVM run."""
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
spec=importlib.util.spec_from_file_location('running146_probe',WEB/'staging/integration/running146_original_probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


class OriginalProbeRefusalTests(unittest.TestCase):
    def test_unprivileged_process_cannot_read_inputs_or_touch_providers(self):
        with patch.object(probe.os,'geteuid',return_value=1000),\
                patch.object(probe.subprocess,'check_output') as command,\
                patch.object(Path,'read_bytes') as read:
            with self.assertRaisesRegex(RuntimeError,'owned_kvm_required'):probe.main()
            read.assert_not_called();command.assert_not_called()

    def test_physical_host_cannot_read_inputs_or_touch_providers(self):
        with patch.object(probe.os,'geteuid',return_value=0),\
                patch.object(probe.subprocess,'check_output',return_value=b'none\n') as command,\
                patch.object(Path,'read_bytes') as read:
            with self.assertRaisesRegex(RuntimeError,'owned_kvm_required'):probe.main()
            read.assert_not_called();command.assert_called_once_with(['systemd-detect-virt'])


if __name__=='__main__':unittest.main()
