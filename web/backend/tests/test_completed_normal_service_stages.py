"""The existing governed service boundary keeps application/controller roles."""
from pathlib import Path
import unittest
from unittest.mock import Mock
from test_completed_normal_admission import fixture_contract
from deployment.lib import control_plane_upgrade as m

class CompletedNormalServiceTests(unittest.TestCase):
    def operations(self):
        ops=object.__new__(m.SystemOperations)
        ops.repo=Path('/srv/madar/production');ops.control_root=Path('/opt/madar/control-plane/deployment')
        ops.contract_path=ops.control_root/'production-paths.conf';ops.authorization_file=Path('/run/madar/control-plane-upgrade/authorized.credential')
        ops.audit=None;ops.write_authorization=Mock();ops.clear_authorization=Mock()
        ops.command=Mock(return_value=m.CommandResult('','',0));return ops
    def test_every_explicit_stage_uses_fresh_controller_auth_and_exact_application(self):
        contract=fixture_contract()
        for stage,flag in {'prepare':'--prepare-only','activate':'--activate-prepared','publish':'--publish-prepared',
                           'adopt':'--adopt-prepared','migrate':'--automatic-migrate','refresh':'--refresh-active-workers'}.items():
            with self.subTest(stage=stage):
                ops=self.operations();ops.run_deploy_service(stage,'d'*40,completed_normal_contract=contract,completed_normal_mode=stage)
                ops.write_authorization.assert_called_once_with('d'*40,completed_normal_contract=contract)
                args=ops.command.call_args_list[0].args[1]
                self.assertIn('--uid=madar',args);self.assertIn('--gid=madar',args)
                self.assertIn('--property=NoNewPrivileges=yes',args)
                self.assertIn('--property=LoadCredential=madar-control-plane-upgrade:'+str(ops.authorization_file),args)
                self.assertEqual(args[-4:],['c'*40,flag,'--slot','green'])
                self.assertNotIn('d'*40,args);self.assertNotIn(str(ops.control_root/'bin/madar-auto-deploy'),args)
                ops.clear_authorization.assert_called_once()
    def test_missing_or_wrong_stage_contract_source_fails_before_any_effect(self):
        contract=fixture_contract()
        for kwargs,sha in (({'completed_normal_mode':'prepare'},'d'*40),
            ({'completed_normal_contract':contract},'d'*40),
            ({'completed_normal_contract':contract,'completed_normal_mode':'prepare'},'c'*40),
            ({'completed_normal_contract':contract,'completed_normal_mode':'prepare','recovery':True},'d'*40)):
            ops=self.operations()
            with self.assertRaises(m.UpgradeError):ops.run_deploy_service('fixture',sha,**kwargs)
            ops.write_authorization.assert_not_called();ops.command.assert_not_called()
    def test_failed_stage_always_clears_ephemeral_authorization_and_never_retries(self):
        contract=fixture_contract();ops=self.operations()
        ops.command.side_effect=[m.CommandResult('','',1),m.CommandResult('sanitized fixture journal','',0)]
        with self.assertRaisesRegex(m.UpgradeError,'prepare_failed'):
            ops.run_deploy_service('prepare','d'*40,completed_normal_contract=contract,completed_normal_mode='prepare')
        ops.write_authorization.assert_called_once();ops.clear_authorization.assert_called_once()
        self.assertEqual(ops.command.call_count,2)
    def test_forward_witness_is_exclusive_to_sql_and_fenced_refresh(self):
        contract=fixture_contract();witness={'fixture':'fresh measured scope'}
        for stage in ('migrate','refresh'):
            ops=self.operations();ops.run_deploy_service(stage,'d'*40,completed_normal_contract=contract,
                completed_normal_mode=stage,migration_resumption=witness)
            ops.write_authorization.assert_called_once_with('d'*40,completed_normal_contract=contract,migration_resumption=witness)
        for stage in ('prepare','activate','adopt','publish'):
            ops=self.operations()
            with self.assertRaisesRegex(m.UpgradeError,'forward_stage_invalid'):
                ops.run_deploy_service(stage,'d'*40,completed_normal_contract=contract,
                    completed_normal_mode=stage,migration_resumption=witness)
            ops.command.assert_not_called();ops.write_authorization.assert_not_called()

if __name__=='__main__':unittest.main()
