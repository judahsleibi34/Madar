import os
import hashlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import tempfile
from unittest.mock import Mock,patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.normal_boot_repair import unit_bytes,dropin_bytes,RepairActor,NormalBootRepair
from deployment.lib.active_recovery_boot import ActiveRecoveryNormalBoot

class NormalBootRepairTests(unittest.TestCase):
    def test_boot_resources_follow_docker_and_replace_only_owned_gate(self):
        unit=unit_bytes('new.service','frozen resume','listener.service').decode()
        self.assertIn('PartOf=docker.service',unit);self.assertIn('WantedBy=multi-user.target docker.service',unit)
        self.assertIn('NoNewPrivileges=yes',unit);self.assertIn('After=docker.service listener.service',unit)
        dropin=dropin_bytes('new.service','frozen gate').decode()
        self.assertIn('Requires=new.service',dropin);self.assertIn('ExecStartPre=\nExecStartPre=frozen gate',dropin)
    def test_new_audit_does_not_append_old_boot_evidence(self):
        actor=ActiveRecoveryNormalBoot.__new__(ActiveRecoveryNormalBoot);actor.audit=Mock()
        actor.event('normal_verified',fixture=True);actor.audit.assert_called_once_with('normal_verified',fixture=True)
    def actor(self):
        actor=RepairActor.__new__(RepairActor);actor.audit=Mock();actor.repair_root=Path('/fresh-repair-root');actor.runtime=Mock();actor.fallback=Mock()
        actor.candidate=SimpleNamespace(contract=object(),_publish_write_authority=Mock(),require_write_authority=Mock())
        actor.workers=SimpleNamespace(stop_consumers=Mock());actor.stop_bound_runtimes_for_failed_compensation=Mock()
        return actor
    def test_compensation_revokes_and_stops_before_existing_maintenance(self):
        actor=self.actor();order=[]
        actor.candidate._publish_write_authority.side_effect=lambda *args:order.append('fence')
        actor.workers.stop_consumers.side_effect=lambda:order.append('stop')
        with patch('deployment.lib.normal_boot_repair.CompensationPublication') as publication:
            publication.return_value.maintenance_or_stop_proxy.side_effect=lambda:order.append('maintenance')
            actor.compensate()
        self.assertEqual(order,['fence','stop','maintenance']);actor.candidate._publish_write_authority.assert_called_once_with(actor.candidate.contract,'READ_ONLY')
    def test_failed_fence_also_stops_exact_bound_application(self):
        actor=self.actor();actor.candidate._publish_write_authority.side_effect=RuntimeError('denied')
        with patch('deployment.lib.normal_boot_repair.CompensationPublication') as publication:
            with self.assertRaisesRegex(RuntimeError,'compensation_incomplete'):actor.compensate()
            publication.return_value.maintenance_or_stop_proxy.assert_called_once()
        actor.stop_bound_runtimes_for_failed_compensation.assert_called_once()
    def test_invalid_original_plan_cannot_select_a_path(self):
        with self.assertRaisesRegex(RuntimeError,'original_plan_invalid'):
            NormalBootRepair({'original_plan_sha256':'../other'},'/frozen')
    def test_baseline_binds_permissions_and_bytes_for_nonsecret_units(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'fixture.service';path.write_text('exact unit');path.chmod(0o644)
            operation=NormalBootRepair.__new__(NormalBootRepair)
            operation.document={'baseline_files':{str(path):{'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'uid':os.getuid(),'mode':0o644}}}
            with patch('deployment.lib.normal_boot_repair.protected',side_effect=lambda path,**kw:path):
                operation.baseline()
                path.chmod(0o600)
                with self.assertRaisesRegex(RuntimeError,'baseline_changed'):operation.baseline()
                path.chmod(0o644);path.write_text('altered unit')
                with self.assertRaisesRegex(RuntimeError,'baseline_changed'):operation.baseline()
    def test_fresh_authorization_is_required_before_audit_publication(self):
        operation=NormalBootRepair.__new__(NormalBootRepair);operation.authorized=False
        with self.assertRaisesRegex(RuntimeError,'fresh_approval'):operation.event('begin')

if __name__=='__main__':unittest.main()
