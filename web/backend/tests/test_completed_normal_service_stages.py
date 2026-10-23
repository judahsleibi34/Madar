"""The existing governed service boundary keeps application/controller roles."""
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
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

    def test_exact160_child_modes_never_request_parent_sql_or_route_execution(self):
        from test_schema160_release import reconciled_contract
        from deployment.lib.completed_normal_profile import RECONCILED
        contract=reconciled_contract()
        with patch('deployment.lib.completed_normal_profile.profile',return_value=RECONCILED),\
                patch('deployment.lib.completed_normal_admission.profile',return_value=RECONCILED):
            for stage in ('prepare','activate','adopt'):
                ops=self.operations();ops.run_deploy_service(stage,'d'*40,completed_normal_contract=contract,completed_normal_mode=stage)
                ops.write_authorization.assert_called_once_with('d'*40,completed_normal_contract=contract,completed_normal_mode=stage)
            for stage in ('migrate','refresh','publish'):
                ops=self.operations()
                with self.assertRaisesRegex(m.UpgradeError,'parent_execution_required'):
                    ops.run_deploy_service(stage,'d'*40,completed_normal_contract=contract,completed_normal_mode=stage)
                ops.write_authorization.assert_not_called();ops.command.assert_not_called()

    def test_real_issuer_payload_keeps_postgres_lease_in_parent_only(self):
        """Actual credential serialization; source/host/admission are models."""
        import json,tempfile
        from contextlib import ExitStack
        from deployment.lib import completed_normal_admission as admission
        from deployment.lib import completed_normal_migration as migration
        from deployment.lib.completed_normal_profile import RECONCILED
        from test_schema160_release import reconciled_contract
        contract=reconciled_contract()
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            root=Path(directory);admissions=root/'admissions'
            stack.enter_context(patch.object(admission,'ADMISSIONS',admissions))
            original=admissions/Path(contract['source_roles']['completion_root']).name
            contract['source_roles']['completion_root']=str(original)
            contract['historical_files']={str(original/Path(path).name):checksum
                for path,checksum in contract['historical_files'].items()}
            context=admission.digest(contract);current=admissions/context
            current.mkdir(parents=True);original.mkdir()
            (current/'admission.json').write_text(json.dumps({'operation':RECONCILED.operation,'contract':contract}))
            (current/'migration-inputs.json').write_text(json.dumps({'intent':migration.intent_document(contract)}))
            old=Path(contract['source_roles']['completion_root'])
            (original/'candidate-runtime.json').write_text(json.dumps({'context_sha256':old.name,
                'source_sha':contract['source_roles']['application_sha'],'images':contract['origin']['images'],
                'worker_generation':contract['origin']['worker_generation']}))
            def protected(path,**kw):
                path=Path(path)
                return original/path.relative_to(old) if path.is_relative_to(old) else path
            stack.enter_context(patch.object(admission,'profile',return_value=RECONCILED))
            stack.enter_context(patch('deployment.lib.completed_normal_profile.profile',return_value=RECONCILED))
            stack.enter_context(patch('deployment.lib.provider_recovery_runtime.protected',side_effect=protected))
            stack.enter_context(patch.object(admission,'verify_history'))
            stack.enter_context(patch.object(admission,'require_candidate_authority',return_value={'mode':'READ_ONLY'}))
            stack.enter_context(patch.object(admission,'measure_provider_record',return_value={'scoped':'fixture'}))
            stack.enter_context(patch.object(m,'require_root_directory'))
            lease=stack.enter_context(patch.object(migration,'issue_database_lease',return_value={'password':'TEST_ONLY_PARENT_LEASE_CANARY'}))
            ops=object.__new__(m.SystemOperations);ops.runtime_root=root/'runtime';ops.runtime_root.mkdir()
            ops.authorization_file=ops.runtime_root/'credential';ops.interlock_file=root/'interlock'
            ops.state_root=root/'state';ops.interlock_document=Mock(return_value={'approved_sha':'d'*40})
            for mode in ('prepare','activate','adopt'):
                ops.write_authorization('d'*40,completed_normal_contract=contract,completed_normal_mode=mode)
                payload=json.loads(ops.authorization_file.read_bytes())
                self.assertNotIn('migration_database',payload)
                self.assertNotIn('TEST_ONLY_PARENT_LEASE_CANARY',json.dumps(payload))
                self.assertIn('migration_inputs',payload)
            lease.assert_not_called()
            ops.write_authorization('d'*40,completed_normal_contract=contract)
            self.assertEqual(json.loads(ops.authorization_file.read_bytes())['migration_database'],lease.return_value)
            lease.assert_called_once_with(contract)

if __name__=='__main__':unittest.main()
