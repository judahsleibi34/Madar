"""Private full-pipeline scope is explicit; production defaults never change."""
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_backup import replica_namespace_scope

class ReplicaScopeTests(unittest.TestCase):
    def test_production_default_needs_no_fixture_guard_or_process(self):
        with patch('deployment.lib.active_recovery_backup.subprocess.run') as run:
            self.assertEqual(replica_namespace_scope('normal-local-production',None),'normal-local-production')
        run.assert_not_called()
    def test_private_scope_requires_exact_measured_guard_and_docker_isolation(self):
        guard=lambda:{'fixture_only':True,'production_modified':False}
        with patch('deployment.lib.active_recovery_backup.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='docker\n')):
            self.assertEqual(replica_namespace_scope('private-schema136-rehearsal',guard),'private-schema136-rehearsal')
        for observed in (SimpleNamespace(returncode=1,stdout='none\n'),SimpleNamespace(returncode=0,stdout='kvm\n')):
            with patch('deployment.lib.active_recovery_backup.subprocess.run',return_value=observed):
                with self.assertRaisesRegex(RuntimeError,'isolation_required'):
                    replica_namespace_scope('private-schema136-rehearsal',guard)
    def test_unknown_scope_missing_guard_or_false_attestation_is_rejected(self):
        for scope,guard in [('unknown',None),('private-schema136-rehearsal',None),
                ('normal-local-production',lambda:{}),('private-schema136-rehearsal',lambda:{'fixture_only':True}),
                ('private-schema136-rehearsal',lambda:{'fixture_only':True,'production_modified':True})]:
            with self.assertRaisesRegex(RuntimeError,'guard_required'):replica_namespace_scope(scope,guard)

if __name__=='__main__':unittest.main()
