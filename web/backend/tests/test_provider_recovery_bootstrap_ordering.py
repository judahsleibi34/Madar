"""Fresh root installation and contract-bound credential ordering regressions."""
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

WEB_ROOT = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB_ROOT))
from deployment.lib.provider_recovery_bootstrap import issue_authorization, TrustedRecoveryBootstrap, installation_interlock, ProductionBootstrapOperations
from deployment.lib.provider_recovery_runtime import digest
from deployment.lib.control_plane_upgrade_authorization import require_upgrade_authorization
from deployment.lib.control_plane_upgrade import BACKUP_TIMERS
import test_provider_recovery_controller as fixtures


class BootstrapOrderingTests(unittest.TestCase):
    def setUp(self):
        fixtures.RecoveryControllerTests.setUp(self)

    def test_fresh_install_attests_before_issuing_credential(self):
        from contextlib import nullcontext
        calls = []
        outer = self
        class Operations:
            def upgrade_lock(self): return nullcontext()
            def deploy_lock(self): return nullcontext()
            def verify_trusted_bootstrap(self): calls.append('trusted')
            def origin_evidence(self): return outer.origin
            def target_evidence(self): return outer.target
            def stage_candidate(self, sha): calls.append('stage'); return Path('candidate'), Path('backup')
            def static_preflight(self, candidate): calls.append('static')
            def installer_dry_run(self, candidate, backup): calls.append('dry-run')
            def require_fresh_installation(self): calls.append('fresh-no-credential')
            def begin_installation(self, contract): calls.append('install-interlock')
            def quiesce_normal_automation(self): calls.append('quiesce')
            def installer_apply(self, *args): calls.append('install')
            def verify_installed_controller(self, sha): calls.append('attest')
            def record_controller_transition(self, contract): calls.append('transition')
            def record_installation(self, contract): calls.append('witness')
            def issue_authorization(self, contract): calls.append('credential')
        with patch('deployment.lib.provider_recovery_bootstrap.os.geteuid',return_value=0), patch('deployment.lib.provider_recovery_phases.require_preparation_evidence'):
            result=TrustedRecoveryBootstrap(Operations()).install(self.contract,self.metadata,digest(self.contract.__dict__))
        self.assertEqual(calls,['trusted','stage','static','dry-run','fresh-no-credential','install-interlock','quiesce','install','attest','transition','witness','credential'])
        self.assertFalse(result['activated'])

    def test_canonical_staging_repository_is_not_transaction_or_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            transaction = root / "staging" / "exact-source-unique"
            candidate = transaction / "repository"
            candidate.mkdir(parents=True)
            backups = root / "backups"
            backups.mkdir()
            system = Mock()
            system.backup_root = backups
            system.stage_candidate.return_value = (transaction, candidate)
            with patch('deployment.lib.control_plane_upgrade.SystemOperations', return_value=system):
                operations = ProductionBootstrapOperations(object())
            staged, backup = operations.stage_candidate(self.contract.sha)
            system.resolve_candidate.assert_called_once_with(self.contract.sha, dry_run=False)
            system.stage_candidate.assert_called_once_with(self.contract.sha)
            self.assertEqual(staged, candidate)
            self.assertEqual(backup.parent, backups)
            self.assertNotEqual(backup, transaction)
            self.assertNotEqual(backup, candidate)
            self.assertFalse(backup.exists())
            backup.mkdir()
            with self.assertRaisesRegex(RuntimeError, 'recovery_installation_backup_already_exists'):
                operations.stage_candidate(self.contract.sha)

    def test_untrusted_installer_and_credential_issuer_are_rejected(self):
        with patch('deployment.lib.provider_recovery_bootstrap.os.geteuid',return_value=1000):
            with self.assertRaisesRegex(RuntimeError,'recovery_root_bootstrap_required'):
                TrustedRecoveryBootstrap(object()).install(self.contract,self.metadata,digest(self.contract.__dict__))
            with self.assertRaisesRegex(RuntimeError,'recovery_root_authorization_required'):
                issue_authorization(self.contract,Path('/does-not-exist'))

    def automation_operations(self, root):
        operations, _ = self.legacy_operations(root)
        (operations.runtime / 'in-progress.json').write_text(json.dumps(
            installation_interlock(operations.recovery.contract)))
        operations.system = Mock()
        states = {name: {'active': 'active', 'enabled': 'enabled'} for name in BACKUP_TIMERS}
        services = {name.replace('.timer', '.service'): {'active': 'inactive', 'enabled': 'static'}
                    for name in BACKUP_TIMERS}
        operations.system.systemctl_state.side_effect = lambda name: dict((states | services)[name])
        def command(args):
            if args[:2] == ['systemctl', 'stop'] and args[2] in states:
                states[args[2]]['active'] = 'inactive'
            return ''
        operations.recovery.command.side_effect = command
        return operations, states, services

    def test_scheduled_backups_quiesce_without_issuing_release_authorization(self):
        with tempfile.TemporaryDirectory() as temp, patch(
                'deployment.lib.provider_recovery_bootstrap.protected', side_effect=lambda p, **kw: p), patch(
                'deployment.lib.provider_recovery_bootstrap.os.geteuid', return_value=0):
            operations, states, _ = self.automation_operations(Path(temp))
            operations.quiesce_normal_automation()
            saved = operations.receipt.parent / 'installation-automation.json'
            snapshot = json.loads(saved.read_text())
            self.assertEqual(snapshot['contract_digest'], digest(operations.recovery.contract.__dict__))
            self.assertEqual(snapshot['backup_timer_states'], {
                name: {'active': 'active', 'enabled': 'enabled'} for name in BACKUP_TIMERS})
            self.assertFalse(snapshot['automatic_resumption_authorized'])
            self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
            self.assertTrue(all(state['active'] == 'inactive' for state in states.values()))
            operations.system.arm_interlock.assert_not_called()
            self.assertFalse((operations.runtime / 'authorized.credential').exists())

    @patch('deployment.lib.provider_recovery_bootstrap.os.geteuid', return_value=0)
    def test_active_backup_rejects_before_any_quiesce(self, _root):
        with tempfile.TemporaryDirectory() as temp, patch(
                'deployment.lib.provider_recovery_bootstrap.protected', side_effect=lambda p, **kw: p):
            operations, _, services = self.automation_operations(Path(temp))
            services[next(iter(services))]['active'] = 'active'
            with self.assertRaisesRegex(RuntimeError, 'backup_operation_running'):
                operations.quiesce_normal_automation()
            operations.recovery.command.assert_not_called()
            self.assertFalse((operations.receipt.parent / 'installation-automation.json').exists())

    @patch('deployment.lib.provider_recovery_bootstrap.os.geteuid', return_value=0)
    def test_untrusted_or_changed_pending_interlock_cannot_quiesce(self, _root):
        with tempfile.TemporaryDirectory() as temp, patch(
                'deployment.lib.provider_recovery_bootstrap.protected', side_effect=lambda p, **kw: p):
            operations, _, _ = self.automation_operations(Path(temp))
            with patch('deployment.lib.provider_recovery_bootstrap.os.geteuid', return_value=1000):
                with self.assertRaisesRegex(RuntimeError, 'root_bootstrap_required'):
                    operations.quiesce_normal_automation()
            (operations.runtime / 'in-progress.json').write_text('{}')
            with self.assertRaisesRegex(RuntimeError, 'installation_interlock_invalid'):
                operations.quiesce_normal_automation()
            operations.recovery.command.assert_not_called()

    @patch('deployment.lib.provider_recovery_bootstrap.os.geteuid', return_value=0)
    def test_timer_stop_failure_prevents_installation_and_preserves_snapshot(self, _root):
        with tempfile.TemporaryDirectory() as temp, patch(
                'deployment.lib.provider_recovery_bootstrap.protected', side_effect=lambda p, **kw: p):
            operations, _, _ = self.automation_operations(Path(temp))
            operations.recovery.command.side_effect = lambda args: ''
            with self.assertRaisesRegex(RuntimeError, 'backup_timer_not_quiesced'):
                operations.quiesce_normal_automation()
            self.assertTrue((operations.receipt.parent / 'installation-automation.json').exists())
            self.assertFalse((operations.runtime / 'authorized.credential').exists())

    def test_witness_required_second_issuance_denied_and_contract_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,value in [('contract.json',self.contract.__dict__),('schema-contract.json',self.metadata)]:
                (root/name).write_text(json.dumps(value))
            witness={'contract_digest':digest(self.contract.__dict__),'source':self.contract.sha,'installed':True}
            with patch('deployment.lib.provider_recovery_bootstrap.os.geteuid',return_value=0), patch('deployment.lib.provider_recovery_bootstrap.protected',side_effect=lambda p,**kw:p), patch('deployment.lib.provider_recovery_phases.require_preparation_evidence'):
                with self.assertRaises(FileNotFoundError):issue_authorization(self.contract,root)
                self.assertFalse((root/'authorized.credential').exists())
                (root/'installation.json').write_text(json.dumps(witness))
                (root/'in-progress.json').write_text(json.dumps(installation_interlock(self.contract)))
                credential=issue_authorization(self.contract,root)
                self.assertEqual(credential.stat().st_mode & 0o777,0o600)
                with self.assertRaisesRegex(RuntimeError,'recovery_existing_authorization_requires_operator_review'):
                    issue_authorization(self.contract,root)
                (root/'madar-control-plane-upgrade').hardlink_to(credential)
                with patch.dict(os.environ,{'CREDENTIALS_DIRECTORY':str(root)}):
                    for altered in (
                        replace(self.contract,sha='9'*40),
                        replace(self.contract,images=dict(self.contract.images,backend='sha256:'+'9'*64)),
                        replace(self.contract,checkpoint_digest='9'*64),
                        replace(self.contract,rehearsal_digest='9'*64),
                    ):
                        with self.subTest(contract=digest(altered.__dict__)), self.assertRaises(RuntimeError):
                            require_upgrade_authorization(altered.sha,interlock=root/'in-progress.json',required_operation='provider402-signin',required_schema=115,require_rehearsal=True,required_context_digest=digest(altered.__dict__))
                    with self.assertRaises(RuntimeError):
                        require_upgrade_authorization(self.contract.sha,interlock=root/'in-progress.json')

    def test_missing_credential_denies_recovery_operation(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError,'control_plane_recovery_authorization_required'):
                require_upgrade_authorization(self.contract.sha,interlock=Path(temp)/'missing',required_operation='provider402-signin')

    def legacy_operations(self, root, *, pinned=True):
        import hashlib
        runtime = root / 'runtime'
        runtime.mkdir(mode=0o711)
        document = {'version': 2, 'approved_sha': self.contract.installed_sha,
            'authorization_sha256': None, 'status': 'quiesced',
            'backup_timer_states': {name: {'active': 'inactive', 'enabled': 'disabled'} for name in BACKUP_TIMERS}}
        path = runtime / 'in-progress.json'
        path.write_text(json.dumps(document)); path.chmod(0o644)
        contract = replace(self.contract, origin_sha=self.contract.installed_sha,
            legacy_quiesced_interlock_digest=hashlib.sha256(path.read_bytes()).hexdigest() if pinned else None)
        recovery = Mock(contract=contract)
        recovery.command.return_value = 'inactive'
        recovery.metadata.return_value = self.metadata
        operations = ProductionBootstrapOperations.__new__(ProductionBootstrapOperations)
        operations.recovery = recovery
        operations.runtime = runtime
        operations.receipt = root / 'packet' / 'controller-transition.json'
        operations.receipt.parent.mkdir(mode=0o700)
        return operations, document

    def test_legacy_quiesce_requires_exact_contract_pin(self):
        with tempfile.TemporaryDirectory() as temp, patch(
                'deployment.lib.provider_recovery_bootstrap.protected', side_effect=lambda p, **kw: p):
            operations, _ = self.legacy_operations(Path(temp), pinned=False)
            with self.assertRaisesRegex(RuntimeError, 'existing_authorization'):
                operations.require_fresh_installation()
            self.assertTrue((operations.runtime / 'in-progress.json').exists())

    def test_pinned_quiesce_preserved_and_replacement_never_authorizes_runtime(self):
        def test_directory(path, *, create=False, mode=0o700):
            if create:
                path.mkdir(mode=mode, exist_ok=True); path.chmod(mode)
        with tempfile.TemporaryDirectory() as temp, patch(
                'deployment.lib.provider_recovery_bootstrap.protected', side_effect=lambda p, **kw: p), patch(
                'deployment.lib.control_plane_upgrade.require_root_directory', side_effect=test_directory):
            operations, document = self.legacy_operations(Path(temp))
            operations.require_fresh_installation()
            operations.begin_installation(operations.recovery.contract)
            archives = list((operations.receipt.parent / 'retired-quiesced-interlocks').glob('*/in-progress.json'))
            self.assertEqual(len(archives), 1)
            self.assertEqual(json.loads(archives[0].read_text()), document)
            self.assertEqual(archives[0].stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads((operations.runtime / 'in-progress.json').read_text()),
                installation_interlock(operations.recovery.contract))
            self.assertFalse((operations.runtime / 'authorized.credential').exists())
            with patch.dict(os.environ, {'CREDENTIALS_DIRECTORY': str(operations.runtime)}), self.assertRaises(RuntimeError):
                require_upgrade_authorization(operations.recovery.contract.sha,
                    interlock=operations.runtime / 'in-progress.json', required_operation='provider402-signin')

    def test_legacy_changed_digest_active_operation_and_existing_credential_rejected(self):
        with tempfile.TemporaryDirectory() as temp, patch(
                'deployment.lib.provider_recovery_bootstrap.protected', side_effect=lambda p, **kw: p):
            operations, _ = self.legacy_operations(Path(temp))
            operations.recovery.command.return_value = 'active'
            with self.assertRaisesRegex(RuntimeError, 'legacy_upgrade_operation_active'):
                operations.require_fresh_installation()
            operations.recovery.command.return_value = 'inactive'
            credential = operations.runtime / 'authorized.credential'
            credential.write_text('synthetic-placeholder')
            with self.assertRaisesRegex(RuntimeError, 'existing_authorization'):
                operations.require_fresh_installation()
            credential.unlink()
            path = operations.runtime / 'in-progress.json'
            path.write_bytes(path.read_bytes() + b' ')
            with self.assertRaisesRegex(RuntimeError, 'existing_authorization'):
                operations.require_fresh_installation()

    def test_even_pinned_authorized_or_wrong_source_interlock_is_rejected(self):
        import hashlib
        for changed in ({'authorization_sha256': '9'*64}, {'approved_sha': '9'*40},
                        {'status': 'provider_recovery_authorized'}, {'version': 1},
                        {'operation': 'provider402-signin'}):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temp, patch(
                    'deployment.lib.provider_recovery_bootstrap.protected', side_effect=lambda p, **kw: p):
                operations, document = self.legacy_operations(Path(temp))
                document.update(changed)
                path = operations.runtime / 'in-progress.json'
                path.write_text(json.dumps(document))
                operations.recovery.contract = replace(operations.recovery.contract,
                    legacy_quiesced_interlock_digest=hashlib.sha256(path.read_bytes()).hexdigest())
                with self.assertRaisesRegex(RuntimeError, 'legacy_interlock_not_quiesced'):
                    operations.require_fresh_installation()
