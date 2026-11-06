"""Actual CLI dispatch selects authenticated admission, never a fake marker.

Filesystem/issuer trust is modeled here. Existing credential and parent-lease
tests exercise their real verifiers; these tests stop before runtime effects.
"""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deployment.lib import completed_normal_admission as admission
from deployment.lib import control_plane_upgrade_authorization as authorization
from deployment.lib import provider_recovery
from deployment.lib.completed_normal_profile import RECONCILED
import test_historical_origin as fixtures
import test_release_bootstrap as cli_fixture


class VerifiedBoundary(Exception):pass


class HistoricalReleaseEntrypointTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);self.state=self.root/'state';self.state.mkdir()
        self.marker=self.root/'interlock.json'
        self.contract=fixtures.HistoricalPreparationBindingTests().contract()
        self.sha=self.contract['candidate']['source_sha']
        self.cli=cli_fixture.release_cli
        self.enterContext(patch.object(authorization,'UPGRADE_INTERLOCK',self.marker))
        self.enterContext(patch('deployment.lib.provider_recovery_runtime.protected',side_effect=lambda p,**kw:Path(p)))

    def interlock(self,operation=RECONCILED.operation):
        self.marker.write_text(json.dumps({'operation':operation,'approved_sha':self.contract['candidate']['controller_sha'],
            'context_sha256':admission.digest(self.contract)}));self.marker.chmod(0o644)

    def invoke(self,verifier):
        stack=self.enterContext(ExitStack())
        stack.enter_context(patch.object(self.cli,'require_production_mutation_identity'))
        stack.enter_context(patch.object(self.cli,'load_production_path_contract'))
        stack.enter_context(patch.dict(os.environ,{'MADAR_PRODUCTION_REPO':str(self.root),
            'MADAR_DEPLOY_STATE_ROOT':str(self.state),'MADAR_ENV_FILE':str(self.root/'never-read.env')}))
        stack.enter_context(patch.object(self.cli.sys,'argv',[str(self.cli.SCRIPT),self.sha,'--prepare-only']))
        ordinary=stack.enter_context(patch.object(self.cli,'require_upgrade_authorization',side_effect=VerifiedBoundary('ordinary')))
        full=stack.enter_context(patch.object(admission,'require_admission',**verifier))
        after=stack.enter_context(patch.object(provider_recovery,'reject_ordinary_operation',side_effect=VerifiedBoundary('admitted')))
        runtime=stack.enter_context(patch.object(self.cli,'DockerGitOperations'))
        return ordinary,full,after,runtime

    def test_markerless_historical_cli_reaches_full_verifier_with_application_identity(self):
        self.interlock();self.assertNotEqual(self.sha,self.contract['candidate']['controller_sha'])
        ordinary,full,after,runtime=self.invoke({'side_effect':VerifiedBoundary('full-authenticated-verifier')})
        with self.assertRaisesRegex(VerifiedBoundary,'full-authenticated-verifier'):self.cli.main()
        full.assert_called_once_with(self.state,self.sha)
        ordinary.assert_not_called();after.assert_not_called();runtime.assert_not_called()
        self.assertFalse((self.state/'provider-recovery.json').exists())

    def test_verified_historical_contract_enters_existing_downstream_guards(self):
        self.interlock();ordinary,full,after,runtime=self.invoke({'return_value':self.contract})
        with self.assertRaisesRegex(VerifiedBoundary,'admitted'):self.cli.main()
        full.assert_called_once_with(self.state,self.sha);ordinary.assert_not_called()
        after.assert_called_once_with(self.state,self.sha);runtime.assert_not_called()

    def test_failed_fresh_credential_or_parent_lease_never_falls_back_to_ordinary(self):
        self.interlock()
        for code in ('control_plane_upgrade_exclusive_interlock','canonical_exceptional_operation_lease_invalid_or_expired',
                     'completed_normal_admission_binding_changed','completed_normal_admission_installed_controller_changed'):
            with self.subTest(code=code),ExitStack() as stack:
                verify=stack.enter_context(patch.object(admission,'require_admission',side_effect=RuntimeError(code)))
                with self.assertRaisesRegex(RuntimeError,code):
                    admission.historical_child_admission(self.state,self.sha)
                verify.assert_called_once_with(self.state,self.sha)

    def test_modern_contract_cannot_use_markerless_historical_selection(self):
        self.interlock();changed=dict(self.contract,source_roles={'completed_compatible_upgrade':True})
        with patch.object(admission,'require_admission',return_value=changed):
            with self.assertRaisesRegex(RuntimeError,'historical_child_origin_required'):
                admission.historical_child_admission(self.state,self.sha)

    def test_ordinary_cli_keeps_existing_candidate_sha_authorization(self):
        ordinary,full,after,runtime=self.invoke({'side_effect':AssertionError('no canonical admission')})
        with self.assertRaisesRegex(VerifiedBoundary,'ordinary'):self.cli.main()
        ordinary.assert_called_once_with(self.sha);full.assert_not_called();runtime.assert_not_called()

    def test_existing_provider_marker_keeps_existing_admission_path(self):
        (self.state/'provider-recovery.json').write_text('{}')
        ordinary,full,after,runtime=self.invoke({'side_effect':VerifiedBoundary('existing-admission')})
        with patch.object(admission,'historical_child_admission',side_effect=AssertionError('must retain legacy path')):
            with self.assertRaisesRegex(VerifiedBoundary,'existing-admission'):self.cli.main()
        full.assert_called_once_with(self.state,self.sha);ordinary.assert_not_called();runtime.assert_not_called()

    def test_other_operation_and_untrusted_interlock_cannot_select_historical_admission(self):
        self.interlock('release')
        with patch.object(admission,'require_admission') as full:
            self.assertIsNone(admission.historical_child_admission(self.state,self.sha));full.assert_not_called()
        self.interlock()
        with patch('deployment.lib.provider_recovery_runtime.protected',side_effect=RuntimeError('untrusted-interlock')):
            with self.assertRaisesRegex(RuntimeError,'untrusted-interlock'):
                admission.historical_child_admission(self.state,self.sha)


if __name__=='__main__':unittest.main()
