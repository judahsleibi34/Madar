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
        with patch('deployment.lib.provider_recovery_bootstrap.os.geteuid',return_value=0), patch('deployment.lib.provider_recovery_phases.require_completed_evidence'):
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

    def test_witness_required_second_issuance_denied_and_contract_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,value in [('contract.json',self.contract.__dict__),('schema-contract.json',self.metadata)]:
                (root/name).write_text(json.dumps(value))
            witness={'contract_digest':digest(self.contract.__dict__),'source':self.contract.sha,'installed':True}
            with patch('deployment.lib.provider_recovery_bootstrap.os.geteuid',return_value=0), patch('deployment.lib.provider_recovery_bootstrap.protected',side_effect=lambda p,**kw:p), patch('deployment.lib.provider_recovery_phases.require_completed_evidence'):
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
